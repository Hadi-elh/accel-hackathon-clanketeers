"""Minimal Supabase REST (PostgREST) client. Stdlib only -- no new dependency.

Reads SUPABASE_URL / SUPABASE_KEY from the environment, loaded from a local
.env if present (never committed -- see .gitignore).
"""

from __future__ import annotations

import json
import os
import urllib.error
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


def _request(method: str, path: str, body: object = None, extra_headers: dict | None = None) -> object:
    url, key = _config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{url}/rest/v1/{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase {method} {path} failed: {e.code} {detail}") from e


def upsert_notices(notices: list[dict]) -> int:
    """Upsert Notice rows into `notices`, keyed on id. Returns row count sent."""
    if not notices:
        return 0
    rows = [
        {
            "id": n["id"],
            "source_url": n.get("source_url"),
            "title": n.get("title"),
            "body": n.get("body"),
            "published_on": n.get("published_on"),
            "municipality": n.get("municipality"),
            "rubriek": n.get("rubriek"),
            "lat": n.get("lat"),
            "lng": n.get("lng"),
        }
        for n in notices
    ]
    _request("POST", "notices", body=rows, extra_headers={"Prefer": "resolution=merge-duplicates"})
    return len(rows)


def fetch_all_notices() -> list[dict]:
    result = _request("GET", "notices?select=id,rubriek,lat,lng")
    return result or []


def get_profile(profile_id: str) -> dict:
    result = _request("GET", f"company_profiles?id=eq.{profile_id}&select=*")
    if not result:
        raise RuntimeError(f"Company profile '{profile_id}' not found in Supabase.")
    return result[0]
