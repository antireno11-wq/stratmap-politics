from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg.rows import dict_row


def _db_url() -> str:
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL no esta configurada")
    return db_url


def get_conn() -> psycopg.Connection:
    return psycopg.connect(_db_url(), row_factory=dict_row)


def init_db() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS parlamentarios (
        id SERIAL PRIMARY KEY,
        camara TEXT NOT NULL,
        external_id TEXT NOT NULL,
        nombre TEXT NOT NULL,
        partido TEXT NOT NULL DEFAULT 'Sin dato',
        distrito_circunscripcion TEXT NOT NULL DEFAULT 'Sin dato',
        region TEXT NOT NULL DEFAULT 'Sin dato',
        periodo TEXT NOT NULL DEFAULT 'Sin dato',
        source TEXT NOT NULL DEFAULT 'manual',
        asistencia_pct NUMERIC(5,2) NULL,
        sesiones_totales INTEGER NULL,
        sesiones_ausentes INTEGER NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(camara, external_id)
    );

    CREATE INDEX IF NOT EXISTS idx_parlamentarios_camara ON parlamentarios(camara);
    CREATE INDEX IF NOT EXISTS idx_parlamentarios_nombre ON parlamentarios(nombre);
    CREATE INDEX IF NOT EXISTS idx_parlamentarios_partido ON parlamentarios(partido);
    CREATE INDEX IF NOT EXISTS idx_parlamentarios_region ON parlamentarios(region);

    CREATE TABLE IF NOT EXISTS asistencia_sala (
        id SERIAL PRIMARY KEY,
        session_id INTEGER NOT NULL,
        fecha DATE NULL,
        diputado_nombre TEXT NOT NULL,
        estado TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'camara.opendata',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(session_id, diputado_nombre)
    );
    CREATE INDEX IF NOT EXISTS idx_asistencia_sala_session_id ON asistencia_sala(session_id);
    CREATE INDEX IF NOT EXISTS idx_asistencia_sala_diputado ON asistencia_sala(diputado_nombre);
    CREATE INDEX IF NOT EXISTS idx_asistencia_sala_estado ON asistencia_sala(estado);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("ALTER TABLE parlamentarios ADD COLUMN IF NOT EXISTS asistencia_pct NUMERIC(5,2) NULL;")
            cur.execute("ALTER TABLE parlamentarios ADD COLUMN IF NOT EXISTS sesiones_totales INTEGER NULL;")
            cur.execute("ALTER TABLE parlamentarios ADD COLUMN IF NOT EXISTS sesiones_ausentes INTEGER NULL;")
            # Backfill no destructivo desde la tabla antigua si existe.
            cur.execute(
                """
                DO $$
                BEGIN
                  IF to_regclass('public.diputados') IS NOT NULL THEN
                    INSERT INTO parlamentarios (
                      camara, external_id, nombre, partido, distrito_circunscripcion, region, periodo, source, updated_at
                    )
                    SELECT 'DIPUTADO', d.external_id, d.nombre,
                           COALESCE(NULLIF(d.partido, ''), 'Sin dato'),
                           COALESCE(NULLIF(d.distrito, ''), 'Sin dato'),
                           COALESCE(NULLIF(d.region, ''), 'Sin dato'),
                           COALESCE(NULLIF(d.periodo, ''), 'Sin dato'),
                           'legacy_diputados', NOW()
                    FROM diputados d
                    ON CONFLICT (camara, external_id) DO NOTHING;
                  END IF;
                END $$;
                """
            )
        conn.commit()


def db_health() -> Tuple[bool, str]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 as ok;")
                _ = cur.fetchone()
        return True, "ok"
    except Exception as exc:
        return False, f"db error: {type(exc).__name__}: {exc}"


