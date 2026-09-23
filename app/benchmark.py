"""GET /api/benchmark data. Every number here is a live Supabase query --
never a value from local /eval/runs/*.jsonl (those files aren't in the
repo, so they don't exist in the deployed environment either).

eval_results has no precision/recall/F1 columns (see schema.sql) --
those require expected_decision, which lives in eval_items. So we join
eval_results -> eval_items (PostgREST embedding) and compute them
ourselves, using the same "positive = relevant OR uncertain" convention
documented in /models/README.md and /eval/metrics.py. escalation_rate,
p95_latency_ms and cost_eur_per_1k come straight from the benchmark_summary
view (schema.sql) -- those need SQL-side percentile/sum aggregation we
don't redo client-side.
"""
from __future__ import annotations

from app import db


def _binary(items: list[dict]) -> dict:
    """items: [{"prediction": ..., "expected_decision": ...}, ...] for one config."""
    tp = fp = fn = tn = 0
    for it in items:
        expected = it.get("expected_decision")
        if expected not in ("relevant", "irrelevant"):
            continue  # no ground truth on this row -- shouldn't happen, defensive
        predicted_positive = it.get("prediction") in ("relevant", "uncertain")
        actual_positive = expected == "relevant"
        if predicted_positive and actual_positive:
            tp += 1
        elif predicted_positive and not actual_positive:
            fp += 1
        elif not predicted_positive and actual_positive:
            fn += 1
        else:
            tn += 1

    n = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision is not None and recall is not None and (precision + recall) > 0
          else None)
    accuracy = (tp + tn) / n if n else None

    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall, "f1": f1, "accuracy": accuracy,
    }


def get_benchmark() -> list[dict]:
    """One row per config that has eval_results rows. Sorted by config name."""
    view_rows = {r["config"]: r for r in db.select("benchmark_summary", "select=*")}
    joined = db.select("eval_results", "select=config,prediction,eval_items(expected_decision)")

    by_config: dict[str, list[dict]] = {}
    for row in joined:
        cfg = row["config"]
        ei = row.get("eval_items") or {}
        by_config.setdefault(cfg, []).append({
            "prediction": row.get("prediction"),
            "expected_decision": ei.get("expected_decision"),
        })

    configs = sorted(set(view_rows) | set(by_config))
    results = []
    for cfg in configs:
        view = view_rows.get(cfg, {})
        b = _binary(by_config.get(cfg, []))
        escalated_n = db.count("eval_results", f"config=eq.{cfg}&escalated=eq.true")

        results.append({
            "config": cfg,
            "items": b["n"] if b["n"] else view.get("items"),
            "accuracy": b["accuracy"], "accuracy_num": b["tp"] + b["tn"], "accuracy_den": b["n"] or None,
            "precision": b["precision"], "precision_num": b["tp"], "precision_den": (b["tp"] + b["fp"]) or None,
            "recall": b["recall"], "recall_num": b["tp"], "recall_den": (b["tp"] + b["fn"]) or None,
            "f1": b["f1"],
            "escalation_rate": view.get("escalation_rate"),
            "escalation_num": escalated_n, "escalation_den": view.get("items"),
            "p95_latency_ms": view.get("p95_latency_ms"),
            "cost_eur_per_1k": view.get("cost_eur_per_1k"),
        })
    return results
