"""Deterministic content rules. Zero cost, zero latency, no model call.

Two jobs, deliberately asymmetric because a missed project costs a sale:
  1. REJECT only obvious non-projects, and only when NO positive signal is present.
     "kappen van een boom" alone -> rejected; "40 appartementen en kappen van 3 bomen" -> not.
  2. POSITIVE hints never accept anything. They only stop the small model from
     confidently rejecting a notice that mentions a commercial project (router escalates).

Build and tune the patterns on NON-test notices. Eval measures rule precision on the test set.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

RULES_VERSION = "r1"
RULE_CONFIDENCE = 0.95  # declared, not measured: eval reports the real rule precision

# name -> (pattern, English project_type, profile exclusion that must be present or None)
# None = not a construction project for any trade profile (driveway, traffic, mooring, stall).
NEGATIVE_RULES: dict[str, tuple[str, str, str | None]] = {
    "tree_felling": (r"\b(?:kappen|vellen|rooien)\b[^.\n]{0,40}?\b(?:boom|bomen|houtopstand)\w*"
                     r"|\b(?:boom|bomen)\b[^.\n]{0,40}?\b(?:kappen|vellen|rooien)\b"
                     r"|\bkapvergunning\b", "tree removal", "tree removal"),
    "dormer": (r"\bdakkapel(?:len)?\b", "dormer on a dwelling", "single-family minor renovation"),
    "event": (r"\bevenement(?:en)?(?:vergunning)?\b", "event", "events"),
    "market_stall": (r"\bstandplaats(?:vergunning)?\b", "market stall permit", None),
    "driveway": (r"\b(?:uitweg|inrit)\b", "driveway permit", None),
    "traffic": (r"\bverkeersbesluit\b|\bgehandicaptenparkeerplaats\b|\bparkeerverbod\b",
                "traffic decision", None),
    "mooring": (r"\bligplaats(?:vergunning)?\b", "mooring permit", None),
}

POSITIVE = re.compile(
    r"\b(?:laadpaa?l(?:en)?|laadpunt(?:en)?|oplaadpunt(?:en)?|laadinfrastructuur|laadstation"
    r"|transformatie|transformeren|bedrijfspand|bedrijfshal|bedrijfsruimte|bedrijfsverzamelgebouw"
    r"|kantoor(?:pand|gebouw|ruimte|en)?|winkel(?:pand|ruimte|centrum)?|supermarkt|hotel|horeca"
    r"|restaurant|appartement(?:en|encomplex)?|wooneenhe(?:id|den)|woongebouw|nieuwbouw"
    r"|distributiecentrum|magazijn|opslaghal|parkeergarage)\b",
    re.I,
)

_STAGES = [
    ("permit_granted", re.compile(r"\bverleend\b|\bverlening\b", re.I)),
    ("permit_application", re.compile(r"\baanvraag\b|\baangevraagd\b", re.I)),
    ("zoning", re.compile(r"\b(?:bestemmingsplan|omgevingsplan|wijzigingsplan)\b", re.I)),
]
_COMPILED = {n: (re.compile(p, re.I), label, req) for n, (p, label, req) in NEGATIVE_RULES.items()}


@dataclass
class Triage:
    reject: dict | None = None                         # full contract result if rejected
    rule: str | None = None                            # which negative rule fired
    positive_hits: list[str] = field(default_factory=list)


def _stage(text: str) -> str:
    for stage, rx in _STAGES:
        if rx.search(text):
            return stage
    return "other"


def _evidence(body: str, start: int, end: int, max_len: int = 240) -> str:
    """Sentence around the match, returned as an exact slice of body (verbatim by construction)."""
    s = max(body.rfind(".", 0, start), body.rfind("\n", 0, start)) + 1
    e_dot, e_nl = body.find(".", end), body.find("\n", end)
    e = min(x for x in (e_dot, e_nl, len(body)) if x != -1)
    if e - s > max_len:  # sentence too long: match padded to word boundaries
        s = body.rfind(" ", 0, max(0, start - 60)) + 1
        e2 = body.find(" ", min(len(body), end + 60))
        e = e2 if e2 != -1 else len(body)
    return body[s:e].strip()


def positive_hits(notice: dict) -> list[str]:
    text = f"{notice.get('title') or ''}\n{notice.get('body') or ''}"
    return sorted({m.group(0).lower() for m in POSITIVE.finditer(text)})


def triage(notice: dict, profile: dict) -> Triage:
    body = notice.get("body") or ""
    hits = positive_hits(notice)
    t = Triage(positive_hits=hits)
    if hits or not body:
        return t  # any commercial signal -> never auto-reject
    excluded = set(profile.get("excluded_project_types") or [])
    for name, (rx, label, requires) in _COMPILED.items():
        if requires is not None and requires not in excluded:
            continue  # e.g. a tree-care company profile must still see tree permits
        m = rx.search(body)
        if not m:
            continue
        t.rule = name
        t.reject = {
            "decision": "irrelevant",
            "confidence": RULE_CONFIDENCE,
            "project_type": label,
            "property_type": "unknown",
            "matched_services": [],
            "project_stage": _stage(f"{notice.get('title') or ''} {body}"),
            "evidence": _evidence(body, m.start(), m.end()),
            "reason": f"Rule {RULES_VERSION}/{name}: {label} is not work this company sells into.",
        }
        return t
    return t
