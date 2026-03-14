from __future__ import annotations

import asyncio
import os
import uuid
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
from .ingest import (
    attendance_percentage_summary,
    ingest_all_parliamentarians,
    ingest_attendance_sala,
    ingest_deputies_from_chamber,
    ingest_senators_from_senate,
)
from .models import IngestPayload
from .scrapers.chamber import inspect_attendance_source, inspect_deputies_source, inspect_deputy_period_structure


auto_ingest_task: Optional[asyncio.Task] = None
last_auto_ingest_at: Optional[str] = None
last_auto_ingest_result: Optional[dict] = None
batch_jobs: dict[str, dict] = {}


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
def ingest_chamber_deputies(
    enrich_profile_page: bool = Query(default=True),
    enrich_offset: int = Query(default=0, ge=0),
    enrich_limit: int = Query(default=0, ge=0, le=200),
) -> dict:
    try:
        result = ingest_deputies_from_chamber(
            enrich_profile_page=enrich_profile_page,
            enrich_offset=enrich_offset,
            enrich_limit=enrich_limit,
        )
        return {
            "ok": True,
            "source": "camara",
            "camara": "DIPUTADO",
            "enrich_profile_page": enrich_profile_page,
            "enrich_offset": enrich_offset,
            "enrich_limit": enrich_limit,
            **result,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error de ingesta Camara: {exc}")


async def _run_chamber_enrich_job(job_id: str, batch_size: int) -> None:
    batch_jobs[job_id]["status"] = "running"
    try:
        total = 157
        processed_batches = 0
        for offset in range(0, total, batch_size):
            await asyncio.to_thread(
                ingest_deputies_from_chamber,
                True,   # enrich_profile_page
                offset, # enrich_offset
                batch_size, # enrich_limit
                False, # include_attendance
            )
            processed_batches += 1
            batch_jobs[job_id]["progress"] = min(100, int(((offset + batch_size) / total) * 100))
            batch_jobs[job_id]["processed_batches"] = processed_batches
        batch_jobs[job_id]["status"] = "completed"
        batch_jobs[job_id]["progress"] = 100
        batch_jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        batch_jobs[job_id]["status"] = "failed"
        batch_jobs[job_id]["error"] = str(exc)
        batch_jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


@app.post("/api/v1/ingest/chamber/deputies/enrich/start")
async def start_chamber_enrich(batch_size: int = Query(default=20, ge=5, le=50)) -> dict:
    job_id = str(uuid.uuid4())
    batch_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "batch_size": batch_size,
        "processed_batches": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    asyncio.create_task(_run_chamber_enrich_job(job_id, batch_size))
    return {"ok": True, "job_id": job_id, "status": "queued", "batch_size": batch_size}


@app.get("/api/v1/ingest/chamber/deputies/enrich/{job_id}")
def chamber_enrich_status(job_id: str) -> dict:
    job = batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return job


@app.get("/api/v1/debug/chamber/source")
def debug_chamber_source(sample_limit: int = Query(default=5, ge=1, le=20)) -> dict:
    try:
        return inspect_deputies_source(sample_limit=sample_limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error debug Camara: {exc}")


@app.get("/api/v1/debug/chamber/deputy-period")
def debug_chamber_deputy_period(sample_limit: int = Query(default=3, ge=1, le=10)) -> dict:
    try:
        return inspect_deputy_period_structure(sample_limit=sample_limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error debug estructura diputado-periodo: {exc}")


@app.get("/api/v1/debug/chamber/attendance")
def debug_chamber_attendance(
    year: Optional[int] = Query(default=None, ge=2010, le=2100),
    session_limit: int = Query(default=10, ge=1, le=100),
    sample_limit: int = Query(default=10, ge=1, le=30),
) -> dict:
    target_year = year or datetime.now(timezone.utc).year
    try:
        return inspect_attendance_source(year=target_year, session_limit=session_limit, sample_limit=sample_limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error debug asistencia Camara: {exc}")


@app.post("/api/v1/ingest/senate/senators")
def ingest_senate_senators() -> dict:
    try:
        result = ingest_senators_from_senate()
        return {"ok": True, "source": "senado", "camara": "SENADOR", **result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error de ingesta Senado: {exc}")


@app.post("/api/v1/ingest/chamber/attendance")
def ingest_chamber_attendance(
    from_year: int = Query(default=2022, ge=2010, le=2100),
    to_year: Optional[int] = Query(default=None, ge=2010, le=2100),
    session_limit_per_year: int = Query(default=300, ge=1, le=1000),
) -> dict:
    target_to_year = to_year or datetime.now(timezone.utc).year
    try:
        result = ingest_attendance_sala(
            from_year=from_year,
            to_year=target_to_year,
            session_limit_per_year=session_limit_per_year,
        )
        return {
            "ok": True,
            "source": "camara",
            "from_year": from_year,
            "to_year": target_to_year,
            **result,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error de ingesta asistencia Camara: {exc}")


@app.get("/api/v1/attendance/deputies")
def attendance_deputies_summary() -> dict:
    try:
        return attendance_percentage_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error calculando asistencia: {exc}")


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
    unique_people: bool = Query(default=True),
    limit: int = Query(default=1000, ge=1, le=1000),
) -> dict:
    rows = list_parliamentarians(
        camara=camara,
        q=q,
        partido=partido,
        region=region,
        unique_people=unique_people,
        limit=limit,
    )
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
