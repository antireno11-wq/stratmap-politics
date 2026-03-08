from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from .db import (
    count_by_camara,
    db_health,
    get_parliamentarian,
    init_db,
    list_parliamentarians,
    upsert_parliamentarians,
)
from .ingest import ingest_all_parliamentarians, ingest_deputies_from_chamber, ingest_senators_from_senate
from .models import IngestPayload
from .scrapers.chamber import inspect_deputies_source


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

    while True:
        try:
            result = await asyncio.to_thread(ingest_all_parliamentarians)
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


app = FastAPI(title="Stratmap Politics API", version="0.3.0", lifespan=lifespan)


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


@app.post("/api/v1/ingest/chamber/deputies")
def ingest_chamber_deputies() -> dict:
    try:
        result = ingest_deputies_from_chamber()
        return {"ok": True, "source": "camara", "camara": "DIPUTADO", **result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error de ingesta Camara: {exc}")


@app.get("/api/v1/debug/chamber/source")
def debug_chamber_source(sample_limit: int = Query(default=5, ge=1, le=20)) -> dict:
    try:
        return inspect_deputies_source(sample_limit=sample_limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error debug Camara: {exc}")


@app.post("/api/v1/ingest/senate/senators")
def ingest_senate_senators() -> dict:
    try:
        result = ingest_senators_from_senate()
        return {"ok": True, "source": "senado", "camara": "SENADOR", **result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error de ingesta Senado: {exc}")


@app.post("/api/v1/ingest/all")
def ingest_all() -> dict:
    try:
        result = ingest_all_parliamentarians()
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error de ingesta: {exc}")


@app.post("/api/v1/ingest/parliamentarians")
def ingest_manual(payload: IngestPayload) -> dict:
    if not payload.items:
        raise HTTPException(status_code=400, detail="No hay items para ingerir")
    processed = upsert_parliamentarians(payload.camara, [i.model_dump() for i in payload.items], source="manual")
    return {"ok": True, "processed": processed, "camara": payload.camara}


@app.get("/api/v1/parliamentarians")
def parliamentarians(
    camara: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    partido: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=1000),
) -> dict:
    rows = list_parliamentarians(camara=camara, q=q, partido=partido, region=region, limit=limit)
    counters = count_by_camara()
    return {
        "items": rows,
        "count": len(rows),
        "total_global": counters.get("DIPUTADO", 0) + counters.get("SENADOR", 0),
        "counters": counters,
    }


@app.get("/api/v1/parliamentarians/{person_id}")
def parliamentarian_profile(person_id: int) -> dict:
    profile = get_parliamentarian(person_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Parlamentario no encontrado")
    return {"parlamentario": profile}


# Compatibilidad temporal con rutas antiguas.
@app.get("/api/v1/ranking")
def ranking_legacy(
    q: Optional[str] = Query(default=None),
    partido: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    rows = list_parliamentarians(camara="DIPUTADO", q=q, partido=partido, region=region, limit=limit)
    legacy = [
        {
            "id": r["id"],
            "external_id": r["external_id"],
            "nombre": r["nombre"],
            "partido": r["partido"],
            "distrito": r["distrito_circunscripcion"],
            "region": r["region"],
            "score": 0,
            "asistencia_pct": r.get("asistencia_pct") or 0,
            "proyectos_presentados": 0,
            "camara": r["camara"],
        }
        for r in rows
    ]
    return {"items": legacy, "count": len(legacy)}


@app.get("/api/v1/deputies/{deputy_id}")
def deputy_profile_legacy(deputy_id: int) -> dict:
    profile = get_parliamentarian(deputy_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Diputado no encontrado")
    return {
        "diputado": {
            "id": profile["id"],
            "nombre": profile["nombre"],
            "partido": profile["partido"],
            "distrito": profile["distrito_circunscripcion"],
            "periodo": profile["periodo"],
        },
        "score": None,
        "comisiones": [],
    }
