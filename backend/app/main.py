from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from .db import db_health, get_deputy_profile, init_db, list_ranking, recalculate_scores, upsert_deputy_snapshots
from .ingest import ingest_from_chamber
from .models import IngestPayload


auto_ingest_task: Optional[asyncio.Task] = None
last_auto_ingest_at: Optional[str] = None
last_auto_ingest_result: Optional[dict] = None


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


async def _auto_ingest_loop() -> None:
    global last_auto_ingest_at, last_auto_ingest_result

    interval_minutes = int(os.getenv("AUTO_INGEST_INTERVAL_MINUTES", "360"))
    session_limit = int(os.getenv("AUTO_INGEST_SESSION_LIMIT", "80"))

    while True:
        try:
            result = await asyncio.to_thread(ingest_from_chamber, None, session_limit)
            last_auto_ingest_at = datetime.now(timezone.utc).isoformat()
            last_auto_ingest_result = result
            print(f"[auto-ingest] completed at {last_auto_ingest_at}: {result}")
        except Exception as exc:
            last_auto_ingest_at = datetime.now(timezone.utc).isoformat()
            last_auto_ingest_result = {"error": str(exc)}
            print(f"[auto-ingest] failed at {last_auto_ingest_at}: {exc}")

        await asyncio.sleep(max(1, interval_minutes) * 60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global auto_ingest_task

    init_db()

    if _env_bool("AUTO_INGEST_ENABLED", default=False):
        auto_ingest_task = asyncio.create_task(_auto_ingest_loop())

    try:
        yield
    finally:
        if auto_ingest_task:
            auto_ingest_task.cancel()
            try:
                await auto_ingest_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Stratmap Politics API", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    ok, detail = db_health()
    return {"status": "ok" if ok else "degraded", "detail": detail}


@app.get("/api/v1/ingest/status")
def ingest_status() -> dict:
    return {
        "auto_ingest_enabled": _env_bool("AUTO_INGEST_ENABLED", default=False),
        "last_auto_ingest_at": last_auto_ingest_at,
        "last_auto_ingest_result": last_auto_ingest_result,
    }


@app.post("/api/v1/ingest/chamber")
def ingest_chamber(
    year: Optional[int] = Query(default=None, ge=2010, le=2100),
    session_limit: int = Query(default=80, ge=1, le=500),
) -> dict:
    try:
        result = ingest_from_chamber(year=year, session_limit=session_limit)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error de ingesta Camara: {exc}")


@app.post("/api/v1/ingest/deputies")
def ingest_deputies(payload: IngestPayload) -> dict:
    if not payload.items:
        raise HTTPException(status_code=400, detail="No hay items para ingerir")
    inserted = upsert_deputy_snapshots([i.model_dump() for i in payload.items])
    return {"ok": True, "processed": inserted}


@app.post("/api/v1/scores/recalculate")
def recalc_scores() -> dict:
    updated = recalculate_scores()
    return {"ok": True, "updated": updated}


@app.get("/api/v1/ranking")
def ranking(
    q: Optional[str] = Query(default=None),
    partido: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    comision: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    rows = list_ranking(q=q, partido=partido, region=region, comision=comision, limit=limit)
    return {"items": rows, "count": len(rows)}


@app.get("/api/v1/deputies/{deputy_id}")
def deputy_profile(deputy_id: int) -> dict:
    profile = get_deputy_profile(deputy_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Diputado no encontrado")
    return profile
