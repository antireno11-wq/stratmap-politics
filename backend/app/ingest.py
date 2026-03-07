from __future__ import annotations

from typing import Dict, Optional

from .db import recalculate_scores, upsert_deputy_snapshots
from .scrapers.chamber import build_deputy_snapshots


def ingest_from_chamber(year: Optional[int] = None, session_limit: int = 80) -> Dict[str, int]:
    items = build_deputy_snapshots(year=year, session_limit=session_limit)
    processed = upsert_deputy_snapshots(items)
    updated = recalculate_scores()
    return {
        "processed": processed,
        "scores_updated": updated,
    }
