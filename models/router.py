"""classify_notice(notice, profile) per CONTRACTS.md §4. Never raises.

Pipeline:  rules (free) -> small model -> large model only on a trigger.
Triggers:  invalid output (schema / evidence not verbatim / missing), decision == uncertain,
           confidence < threshold, small says irrelevant but rules saw a commercial signal.
Retry:     once on parse_failed or transient API errors. Not on truncation or
           ConfigRejected: at temperature 0 those fail identically again.
"""
from __future__ import annotations

import os
import time
from models import rules
from models.client import MODELS, _norm, classify, validate

THRESHOLD = float(os.environ.get("ROUTER_THRESHOLD", "0.82"))
# Product default: rules -> large. Benchmark (46 test items, prompt v3): the small tier missed 6/21
# relevant notices with confidence >= 0.95, so no trigger caught them; large missed 0 at ~2x cost.
# The small path stays for measurement: eval config "router" passes use_small=True.
USE_SMALL = os.environ.get("ROUTER_USE_SMALL", "0") == "1"
CONTRACT_KEYS = ("decision", "confidence", "project_type", "property_type",
                 "matched_services", "project_stage", "evidence", "reason")
_NO_RETRY = ("truncated", "ConfigRejected", "ValueError")
MIN_BODY_CHARS = 40  # below this there is nothing to classify or quote


def _attempt(notice: dict, profile: dict, alias: str, calls: list[dict]) -> tuple[dict | None, dict]:
    """One call, plus one retry if the failure could plausibly be transient."""
    result, meta = classify(notice, profile, alias)
    calls.append(meta)
    err = meta.get("error") or ""
    if result is None and not err.startswith(_NO_RETRY):
        result, meta = classify(notice, profile, alias)
        calls.append(meta)
    return result, meta


def escalation_triggers(result: dict | None, meta: dict, hits: list[str],
                        threshold: float = THRESHOLD) -> list[str]:
    if result is None:
        return [f"no_result:{meta.get('error')}"]
    if meta.get("errors"):
        return [f"invalid:{e}" for e in meta["errors"]]
    t = []
    if result["decision"] == "uncertain":
        t.append("uncertain")
    if result["confidence"] < threshold:
        t.append("low_confidence")
    if result["decision"] == "irrelevant" and hits:
        t.append("rule_conflict:" + ",".join(hits))
    return t


def _total_cost(calls: list[dict]) -> float | None:
    costs = [c.get("cost_eur") for c in calls]
    return None if any(c is None for c in costs) else round(sum(costs), 8)


def _fallback(error: str) -> dict:
    return {"decision": "uncertain", "confidence": 0.0, "project_type": "", "property_type": "",
            "matched_services": [], "project_stage": "other", "evidence": "",
            "reason": "Automatic classification failed; needs human review.", "error": error}


def classify_notice(notice: dict, profile: dict, *, threshold: float = THRESHOLD,
                    trace: dict | None = None, use_small: bool | None = None) -> dict:
    """Contract signature; threshold and trace are optional extras for eval.
    trace gets decided_by, triggers, rule, positive_hits and every call's meta."""
    t0 = time.perf_counter()
    try:
        out = _route(notice, profile, threshold, trace if trace is not None else {},
                     USE_SMALL if use_small is None else use_small)
    except Exception as e:  # belt and braces: never raise
        out = {**_fallback(f"router_exception: {e}"[:500]), "escalated": False,
               "model_used": "none", "cost_eur": None}
    out["latency_ms"] = int((time.perf_counter() - t0) * 1000)  # wall clock incl. retries
    return out


def _route(notice: dict, profile: dict, threshold: float, tr: dict, use_small: bool = True) -> dict:
    calls: list[dict] = []
    tr.update(decided_by=None, triggers=[], rule=None, positive_hits=[], calls=calls,
              small=None, large=None)
    try:
        if len(_norm(notice.get("body") or "")) < MIN_BODY_CHARS:
            tr["decided_by"] = "fallback"
            return {**_fallback("empty_or_short_body"), "escalated": False,
                    "model_used": "none", "cost_eur": 0.0}
        tri = rules.triage(notice, profile)
        tr["rule"], tr["positive_hits"] = tri.rule, tri.positive_hits
        if tri.reject is not None:
            tr["decided_by"] = "rules"
            return {**tri.reject, "escalated": False, "model_used": f"rules:{rules.RULES_VERSION}",
                    "cost_eur": 0.0, "error": None}

        if use_small:
            small, s_meta = _attempt(notice, profile, "small", calls)
            tr["small"] = small
            triggers = escalation_triggers(small, s_meta, tri.positive_hits, threshold)
        else:
            small, s_meta, triggers = None, {}, []
        tr["triggers"] = triggers
        if use_small and not triggers:
            tr["decided_by"] = "small"
            return {**{k: small[k] for k in CONTRACT_KEYS}, "escalated": False,
                    "model_used": s_meta["model"], "cost_eur": _total_cost(calls), "error": None}

        large, l_meta = _attempt(notice, profile, "large", calls)
        tr["large"] = large
        if large is not None and not validate(large, notice, profile):
            tr["decided_by"] = "large"
            return {**{k: large[k] for k in CONTRACT_KEYS}, "escalated": use_small,
                    "model_used": l_meta["model"], "cost_eur": _total_cost(calls), "error": None}

        # Large failed or produced unpublishable output: surface for review, never publish it.
        tr["decided_by"] = "fallback"
        why = l_meta.get("error") or "large_invalid"
        return {**_fallback(f"escalation_failed: {why}"), "escalated": use_small,
                "model_used": l_meta.get("model") or MODELS["large"]["id"],
                "cost_eur": _total_cost(calls)}
    except Exception as e:  # never raise
        tr["decided_by"] = "fallback"
        return {**_fallback(f"router_exception: {type(e).__name__}: {e}"[:500]),
                "escalated": bool(calls), "model_used": "none", "cost_eur": _total_cost(calls)}