def replace_parliamentarians(camara: str, items: List[Dict[str, Any]], source: str) -> int:
    clean_camara = camara.upper().strip()
    if clean_camara not in {"DIPUTADO", "SENADOR"}:
        raise ValueError("camara debe ser DIPUTADO o SENADOR")

    insert_sql = """
    INSERT INTO parlamentarios (
      camara, external_id, nombre, partido, distrito_circunscripcion,
      region, periodo, source, asistencia_pct, sesiones_totales, sesiones_ausentes, updated_at
    ) VALUES (
      %(camara)s, %(external_id)s, %(nombre)s, %(partido)s, %(distrito_circunscripcion)s,
      %(region)s, %(periodo)s, %(source)s, %(asistencia_pct)s, %(sesiones_totales)s, %(sesiones_ausentes)s, NOW()
    )
    ON CONFLICT (camara, external_id) DO UPDATE SET
      nombre = EXCLUDED.nombre,
      partido = EXCLUDED.partido,
      distrito_circunscripcion = EXCLUDED.distrito_circunscripcion,
      region = EXCLUDED.region,
      periodo = EXCLUDED.periodo,
      source = EXCLUDED.source,
      asistencia_pct = COALESCE(EXCLUDED.asistencia_pct, parlamentarios.asistencia_pct),
      sesiones_totales = COALESCE(EXCLUDED.sesiones_totales, parlamentarios.sesiones_totales),
      sesiones_ausentes = COALESCE(EXCLUDED.sesiones_ausentes, parlamentarios.sesiones_ausentes),
      updated_at = NOW();
    """

    if not items:
        # Protección: nunca vaciar una cámara por un scrape vacío/fallido.
        return 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM parlamentarios WHERE camara = %(camara)s", {"camara": clean_camara})
            for item in items:
                params = {
                    "camara": clean_camara,
                    "external_id": str(item.get("external_id", "")).strip(),
                    "nombre": str(item.get("nombre", "")).strip(),
                    "partido": str(item.get("partido") or "Sin dato").strip() or "Sin dato",
                    "distrito_circunscripcion": str(
                        item.get("distrito_circunscripcion")
                        or item.get("distrito")
                        or item.get("circunscripcion")
                        or "Sin dato"
                    ).strip()
                    or "Sin dato",
                    "region": str(item.get("region") or "Sin dato").strip() or "Sin dato",
                    "periodo": str(item.get("periodo") or "Sin dato").strip() or "Sin dato",
                    "source": source,
                    "asistencia_pct": item.get("asistencia_pct"),
                    "sesiones_totales": item.get("sesiones_totales"),
                    "sesiones_ausentes": item.get("sesiones_ausentes"),
                }
                if not params["external_id"] or not params["nombre"]:
                    continue
                cur.execute(insert_sql, params)
        conn.commit()

    return len(items)


def quality_summary(items: List[Dict[str, Any]]) -> Dict[str, int]:
    total = len(items)
    with_party = 0
    with_territory = 0
    with_region = 0
    with_attendance = 0

    for it in items:
        if (it.get("partido") or "Sin dato").strip().lower() != "sin dato":
            with_party += 1
        territory = (it.get("distrito_circunscripcion") or it.get("distrito") or "").strip()
        if territory and territory.lower() != "sin dato":
            with_territory += 1
        region = (it.get("region") or "").strip()
        if region and region.lower() != "sin dato":
            with_region += 1
        if it.get("asistencia_pct") is not None:
            with_attendance += 1

    return {
        "total": total,
        "with_party": with_party,
        "with_territory": with_territory,
        "with_region": with_region,
        "with_attendance": with_attendance,
    }


