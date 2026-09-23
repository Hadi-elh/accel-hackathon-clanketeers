"""Run one configuration over a set of notices and record everything.

Labelled benchmark (the 50 test items):
    python -m eval.run --config small
    python -m eval.run --config router --threshold 0.82
Unlabelled volume run on real notices (cost projection, validity, escalation mix):
    python -m eval.run --config router --source notices --limit 300 --run-name volume_router
Repeat run for stability (never written to eval_results):
    python -m eval.run --config small --run-name small_rep2 --no-db

Every notice becomes one JSON line in /eval/runs/<run_name>.jsonl: full output, confidence,
triggers, rule verdict, per-call tokens and cost. Labelled runs of contract configs also write
one eval_results row per item. Resumable: notices already in the JSONL are skipped, so a crash
or Ctrl-C never re-spends budget. --max-eur stops the run when this invocation's spend hits it.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import rules
from models.client import classify, evidence_ok
from models.prompt import PROMPT_VERSION
from models.router import CONTRACT_KEYS, THRESHOLD, classify_notice

RUNS_DIR = Path(__file__).with_name("runs")
BORDERLINE_FILE = Path(__file__).with_name("borderline.txt")  # optional: one notice_id per line
# /CONTRACTS.md §5. Add "baseline_open" only once CONTRACTS.md lists it.
DB_CONFIGS = {"small", "large", "router", "baseline_closed", "finetuned"}
DECISIONS = {"relevant", "irrelevant", "uncertain"}
POSITIVE = {"relevant", "uncertain"}  # uncertain is surfaced for review, so it counts as positive
_sb_client = None


# ------------------------------------------------------------------ data
def _sb():
    global _sb_client
    if _sb_client is None:
        import os
        from supabase import create_client
        _sb_client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _sb_client


def load_profile(profile_id: str) -> dict:
    local = Path("app/profiles") / f"{profile_id}.json"
    try:
        rows = _sb().table("company_profiles").select("*").eq("id", profile_id).execute().data
        if rows:
            return rows[0]
    except Exception as e:
        print(f"[run] profile from DB failed ({e}); trying {local}", file=sys.stderr)
    return json.loads(local.read_text())


def _notices_by_id(ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 100):
        for n in _sb().table("notices").select("*").in_("id", ids[i:i + 100]).execute().data:
            out[n["id"]] = n
    return out


def load_test_items(limit: int | None) -> list[dict]:
    """eval_items where split='test', joined with notices. Never writes eval_items."""
    labels = _sb().table("eval_items").select("*").eq("split", "test").execute().data
    notices = _notices_by_id([l["notice_id"] for l in labels])
    border = set(BORDERLINE_FILE.read_text().split()) if BORDERLINE_FILE.exists() else None
    items = []
    for l in labels:
        n = notices.get(l["notice_id"])
        if n is None:
            print(f"[run] eval_item {l['notice_id']} has no notice row, skipped", file=sys.stderr)
            continue
        items.append({"notice": n, "label": {
            "expected_decision": l["expected_decision"],
            "expected_evidence": l.get("expected_evidence"),
            "borderline": (l["notice_id"] in border) if border is not None else None}})
    return items[:limit] if limit else items


def load_unlabelled(limit: int | None, file: str | None) -> list[dict]:
    if file:
        notices = json.loads(Path(file).read_text())
    else:
        q = _sb().table("notices").select("*").order("published_on", desc=True)
        notices = q.limit(limit or 1000).execute().data
    if limit:
        notices = notices[:limit]
    return [{"notice": n, "label": None} for n in notices]


# ------------------------------------------------------------------ one item
def _call_summary(meta: dict) -> dict:
    keys = ("model", "stage", "mode", "input_tokens", "output_tokens", "reasoning_chars",
            "latency_ms", "cost_eur", "ok", "error", "finish_reason")
    return {k: meta.get(k) for k in keys}


def run_one(item: dict, profile: dict, config: str, threshold: float) -> dict:
    notice, label = item["notice"], item.get("label")
    body = notice.get("body") or ""
    tri = rules.triage(notice, profile)  # recorded for every config: replay needs it, it's free
    rec: dict[str, Any] = {
        "notice_id": notice.get("id"), "config": config, "prompt_version": PROMPT_VERSION,
        "rules_version": rules.RULES_VERSION, "threshold": threshold if config == "router" else None,
        "rule": tri.rule, "rule_reject": tri.reject is not None, "positive_hits": tri.positive_hits,
        "body_chars": len(body), "ts": datetime.now(timezone.utc).isoformat(), "run_error": None,
    }
    if config == "router":
        tr: dict = {}
        out = classify_notice(notice, profile, threshold=threshold, trace=tr)
        result = {k: out.get(k) for k in CONTRACT_KEYS}
        rec.update(decision=out["decision"], parsed=True, errors=[], error=out.get("error"),
                   escalated=out["escalated"], decided_by=tr.get("decided_by"),
                   triggers=tr.get("triggers", []), model_used=out["model_used"],
                   cost_eur=out["cost_eur"], latency_ms=out["latency_ms"],
                   calls=[_call_summary(m) for m in tr.get("calls", [])])
    else:
        result, meta = classify(notice, profile, config)
        parsed = bool(result) and result.get("decision") in DECISIONS
        rec.update(decision=result["decision"] if parsed else "uncertain",  # unusable -> review
                   parsed=parsed, errors=meta.get("errors", []), error=meta.get("error"),
                   escalated=False, decided_by=config, triggers=[], model_used=meta.get("model"),
                   cost_eur=meta.get("cost_eur"), latency_ms=meta.get("latency_ms"),
                   calls=[_call_summary(meta)])
    rec["result"] = result
    rec["confidence"] = (result or {}).get("confidence")
    rec["evidence"] = (result or {}).get("evidence")
    rec["evidence_valid"] = evidence_ok(rec["evidence"], body)
    rec["positive"] = rec["decision"] in POSITIVE
    if label:
        rec.update(label)
        rec["correct"] = rec["positive"] == (label["expected_decision"] == "relevant")
    else:
        rec.update(expected_decision=None, expected_evidence=None, borderline=None, correct=None)
    return rec


NOTICE_COLUMNS = ("id", "source_url", "title", "body", "published_on", "municipality", "rubriek",
                  "lat", "lng")


def _upsert_signal(rec: dict, notice: dict, profile_id: str) -> None:
    """Router output -> signals row (unique on notice_id, profile_id, so reruns update).
    signals.notice_id is a foreign key, so the notice row is inserted first if it is missing;
    ignore_duplicates means an existing notice row (A's data) is never overwritten."""
    try:
        _sb().table("notices").upsert({k: notice.get(k) for k in NOTICE_COLUMNS},
                                      on_conflict="id", ignore_duplicates=True).execute()
        r = rec.get("result") or {}
        _sb().table("signals").upsert({
            "notice_id": rec["notice_id"], "profile_id": profile_id,
            "decision": rec["decision"], "confidence": r.get("confidence"),
            "project_type": r.get("project_type"), "property_type": r.get("property_type"),
            "project_stage": r.get("project_stage"), "matched_services": r.get("matched_services") or [],
            "evidence": r.get("evidence"), "reason": r.get("reason"),
            "escalated": rec.get("escalated", False), "model_used": rec.get("model_used"),
            "error": rec.get("error")}, on_conflict="notice_id,profile_id").execute()
    except Exception as e:
        print(f"[run] signals upsert failed for {rec.get('notice_id')}: {e}", file=sys.stderr)


def _insert_eval_result(rec: dict) -> None:
    try:
        _sb().table("eval_results").insert({
            "notice_id": rec["notice_id"], "config": rec["config"], "prediction": rec["decision"],
            "correct": rec["correct"], "escalated": rec["escalated"],
            "latency_ms": rec["latency_ms"], "cost_eur": rec["cost_eur"]}).execute()
    except Exception as e:
        print(f"[run] eval_results insert failed for {rec['notice_id']}: {e}", file=sys.stderr)


# ------------------------------------------------------------------ main
def done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("run_error") is None:
            ids.add(r["notice_id"])
    return ids


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run-name")
    ap.add_argument("--source", choices=["test", "notices"], default="test")
    ap.add_argument("--notices-file", help="JSON list of notices (unlabelled) instead of the DB")
    ap.add_argument("--items-file", help="JSON list of {notice, label} (offline testing)")
    ap.add_argument("--profile", default="vandijk")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-eur", type=float, default=0.25)
    ap.add_argument("--no-db", action="store_true", help="never write eval_results")
    ap.add_argument("--fresh", action="store_true", help="archive the old JSONL and start over")
    ap.add_argument("--write-signals", action="store_true",
                    help="router only: upsert each result into the signals table for the UI")
    a = ap.parse_args(argv)

    if a.write_signals and a.config != "router":
        ap.error("--write-signals only makes sense with --config router")
    run_name = a.run_name or a.config
    RUNS_DIR.mkdir(exist_ok=True)
    path = RUNS_DIR / f"{run_name}.jsonl"
    if a.fresh and path.exists():
        path.rename(path.with_suffix(f".{int(time.time())}.archived.jsonl"))  # never delete data

    profile = load_profile(a.profile)
    if a.items_file:
        items = json.loads(Path(a.items_file).read_text())
        items = items[:a.limit] if a.limit else items
    elif a.source == "test":
        items = load_test_items(a.limit)
    else:
        items = load_unlabelled(a.limit, a.notices_file)

    skip = done_ids(path)
    todo = [it for it in items if it["notice"].get("id") not in skip]
    write_db = (not a.no_db and not a.items_file and a.source == "test"
                and a.config in DB_CONFIGS and run_name == a.config)
    print(f"[run] {run_name}: {len(items)} items, {len(skip)} already done, {len(todo)} to run, "
          f"eval_results={'on' if write_db else 'off'}, budget €{a.max_eur}")

    lock = threading.Lock()
    state = {"spent": 0.0, "n": 0, "over_budget": 0}

    def work(item: dict) -> None:
        with lock:
            if state["spent"] >= a.max_eur:
                state["over_budget"] += 1
                return
        try:
            rec = run_one(item, profile, a.config, a.threshold)
        except Exception as e:  # one bad item never kills the run
            rec = {"notice_id": item["notice"].get("id"), "config": a.config,
                   "run_error": f"{type(e).__name__}: {e}"[:500]}
        if write_db and rec.get("run_error") is None:
            _insert_eval_result(rec)
        if a.write_signals and rec.get("run_error") is None:
            _upsert_signal(rec, item["notice"], a.profile)
        with lock:
            state["spent"] += rec.get("cost_eur") or 0.0
            state["n"] += 1
            with path.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            if state["n"] % 10 == 0:
                print(f"[run] {state['n']}/{len(todo)}  spent €{state['spent']:.5f}")

    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        for f in as_completed([ex.submit(work, it) for it in todo]):
            f.result()

    print(f"[run] done: {state['n']} written, {state['over_budget']} skipped for budget, "
          f"spent €{state['spent']:.5f} -> {path}")
    if state["over_budget"]:
        print("[run] budget hit: rerun with a higher --max-eur to finish (done items are skipped)")


if __name__ == "__main__":
    main()
