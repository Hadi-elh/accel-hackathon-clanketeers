"""One row per model call into model_runs. Never raises.
If Supabase is down, the row goes to models/runs.local.jsonl so no call goes unrecorded."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LOCAL_FALLBACK = Path(__file__).with_name("runs.local.jsonl")
_sb = None


def _supabase():
    global _sb
    if _sb is None:
        from supabase import create_client
        _sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _sb


def log_run(notice_id: str | None, profile_id: str | None, meta: dict) -> None:
    row = {
        "notice_id": notice_id,
        "profile_id": profile_id,
        "model": meta.get("model") or "unknown",
        "stage": meta.get("stage"),
        "prompt_version": meta.get("prompt_version"),
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "latency_ms": meta.get("latency_ms"),
        "cost_eur": meta.get("cost_eur"),
        "ok": bool(meta.get("ok")),
        "error": (str(meta["error"])[:1000] if meta.get("error") else None),
    }
    try:
        _supabase().table("model_runs").insert(row).execute()
        return
    except Exception as e:
        print(f"[log] supabase insert failed, writing local: {e}", file=sys.stderr)
    try:
        with LOCAL_FALLBACK.open("a") as f:
            f.write(json.dumps({**row, "created_at": datetime.now(timezone.utc).isoformat()}) + "\n")
    except Exception as e:
        print(f"[log] local write failed too: {e}", file=sys.stderr)
