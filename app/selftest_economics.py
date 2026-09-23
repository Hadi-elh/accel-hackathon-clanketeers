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
        {"model_used": "rules:r2"},
        {"model_used": "rules:r2"},
        {"model_used": "openai/gpt-oss-120b"},
        {"model_used": "openai/gpt-oss-120b"},
        {"model_used": "openai/gpt-oss-120b"},
        {"model_used": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"},
    ]
    c = decision_counts(rows)
    ok(c["rule_rejected"] == 2, "rule_rejected counts model_used starting with 'rules:'")
    ok(c["gpt_oss"] == 3, "gpt_oss counts model_used containing 'gpt-oss'")
    ok(c["nemotron"] == 1, "nemotron counts model_used containing 'Nemotron'")
    ok(sum(c.values()) == len(rows), "counts partition every row exactly once")

    # rules rows are classified as rules even if the model_used string also
    # happens to mention gpt-oss or Nemotron somewhere (rules: prefix wins)
    rows2 = [{"model_used": "rules:r2"}]
    c2 = decision_counts(rows2)
    ok(c2["rule_rejected"] == 1 and c2["gpt_oss"] == 0 and c2["nemotron"] == 0,
       "a rules-path row is always rule_rejected")

    # missing/unrecognized model_used doesn't crash and isn't counted anywhere
    rows3 = [{"model_used": None}, {"model_used": "none"}, {}]
    c3 = decision_counts(rows3)
    ok(c3 == {"rule_rejected": 0, "gpt_oss": 0, "nemotron": 0},
       "missing/unrecognized model_used doesn't crash and isn't miscounted")

    # empty input -> all zero, not an error
    c4 = decision_counts([])
    ok(c4 == {"rule_rejected": 0, "gpt_oss": 0, "nemotron": 0}, "empty input -> all zero")

    # current production data has no Nemotron tier -> reads 0, not hidden/None
    rows5 = [{"model_used": "rules:r2"}, {"model_used": "openai/gpt-oss-120b"}]
    c5 = decision_counts(rows5)
    ok(c5["nemotron"] == 0, "no Nemotron rows -> nemotron is 0 (real count), matching current prod")

    print(f"\n{'FAILED' if FAILURES else 'OK'}: {len(FAILURES)} failure(s)")
    if FAILURES:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
