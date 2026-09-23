"""Nebius Token Factory client.

classify(notice, profile, model) -> (result | None, meta)
Every API call, including rejected ones and capability probes, writes a model_runs row.
Never raises. No retry/escalation here: that is router.py's job.
Smoke test:  python -m models.client ingest/sample_notices.json
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from openai import BadRequestError, OpenAI

from models.log import log_run
from models.prompt import PROMPT_VERSION, build_messages

# Confirm against the starter kit PDF; override without a code change via env.
NEBIUS_BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
BASE_SCHEMA: dict = json.loads(Path(__file__).with_name("schema.json").read_text())

# ---- Fill from the Nebius dashboard, mirror into models/PRICES.md. ------------------
# Never guess. A None price makes cost_eur None: visible, not silently wrong.
USD_TO_EUR: float | None = round(1 / 1.1463, 6)  # ECB reference 2026-09-22: 1 EUR = 1.1463 USD

MODELS: dict[str, dict[str, Any]] = {
    "small": {
        "id": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",  # Base public endpoint, 60 tok/s
        "usd_in_per_m": 0.06, "usd_out_per_m": 0.24,
        "max_tokens": 1000,
        # Model-card switch. Verify Nebius honours it: run the smoke test, output_tokens
        # and reasoning_chars must drop versus extra_body={}.
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    },
    # Measurement only: small at its DEFAULT reasoning setting. Own stage so model_runs can tell them apart. Benchmark both, keep the
    # cheaper one only if the numbers say so. Never used by the router.
    "small_think": {
        "id": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
        "usd_in_per_m": 0.06, "usd_out_per_m": 0.24,
        "max_tokens": 6000,
        "extra_body": {},
    },
    "large": {
        "id": "openai/gpt-oss-120b",  # Base public endpoint, 40 tok/s
        "usd_in_per_m": 0.15, "usd_out_per_m": 0.60,
        "max_tokens": 6000,  # reasoning + JSON; truncation shows up as error="truncated"
        "extra_body": {"reasoning_effort": "medium"},  # low|medium|high, cannot be off
    },
    "baseline_open": {
        "id": "deepseek-ai/DeepSeek-V4-Pro",  # prices: fill from the prices page before running
        "usd_in_per_m": None, "usd_out_per_m": None,
        "max_tokens": 8000,
        "extra_body": {},  # leave reasoning at its default: this row is "big model on everything"
    },
    "finetuned": {
        "id": "FILL_AFTER_LORA_JOB",  # Nano has NO LoRA on Nebius: finetuned row is cut unless a different base is agreed
        "usd_in_per_m": None, "usd_out_per_m": None,
        "max_tokens": 1000,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    },
    "baseline_closed": {
        "id": "FILL_CLAUDE_MODEL_ID",
        "base_url": "https://api.anthropic.com/v1/",  # Anthropic OpenAI-compatible endpoint
        "key_env": "ANTHROPIC_API_KEY",
        "usd_in_per_m": None, "usd_out_per_m": None,
        "max_tokens": 1500,
        "extra_body": {},
    },
}
# model_runs.stage values. baseline_open needs "baseline_open" agreed at the sync.
STAGE = {"small": "small", "small_think": "small_think", "large": "large", "finetuned": "finetuned",
         "baseline_closed": "baseline", "baseline_open": "baseline_open"}

MODES = ("json_schema", "json_object", "none")
PROBE_SCHEMA = {"type": "object", "additionalProperties": False,
                "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}


class ConfigRejected(Exception):
    """A 400 caused by OUR request (schema or extra_body), not by model capability.
    Never downgraded to looser formats: a broken schema must fail loudly."""


_mode_cache: dict[str, str] = {}               # alias -> strongest accepted response_format
_config_rejected: dict[str, str] = {}          # alias -> diagnosis, fail fast after first
_clients: dict[str, OpenAI] = {}

_THINK = re.compile(r"<think>.*?</think>", re.S)
_WS = re.compile(r"\s+")
_EDGE = " \t\n\"'“”‘’.…,;:"
MIN_EVIDENCE_CHARS = 12  # stops "de" or "pand" passing the substring check


# ------------------------------------------------------------------ helpers
def _client(cfg: dict) -> OpenAI:
    base = cfg.get("base_url", NEBIUS_BASE_URL)
    if base not in _clients:
        _clients[base] = OpenAI(base_url=base, api_key=os.environ[cfg.get("key_env", "NEBIUS_API_KEY")],
                                timeout=90, max_retries=1)
    return _clients[base]


def schema_for(profile: dict) -> dict:
    """Base schema with matched_services constrained to this profile's services."""
    schema = copy.deepcopy(BASE_SCHEMA)
    services = [s for s in profile.get("services") or [] if isinstance(s, str)]
    if services:
        schema["properties"]["matched_services"]["items"]["enum"] = services
    return schema


