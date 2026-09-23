"""Offline self-test for /eval and the evidence/edge-case logic in /models. No API, no DB, no keys.

python -m eval.selftest_eval

Asserts, so any failure stops with a traceback. The key check is REPLAY == LIVE ROUTER:
if the offline threshold replay did not reproduce the real router decision by decision, every
threshold-sweep number on the slides would be fiction.
"""
from __future__ import annotations

import io
import json
import math
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

import eval.metrics as M
import eval.run as R
import models.router as router
from models.client import evidence_ok

PROFILE = {"id": "vandijk", "name": "Van Dijk Techniek",
           "services": ["commercial electrical installations", "EV charging infrastructure",
                        "access control systems", "commercial lighting"],
           "preferred_property_types": ["office", "warehouse", "retail", "hospitality",
                                        "multi-unit residential"],
           "excluded_project_types": ["single-family minor renovation", "tree removal",
                                      "events", "private gardens"]}

REL = "Er is een aanvraag ontvangen voor het transformeren en uitbreiden van het bestaande bedrijfspand aan de Kade {i}."
VAGUE = "Er is een aanvraag ontvangen voor het wijzigen van het gebruik van het perceel aan de Industrieweg {i}."
TREE = "Er is een aanvraag ontvangen voor het kappen van een boom aan de Lindengracht {i}."


def ok(cond: bool, msg: str) -> None:
    assert cond, msg
    print(f"  ok  {msg}")


def dataset() -> list[dict]:
    items = []
    for i in range(10):
        items.append({"notice": {"id": f"rel{i}", "title": "Aanvraag", "body": REL.format(i=i)},
                      "label": {"expected_decision": "relevant", "borderline": i >= 8,
                                "expected_evidence": "transformeren en uitbreiden van het bestaande bedrijfspand"}})
    for i in range(5):
        items.append({"notice": {"id": f"tree{i}", "title": "Kap", "body": TREE.format(i=i)},
                      "label": {"expected_decision": "irrelevant", "borderline": False,
                                "expected_evidence": "kappen van een boom"}})
    for i in range(5):
        items.append({"notice": {"id": f"vag{i}", "title": "Aanvraag", "body": VAGUE.format(i=i)},
                      "label": {"expected_decision": "irrelevant", "borderline": i == 4,
                                "expected_evidence": "wijzigen van het gebruik van het perceel"}})
    return items


def _res(n: dict, decision: str, conf: float, ev: str | None = None) -> dict:
    body = n["body"]
    return {"decision": decision, "confidence": conf, "project_type": "x", "property_type": "office",
            "matched_services": [], "project_stage": "permit_application",
            "evidence": ev if ev is not None else body[31:90], "reason": "r"}


def fake_small(n: dict, p: dict, alias: str):
    i = n["id"]
    if i in ("rel0", "rel1"):                       # confident misses on relevant notices
        r = _res(n, "irrelevant", 0.95)
    elif i == "rel2":                               # paraphrased evidence -> invalid
        r = _res(n, "relevant", 0.9, ev="renovation of an office building downtown")
    elif i.startswith("vag") and i in ("vag0", "vag1"):
        r = _res(n, "relevant", 0.6)                # low confidence false positive
    elif i.startswith("rel"):
        r = _res(n, "relevant", 0.92)
    else:
        r = _res(n, "irrelevant", 0.9)
    from models.client import validate
    errs = validate(r, n, p)
    return r, {"model": "small-id", "stage": "small", "errors": errs,
               "error": ",".join(errs) or None, "cost_eur": 0.00006, "latency_ms": 1000,
               "ok": not errs}


def fake_large(n: dict, p: dict, alias: str):
    truth = "relevant" if n["id"].startswith("rel") else "irrelevant"
    r = _res(n, truth, 0.9)
    return r, {"model": "large-id", "stage": "large", "errors": [], "error": None,
               "cost_eur": 0.00026, "latency_ms": 2000, "ok": True}


def fake_any(n, p, alias):
    return fake_small(n, p, alias) if alias == "small" else fake_large(n, p, alias)


