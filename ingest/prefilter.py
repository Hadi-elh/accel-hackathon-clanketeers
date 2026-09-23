"""Deterministic prefilter: geography + rubriek. Never calls a model.

Rubriek allowlist derived from a real 200-record KOOP sample (gemeenteblad,
2026-09-22) -- see PLAYBOOK.md SS4: "never spend model tokens on something
the metadata already answers."
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

# From the real sample: omgevingsvergunning (112/200), omgevingsmelding (12),
# andere vergunning (16), andere beschikking (5) are the rubrieken that
# plausibly cover construction / environment permits -- the physical-project
# signals Van Dijk Techniek cares about. Excluded: evenementenvergunning /
# evenementmelding (events, explicitly out of scope), andere melding (too
# broad/noisy - catches noise complaints, animal permits, etc.), council
# meeting minutes, general government info.
ALLOWED_RUBRIEKEN = {
    "omgevingsvergunning",
    "omgevingsmelding",
    "andere vergunning",
    "andere beschikking",
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def prefilter(
    notices: list[dict],
    profile: dict,
    allowed_rubrieken: set[str] | None = None,
) -> tuple[list[dict], dict]:
    """Apply the deterministic prefilter (radius check + rubriek allowlist).

    Returns (kept_notices, funnel) where funnel matches CONTRACTS.md SS4:
    {"fetched", "in_region", "plausible_rubriek", "location_unknown"}.
    `in_region` and `plausible_rubriek` describe the known-location subset
    (a decreasing funnel); `location_unknown` is a separate diagnostic count
    -- those notices are never silently dropped, they still pass the rubriek
    check and enter `kept`, but since we cannot verify their geography they
    don't count toward `in_region`/`plausible_rubriek`.
    """
    allowed = allowed_rubrieken or ALLOWED_RUBRIEKEN
    fetched = len(notices)
    in_region = 0
    plausible_rubriek = 0
    location_unknown = 0
    kept: list[dict] = []

    for n in notices:
        lat, lng = n.get("lat"), n.get("lng")
        rubriek_ok = n.get("rubriek") in allowed

        if lat is None or lng is None:
            location_unknown += 1
            if rubriek_ok:
                kept.append(n)
            continue

        dist = haversine_km(profile["lat"], profile["lng"], lat, lng)
        if dist > profile["radius_km"]:
            continue

        in_region += 1
        if rubriek_ok:
            plausible_rubriek += 1
            kept.append(n)

    funnel = {
        "fetched": fetched,
        "in_region": in_region,
        "plausible_rubriek": plausible_rubriek,
        "location_unknown": location_unknown,
    }
    return kept, funnel


def prefilter_stats(profile: dict | None = None) -> dict:
    """Real funnel counters for the UI, computed live from the notices table.

    CONTRACTS.md SS4 defines this as zero-argument; it defaults to the fixed
    demo profile (vandijk) pulled from Supabase, so every call recomputes
    against current data instead of returning a cached/hard-coded number.
    """
    from ingest import db

    prof = profile or db.get_profile("vandijk")
    notices = db.fetch_all_notices()
    _kept, funnel = prefilter(notices, prof)
    return funnel
