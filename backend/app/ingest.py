from __future__ import annotations

from typing import Dict

from .db import calculate_attendance_pct_by_deputy, quality_summary, replace_asistencia_sala, replace_parliamentarians
from .scrapers.chamber import build_deputy_profiles, scrape_attendance_rows
from .scrapers.senate import fetch_senators


def ingest_deputies_from_chamber() -> Dict[str, int]:
    items = build_deputy_profiles()
    summary = quality_summary(items)
    # Gate de calidad para no sobreescribir con datos vacíos.
    if summary["total"] > 0:
        party_ratio = summary["with_party"] / summary["total"]
        territory_ratio = summary["with_territory"] / summary["total"]
        if party_ratio < 0.15 and territory_ratio < 0.15:
            return {
                "processed": 0,
                "blocked_low_quality": 1,
                "total": summary["total"],
                "with_party": summary["with_party"],
                "with_territory": summary["with_territory"],
            }
    processed = replace_parliamentarians(camara="DIPUTADO", items=items, source="camara.opendata")
    return {"processed": processed, **summary}


def ingest_senators_from_senate() -> Dict[str, int]:
    items = fetch_senators()
    processed = replace_parliamentarians(camara="SENADOR", items=items, source="senado.web")
    return {"processed": processed, **quality_summary(items)}


def ingest_all_parliamentarians() -> Dict[str, int]:
    d = ingest_deputies_from_chamber()
    s = ingest_senators_from_senate()
    return {
        "diputados_processed": d["processed"],
        "senadores_processed": s["processed"],
        "total_processed": d["processed"] + s["processed"],
    }


def ingest_attendance_sala(year: int, session_limit: int = 80) -> Dict[str, int]:
    rows = scrape_attendance_rows(year=year, session_limit=session_limit)
    stored = replace_asistencia_sala(rows, source="camara.opendata")
    return {"sessions_processed": len({r["session_id"] for r in rows}), "rows_processed": stored}


def attendance_percentage_summary() -> Dict[str, object]:
    items = calculate_attendance_pct_by_deputy()
    return {"items": items, "count": len(items)}
