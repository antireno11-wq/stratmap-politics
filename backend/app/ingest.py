from __future__ import annotations

from typing import Dict

from .db import replace_parliamentarians
from .scrapers.chamber import build_deputy_profiles
from .scrapers.senate import fetch_senators


def ingest_deputies_from_chamber() -> Dict[str, int]:
    items = build_deputy_profiles()
    processed = replace_parliamentarians(camara="DIPUTADO", items=items, source="camara.opendata")
    return {"processed": processed}


def ingest_senators_from_senate() -> Dict[str, int]:
    items = fetch_senators()
    processed = replace_parliamentarians(camara="SENADOR", items=items, source="senado.web")
    return {"processed": processed}


def ingest_all_parliamentarians() -> Dict[str, int]:
    d = ingest_deputies_from_chamber()
    s = ingest_senators_from_senate()
    return {
        "diputados_processed": d["processed"],
        "senadores_processed": s["processed"],
        "total_processed": d["processed"] + s["processed"],
    }
