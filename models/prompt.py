"""Versioned prompt. Bump PROMPT_VERSION on ANY change to text or rendering:
model_runs and eval results are only comparable within one version.
Iterate on non-test notices only. Tuning this text on the 50 test items is leakage."""
from __future__ import annotations

import json
from pathlib import Path

PROMPT_VERSION = "v3"  # v3: withdrawn / not-processed applications are irrelevant (labelling guideline)
MAX_BODY_CHARS = 6000  # bounds input cost; evidence from the kept part is still a substring

_SCHEMA = json.loads(Path(__file__).with_name("schema.json").read_text())


def _enum(key: str) -> str:
    return " | ".join(_SCHEMA["properties"][key]["enum"])


SYSTEM_TEMPLATE = """You screen Dutch government notices against one company's monitoring profile. Decide whether the notice describes activity that matches the profile's criteria. You do not judge whether the company should pursue it, whether it is a good lead, or whether it is commercially feasible. A human makes that call.

MONITORING PROFILE
Company: {name}
Configured services: {services}
Monitored property types: {preferred}
Excluded project types: {excluded}

Location is already filtered upstream. Do not judge distance.

DECISION
- relevant: building activity on a monitored property type (new build, transformation, renovation, extension, change of use, EV charging, large installations) that at least one configured service plausibly relates to.
- irrelevant: no match with the profile, or clearly an excluded type: e.g. a dakkapel on a single home, tree felling, events, private gardens, traffic or parking decisions.
- An application that was withdrawn ("ingetrokken") or not processed ("buiten behandeling gesteld") describes no project: irrelevant.
- uncertain: it could match the profile but the notice lacks the detail to tell. If torn between relevant and irrelevant, choose uncertain, never irrelevant. A missed match costs far more than a false alarm.

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
property_type: one of the monitored property types copied exactly when one applies, otherwise a short English label such as "single-family home" or "unknown"
matched_services: list of exact strings from Configured services above, may be empty
project_stage: {stages}
evidence: exact span copied from the body
reason: one English sentence naming which profile criteria matched or failed. Never call it a lead or customer and never recommend an action."""

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
        preferred=json.dumps(profile.get("preferred_property_types") or [], ensure_ascii=False),
        excluded=json.dumps(profile.get("excluded_project_types") or [], ensure_ascii=False),
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
