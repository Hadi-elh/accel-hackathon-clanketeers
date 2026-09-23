"""ReguLine FastAPI app. Owner: C.

Routes so far (CONTRACTS.md SS4):
    GET /api/health
    GET /api/signals?profile_id=vandijk
"""
from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import classify as classify_demo
from app import db
from app.benchmark import get_benchmark
from app.economics import get_decision_stats, get_stream_stats
from app.logic import is_failed, is_no_text, rank_signals

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="ReguLine")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# /api/classify calls a real paid model per request and is reachable by anyone
# on the page -- a minimal in-memory cap so a stray refresh-spam doesn't run
# up a bill during the pitch. Not persistent, not distributed; fine for a
# single-process demo deployment.
_CLASSIFY_RATE_WINDOW_S = 300
_CLASSIFY_RATE_LIMIT = 5
_classify_calls: dict[str, list[float]] = defaultdict(list)


def _check_classify_rate_limit(client_ip: str) -> None:
    now = time.time()
    calls = _classify_calls[client_ip]
    calls[:] = [t for t in calls if now - t < _CLASSIFY_RATE_WINDOW_S]
    if len(calls) >= _CLASSIFY_RATE_LIMIT:
        raise HTTPException(429, "Too many live-classify requests. Try again in a few minutes.")
    calls.append(now)


class ClassifyRequest(BaseModel):
    # Optional[str], not `str | None`: pydantic evaluates annotations eagerly to
    # build its schema, so PEP 604 unions break under Python 3.9 regardless of
    # `from __future__ import annotations`. Optional[] is equivalent and portable.
    notice_id: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    municipality: Optional[str] = None


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


@app.get("/api/random_notice")
def api_random_notice() -> dict:
    notice = classify_demo.pick_random_notice()
    if notice is None:
        raise HTTPException(503, "No suitable notice available right now.")
    return notice


@app.post("/api/classify")
def api_classify(payload: ClassifyRequest, request: Request) -> dict:
    client_ip = request.client.host if request.client else "unknown"
    _check_classify_rate_limit(client_ip)
    try:
        return classify_demo.classify(
            notice_id=payload.notice_id, title=payload.title,
            body=payload.body, municipality=payload.municipality,
        )
    except classify_demo.NotFound as e:
        raise HTTPException(404, str(e))
    except classify_demo.BadRequest as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@app.get("/api/signals")
def get_signals(profile_id: str = "vandijk") -> dict:
    profile = db.get_profile(profile_id)
    if profile is None:
        raise HTTPException(404, f"Unknown profile_id: {profile_id}")

    rows = db.select("signals", f"profile_id=eq.{profile_id}&select={SIGNALS_SELECT}")
    no_text_count = sum(1 for r in rows if is_no_text(r))
    failed_count = sum(1 for r in rows if is_failed(r))
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
        "failed_count": failed_count,
        "signals": signals,
    }