def upsert_parliamentarians(camara: str, items: List[Dict[str, Any]], source: str = "manual") -> int:
    clean_camara = camara.upper().strip()
    if clean_camara not in {"DIPUTADO", "SENADOR"}:
        raise ValueError("camara debe ser DIPUTADO o SENADOR")

    sql = """
    INSERT INTO parlamentarios (
      camara, external_id, nombre, partido, distrito_circunscripcion,
      region, periodo, source, asistencia_pct, sesiones_totales, sesiones_ausentes, updated_at
    ) VALUES (
      %(camara)s, %(external_id)s, %(nombre)s, %(partido)s, %(distrito_circunscripcion)s,
      %(region)s, %(periodo)s, %(source)s, %(asistencia_pct)s, %(sesiones_totales)s, %(sesiones_ausentes)s, NOW()
    )
    ON CONFLICT (camara, external_id) DO UPDATE SET
      nombre = EXCLUDED.nombre,
      partido = EXCLUDED.partido,
      distrito_circunscripcion = EXCLUDED.distrito_circunscripcion,
      region = EXCLUDED.region,
      periodo = EXCLUDED.periodo,
      source = EXCLUDED.source,
      asistencia_pct = COALESCE(EXCLUDED.asistencia_pct, parlamentarios.asistencia_pct),
      sesiones_totales = COALESCE(EXCLUDED.sesiones_totales, parlamentarios.sesiones_totales),
      sesiones_ausentes = COALESCE(EXCLUDED.sesiones_ausentes, parlamentarios.sesiones_ausentes),
      updated_at = NOW();
    """

    processed = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            for item in items:
                params = {
                    "camara": clean_camara,
                    "external_id": str(item.get("external_id", "")).strip(),
                    "nombre": str(item.get("nombre", "")).strip(),
                    "partido": str(item.get("partido") or "Sin dato").strip() or "Sin dato",
                    "distrito_circunscripcion": str(
                        item.get("distrito_circunscripcion")
                        or item.get("distrito")
                        or item.get("circunscripcion")
                        or "Sin dato"
                    ).strip()
                    or "Sin dato",
                    "region": str(item.get("region") or "Sin dato").strip() or "Sin dato",
                    "periodo": str(item.get("periodo") or "Sin dato").strip() or "Sin dato",
                    "source": source,
                    "asistencia_pct": item.get("asistencia_pct"),
                    "sesiones_totales": item.get("sesiones_totales"),
                    "sesiones_ausentes": item.get("sesiones_ausentes"),
                }
                if not params["external_id"] or not params["nombre"]:
                    continue
                cur.execute(sql, params)
                processed += 1
        conn.commit()
    return processed


def list_parliamentarians(
    camara: Optional[str] = None,
    q: Optional[str] = None,
    partido: Optional[str] = None,
    region: Optional[str] = None,
    unique_people: bool = True,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"limit": max(1, min(int(limit), 1000))}
    where: List[str] = []

    if camara:
        where.append("p.camara = %(camara)s")
        params["camara"] = camara.upper().strip()
    if q:
        where.append("p.nombre ILIKE %(q)s")
        params["q"] = f"%{q}%"
    if partido:
        where.append("p.partido ILIKE %(partido)s")
        params["partido"] = f"%{partido}%"
    if region:
        where.append("(p.region ILIKE %(region)s OR p.distrito_circunscripcion ILIKE %(region)s)")
        params["region"] = f"%{region}%"

    where_sql = "" if not where else "WHERE " + " AND ".join(where)
    sql_limit = params["limit"]
    if unique_people and not camara:
        sql_limit = min(1000, max(params["limit"] * 3, params["limit"] + 50))
    params["sql_limit"] = sql_limit

    sql = f"""
    SELECT
      p.id,
      p.camara,
      p.external_id,
      p.nombre,
      p.partido,
      p.distrito_circunscripcion,
      p.region,
      p.periodo,
      p.asistencia_pct::float AS asistencia_pct,
      p.sesiones_totales,
      p.sesiones_ausentes,
      p.source,
      p.updated_at
    FROM parlamentarios p
    {where_sql}
    ORDER BY p.camara ASC, p.nombre ASC
    LIMIT %(sql_limit)s;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    out = [dict(r) for r in rows]

    if unique_people and not camara:
        out = _dedup_by_current_role(out)

    return out[: params["limit"]]


def _normalize_person_name(name: str) -> str:
    text = unicodedata.normalize("NFD", str(name or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def _current_role_rank(row: Dict[str, Any]) -> Tuple[float, int, int, int, int, float]:
    party = str(row.get("partido") or "").strip().lower()
    region = str(row.get("region") or "").strip().lower()
    district = str(row.get("distrito_circunscripcion") or "").strip().lower()
    has_party = 1 if party and party != "sin dato" else 0
    has_region = 1 if region and region != "sin dato" else 0
    has_district = 1 if district and district != "sin dato" else 0
    coverage = has_party + has_region + has_district

    pct_raw = row.get("asistencia_pct")
    total_raw = row.get("sesiones_totales")
    absent_raw = row.get("sesiones_ausentes")

    pct = float(pct_raw) if pct_raw is not None else -1.0
    total = int(total_raw) if total_raw is not None else -1
    absent = int(absent_raw) if absent_raw is not None else -1

    has_attendance = 1 if pct_raw is not None and total_raw is not None else 0
    has_positive_attendance = 1 if pct > 0 else 0
    suspicious_zero = 1 if total > 0 and absent >= total and pct <= 0 else 0

    updated = row.get("updated_at")
    if hasattr(updated, "timestamp"):
        updated_ts = float(updated.timestamp())
    elif isinstance(updated, str):
        try:
            updated_ts = float(datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp())
        except Exception:
            updated_ts = 0.0
    else:
        updated_ts = 0.0

    # Prioriza el registro más reciente para reflejar el cargo vigente.
    # Si hay empate temporal, usa cobertura y consistencia de asistencia.
    return (
        updated_ts,
        coverage,
        has_attendance,
        -suspicious_zero,
        has_positive_attendance,
        pct,
    )


def _dedup_by_current_role(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_name: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = _normalize_person_name(str(row.get("nombre") or ""))
        if not key:
            key = f"id-{row.get('id')}"
        by_name.setdefault(key, []).append(row)

    selected: List[Dict[str, Any]] = []
    for candidates in by_name.values():
        if len(candidates) == 1:
            selected.append(candidates[0])
            continue
        selected.append(max(candidates, key=_current_role_rank))

    selected.sort(key=lambda r: (str(r.get("camara") or ""), str(r.get("nombre") or "")))
    return selected


def get_parliamentarian(parliamentarian_id: int) -> Optional[Dict[str, Any]]:
    sql = """
    SELECT
      id, camara, external_id, nombre, partido, distrito_circunscripcion,
      region, periodo, asistencia_pct::float AS asistencia_pct,
      sesiones_totales, sesiones_ausentes, source, created_at, updated_at
    FROM parlamentarios
    WHERE id = %(id)s
    LIMIT 1;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"id": parliamentarian_id})
            row = cur.fetchone()
    return dict(row) if row else None


