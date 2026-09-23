"""Offline regression for app/benchmark.py's _binary(). No network.

    python -m app.selftest_benchmark
"""
from __future__ import annotations

from app.benchmark import _binary

FAILURES: list[str] = []


def ok(cond: bool, msg: str) -> None:
    if not cond:
        FAILURES.append(msg)
        print(f"FAIL: {msg}")


def item(prediction: str, expected: str) -> dict:
    return {"prediction": prediction, "expected_decision": expected}


def main() -> None:
    # 2 TP, 1 FP, 1 FN, 1 TN
    items = [
        item("relevant", "relevant"),
        item("uncertain", "relevant"),   # uncertain counts as positive
        item("relevant", "irrelevant"),  # FP
        item("irrelevant", "relevant"),  # FN
        item("irrelevant", "irrelevant"),
    ]
    b = _binary(items)
    ok(b["tp"] == 2 and b["fp"] == 1 and b["fn"] == 1 and b["tn"] == 1, "confusion counts correct")
    ok(b["precision"] == 2 / 3, "precision = tp/(tp+fp)")
    ok(b["recall"] == 2 / 3, "recall = tp/(tp+fn)")
    ok(abs(b["f1"] - 2 / 3) < 1e-9, "f1 = harmonic mean of equal precision/recall")
    ok(b["accuracy"] == 3 / 5, "accuracy = (tp+tn)/n")

    # rows with no ground truth are excluded, never counted
    items2 = items + [{"prediction": "relevant", "expected_decision": None}]
    b2 = _binary(items2)
    ok(b2["n"] == 5, "rows without expected_decision are excluded from n")

    # empty input -> all None, never a guessed number
    b3 = _binary([])
    ok(b3["precision"] is None and b3["recall"] is None and b3["f1"] is None
       and b3["accuracy"] is None, "empty input -> None, not 0 or a guess")

    # no positives predicted -> precision undefined (None), not divide-by-zero
    b4 = _binary([item("irrelevant", "relevant"), item("irrelevant", "irrelevant")])
    ok(b4["precision"] is None, "no predicted positives -> precision is None")
    ok(b4["recall"] == 0.0, "recall is 0 (not None) when there are positives to find but none caught")

    print(f"\n{'FAILED' if FAILURES else 'OK'}: {len(FAILURES)} failure(s)")
    if FAILURES:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
