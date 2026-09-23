"""Versioned prompt. Bump PROMPT_VERSION on ANY change to text or rendering:
model_runs and eval results are only comparable within one version.
Iterate on non-test notices only. Tuning this text on the 50 test items is leakage."""
from __future__ import annotations

import json
from pathlib import Path

PROMPT_VERSION = "v1"
MAX_BODY_CHARS = 6000  # bounds input cost; evidence from the kept part is still a substring

_SCHEMA = json.loads(Path(__file__).with_name("schema.json").read_text())


def _enum(key: str) -> str:
    return " | ".join(_SCHEMA["properties"][key]["enum"])


SYSTEM_TEMPLATE = """You screen Dutch government notices for one company. Decide whether a notice signals a project this company could sell its services into.

COMPANY
Name: {name}
Services: {services}
Wanted property types: {preferred}
Not wanted: {excluded}

Location is already filtered upstream. Do not judge distance.

DECISION
- relevant: work on a wanted property type where at least one service plausibly applies: new build, transformation, renovation, extension, change of use, EV charging, large installations.
- irrelevant: nothing the company could sell into, or clearly a not-wanted type: e.g. a dakkapel on a single home, tree felling, events, private gardens, traffic or parking decisions.
- uncertain: it could be a relevant commercial project but the notice lacks the detail to tell. If torn between relevant and irrelevant, choose uncertain, never irrelevant. A missed project costs a sale; a false alarm costs seconds.

EVIDENCE, required for every decision
Copy one phrase or sentence from the BODY exactly as written: Dutch, character for character. No translating, paraphrasing, ellipses or added words. Never quote the title.
- relevant or uncertain: the span that shows the project, e.g. "transformeren en uitbreiden van het bestaande bedrijfspand".
- irrelevant: the span that rules it out, e.g. "kappen van een boom".

PROJECT STAGE
- permit_application: an application was received ("aanvraag ontvangen", "aangevraagd").
- permit_granted: a decision granting it ("verleend", "besluit tot verlening").
- zoning: a zoning or spatial plan ("bestemmingsplan", "omgevingsplan", "wijzigingsplan").
- other: anything else.

CONFIDENCE
Your probability, 0.0 to 1.0, that the decision is correct.

OUTPUT
Return one JSON object and nothing else, no markdown, with exactly these keys:
decision: {decisions}
confidence: number from 0.0 to 1.0
project_type: short English label, e.g. "commercial renovation", "new build", "tree removal"
property_type: short English label, e.g. "office", "warehouse", "single-family home", "unknown"
matched_services: list of exact strings from Services above, may be empty
project_stage: {stages}
evidence: exact span copied from the body
reason: one English sentence"""

USER_TEMPLATE = """TITLE: {title}
MUNICIPALITY: {municipality}
RUBRIEK: {rubriek}
PUBLISHED: {published_on}

BODY:
{body}"""


def build_system(profile: dict) -> str:
    """Identical for every notice of one profile: keeps the prompt prefix stable."""
    return SYSTEM_TEMPLATE.format(
        name=profile.get("name", ""),
        services=json.dumps(profile.get("services") or [], ensure_ascii=False),
        preferred=", ".join(profile.get("preferred_property_types") or []),
        excluded=", ".join(profile.get("excluded_project_types") or []),
        decisions=_enum("decision"),
        stages=_enum("project_stage"),
    )


def build_messages(notice: dict, profile: dict) -> list[dict]:
    body = (notice.get("body") or "")[:MAX_BODY_CHARS]
    user = USER_TEMPLATE.format(
        title=notice.get("title") or "",
        municipality=notice.get("municipality") or "unknown",
        rubriek=notice.get("rubriek") or "unknown",
        published_on=notice.get("published_on") or "unknown",
        body=body,
    )
    return [{"role": "system", "content": build_system(profile)},
            {"role": "user", "content": user}]
