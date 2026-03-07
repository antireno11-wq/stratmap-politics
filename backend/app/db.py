from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg.rows import dict_row

from .scoring import calc_scores


def _db_url() -> str:
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL no esta configurada")
    return db_url


def get_conn() -> psycopg.Connection:
    return psycopg.connect(_db_url(), row_factory=dict_row)


def init_db() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS diputados (
        id SERIAL PRIMARY KEY,
        external_id TEXT NOT NULL UNIQUE,
        nombre TEXT NOT NULL,
        partido TEXT NOT NULL,
        distrito TEXT NOT NULL,
        region TEXT,
        periodo TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS sesiones (
        id SERIAL PRIMARY KEY,
        diputado_id INTEGER NOT NULL REFERENCES diputados(id) ON DELETE CASCADE,
        periodo TEXT NOT NULL,
        asistencia_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
        sesiones_ausentes INTEGER NOT NULL DEFAULT 0,
        sesiones_totales INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(diputado_id, periodo)
    );

    CREATE TABLE IF NOT EXISTS votaciones (
        id SERIAL PRIMARY KEY,
        diputado_id INTEGER NOT NULL REFERENCES diputados(id) ON DELETE CASCADE,
        periodo TEXT NOT NULL,
        votaciones_participadas INTEGER NOT NULL DEFAULT 0,
        votaciones_ausentes INTEGER NOT NULL DEFAULT 0,
        alineacion_partido_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(diputado_id, periodo)
    );

    CREATE TABLE IF NOT EXISTS proyectos_ley (
        id SERIAL PRIMARY KEY,
        diputado_id INTEGER NOT NULL REFERENCES diputados(id) ON DELETE CASCADE,
        periodo TEXT NOT NULL,
        presentados INTEGER NOT NULL DEFAULT 0,
        aprobados INTEGER NOT NULL DEFAULT 0,
        en_tramite INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(diputado_id, periodo)
    );

    CREATE TABLE IF NOT EXISTS lobby (
        id SERIAL PRIMARY KEY,
        diputado_id INTEGER NOT NULL REFERENCES diputados(id) ON DELETE CASCADE,
        periodo TEXT NOT NULL,
        cumplimiento_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
        reuniones_registradas INTEGER NOT NULL DEFAULT 0,
        viajes_oficiales INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(diputado_id, periodo)
    );

    CREATE TABLE IF NOT EXISTS comisiones (
        id SERIAL PRIMARY KEY,
        diputado_id INTEGER NOT NULL REFERENCES diputados(id) ON DELETE CASCADE,
        periodo TEXT NOT NULL,
        comision TEXT NOT NULL,
        participacion_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(diputado_id, periodo, comision)
    );

    CREATE TABLE IF NOT EXISTS scores (
        id SERIAL PRIMARY KEY,
        diputado_id INTEGER NOT NULL UNIQUE REFERENCES diputados(id) ON DELETE CASCADE,
        attendance_score NUMERIC(5,2) NOT NULL,
        voting_score NUMERIC(5,2) NOT NULL,
        legislative_score NUMERIC(5,2) NOT NULL,
        transparency_score NUMERIC(5,2) NOT NULL,
        commissions_score NUMERIC(5,2) NOT NULL,
        total_score NUMERIC(5,2) NOT NULL,
        formula_version TEXT NOT NULL DEFAULT 'v1',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_diputados_partido ON diputados(partido);
    CREATE INDEX IF NOT EXISTS idx_diputados_region ON diputados(region);
    CREATE INDEX IF NOT EXISTS idx_scores_total ON scores(total_score DESC);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def db_health() -> Tuple[bool, str]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok;")
                _ = cur.fetchone()
        return True, "ok"
    except Exception as exc:
        return False, f"db error: {type(exc).__name__}: {exc}"


def _upsert_diputado(item: Dict[str, Any]) -> int:
    sql = """
    INSERT INTO diputados (external_id, nombre, partido, distrito, region, periodo, updated_at)
    VALUES (%(external_id)s, %(nombre)s, %(partido)s, %(distrito)s, %(region)s, %(periodo)s, NOW())
    ON CONFLICT (external_id) DO UPDATE SET
        nombre = EXCLUDED.nombre,
        partido = EXCLUDED.partido,
        distrito = EXCLUDED.distrito,
        region = EXCLUDED.region,
        periodo = EXCLUDED.periodo,
        updated_at = NOW()
    RETURNING id;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, item)
            row = cur.fetchone()
        conn.commit()
    return int(row["id"])


def _upsert_metric_table(table: str, diputado_id: int, periodo: str, payload: Dict[str, Any], fields: List[str]) -> None:
    columns = ["diputado_id", "periodo"] + fields + ["updated_at"]
    placeholders = ["%(diputado_id)s", "%(periodo)s"] + [f"%({f})s" for f in fields] + ["NOW()"]
    updates = ", ".join([f"{f} = EXCLUDED.{f}" for f in fields] + ["updated_at = NOW()"])
    sql = f"""
    INSERT INTO {table} ({', '.join(columns)})
    VALUES ({', '.join(placeholders)})
    ON CONFLICT (diputado_id, periodo) DO UPDATE SET
    {updates};
    """
    params = {"diputado_id": diputado_id, "periodo": periodo, **payload}
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def _upsert_comisiones(diputado_id: int, periodo: str, commissions: List[Dict[str, Any]]) -> None:
    if not commissions:
        return
    sql = """
    INSERT INTO comisiones (diputado_id, periodo, comision, participacion_pct, updated_at)
    VALUES (%(diputado_id)s, %(periodo)s, %(comision)s, %(participacion_pct)s, NOW())
    ON CONFLICT (diputado_id, periodo, comision) DO UPDATE SET
        participacion_pct = EXCLUDED.participacion_pct,
        updated_at = NOW();
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            for commission in commissions:
                cur.execute(
                    sql,
                    {
                        "diputado_id": diputado_id,
                        "periodo": periodo,
                        "comision": commission["name"],
                        "participacion_pct": commission["participation_pct"],
                    },
                )
        conn.commit()


def upsert_deputy_snapshots(items: List[Dict[str, Any]]) -> int:
    total = 0
    for item in items:
        diputado_id = _upsert_diputado(item)
        periodo = item["periodo"]

        _upsert_metric_table(
            "sesiones",
            diputado_id,
            periodo,
            {
                "asistencia_pct": item["attendance_pct"],
                "sesiones_ausentes": item["sesiones_ausentes"],
                "sesiones_totales": item["sesiones_totales"],
            },
            ["asistencia_pct", "sesiones_ausentes", "sesiones_totales"],
        )
        _upsert_metric_table(
            "votaciones",
            diputado_id,
            periodo,
            {
                "votaciones_participadas": item["votaciones_participadas"],
                "votaciones_ausentes": item["votaciones_ausentes"],
                "alineacion_partido_pct": item["party_alignment_pct"],
            },
            ["votaciones_participadas", "votaciones_ausentes", "alineacion_partido_pct"],
        )
        _upsert_metric_table(
            "proyectos_ley",
            diputado_id,
            periodo,
            {
                "presentados": item["bills_presented"],
                "aprobados": item["bills_approved"],
                "en_tramite": item["bills_in_progress"],
            },
            ["presentados", "aprobados", "en_tramite"],
        )
        _upsert_metric_table(
            "lobby",
            diputado_id,
            periodo,
            {
                "cumplimiento_pct": item["lobby_compliance_pct"],
                "reuniones_registradas": item["meetings_registered"],
                "viajes_oficiales": item["official_trips"],
            },
            ["cumplimiento_pct", "reuniones_registradas", "viajes_oficiales"],
        )
        _upsert_comisiones(diputado_id, periodo, item.get("commissions", []))
        total += 1
    return total


def purge_invalid_deputies() -> int:
    sql = "DELETE FROM diputados WHERE external_id !~ '^[0-9]+$' RETURNING id;"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        conn.commit()
    return len(rows)


def _latest_metrics(diputado_id: int) -> Dict[str, float]:
    sql = """
    SELECT
      COALESCE((SELECT asistencia_pct::float FROM sesiones WHERE diputado_id = %(id)s ORDER BY updated_at DESC LIMIT 1), 0) AS attendance_pct,
      COALESCE((SELECT votaciones_participadas::float FROM votaciones WHERE diputado_id = %(id)s ORDER BY updated_at DESC LIMIT 1), 0) AS votes_in,
      COALESCE((SELECT votaciones_ausentes::float FROM votaciones WHERE diputado_id = %(id)s ORDER BY updated_at DESC LIMIT 1), 0) AS votes_out,
      COALESCE((SELECT alineacion_partido_pct::float FROM votaciones WHERE diputado_id = %(id)s ORDER BY updated_at DESC LIMIT 1), 0) AS party_alignment_pct,
      COALESCE((SELECT presentados::float FROM proyectos_ley WHERE diputado_id = %(id)s ORDER BY updated_at DESC LIMIT 1), 0) AS bills_presented,
      COALESCE((SELECT aprobados::float FROM proyectos_ley WHERE diputado_id = %(id)s ORDER BY updated_at DESC LIMIT 1), 0) AS bills_approved,
      COALESCE((SELECT en_tramite::float FROM proyectos_ley WHERE diputado_id = %(id)s ORDER BY updated_at DESC LIMIT 1), 0) AS bills_in_progress,
      COALESCE((SELECT cumplimiento_pct::float FROM lobby WHERE diputado_id = %(id)s ORDER BY updated_at DESC LIMIT 1), 0) AS lobby_compliance_pct,
      COALESCE((SELECT reuniones_registradas::float FROM lobby WHERE diputado_id = %(id)s ORDER BY updated_at DESC LIMIT 1), 0) AS meetings_registered,
      COALESCE((SELECT viajes_oficiales::float FROM lobby WHERE diputado_id = %(id)s ORDER BY updated_at DESC LIMIT 1), 0) AS official_trips,
      COALESCE((SELECT AVG(participacion_pct)::float FROM comisiones WHERE diputado_id = %(id)s), 0) AS commission_participation_pct;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"id": diputado_id})
            row = cur.fetchone() or {}

    voting_total = row.get("votes_in", 0) + row.get("votes_out", 0)
    voting_participation_pct = 0 if voting_total == 0 else (row.get("votes_in", 0) / voting_total) * 100

    return {
        "attendance_pct": row.get("attendance_pct", 0),
        "voting_participation_pct": voting_participation_pct,
        "party_alignment_pct": row.get("party_alignment_pct", 0),
        "bills_presented": row.get("bills_presented", 0),
        "bills_approved": row.get("bills_approved", 0),
        "bills_in_progress": row.get("bills_in_progress", 0),
        "lobby_compliance_pct": row.get("lobby_compliance_pct", 0),
        "meetings_registered": row.get("meetings_registered", 0),
        "official_trips": row.get("official_trips", 0),
        "commission_participation_pct": row.get("commission_participation_pct", 0),
    }


def recalculate_scores() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM diputados ORDER BY id ASC")
            deputy_rows = cur.fetchall()

    updated = 0
    for row in deputy_rows:
        diputado_id = row["id"]
        metrics = _latest_metrics(diputado_id)
        scores = calc_scores(metrics)
        sql = """
        INSERT INTO scores (
            diputado_id, attendance_score, voting_score, legislative_score,
            transparency_score, commissions_score, total_score, formula_version, updated_at
        )
        VALUES (
            %(diputado_id)s, %(attendance_score)s, %(voting_score)s, %(legislative_score)s,
            %(transparency_score)s, %(commissions_score)s, %(total_score)s, 'v1', NOW()
        )
        ON CONFLICT (diputado_id) DO UPDATE SET
            attendance_score = EXCLUDED.attendance_score,
            voting_score = EXCLUDED.voting_score,
            legislative_score = EXCLUDED.legislative_score,
            transparency_score = EXCLUDED.transparency_score,
            commissions_score = EXCLUDED.commissions_score,
            total_score = EXCLUDED.total_score,
            formula_version = EXCLUDED.formula_version,
            updated_at = NOW();
        """
        params = {"diputado_id": diputado_id, **scores}
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        updated += 1
    return updated


def list_ranking(
    q: Optional[str] = None,
    partido: Optional[str] = None,
    region: Optional[str] = None,
    comision: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    where = []
    params: Dict[str, Any] = {"limit": max(1, min(limit, 500))}

    if q:
        where.append("d.nombre ILIKE %(q)s")
        params["q"] = f"%{q}%"
    if partido:
        where.append("d.partido ILIKE %(partido)s")
        params["partido"] = f"%{partido}%"
    if region:
        where.append("COALESCE(d.region, d.distrito) ILIKE %(region)s")
        params["region"] = f"%{region}%"
    if comision:
        where.append(
            "EXISTS (SELECT 1 FROM comisiones c WHERE c.diputado_id = d.id AND c.comision ILIKE %(comision)s)"
        )
        params["comision"] = f"%{comision}%"

    where_sql = "" if not where else "WHERE " + " AND ".join(where)
    sql = f"""
    SELECT
      d.id,
      d.external_id,
      d.nombre,
      d.partido,
      d.distrito,
      d.region,
      COALESCE(sc.total_score::float, 0) AS score,
      COALESCE(se.asistencia_pct::float, 0) AS asistencia_pct,
      COALESCE(pl.presentados, 0) AS proyectos_presentados
    FROM diputados d
    LEFT JOIN scores sc ON sc.diputado_id = d.id
    LEFT JOIN LATERAL (
      SELECT asistencia_pct FROM sesiones s WHERE s.diputado_id = d.id ORDER BY updated_at DESC LIMIT 1
    ) se ON TRUE
    LEFT JOIN LATERAL (
      SELECT presentados FROM proyectos_ley p WHERE p.diputado_id = d.id ORDER BY updated_at DESC LIMIT 1
    ) pl ON TRUE
    {where_sql}
    ORDER BY score DESC, asistencia_pct DESC, d.nombre ASC
    LIMIT %(limit)s;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_deputy_profile(deputy_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM diputados WHERE id = %(id)s", {"id": deputy_id})
            deputy = cur.fetchone()
            if not deputy:
                return None

            cur.execute("SELECT * FROM scores WHERE diputado_id = %(id)s", {"id": deputy_id})
            score = cur.fetchone()

            cur.execute(
                "SELECT periodo, asistencia_pct::float AS asistencia_pct, sesiones_ausentes, sesiones_totales FROM sesiones WHERE diputado_id=%(id)s ORDER BY periodo DESC",
                {"id": deputy_id},
            )
            sesiones = cur.fetchall()

            cur.execute(
                "SELECT periodo, votaciones_participadas, votaciones_ausentes, alineacion_partido_pct::float AS alineacion_partido_pct FROM votaciones WHERE diputado_id=%(id)s ORDER BY periodo DESC",
                {"id": deputy_id},
            )
            votaciones = cur.fetchall()

            cur.execute(
                "SELECT periodo, presentados, aprobados, en_tramite FROM proyectos_ley WHERE diputado_id=%(id)s ORDER BY periodo DESC",
                {"id": deputy_id},
            )
            proyectos = cur.fetchall()

            cur.execute(
                "SELECT periodo, cumplimiento_pct::float AS cumplimiento_pct, reuniones_registradas, viajes_oficiales FROM lobby WHERE diputado_id=%(id)s ORDER BY periodo DESC",
                {"id": deputy_id},
            )
            lobby_rows = cur.fetchall()

            cur.execute(
                "SELECT periodo, comision, participacion_pct::float AS participacion_pct FROM comisiones WHERE diputado_id=%(id)s ORDER BY periodo DESC, comision ASC",
                {"id": deputy_id},
            )
            comisiones = cur.fetchall()

    return {
        "diputado": dict(deputy),
        "score": dict(score) if score else None,
        "sesiones": [dict(r) for r in sesiones],
        "votaciones": [dict(r) for r in votaciones],
        "proyectos_ley": [dict(r) for r in proyectos],
        "lobby": [dict(r) for r in lobby_rows],
        "comisiones": [dict(r) for r in comisiones],
    }
