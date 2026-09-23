"""Offline router/rules regression. No API calls, no keys. Run: python -m models.selftest_router
Re-run after every change to rules.py or router.py."""
import os; os.environ["NEBIUS_API_KEY"]="k"
import models.router as R, models.rules as rules
R.USE_SMALL = True  # scenarios below test the small -> large path
from models.client import validate
P={"id":"vandijk","services":["commercial electrical installations","EV charging infrastructure","access control systems","commercial lighting"],
   "excluded_project_types":["single-family minor renovation","tree removal","events","private gardens"]}
TREE={"id":"a","title":"Omgevingsvergunning kappen","body":"Burgemeester en wethouders hebben een aanvraag ontvangen voor het kappen van een boom aan de Lindengracht 12. Belanghebbenden kunnen reageren."}
MIXED={"id":"b","title":"Aanvraag omgevingsvergunning","body":"Aanvraag ontvangen voor de nieuwbouw van 40 appartementen en het kappen van 3 bomen aan de Kade 5."}
OFFICE={"id":"c","title":"Aanvraag","body":"Er is een aanvraag ontvangen voor het transformeren en uitbreiden van het bestaande bedrijfspand aan de Kade 7."}
DORM={"id":"d","title":"Aanvraag","body":"Aanvraag ontvangen voor het plaatsen van een dakkapel op het achterdakvlak van de woning Dorpsstraat 3."}
EVTRAFFIC={"id":"e","title":"Verkeersbesluit","body":"Verkeersbesluit: het aanwijzen van een parkeerplaats voor het opladen van elektrische voertuigen bij een laadpaal aan de Weg 1."}
VAGUE={"id":"f","title":"Aanvraag","body":"Aanvraag ontvangen voor het wijzigen van het gebruik van het perceel aan de Industrieweg 9."}
KANTOORUREN={"id":"g","title":"Kapvergunning","body":"Verleend: kapvergunning voor twee bomen aan de Parklaan. Stukken liggen ter inzage tijdens kantooruren."}

def mk(n, decision, conf, ev=None, **kw):
    r={"decision":decision,"confidence":conf,"project_type":"x","property_type":"office","matched_services":[],"project_stage":"other",
       "evidence": ev if ev is not None else n["body"][10:60],"reason":"r"}; r.update(kw); return r
def script(plan):
    q=list(plan)
    def fake(n,p,alias):
        exp_alias, res, err = q.pop(0); assert exp_alias==alias,(exp_alias,alias)
        errs = validate(res,n,p) if res is not None else []
        return res, {"model":alias+"-id","error":err or (",".join(errs) or None),"errors":errs,"cost_eur":0.001 if alias=="small" else 0.01}
    R.classify=fake; return q

def run(name, n, plan, profile=P, **kw):
    q=script(plan); tr={}; out=R.classify_notice(n, profile, trace=tr, **kw)
    assert not q, f"{name}: unused scripted calls {q}"
    assert set(out)>= set(R.CONTRACT_KEYS)|{"escalated","model_used","latency_ms","cost_eur"}
    ev_ok = out["decision"]=="uncertain" and out.get("error") or out["evidence"] in n["body"]
    print(f"{name:28} -> {out['decision']:10} by={tr['decided_by']:8} esc={out['escalated']!s:5} cost={out['cost_eur']} "
          f"trig={tr['triggers']} rule={tr['rule']} hits={tr['positive_hits']} err={out.get('error')} ev_ok={bool(ev_ok)}")
    return out

o=run("product path: no small", OFFICE, [("large", mk(OFFICE,"relevant",0.9),None)], use_small=False)
assert o["model_used"]=="large-id" and o["escalated"] is False and o["decision"]=="relevant"
o=run("product path: rules first", TREE, [], use_small=False); assert o["model_used"].startswith("rules:")
o=run("tree alone -> rules", TREE, [])
print("   evidence:", repr(o["evidence"]), "stage:", o["project_stage"])
run("trees + 40 appartementen", MIXED, [("small", mk(MIXED,"relevant",0.93),None)])
run("office, small confident", OFFICE, [("small", mk(OFFICE,"relevant",0.9),None)])
run("office, small says irrelevant", OFFICE, [("small", mk(OFFICE,"irrelevant",0.97),None),("large",mk(OFFICE,"relevant",0.88),None)])
run("dormer -> rules", DORM, [])
run("EV verkeersbesluit (conflict)", EVTRAFFIC, [("small", mk(EVTRAFFIC,"irrelevant",0.9),None),("large",mk(EVTRAFFIC,"uncertain",0.6),None)])
run("vague, low confidence", VAGUE, [("small", mk(VAGUE,"relevant",0.7),None),("large",mk(VAGUE,"irrelevant",0.9),None)])
run("small parse fail x2", VAGUE, [("small",None,"parse_failed"),("small",None,"parse_failed"),("large",mk(VAGUE,"irrelevant",0.9),None)])
run("small truncated (no retry)", VAGUE, [("small",None,"truncated"),("large",mk(VAGUE,"irrelevant",0.9),None)])
run("paraphrased evidence", OFFICE, [("small", mk(OFFICE,"relevant",0.95,ev="renovating the office building"),None),("large",mk(OFFICE,"relevant",0.9),None)])
run("large also invalid", OFFICE, [("small", mk(OFFICE,"uncertain",0.5),None),("large",mk(OFFICE,"relevant",0.9,ev="made up text here"),None)])
run("everything fails", VAGUE, [("small",None,"APIConnectionError: x"),("small",None,"APIConnectionError: x"),("large",None,"APIConnectionError: x"),("large",None,"APIConnectionError: x")])
run("kantooruren != kantoor", KANTOORUREN, [])
run("tree-care profile: no tree rule", TREE, [("small", mk(TREE,"relevant",0.9),None)], profile={**P,"excluded_project_types":[]})
run("threshold 0.95 escalates", OFFICE, [("small", mk(OFFICE,"relevant",0.9),None),("large",mk(OFFICE,"relevant",0.9),None)], threshold=0.95)
def boom(*a): raise RuntimeError("boom")
R.rules.triage, orig = boom, R.rules.triage
out=R.classify_notice(OFFICE,P); print("rules crash ->", out["decision"], out["error"]); R.rules.triage=orig
