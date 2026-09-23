"""ReguLine FastAPI app. Owner: C.

Routes so far (CONTRACTS.md SS4):
    GET /api/health
    GET /api/signals?profile_id=vandijk
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app import db
from app.logic import rank_signals

app = FastAPI(title="ReguLine")

SIGNALS_SELECT = (
    "notice_id,decision,project_type,property_type,project_stage,matched_services,"
    "evidence,reason,escalated,model_used,error,"
    "notices(title,municipality,published_on,source_url,lat,lng)"
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/signals")
def get_signals(profile_id: str = "vandijk") -> dict:
    profile = db.get_profile(profile_id)
    if profile is None:
        raise HTTPException(404, f"Unknown profile_id: {profile_id}")

    rows = db.select("signals", f"profile_id=eq.{profile_id}&select={SIGNALS_SELECT}")
    no_text_count = sum(1 for r in rows if r.get("error") == "empty_or_short_body")
    signals = rank_signals(rows, profile)

    return {
        "profile": {
            "id": profile["id"],
            "name": profile["name"],
            "radius_km": profile["radius_km"],
            "services": profile.get("services") or [],
            "preferred_property_types": profile.get("preferred_property_types") or [],
        },
        "funnel": None,
        "scanned_at": None,
        "no_text_count": no_text_count,
        "signals": signals,
    }