def _response_format(mode: str, schema: dict) -> dict | None:
    if mode == "json_schema":
        return {"type": "json_schema",
                "json_schema": {"name": "notice_classification", "schema": schema, "strict": True}}
    if mode == "json_object":
        return {"type": "json_object"}
    return None


def parse_json(text: str | None) -> dict | None:
    """Tolerates <think> blocks, code fences and chatter around one JSON object."""
    if not text:
        return None
    text = _THINK.sub("", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _norm(s: str) -> str:
    return _WS.sub(" ", s).strip()


def evidence_ok(evidence: Any, body: Any) -> bool:
    """Verbatim substring check. Whitespace-collapsed only: words must match exactly."""
    if not isinstance(evidence, str) or not isinstance(body, str):
        return False
    ev = _norm(evidence).strip(_EDGE)
    return len(ev) >= MIN_EVIDENCE_CHARS and ev in _norm(body)


def validate(result: Any, notice: dict, profile: dict) -> list[str]:
    """CONTRACTS.md §3 checks. Empty list means valid."""
    if not isinstance(result, dict):
        return ["not_an_object"]
    props = BASE_SCHEMA["properties"]
    errs = [f"missing:{k}" for k in BASE_SCHEMA["required"] if k not in result]
    for k in ("decision", "project_stage"):
        if k in result and result[k] not in props[k]["enum"]:
            errs.append(f"bad_enum:{k}")
    c = result.get("confidence")
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
        errs.append("bad_confidence")
    for k in ("project_type", "property_type", "evidence", "reason"):
        if k in result and not isinstance(result[k], str):
            errs.append(f"bad_type:{k}")
    ms = result.get("matched_services")
    allowed = set(profile.get("services") or [])
    if not isinstance(ms, list) or not all(isinstance(x, str) and x in allowed for x in ms):
        errs.append("bad_matched_services")
    if not evidence_ok(result.get("evidence"), notice.get("body")):
        errs.append("evidence_not_verbatim")
    return errs


def cost_eur(cfg: dict, tokens_in: int | None, tokens_out: int | None) -> float | None:
    p_in, p_out = cfg.get("usd_in_per_m"), cfg.get("usd_out_per_m")
    if None in (p_in, p_out, USD_TO_EUR, tokens_in, tokens_out):
        return None
    return round((tokens_in * p_in + tokens_out * p_out) / 1e6 * USD_TO_EUR, 8)


def _log_side_call(alias: str, cfg: dict, ids: tuple, error: str, resp: Any = None) -> None:
    """model_runs row for a rejected attempt or a probe, so nothing is invisible."""
    usage = getattr(resp, "usage", None)
    tin, tout = (usage.prompt_tokens, usage.completion_tokens) if usage else (None, None)
    log_run(ids[0], ids[1], {"model": cfg["id"], "stage": STAGE.get(alias, alias),
                             "prompt_version": PROMPT_VERSION, "input_tokens": tin,
                             "output_tokens": tout, "cost_eur": cost_eur(cfg, tin, tout),
                             "ok": False, "error": error})


def _probe_ok(cfg: dict, alias: str, ids: tuple, extra_body: dict | None) -> bool:
    kwargs: dict[str, Any] = {"model": cfg["id"], "max_tokens": 16, "temperature": 0,
                              "messages": [{"role": "user", "content": 'Reply {"ok": true}'}],
                              "response_format": _response_format("json_schema", PROBE_SCHEMA)}
    if extra_body:
        kwargs["extra_body"] = extra_body
    tag = "probe:json_schema" + ("+extra_body" if extra_body else "")
    try:
        resp = _client(cfg).chat.completions.create(**kwargs)
    except BadRequestError as e:
        _log_side_call(alias, cfg, ids, f"{tag}:rejected:{e}")
        return False
    _log_side_call(alias, cfg, ids, f"{tag}:accepted", resp)
    return True


def _diagnose_schema_400(cfg: dict, alias: str, ids: tuple, err: Exception) -> None:
    """Returns if json_schema is genuinely unsupported (safe to downgrade).
    Raises ConfigRejected if the model supports json_schema but rejects our request."""
    if not _probe_ok(cfg, alias, ids, None):
        return  # trivial schema rejected too: capability gap, downgrade is legitimate
    if cfg.get("extra_body") and not _probe_ok(cfg, alias, ids, cfg["extra_body"]):
        raise ConfigRejected(f"extra_body rejected: {cfg['extra_body']} :: {err}")
    raise ConfigRejected(f"schema rejected (model supports json_schema): {err}")


def _call(cfg: dict, alias: str, messages: list[dict], schema: dict, ids: tuple):
    """Strongest response_format the model accepts. Downgrades only on a confirmed
    capability gap; our own schema/extra_body errors raise ConfigRejected instead."""
    if alias in _config_rejected:
        raise ConfigRejected(_config_rejected[alias])
    last_err: Exception | None = None
    for mode in MODES[MODES.index(_mode_cache.get(alias, "json_schema")):]:
        kwargs: dict[str, Any] = {"model": cfg["id"], "messages": messages,
                                  "temperature": 0, "max_tokens": cfg["max_tokens"]}
        rf = _response_format(mode, schema)
        if rf:
            kwargs["response_format"] = rf
        if cfg.get("extra_body"):
            kwargs["extra_body"] = cfg["extra_body"]
        t0 = time.perf_counter()
        try:
            resp = _client(cfg).chat.completions.create(**kwargs)
        except BadRequestError as e:
            _log_side_call(alias, cfg, ids, f"format_rejected:{mode}:{e}"[:1000])
            last_err = e
            if mode == "json_schema":
                try:
                    _diagnose_schema_400(cfg, alias, ids, e)
                except ConfigRejected as cr:
                    _config_rejected[alias] = str(cr)
                    raise
            print(f"[client] {alias}: {mode} unsupported, downgrading", file=sys.stderr)
            continue
        _mode_cache[alias] = mode
        return resp, mode, int((time.perf_counter() - t0) * 1000)
    raise last_err or RuntimeError("no response_format mode worked")


def _reasoning_chars(message: Any) -> int:
    extra = getattr(message, "model_extra", None) or {}
    r = extra.get("reasoning_content") or extra.get("reasoning") or ""
    think = "".join(_THINK.findall(message.content or ""))
    return len(r) + len(think)


# ------------------------------------------------------------------ public
def classify(notice: dict, profile: dict, model: str = "small") -> tuple[dict | None, dict]:
    cfg = MODELS.get(model)
    ids = (notice.get("id"), profile.get("id"))
    meta: dict[str, Any] = {
        "model": cfg["id"] if cfg else model, "stage": STAGE.get(model, model),
        "prompt_version": PROMPT_VERSION, "input_tokens": None, "output_tokens": None,
        "latency_ms": None, "cost_eur": None, "mode": None, "finish_reason": None,
        "reasoning_chars": None, "reasoning_tokens": None, "ok": False, "error": None, "errors": [], "raw": None,
    }
    result: dict | None = None
    try:
        if cfg is None:
            raise ValueError(f"unknown model alias {model!r}")
        resp, meta["mode"], meta["latency_ms"] = _call(
            cfg, model, build_messages(notice, profile), schema_for(profile), ids)
        choice, usage = resp.choices[0], resp.usage
        if usage is not None:  # completion_tokens includes hidden reasoning tokens
            meta["input_tokens"], meta["output_tokens"] = usage.prompt_tokens, usage.completion_tokens
            details = getattr(usage, "completion_tokens_details", None)
            meta["reasoning_tokens"] = getattr(details, "reasoning_tokens", None)  # None = not reported
        meta["cost_eur"] = cost_eur(cfg, meta["input_tokens"], meta["output_tokens"])
        meta["finish_reason"] = choice.finish_reason
        meta["raw"] = choice.message.content
        meta["reasoning_chars"] = _reasoning_chars(choice.message)

        parsed = parse_json(meta["raw"])
        if parsed is None:
            meta["error"] = "truncated" if choice.finish_reason == "length" else "parse_failed"
        else:
            result = {k: parsed[k] for k in BASE_SCHEMA["properties"] if k in parsed}
            meta["errors"] = validate(result, notice, profile)
            meta["ok"] = not meta["errors"]
            meta["error"] = ",".join(meta["errors"]) or None
    except Exception as e:  # never raise
        meta["error"] = f"{type(e).__name__}: {e}"[:1000]
    finally:
        log_run(*ids, meta)
    return result, meta


if __name__ == "__main__":
    # Reasoning audit on real notices. Answers: does the switch work, how is reasoning
    # reported in usage, and what does each configuration actually cost per notice.
    # Afterwards compare the Nebius dashboard usage for these calls with SUM(tokens)
    # in model_runs: that is the billing check.
    path = sys.argv[1] if len(sys.argv) > 1 else "ingest/sample_notices.json"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    notices = json.loads(Path(path).read_text())[:k]
    profile = json.loads(Path("app/profiles/vandijk.json").read_text())
    for alias in ("small", "small_think", "large"):
        rows = [classify(n, profile, alias)[1] for n in notices]
        def avg(key):
            vals = [r[key] for r in rows if r[key] is not None]
            return round(sum(vals) / len(vals), 1) if vals else None
        print(f"{alias:12} n={len(rows)} ok={sum(r['ok'] for r in rows)} "
              f"in={avg('input_tokens')} out={avg('output_tokens')} "
              f"reasoning_tokens={avg('reasoning_tokens')} reasoning_chars={avg('reasoning_chars')} "
              f"latency_ms={avg('latency_ms')} cost_eur={avg('cost_eur')} "
              f"modes={sorted({r['mode'] for r in rows if r['mode']})} "
              f"errors={[r['error'] for r in rows if r['error']][:3]}")