def count_by_camara() -> Dict[str, int]:
    sql = """
    SELECT camara, COUNT(*)::int AS total
    FROM parlamentarios
    GROUP BY camara;
    """
    out = {"DIPUTADO": 0, "SENADOR": 0}
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            for row in cur.fetchall():
                out[row["camara"]] = row["total"]
    return out


def replace_asistencia_sala(rows: List[Dict[str, Any]], source: str = "camara.opendata") -> int:
    if not rows:
        return 0

    session_ids = sorted({int(r["session_id"]) for r in rows if r.get("session_id") is not None})
    sql_delete = "DELETE FROM asistencia_sala WHERE session_id = ANY(%(session_ids)s);"
    sql_insert = """
    INSERT INTO asistencia_sala (session_id, fecha, diputado_nombre, estado, source)
    VALUES (%(session_id)s, %(fecha)s, %(diputado_nombre)s, %(estado)s, %(source)s)
    ON CONFLICT (session_id, diputado_nombre) DO UPDATE SET
      fecha = EXCLUDED.fecha,
      estado = EXCLUDED.estado,
      source = EXCLUDED.source;
    """

    inserted = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_delete, {"session_ids": session_ids})
            for row in rows:
                params = {
                    "session_id": int(row["session_id"]),
                    "fecha": row.get("fecha"),
                    "diputado_nombre": str(row.get("diputado_nombre", "")).strip(),
                    "estado": str(row.get("estado", "")).strip().lower(),
                    "source": source,
                }
                if not params["diputado_nombre"] or not params["estado"]:
                    continue
                cur.execute(sql_insert, params)
                inserted += 1
        conn.commit()
    return inserted


def calculate_attendance_pct_by_deputy() -> List[Dict[str, Any]]:
    sql = """
    SELECT
      diputado_nombre,
      COUNT(*)::int AS sesiones_totales,
      COUNT(*) FILTER (WHERE estado IN ('ausente', 'permiso', 'pareo'))::int AS sesiones_ausentes,
      ROUND(
        100.0 * (COUNT(*) FILTER (WHERE estado = 'presente'))::numeric / NULLIF(COUNT(*), 0),
        2
      )::float AS asistencia_pct
    FROM asistencia_sala
    GROUP BY diputado_nombre
    ORDER BY asistencia_pct DESC NULLS LAST, sesiones_totales DESC, diputado_nombre ASC;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    return [dict(r) for r in rows]
