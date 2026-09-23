"""Metrics over /eval/runs/<run>.jsonl. No API calls, no DB, costs nothing to rerun.

python -m eval.metrics small large router                 # benchmark table (+ --md for slides)
python -m eval.metrics small large router --per-day 45    # + cost projection at 45 notices/day
python -m eval.metrics --compare large router             # paired significance test (McNemar)
python -m eval.metrics --stability small small_rep2       # run-to-run decision flip rate
python -m eval.metrics --replay small large               # offline router: thresholds x rules on/off
python -m eval.metrics --hist small                       # confidence histogram of one run
python -m eval.metrics --agreement eval/agreement.csv     # human-vs-human label agreement

Definitions (locked):
- positive = predicted relevant OR uncertain (uncertain is surfaced for human review).
- ground truth is binary: expected_decision relevant/irrelevant, human-labelled.
- headline = recall and precision reported separately, each with a Wilson 95% interval,
  plus F2 (recall weighted 2x: a missed match costs more than a false alarm).
- review_load = share of notices surfaced. Guards against "always uncertain" gaming recall.
- evidence accuracy = predicted evidence contains the labelled span or vice versa, after
  whitespace normalisation and lowercasing; predicted span must be >= 12 characters.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

from models.client import MIN_EVIDENCE_CHARS, _norm
from models.router import escalation_triggers

RUNS_DIR = Path(__file__).with_name("runs")


# ------------------------------------------------------------------ primitives
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def fbeta(p: float | None, r: float | None, beta: float) -> float | None:
    if p is None or r is None:
        return None
    b2 = beta * beta
    return 0.0 if p + r == 0 else (1 + b2) * p * r / (b2 * p + r)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the discordant pair counts."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def percentile(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def evidence_match(pred: str | None, expected: str | None) -> bool | None:
    if not expected:
        return None
    p = _norm(pred or "").lower()
    e = _norm(expected).lower()
    return len(p) >= MIN_EVIDENCE_CHARS and (p in e or e in p)


# ------------------------------------------------------------------ loading
def load(run: str) -> tuple[dict[str, dict], int]:
    path = RUNS_DIR / f"{run}.jsonl"
    recs: dict[str, dict] = {}
    errors = 0
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("run_error"):
            errors += 1
            continue
        recs[r["notice_id"]] = r  # last write wins
    return recs, errors


# ------------------------------------------------------------------ summary
def summarize(recs: list[dict]) -> dict:
    lab = [r for r in recs if r.get("expected_decision") in ("relevant", "irrelevant")]
    tp = sum(r["positive"] and r["expected_decision"] == "relevant" for r in lab)
    fp = sum(r["positive"] and r["expected_decision"] == "irrelevant" for r in lab)
    fn = sum(not r["positive"] and r["expected_decision"] == "relevant" for r in lab)
    tn = sum(not r["positive"] and r["expected_decision"] == "irrelevant" for r in lab)
    prec = tp / (tp + fp) if tp + fp else None
    rec_ = tp / (tp + fn) if tp + fn else None
    border = [r for r in lab if r.get("borderline")]
    ev = [evidence_match(r.get("evidence"), r.get("expected_evidence")) for r in lab]
    ev = [x for x in ev if x is not None]
    lat = [r["latency_ms"] for r in recs if r.get("latency_ms") is not None]
    costs = [r["cost_eur"] for r in recs if r.get("cost_eur") is not None]
    # Correctness invariant: anything the router publishes must carry verbatim evidence.
    published = [r for r in recs if r.get("decided_by") in ("rules", "small", "large")
                 and r["config"] == "router"]
    triggers = Counter(t.split(":")[0] for r in recs for t in r.get("triggers") or [])
    return {
        "n": len(recs), "labelled": len(lab), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": prec, "precision_ci": wilson(tp, tp + fp),
        "recall": rec_, "recall_ci": wilson(tp, tp + fn),
        "f1": fbeta(prec, rec_, 1), "f2": fbeta(prec, rec_, 2),
        "accuracy": (tp + tn) / len(lab) if lab else None,
        "borderline_n": len(border),
        "borderline_acc": sum(r["correct"] for r in border) / len(border) if border else None,
        "review_load": sum(r["positive"] for r in recs) / len(recs) if recs else None,
        "uncertain_rate": sum(r["decision"] == "uncertain" for r in recs) / len(recs) if recs else None,
        "valid_rate": sum(r.get("evidence_valid") and not r.get("errors") for r in recs) / len(recs) if recs else None,
        "evidence_acc": sum(ev) / len(ev) if ev else None, "evidence_n": len(ev),
        "escalation_rate": sum(bool(r.get("escalated")) for r in recs) / len(recs) if recs else None,
        "decided_by": dict(Counter(r.get("decided_by") for r in recs)),
        "triggers": dict(triggers),
        "p50_ms": percentile(lat, 0.5), "p95_ms": percentile(lat, 0.95),
        "eur_per_notice": sum(costs) / len(costs) if costs else None,
        "cost_missing": len(recs) - len(costs), "eur_total": sum(costs),
        "invariant_violations": [r["notice_id"] for r in published if not r.get("evidence_valid")],
    }


def _pct(x: float | None) -> str:
    return "  -  " if x is None else f"{100 * x:5.1f}"


def _ci(ci: tuple) -> str:
    return "" if ci[0] is None else f"[{100 * ci[0]:.0f}-{100 * ci[1]:.0f}]"


def print_table(runs: list[str], md: bool, per_day: float | None) -> None:
    head = ["run", "n", "P % [95% CI]", "R % [95% CI]", "F2", "review", "valid", "evid",
            "esc", "p95 ms", "€/1k"]
    rows = []
    for run in runs:
        recs, errs = load(run)
        s = summarize(list(recs.values()))
        rows.append([
            run, f"{s['n']}" + (f"(+{errs}err)" if errs else ""),
            f"{_pct(s['precision'])} {_ci(s['precision_ci'])}",
            f"{_pct(s['recall'])} {_ci(s['recall_ci'])}",
            _pct(s["f2"]), _pct(s["review_load"]), _pct(s["valid_rate"]), _pct(s["evidence_acc"]),
            _pct(s["escalation_rate"]),
            "-" if s["p95_ms"] is None else f"{s['p95_ms']:.0f}",
            "-" if s["eur_per_notice"] is None else f"{1000 * s['eur_per_notice']:.4f}"])
        extras = [f"decided_by={s['decided_by']}"]
        if s["triggers"]:
            extras.append(f"triggers={s['triggers']}")
        if s["borderline_n"]:
            extras.append(f"borderline acc={_pct(s['borderline_acc'])}% (n={s['borderline_n']})")
        if s["cost_missing"]:
            extras.append(f"COST MISSING on {s['cost_missing']} rows (price not set?)")
        if s["invariant_violations"]:
            extras.append(f"!! PUBLISHED WITHOUT VERBATIM EVIDENCE: {s['invariant_violations']}")
        if per_day and s["eur_per_notice"] is not None:
            d = per_day * s["eur_per_notice"]
            warn = " (TEST MIX, NOT REPRESENTATIVE: project from a volume run)" if s["labelled"] else ""
            extras.append(f"projection: €{d:.4f}/day, €{365 * d:.2f}/year at {per_day:g} notices/day{warn}")
        rows.append(["", "  " + " | ".join(extras)] + [""] * (len(head) - 2))
    if md:
        print("| " + " | ".join(head) + " |")
        print("|" + "---|" * len(head))
        for r in rows:
            if r[0]:
                print("| " + " | ".join(r) + " |")
        return
    widths = [max(len(str(r[i])) for r in [head] + [x for x in rows if x[0]]) for i in range(len(head))]
    print("  ".join(h.ljust(w) for h, w in zip(head, widths)))
    for r in rows:
        print(r[1] if not r[0] else "  ".join(str(c).ljust(w) for c, w in zip(r, widths)))
    print("\nP/R: labelled items only. review = share surfaced. valid = schema ok + verbatim "
          "evidence. evid = evidence accuracy vs label. esc = escalation rate.")


# ------------------------------------------------------------------ paired analyses
def compare(a: str, b: str) -> None:
    ra, _ = load(a)
    rb, _ = load(b)
    ids = [i for i in ra if i in rb and ra[i].get("correct") is not None]
    b_only = sum(ra[i]["correct"] and not rb[i]["correct"] for i in ids)
    c_only = sum(rb[i]["correct"] and not ra[i]["correct"] for i in ids)
    missed_a = sum(ra[i]["expected_decision"] == "relevant" and not ra[i]["positive"] for i in ids)
    missed_b = sum(rb[i]["expected_decision"] == "relevant" and not rb[i]["positive"] for i in ids)
    ca = sum(ra[i].get("cost_eur") or 0 for i in ids)
    cb = sum(rb[i].get("cost_eur") or 0 for i in ids)
    print(f"paired on {len(ids)} labelled items")
    print(f"  only {a} correct: {b_only}   only {b} correct: {c_only}   "
          f"McNemar exact p = {mcnemar_exact(b_only, c_only):.3f}")
    print(f"  relevant items missed: {a}={missed_a}  {b}={missed_b}")
    if ca:
        print(f"  cost: {b} is {100 * cb / ca:.1f}% of {a} on the same items")
    print("  p >= 0.05 means the accuracy difference is not distinguishable from noise at this n.")


def stability(a: str, b: str) -> None:
    ra, _ = load(a)
    rb, _ = load(b)
    ids = [i for i in ra if i in rb]
    flips = [i for i in ids if ra[i]["decision"] != rb[i]["decision"]]
    pflips = [i for i in ids if ra[i]["positive"] != rb[i]["positive"]]
    dconf = [abs((ra[i].get("confidence") or 0) - (rb[i].get("confidence") or 0)) for i in ids]
    print(f"{len(ids)} notices in both runs")
    print(f"  decision changed: {len(flips)} ({_pct(len(flips) / len(ids) if ids else None)}%)")
    print(f"  surfaced/not-surfaced changed: {len(pflips)} "
          f"({_pct(len(pflips) / len(ids) if ids else None)}%)  <- what a user would notice")
    print(f"  mean |confidence change|: {sum(dconf) / len(dconf):.3f}" if dconf else "")
    if pflips:
        print(f"  flipped ids: {pflips[:15]}")


def simulate(rs: dict[str, dict], rl: dict[str, dict], t: float, with_rules: bool) -> list[dict]:
    """Router decisions re-derived from saved small and large outputs. Zero API calls.
    Ignores retries (a retry is a second small call), so it slightly understates cost."""
    sim = []
    for i in [k for k in rs if k in rl]:
        s, l = rs[i], rl[i]
        if with_rules and s.get("rule_reject"):
            sim.append({**s, "decision": "irrelevant", "positive": False, "escalated": False,
                        "cost_eur": 0.0, "decided_by": "rules", "triggers": []})
            continue
        hits = s.get("positive_hits", []) if with_rules else []
        trig = escalation_triggers(s.get("result"), {"error": s.get("error"),
                                   "errors": s.get("errors") or []}, hits, t)
        cost_s = s.get("cost_eur") or 0.0
        if not trig:
            sim.append({**s, "escalated": False, "cost_eur": cost_s, "decided_by": "small",
                        "triggers": []})
            continue
        ok_large = l.get("result") is not None and not l.get("errors")
        dec = l["decision"] if ok_large else "uncertain"
        sim.append({**s, "decision": dec, "positive": dec in ("relevant", "uncertain"),
                    "escalated": True, "cost_eur": cost_s + (l.get("cost_eur") or 0.0),
                    "decided_by": "large" if ok_large else "fallback", "triggers": trig})
    for r in sim:
        if r.get("expected_decision"):
            r["correct"] = r["positive"] == (r["expected_decision"] == "relevant")
    return sim


def replay(small_run: str, large_run: str, thresholds: list[float]) -> None:
    rs, _ = load(small_run)
    rl, _ = load(large_run)
    print(f"replay on {len([i for i in rs if i in rl])} notices present in both runs "
          f"(retries not simulated)")
    print(f"{'variant':<22}{'P %':>7}{'R %':>7}{'F2':>7}{'review':>8}{'esc %':>7}"
          f"{'rules %':>8}{'€/1k':>9}")
    for with_rules in (False, True):
        for t in thresholds:
            sim = simulate(rs, rl, t, with_rules)
            m = summarize(sim)
            rules_share = sum(r["decided_by"] == "rules" for r in sim) / len(sim) if sim else 0
            name = f"{'rules+' if with_rules else ''}router@{t:g}"
            eur = 1000 * m["eur_per_notice"] if m["eur_per_notice"] is not None else 0.0
            print(f"{name:<22}{_pct(m['precision']):>7}{_pct(m['recall']):>7}{_pct(m['f2']):>7}"
                  f"{_pct(m['review_load']):>8}{_pct(m['escalation_rate']):>7}"
                  f"{_pct(rules_share):>8}{eur:>9.4f}")


def hist(run: str, threshold: float = 0.82) -> None:
    recs, _ = load(run)
    conf = [r["confidence"] for r in recs.values() if isinstance(r.get("confidence"), (int, float))]
    if not conf:
        print("no confidences")
        return
    bins = Counter(min(19, int(c * 20)) for c in conf)
    top = max(bins.values())
    for b in range(20):
        if bins.get(b):
            print(f"{b / 20:.2f}-{(b + 1) / 20:.2f} {bins[b]:>4} {'#' * round(40 * bins[b] / top)}")
    above = sum(c >= threshold for c in conf) / len(conf)
    print(f"n={len(conf)}  share >= {threshold}: {100 * above:.0f}%  distinct values: {len(set(conf))}")
    if len(set(conf)) <= 4:
        print("Confidence takes very few distinct values: a threshold sweep on it is nearly meaningless.")


def agreement(path: str) -> None:
    rows = list(csv.DictReader(open(path)))
    a = [r["label_a"].strip() for r in rows]
    b = [r["label_b"].strip() for r in rows]
    k = cohen_kappa(a, b)
    agree = sum(x == y for x, y in zip(a, b))
    print(f"{len(rows)} double-labelled items: raw agreement {agree}/{len(rows)}, "
          f"Cohen's kappa = {k:.2f}" if k is not None else "no rows")
    print("kappa < 0.6: the labelling question is ambiguous. Fix the guideline before blaming the model.")
    for r in rows:
        if r["label_a"].strip() != r["label_b"].strip():
            print(f"  disagree: {r['notice_id']}  a={r['label_a']}  b={r['label_b']}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--per-day", type=float)
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
    ap.add_argument("--stability", nargs=2, metavar=("A", "B"))
    ap.add_argument("--replay", nargs=2, metavar=("SMALL", "LARGE"))
    ap.add_argument("--thresholds", default="0.7,0.8,0.82,0.9")
    ap.add_argument("--hist")
    ap.add_argument("--agreement")
    a = ap.parse_args(argv)
    if a.runs:
        print_table(a.runs, a.md, a.per_day)
    if a.compare:
        compare(*a.compare)
    if a.stability:
        stability(*a.stability)
    if a.replay:
        replay(*a.replay, [float(x) for x in a.thresholds.split(",")])
    if a.hist:
        hist(a.hist)
    if a.agreement:
        agreement(a.agreement)


if __name__ == "__main__":
    main()
