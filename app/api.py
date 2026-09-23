"""ReguLine FastAPI app. Owner: C.

Routes so far (CONTRACTS.md SS4):
    GET /api/health
    GET /api/signals?profile_id=vandijk
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.benchmark import get_benchmark
from app.economics import get_decision_stats, get_stream_stats
from app.logic import rank_signals

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="ReguLine")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/benchmark", response_class=FileResponse)
def benchmark_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "benchmark.html")


@app.get("/api/benchmark")
def api_benchmark() -> dict:
    return {"results": get_benchmark()}


@app.get("/api/stream_stats")
def api_stream_stats(profile_id: str = "vandijk") -> dict:
    return get_stream_stats(profile_id)


@app.get("/api/decision_stats")
def api_decision_stats(profile_id: str = "vandijk") -> dict:
    return get_decision_stats(profile_id)

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
