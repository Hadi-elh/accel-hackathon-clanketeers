"""Minimal Supabase REST (PostgREST) client for /app. Stdlib only -- no new
dependency for this module (the `supabase` package in requirements.txt is
for /models, not /app).

Read-only: /app reads company_profiles, notices, signals, model_runs,
eval_results, benchmark_summary and (once created) scan_runs. It never
writes to a table it doesn't own -- see CONTRACTS.md.

Reads SUPABASE_URL / SUPABASE_KEY from the environment, loaded from a
local .env if present (never committed -- see .gitignore).

Auth: the project key is the newer `sb_secret_` format. It requires the
`apikey` header; `Authorization: Bearer` with the same key is optional
but harmless alongside it (verified against the live project -- Bearer
alone, with no apikey, gets 401). Both are sent for parity with
ingest/db.py. Never log or print the key.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_ENV_LOADED = False


def _load_dotenv() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _config() -> tuple[str, str]:
    _load_dotenv()
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_KEY not set. Copy .env.example to .env and fill them in."
        )
    return url, key


def _get(path: str, extra_headers: dict | None = None) -> tuple[object, dict]:
    """GET against PostgREST. Returns (parsed_body, response_headers)."""
    url, key = _config()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(f"{url}/rest/v1/{path}", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            body = json.loads(raw) if raw else None
            return body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase GET {path} failed: {e.code} {detail}") from e


def select(table: str, query: str = "select=*") -> list[dict]:
    """Plain select, no count. Returns [] on an empty result set."""
    body, _ = _get(f"{table}?{query}")
    return body or []


def count(table: str, query: str = "select=id") -> int:
    """Exact row count via Prefer: count=exact + Range: 0-0 (no rows fetched)."""
    _, headers = _get(f"{table}?{query}", {"Prefer": "count=exact", "Range": "0-0"})
    content_range = headers.get("Content-Range", "*/0")
    total = content_range.split("/")[-1]
    return int(total) if total.isdigit() else 0


def get_profile(profile_id: str) -> dict | None:
    rows = select("company_profiles", f"id=eq.{profile_id}&select=*")
    return rows[0] if rows else None


def get_notice(notice_id: str) -> dict | None:
    """notice_id is arbitrary user input (POST /api/classify) -- quote it."""
    safe_id = urllib.parse.quote(notice_id, safe="")
    rows = select("notices", f"id=eq.{safe_id}&select=*")
    return rows[0] if rows else None


NOTICE_FIELDS = "id,title,body,municipality,rubriek,published_on,source_url,lat,lng"


def recent_notices_with_body(min_body_chars: int = 100, sample: int = 300) -> list[dict]:
    """Recent notices with a body over min_body_chars. PostgREST can't filter or
    order by length()/random() directly, so fetch a recent page and filter in
    Python -- honest (real rows, real check), just done client-side."""
    rows = select("notices", f"select={NOTICE_FIELDS}&order=fetched_at.desc&limit={sample}")
    return [r for r in rows if r.get("body") and len(r["body"]) > min_body_chars]
