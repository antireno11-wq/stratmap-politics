from __future__ import annotations

from typing import Dict

from .db import (
    calculate_attendance_pct_by_deputy,
    quality_summary,
    replace_asistencia_sala,
    replace_parliamentarians,
    upsert_parliamentarians,
)
from .scrapers.chamber import build_deputy_profiles, scrape_attendance_rows
from .scrapers.senate import fetch_senators


def ingest_deputies_from_chamber(
    enrich_profile_page: bool = False,
    enrich_offset: int = 0,
    enrich_limit: int = 0,
    include_attendance: bool = True,
) -> Dict[str, int]:
    items = build_deputy_profiles(
        enrich_profile_page=enrich_profile_page,
        enrich_offset=enrich_offset,
        enrich_limit=enrich_limit,
        include_attendance=include_attendance,
    )

    # En enriquecimiento por lotes, solo persistimos el tramo pedido.
    # Si se upsert-ean los 157 en cada batch, los lotes siguientes vuelven a
    # sobrescribir con "Sin dato" a los enriquecidos previamente.
    is_batch_enrich = enrich_profile_page and enrich_limit > 0
    if is_batch_enrich:
        start = max(0, enrich_offset)
        end = start + max(1, enrich_limit)
        items = items[start:end]

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
    # Si estamos enriqueciendo por lotes, no borrar la tabla completa.
    if is_batch_enrich or not include_attendance:
        processed = upsert_parliamentarians(camara="DIPUTADO", items=items, source="camara.opendata")
    else:
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


def ingest_attendance_sala(from_year: int, to_year: int, session_limit_per_year: int = 300) -> Dict[str, int]:
    rows = scrape_attendance_rows(from_year=from_year, to_year=to_year, session_limit_per_year=session_limit_per_year)
    stored = replace_asistencia_sala(rows, source="camara.opendata")
    return {"sessions_processed": len({r["session_id"] for r in rows}), "rows_processed": stored}


def attendance_percentage_summary() -> Dict[str, object]:
    items = calculate_attendance_pct_by_deputy()
    return {"items": items, "count": len(items)}
