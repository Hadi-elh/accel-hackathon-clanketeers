"""KOOP ingest entrypoint. Owner: A.

CLI: python -m ingest.fetch --date today [--limit N]
Fetches gemeenteblad notices and upserts raw rows into Supabase `notices`.

See CONTRACTS.md SS4 for the frozen function signatures /models and /app
import: fetch_notices() and prefilter_stats() (the latter implemented in
prefilter.py, re-exported here so the contract's import path holds).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from ingest import koop_client
from ingest.prefilter import prefilter, prefilter_stats  # noqa: F401 (re-exported, CONTRACTS.md SS4)
from ingest.prefilter import prefilter_stats_for_date  # noqa: F401 (additive, not part of the frozen contract)

DEFAULT_FETCH_LIMIT = 500  # keep hackathon runs fast; raise for full daily volume

__all__ = ["fetch_notices", "prefilter_stats", "prefilter_stats_for_date", "fetch_raw_notices"]


def _resolve_date(value: str) -> str:
    if value == "today":
        return date.today().isoformat()
    if value == "yesterday":
        return (date.today() - timedelta(days=1)).isoformat()
    return value


def fetch_raw_notices(target_date: str, limit: int | None = DEFAULT_FETCH_LIMIT) -> list[dict]:
    """Fetch gemeenteblad notices for a date, unfiltered. Never calls a model."""
    return koop_client.fetch_gmb_notices(_resolve_date(target_date), limit=limit)


def fetch_notices(date: str, profile: dict) -> list[dict]:
    """Fetch + prefilter. Returns Notice dicts (CONTRACTS.md SS1).

    Prefilter drops: wrong rubriek, outside radius_km. Also drops
    location_unknown notices whose municipality is empirically confirmed
    out-of-radius by real coordinates already observed elsewhere in the
    notices table (see prefilter.municipalities_in_radius) -- falls back to
    no municipality filtering if that lookup fails for any reason. Never
    calls a model.
    """
    raw = fetch_raw_notices(date)
    try:
        from ingest import db
        from ingest.prefilter import municipalities_in_radius

        muni_class = municipalities_in_radius(profile, db.fetch_all_notices())
    except Exception:
        muni_class = None
    kept, _funnel = prefilter(raw, profile, municipality_classification=muni_class)
    return kept


def _write_sample(notices: list[dict], path: Path) -> None:
    path.write_text(json.dumps(notices, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch KOOP gemeenteblad notices into Supabase.")
    parser.add_argument("--date", default="today", help='"today", "yesterday", or YYYY-MM-DD')
    parser.add_argument("--limit", type=int, default=DEFAULT_FETCH_LIMIT)
    parser.add_argument("--no-db", action="store_true", help="skip Supabase write (dry run)")
    parser.add_argument("--sample-out", default=None, help="also write notices to this JSON path")
    args = parser.parse_args()

    target_date = _resolve_date(args.date)
    print(f"Fetching gemeenteblad notices for {target_date} (limit={args.limit})...", file=sys.stderr)
    notices = fetch_raw_notices(target_date, limit=args.limit)
    print(f"Fetched {len(notices)} notices.")

    if args.sample_out:
        _write_sample(notices, Path(args.sample_out))
        print(f"Wrote sample to {args.sample_out}")

    if not args.no_db:
        from ingest import db

        count = db.upsert_notices(notices)
        print(f"Upserted {count} rows into Supabase `notices`.")
    else:
        print("Skipped Supabase write (--no-db).")


if __name__ == "__main__":
    main()
