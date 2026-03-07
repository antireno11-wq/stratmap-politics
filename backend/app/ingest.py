from __future__ import annotations

from typing import Dict, Optional

from .db import purge_invalid_deputies, recalculate_scores, upsert_deputy_snapshots
from .scrapers.chamber import build_deputy_snapshots


def ingest_from_chamber(year: Optional[int] = None, session_limit: int = 80) -> Dict[str, int]:
    removed_invalid = purge_invalid_deputies()
    items = build_deputy_snapshots(year=year, session_limit=session_limit)
    processed = upsert_deputy_snapshots(items)
    updated = recalculate_scores()
    return {
        "removed_invalid": removed_invalid,
        "processed": processed,
        "scores_updated": updated,
    }
