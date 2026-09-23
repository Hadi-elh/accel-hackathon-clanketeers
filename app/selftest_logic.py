"""Offline regression for app/logic.py. No API keys, no network.

    python -m app.selftest_logic
"""
from __future__ import annotations

from app.logic import build_signal, compute_checks, compute_tier, rank_signals

PROFILE = {
    "lat": 52.3702, "lng": 4.8952, "radius_km": 35,
    "preferred_property_types": ["office", "warehouse", "retail", "hospitality",
                                  "multi-unit residential"],
}

FAILURES: list[str] = []


def ok(cond: bool, msg: str) -> None:
    if not cond:
        FAILURES.append(msg)
        print(f"FAIL: {msg}")


def notice(lat=52.34, lng=4.87, **kw):
    return {"lat": lat, "lng": lng, "title": "t", "municipality": "Amsterdam",
            "published_on": "2026-09-23", "source_url": "https://example.org", **kw}


def signal(**kw):
    base = {"decision": "relevant", "property_type": "office",
            "matched_services": ["commercial lighting"], "error": None,
            "notice_id": "n1", "project_type": "renovation", "project_stage": "other",
            "evidence": "x", "reason": "y", "escalated": False, "model_used": "small"}
    base.update(kw)
    return base


def main() -> None:
    # HIGH: relevant + property_match + services_match
    row = {**signal(), "notices": notice()}
    card = build_signal(row, PROFILE)
    ok(card is not None and card["tier"] == "HIGH", "relevant + both matches -> HIGH")
    ok(card["checks"]["distance_km"] is not None, "distance computed when coords present")
    ok(card["checks"]["inside_radius"] is True, "inside_radius true within 35km")

    # MEDIUM: relevant + property_match only
    row = {**signal(matched_services=[]), "notices": notice()}
    card = build_signal(row, PROFILE)
    ok(card["tier"] == "MEDIUM", "relevant + property only -> MEDIUM")

    # MEDIUM: relevant + services_match only
    row = {**signal(property_type="unknown"), "notices": notice()}
    card = build_signal(row, PROFILE)
    ok(card["tier"] == "MEDIUM", "relevant + services only -> MEDIUM")
    ok(card["checks"]["property_match"] is False, "'unknown' property_type never matches")

    # LOW: relevant + neither
    row = {**signal(property_type="single-family home", matched_services=[]), "notices": notice()}
    card = build_signal(row, PROFILE)
    ok(card["tier"] == "LOW", "relevant + neither -> LOW")

    # NEEDS_REVIEW: uncertain
    row = {**signal(decision="uncertain"), "notices": notice()}
    card = build_signal(row, PROFILE)
    ok(card["tier"] == "NEEDS_REVIEW", "uncertain -> NEEDS_REVIEW")

    # Excluded: irrelevant
    row = {**signal(decision="irrelevant"), "notices": notice()}
    ok(build_signal(row, PROFILE) is None, "irrelevant decision is excluded")

    # Excluded: empty_or_short_body, even if decision looks relevant
    row = {**signal(error="empty_or_short_body"), "notices": notice()}
    ok(build_signal(row, PROFILE) is None, "empty_or_short_body is excluded regardless of decision")

    # uncertain rows are NOT excluded by the irrelevant rule
    row = {**signal(decision="uncertain", error=None), "notices": notice()}
    ok(build_signal(row, PROFILE) is not None, "uncertain (no error) is not excluded")

    # No coordinates -> distance_km and inside_radius both null
    row = {**signal(), "notices": notice(lat=None, lng=None)}
    card = build_signal(row, PROFILE)
    ok(card["checks"]["distance_km"] is None, "no coords -> distance_km null")
    ok(card["checks"]["inside_radius"] is None, "no coords -> inside_radius null")

    # property_type normalization: whitespace + case
    checks = compute_checks({"property_type": "  Office  ", "matched_services": []},
                             notice(), PROFILE)
    ok(checks["property_match"] is True, "property_type trimmed and case-insensitive")

    # tier ordering + published_on descending within a tier
    cards = [
        {"tier": "MEDIUM", "published_on": "2026-09-20"},
        {"tier": "HIGH", "published_on": "2026-09-01"},
        {"tier": "HIGH", "published_on": "2026-09-23"},
        {"tier": "NEEDS_REVIEW", "published_on": "2026-09-23"},
        {"tier": "LOW", "published_on": "2026-09-23"},
    ]
    ranked = sorted(cards, key=__import__("app.logic", fromlist=["sort_key"]).sort_key)
    ok([c["tier"] for c in ranked] == ["HIGH", "HIGH", "MEDIUM", "LOW", "NEEDS_REVIEW"],
       "tier order: HIGH, MEDIUM, LOW, NEEDS_REVIEW")
    ok(ranked[0]["published_on"] == "2026-09-23", "within HIGH, most recent published_on first")

    # rank_signals end to end: irrelevant dropped, order applied
    rows = [
        {**signal(decision="irrelevant"), "notices": notice()},
        {**signal(decision="uncertain"), "notices": notice(), "notice_id": "n2"},
        {**signal(), "notices": notice(), "notice_id": "n3"},
    ]
    ranked = rank_signals(rows, PROFILE)
    ok(len(ranked) == 2, "rank_signals drops the irrelevant row")
    ok(ranked[0]["notice_id"] == "n3" and ranked[0]["tier"] == "HIGH", "HIGH card ranked first")
    ok(ranked[1]["tier"] == "NEEDS_REVIEW", "NEEDS_REVIEW card ranked last")

    print(f"\n{'FAILED' if FAILURES else 'OK'}: {len(FAILURES)} failure(s)")
    if FAILURES:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
