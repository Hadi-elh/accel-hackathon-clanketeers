"""Data for the two economics panels on /. Deliberately two independent
code paths -- per the product brief, they describe different things and
must never block each other or be joined into one call chain.

Panel "Today's publication stream": ingest.prefilter.prefilter_stats_for_date()
over the whole notices table. Real, but can be slow as the table grows, so it
gets a soft 5s timeout, a 10-minute in-memory cache, and its own endpoint
(GET /api/stream_stats) so a slow call never blocks the feed.

Panel "How signals were decided": counts derived from `signals.model_used` /
`escalated` for this profile, plus total cost summed from `model_runs.cost_eur`.
Fast REST reads; no cache needed, but still never allowed to crash the page.

Both panels prefer scan_runs (if a row exists for the profile) over these live
sources -- scan_runs doesn't exist until the migration in CONTRACTS.md/schema.sql
is applied, so "not available yet" is treated exactly like "no row found".
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from app import db

STREAM_STATS_TIMEOUT_S = 5
STREAM_STATS_CACHE_TTL_S = 600

_executor = ThreadPoolExecutor(max_workers=2)
_stream_cache: dict[str, dict] = {}


def _latest_scan_run(profile_id: str) -> dict | None:
    """None if no scan_runs row exists for this profile -- including when the
    table itself doesn't exist yet (pre-migration). Never raises."""
    try:
        rows = db.select("scan_runs", f"profile_id=eq.{profile_id}&order=scan_date.desc&limit=1")
        return rows[0] if rows else None
    except RuntimeError:
        return None


# --------------------------------------------------------------- stream stats
def _live_stream_stats(profile_id: str) -> dict:
    from datetime import date

    from ingest import db as idb
    from ingest.prefilter import prefilter_stats_for_date

    profile = idb.get_profile(profile_id)
    if profile is None:
        raise ValueError(f"unknown profile_id: {profile_id}")
    today = date.today().isoformat()
    future = _executor.submit(prefilter_stats_for_date, today, profile)
    funnel = future.result(timeout=STREAM_STATS_TIMEOUT_S)

    plausible_rubriek = funnel.get("plausible_rubriek")
    location_unknown_kept = funnel.get("location_unknown_kept")
    kept = (
        None if plausible_rubriek is None or location_unknown_kept is None
        else plausible_rubriek + location_unknown_kept
    )
    return {
        "fetched": funnel.get("fetched"),
        "kept": kept,
        "plausible_rubriek": plausible_rubriek,
        "location_unknown_kept": location_unknown_kept,
        "source": "live",
        "last_scan": None,
    }


def _from_scan_run(scan: dict) -> dict:
    stats = scan.get("prefilter_stats") or {}
    plausible_rubriek = stats.get("plausible_rubriek")
    location_unknown_kept = stats.get("location_unknown_kept")
    return {
        "fetched": scan.get("fetched"),
        "kept": scan.get("kept"),
        "plausible_rubriek": plausible_rubriek,
        "location_unknown_kept": location_unknown_kept,
        "source": "scan_runs",
        "last_scan": scan.get("scan_date"),
    }


def get_stream_stats(profile_id: str = "vandijk") -> dict:
    scan = _latest_scan_run(profile_id)
    if scan is not None:
        return _from_scan_run(scan)

    now = time.time()
    cached = _stream_cache.get(profile_id)
    if cached and now - cached["cached_at"] < STREAM_STATS_CACHE_TTL_S:
        return cached["data"]

    try:
        data = _live_stream_stats(profile_id)
    except Exception:
        # Timeout, missing profile, Supabase error, whatever -- never block the page.
        data = {"fetched": None, "kept": None, "plausible_rubriek": None,
                "location_unknown_kept": None, "source": "live", "last_scan": None}

    _stream_cache[profile_id] = {"data": data, "cached_at": now}
    return data


# ------------------------------------------------------------- decision stats
def decision_counts(rows: list[dict]) -> dict:
    """rows: [{"model_used": ..., "escalated": ...}, ...] for one profile's
    signals. Pure -- no I/O, so directly testable."""
    rule_rejected = 0
    nemotron_only = 0
    escalated = 0
    for r in rows:
        model_used = r.get("model_used") or ""
        if model_used.startswith("rules:"):
            rule_rejected += 1
        elif r.get("escalated"):
            escalated += 1
        else:
            nemotron_only += 1
    return {"rule_rejected": rule_rejected, "nemotron_only": nemotron_only, "escalated": escalated}


def _live_decision_stats(profile_id: str) -> dict:
    signal_rows = db.select("signals", f"profile_id=eq.{profile_id}&select=model_used,escalated")
    counts = decision_counts(signal_rows)

    cost_rows = db.select("model_runs", f"profile_id=eq.{profile_id}&select=cost_eur")
    if not cost_rows or any(r.get("cost_eur") is None for r in cost_rows):
        total_cost_eur = None
    else:
        total_cost_eur = sum(r["cost_eur"] for r in cost_rows)

    return {**counts, "total_cost_eur": total_cost_eur, "source": "live", "last_scan": None}


def _decision_stats_from_scan_run(scan: dict) -> dict:
    ai_analysed = scan.get("ai_analysed")
    escalated = scan.get("escalated")
    nemotron_only = (
        None if ai_analysed is None or escalated is None else ai_analysed - escalated
    )
    return {
        "rule_rejected": scan.get("rule_rejected"),
        "nemotron_only": nemotron_only,
        "escalated": escalated,
        "total_cost_eur": scan.get("cost_eur"),
        "source": "scan_runs",
        "last_scan": scan.get("scan_date"),
    }


def get_decision_stats(profile_id: str = "vandijk") -> dict:
    scan = _latest_scan_run(profile_id)
    if scan is not None:
        return _decision_stats_from_scan_run(scan)
    try:
        return _live_decision_stats(profile_id)
    except Exception:
        return {"rule_rejected": None, "nemotron_only": None, "escalated": None,
                "total_cost_eur": None, "source": "live", "last_scan": None}
