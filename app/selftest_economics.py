"""Offline regression for app/economics.py's decision_counts(). No network.

    python -m app.selftest_economics
"""
from __future__ import annotations

from app.economics import decision_counts

FAILURES: list[str] = []


def ok(cond: bool, msg: str) -> None:
    if not cond:
        FAILURES.append(msg)
        print(f"FAIL: {msg}")


def main() -> None:
    rows = [
        {"model_used": "rules:r2", "escalated": False},
        {"model_used": "rules:r2", "escalated": False},
        {"model_used": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "escalated": False},
        {"model_used": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "escalated": False},
        {"model_used": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", "escalated": False},
        {"model_used": "openai/gpt-oss-120b", "escalated": True},
    ]
    c = decision_counts(rows)
    ok(c["rule_rejected"] == 2, "rule_rejected counts model_used starting with 'rules:'")
    ok(c["nemotron_only"] == 3, "nemotron_only counts non-rules, non-escalated rows")
    ok(c["escalated"] == 1, "escalated counts non-rules rows with escalated=True")
    ok(sum(c.values()) == len(rows), "counts partition every row exactly once")

    # rules rows are never counted as escalated even if the field were somehow set
    rows2 = [{"model_used": "rules:r2", "escalated": True}]
    c2 = decision_counts(rows2)
    ok(c2["rule_rejected"] == 1 and c2["escalated"] == 0,
       "a rules-path row is always rule_rejected, never escalated")

    # missing model_used doesn't crash, falls into nemotron_only bucket (not rules)
    rows3 = [{"model_used": None, "escalated": False}]
    c3 = decision_counts(rows3)
    ok(c3["nemotron_only"] == 1, "missing model_used doesn't crash and isn't counted as rules")

    # empty input -> all zero, not an error
    c4 = decision_counts([])
    ok(c4 == {"rule_rejected": 0, "nemotron_only": 0, "escalated": 0}, "empty input -> all zero")

    print(f"\n{'FAILED' if FAILURES else 'OK'}: {len(FAILURES)} failure(s)")
    if FAILURES:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