def main() -> None:
    print("statistics")
    lo, hi = M.wilson(18, 20)
    ok(abs(lo - 0.699) < 0.002 and abs(hi - 0.972) < 0.002, f"Wilson 18/20 = [{lo:.3f}, {hi:.3f}]")
    ok(M.wilson(0, 0) == (None, None), "Wilson with n=0 is undefined, not a crash")
    ok(abs(M.mcnemar_exact(0, 5) - 0.0625) < 1e-9, "McNemar exact (0,5) = 0.0625")
    ok(M.mcnemar_exact(3, 3) == 1.0, "McNemar symmetric = 1.0")
    ok(abs(M.fbeta(0.5, 1.0, 2) - (5 * 0.5 / (4 * 0.5 + 1))) < 1e-9, "F2 formula")
    ok(M.cohen_kappa(list("aabb"), list("aabb")) == 1.0, "kappa perfect agreement = 1")
    ok(abs(M.cohen_kappa(list("aaab"), list("aabb")) - 0.5) < 1e-9, "kappa known case = 0.5")
    ok(M.percentile([1, 2, 3, 4], 0.5) == 2.5, "percentile interpolation")

    print("evidence edge cases")
    body = "Aanvraag voor het trans\u00adformeren van het\u00a0bestaande bedrijfspand."
    ok(evidence_ok("transformeren van het bestaande bedrijfspand", body), "soft hyphen + nbsp in body still match")
    ok(not evidence_ok("Transformeren van het bestaande bedrijfspand", body), "case change is NOT verbatim")
    ok(not evidence_ok("pand", body), "trivially short evidence rejected")
    ok(not evidence_ok("transformeren van het bestaande kantoor", body), "one changed word rejected")
    ok(M.evidence_match("het bestaande bedrijfspand aan de Kade", "bestaande bedrijfspand") is True,
       "evidence accuracy: containment either way")
    ok(M.evidence_match("de", "bestaande bedrijfspand") is False, "evidence accuracy: short span can't win")

    print("router edge cases")
    calls = []
    router.classify = lambda n, p, a: (calls.append(a), fake_any(n, p, a))[1]
    out = router.classify_notice({"id": "e", "body": "   "}, PROFILE)
    ok(out["decision"] == "uncertain" and not calls and out["error"] == "empty_or_short_body",
       "empty body: uncertain, zero model calls")
    out = router.classify_notice({"id": "e2", "body": "Kort."}, PROFILE)
    ok(not calls, "very short body: zero model calls")

    with tempfile.TemporaryDirectory() as d:
        R.RUNS_DIR = M.RUNS_DIR = Path(d)
        R.load_profile = lambda pid: PROFILE
        R.classify = fake_any
        router.classify = fake_any
        items_file = Path(d) / "items.json"
        items_file.write_text(json.dumps(dataset()))

        print("runner")
        R.main(["--config", "small", "--items-file", str(items_file), "--workers", "4"])
        lines = (Path(d) / "small.jsonl").read_text().splitlines()
        ok(len(lines) == 20, "small run wrote 20 records")
        R.main(["--config", "small", "--items-file", str(items_file)])
        ok(len((Path(d) / "small.jsonl").read_text().splitlines()) == 20, "resume: rerun spends nothing")
        R.main(["--config", "small", "--items-file", str(items_file), "--run-name", "capped",
                "--workers", "1", "--max-eur", "0.0001"])
        n_capped = len((Path(d) / "capped.jsonl").read_text().splitlines())
        ok(n_capped == 2, f"budget cap stops the run (wrote {n_capped}, then stopped)")
        R.main(["--config", "large", "--items-file", str(items_file)])
        R.main(["--config", "router", "--items-file", str(items_file)])

        print("metrics")
        small, _ = M.load("small")
        s = M.summarize(list(small.values()))
        # small: rel0, rel1 missed; rel2 relevant (invalid evidence but decision counts); vag0/1 FP
        ok((s["tp"], s["fn"], s["fp"], s["tn"]) == (8, 2, 2, 8), f"small confusion {s['tp'], s['fn'], s['fp'], s['tn']}")
        ok(abs(s["recall"] - 0.8) < 1e-9 and abs(s["precision"] - 0.8) < 1e-9, "small P=R=0.8")
        ok(abs(s["valid_rate"] - 19 / 20) < 1e-9, "small valid rate counts the paraphrase as invalid")
        ok(s["borderline_n"] == 3, "borderline subset found (3 items)")
        rt, _ = M.load("router")
        sr = M.summarize(list(rt.values()))
        ok(sr["recall"] == 1.0, "router recovers the confident misses (rule_conflict escalation)")
        ok(sr["decided_by"].get("rules") == 5, "rules decide all 5 tree notices for free")
        ok(sr["invariant_violations"] == [], "router never published non-verbatim evidence")
        ok(abs(sr["eur_per_notice"] - (15 * 0.00006 + 5 * 0.00026) / 20) < 1e-12,
           "router cost = small on 15 + large on 5 escalations, rules free")
        ok(sr["triggers"] == {"rule_conflict": 2, "invalid": 1, "low_confidence": 2},
           f"trigger breakdown {sr['triggers']}")

        print("replay vs live router (must be identical)")
        buf = io.StringIO()
        with redirect_stdout(buf):
            M.replay("small", "large", [router.THRESHOLD])
        rs, _ = M.load("small")
        rl, _ = M.load("large")
        sim = {r["notice_id"]: r for r in M.simulate(rs, rl, router.THRESHOLD, with_rules=True)}
        mism = [i for i, live in rt.items()
                if (sim[i]["decision"], sim[i]["escalated"], sim[i]["decided_by"])
                != (live["decision"], live["escalated"], live["decided_by"])]
        cost_gap = abs(sum(r["cost_eur"] for r in sim.values()) - sum(r["cost_eur"] for r in rt.values()))
        ok(cost_gap < 1e-12, "replay cost equals live router cost")
        ok(not mism, f"replay reproduces every live router decision ({len(rt)} notices)")
        ok("rules+router@0.82" in buf.getvalue(), "replay prints rules on/off variants")

        print("stability and comparison")
        rep = [json.loads(l) for l in (Path(d) / "small.jsonl").read_text().splitlines()]
        rep[0]["decision"], rep[0]["positive"] = "uncertain", True  # simulate one flip
        (Path(d) / "small_rep.jsonl").write_text("\n".join(json.dumps(r) for r in rep))
        buf = io.StringIO()
        with redirect_stdout(buf):
            M.stability("small", "small_rep")
            M.compare("large", "router")
            M.print_table(["small", "large", "router"], md=True, per_day=45)
            M.hist("small")
        text = buf.getvalue()
        ok("decision changed: 1" in text, "stability detects the flipped decision")
        ok("McNemar" in text and "| router |" in text, "compare and markdown table render")
        ok("projection" not in text or "€" in text, "projection line renders")

        agree = Path(d) / "agreement.csv"
        agree.write_text("notice_id,label_a,label_b\nx1,relevant,relevant\nx2,irrelevant,relevant\n"
                         "x3,irrelevant,irrelevant\nx4,relevant,relevant\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            M.agreement(str(agree))
        ok("kappa" in buf.getvalue() and "disagree: x2" in buf.getvalue(), "agreement lists disagreements")

    print("\nALL EVAL SELFTESTS PASSED")


if __name__ == "__main__":
    main()
