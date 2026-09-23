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
    municipality_classification: dict[str, str] | None = None,
) -> tuple[list[dict], dict]:
    """Apply the deterministic prefilter (radius check + rubriek allowlist).

    Returns (kept_notices, funnel) where funnel matches CONTRACTS.md SS4:
    {"fetched", "in_region", "plausible_rubriek", "location_unknown"}.
    `in_region` and `plausible_rubriek` describe the known-location subset
    (a decreasing funnel); `location_unknown` is a separate diagnostic count
    -- those notices are never silently dropped by default, they still pass
    the rubriek check and enter `kept`, but since we cannot verify their
    geography they don't count toward `in_region`/`plausible_rubriek`.

    `municipality_classification` (see municipalities_in_radius()) is
    optional and, when given, actively drops location_unknown notices whose
    municipality is empirically 'out' of radius (every real coordinate ever
    observed for that municipality was outside radius_km) -- these are
    counted separately as `dropped_by_municipality`, never silently merged
    into `location_unknown`, so the funnel still shows why they left.
    """
    allowed = allowed_rubrieken or ALLOWED_RUBRIEKEN
    fetched = len(notices)
    in_region = 0
    plausible_rubriek = 0
    location_unknown = 0
    dropped_by_municipality = 0
    kept: list[dict] = []

    for n in notices:
        lat, lng = n.get("lat"), n.get("lng")
        rubriek_ok = n.get("rubriek") in allowed

        if lat is None or lng is None:
            muni_class = None
            if municipality_classification and n.get("municipality"):
                muni_class = municipality_classification.get(n["municipality"])
            if muni_class == "out":
                dropped_by_municipality += 1
                continue
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
        "dropped_by_municipality": dropped_by_municipality,
    }
    return kept, funnel


def prefilter_stats(profile: dict | None = None) -> dict:
    """Real funnel counters for the UI, computed live from the notices table.

    CONTRACTS.md SS4 defines this as zero-argument; it defaults to the fixed
    demo profile (vandijk) pulled from Supabase, so every call recomputes
    against current data instead of returning a cached/hard-coded number.
    Counts across the whole table (no date filter) -- see
    prefilter_stats_for_date() for a single scan's numbers.
    """
    from ingest import db

    prof = profile or db.get_profile("vandijk")
    notices = db.fetch_all_notices()
    _kept, funnel = prefilter(notices, prof)
    return funnel


def municipalities_in_radius(profile: dict, notices: list[dict]) -> dict[str, str]:
    """Classify each municipality as 'in' / 'out' / 'mixed' / 'insufficient_data'
    using ONLY the real observed coordinates already fetched for that
    municipality -- never a fabricated municipality centroid or guessed
    distance. A municipality is 'in' only if every coordinate we've actually
    seen for it falls within radius_km (min 2 observations); 'out' if every
    one we've seen falls outside; 'mixed' if it straddles the boundary
    (large municipality); otherwise 'insufficient_data'.
    """
    by_muni: dict[str, list[float]] = {}
    for n in notices:
        muni = n.get("municipality")
        lat, lng = n.get("lat"), n.get("lng")
        if not muni or lat is None or lng is None:
            continue
        dist = haversine_km(profile["lat"], profile["lng"], lat, lng)
        by_muni.setdefault(muni, []).append(dist)

    classification: dict[str, str] = {}
    for muni, dists in by_muni.items():
        if len(dists) < 2:
            classification[muni] = "insufficient_data"
        elif max(dists) <= profile["radius_km"]:
            classification[muni] = "in"
        elif min(dists) > profile["radius_km"]:
            classification[muni] = "out"
        else:
            classification[muni] = "mixed"
    return classification


def prefilter_stats_for_date(target_date: str, profile: dict | None = None) -> dict:
    """Funnel counters scoped to one scan date (additive; prefilter_stats()
    is unchanged and keeps counting the whole table). Also reports
    geo_inferred_in_region: location_unknown notices whose municipality is
    empirically 'in' per municipalities_in_radius() -- a deterministic,
    data-derived signal, not a fabricated distance. Kept as a separate key,
    never folded into in_region, since it is inferred, not confirmed.
    """
    from ingest import db

    prof = profile or db.get_profile("vandijk")
    notices = [n for n in db.fetch_all_notices() if n.get("published_on") == target_date]
    _kept, funnel = prefilter(notices, prof)

    all_notices = db.fetch_all_notices()  # broader sample for a stable municipality classification
    classification = municipalities_in_radius(prof, all_notices)
    geo_inferred_in_region = sum(
        1
        for n in notices
        if n.get("lat") is None
        and n.get("municipality")
        and classification.get(n["municipality"]) == "in"
    )

    return {**funnel, "date": target_date, "geo_inferred_in_region": geo_inferred_in_region}
