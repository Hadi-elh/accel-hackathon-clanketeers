"""Pure functions behind GET /api/signals: checks, tier, card shaping, sort.

No I/O, no Supabase, no network -- safe to unit test directly (see
selftest_logic.py). Every field here maps to a real column; nothing here
invents a number or a checkmark.
"""
from __future__ import annotations

from datetime import date as _date
from math import asin, cos, radians, sin, sqrt

TIER_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NEEDS_REVIEW": 3}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def compute_checks(signal: dict, notice: dict, profile: dict) -> dict:
    """property_match, services_match, distance_km, inside_radius. Each is a real,
    independently-verifiable fact -- never a guess.

    property_match: "unknown" (the rules-path default) or an empty property_type
    is always False, even if "unknown" somehow appeared in preferred_property_types.
    """
    property_type = _norm(signal.get("property_type"))
    preferred = {_norm(p) for p in (profile.get("preferred_property_types") or [])}
    property_match = bool(property_type) and property_type != "unknown" and property_type in preferred

    services_match = bool(signal.get("matched_services"))

    lat, lng = notice.get("lat"), notice.get("lng")
    if lat is None or lng is None:
        distance_km, inside_radius = None, None
    else:
        distance_km = round(haversine_km(profile["lat"], profile["lng"], lat, lng), 1)
        inside_radius = distance_km <= profile["radius_km"]

    return {
        "property_match": property_match,
        "services_match": services_match,
        "distance_km": distance_km,
        "inside_radius": inside_radius,
    }


def compute_tier(decision: str, checks: dict) -> str:
    """Assumes decision is already filtered to relevant/uncertain -- irrelevant and
    empty_or_short_body rows never reach this function (see build_signal)."""
    if decision == "uncertain":
        return "NEEDS_REVIEW"
    hits = int(checks["property_match"]) + int(checks["services_match"])
    if hits == 2:
        return "HIGH"
    if hits == 1:
        return "MEDIUM"
    return "LOW"


def build_signal(row: dict, profile: dict) -> dict | None:
    """One `signals` row (with an embedded `notices` object) -> one API card, or
    None if this row is excluded from the feed entirely:
    - error == 'empty_or_short_body' (counted separately as no_text_count)
    - decision == 'irrelevant'
    """
    if row.get("error") == "empty_or_short_body":
        return None
    decision = row.get("decision")
    if decision == "irrelevant":
        return None

    notice = row.get("notices") or {}
    checks = compute_checks(row, notice, profile)
    tier = compute_tier(decision, checks)

    return {
        "notice_id": row.get("notice_id"),
        "title": notice.get("title"),
        "municipality": notice.get("municipality"),
        "published_on": notice.get("published_on"),
        "source_url": notice.get("source_url"),
        "decision": decision,
        "project_type": row.get("project_type"),
        "property_type": row.get("property_type"),
        "project_stage": row.get("project_stage"),
        "matched_services": row.get("matched_services") or [],
        "evidence": row.get("evidence"),
        "reason": row.get("reason"),
        "escalated": bool(row.get("escalated")),
        "model_used": row.get("model_used"),
        "tier": tier,
        "checks": checks,
    }


def _date_ordinal(s: str | None) -> int:
    if not s:
        return 0
    try:
        return _date.fromisoformat(s).toordinal()
    except ValueError:
        return 0


def sort_key(card: dict) -> tuple:
    """HIGH, MEDIUM, LOW, NEEDS_REVIEW, then published_on descending within a tier."""
    return (TIER_ORDER.get(card["tier"], 99), -_date_ordinal(card.get("published_on")))


def rank_signals(rows: list[dict], profile: dict) -> list[dict]:
    cards = [c for c in (build_signal(r, profile) for r in rows) if c is not None]
    cards.sort(key=sort_key)
    return cards
