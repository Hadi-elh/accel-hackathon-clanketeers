"""Live classify demo: POST /api/classify runs the real production router
(rules -> gpt-oss-120b, via models.router.classify_notice) on one notice, on
demand, for the pitch. It is a demo run, not a scan: it never writes to
`signals`, and it never returns `confidence` (see the product boundary).

/models is imported lazily inside classify() -- it pulls in the openai SDK,
a heavier dependency the rest of /app doesn't need, matching the pattern
already used in app/economics.py for the /ingest import.
"""
from __future__ import annotations

import random

from app import db
from app.logic import compute_checks, compute_tier

PROFILE_ID = "vandijk"


class NotFound(Exception):
    """notice_id doesn't exist in the notices table."""


class BadRequest(Exception):
    """Neither notice_id nor title+body were given."""


def pick_random_notice() -> dict | None:
    candidates = db.recent_notices_with_body()
    return random.choice(candidates) if candidates else None


def _ad_hoc_notice(title: str | None, body: str, municipality: str | None) -> dict:
    return {
        "id": None, "title": title, "body": body, "municipality": municipality,
        "rubriek": None, "published_on": None, "source_url": None, "lat": None, "lng": None,
    }


def classify(*, notice_id: str | None = None, title: str | None = None,
             body: str | None = None, municipality: str | None = None) -> dict:
    if notice_id:
        notice = db.get_notice(notice_id)
        if notice is None:
            raise NotFound(f"Unknown notice_id: {notice_id}")
    elif body:
        notice = _ad_hoc_notice(title, body, municipality)
    else:
        raise BadRequest("Provide notice_id, or title and body.")

    profile = db.get_profile(PROFILE_ID)
    if profile is None:
        raise RuntimeError(f"Profile '{PROFILE_ID}' not found in company_profiles.")

    from models.router import classify_notice

    trace: dict = {}
    result = classify_notice(notice, profile, trace=trace)

    decision = result.get("decision") or "uncertain"
    checks = compute_checks(result, notice, profile)
    tier = compute_tier(decision, checks)

    evidence = result.get("evidence") or ""
    evidence_verbatim = bool(evidence) and evidence in (notice.get("body") or "")

    return {
        "decision": decision,
        "project_type": result.get("project_type"),
        "property_type": result.get("property_type"),
        "matched_services": result.get("matched_services") or [],
        "evidence": evidence,
        "reason": result.get("reason"),
        "model_used": result.get("model_used"),
        "latency_ms": result.get("latency_ms"),
        "cost_eur": result.get("cost_eur"),
        "error": result.get("error"),
        "checks": checks,
        "tier": tier,
        "evidence_verbatim": evidence_verbatim,
        "decided_by": trace.get("decided_by"),
        "notice": {
            "title": notice.get("title"),
            "municipality": notice.get("municipality"),
            "published_on": notice.get("published_on"),
            "source_url": notice.get("source_url"),
        },
    }
