from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class ParliamentarianIn(BaseModel):
    external_id: str
    nombre: str
    partido: Optional[str] = "Sin dato"
    distrito_circunscripcion: Optional[str] = "Sin dato"
    region: Optional[str] = "Sin dato"
    periodo: Optional[str] = "Sin dato"
    biografia: Optional[str] = None
    biografia_url: Optional[str] = None
    asistencia_pct: Optional[float] = None
    sesiones_totales: Optional[int] = None
    sesiones_ausentes: Optional[int] = None
    committee_memberships: Optional[List[Dict[str, Any]]] = None
    committee_sessions_attended: Optional[int] = None
    committee_total_sessions: Optional[int] = None
    committee_count: Optional[int] = None
    committee_activity_bills_discussed: Optional[int] = None
    committee_activity_bills_sponsored: Optional[int] = None
    committee_activity_interventions: Optional[int] = None
    committee_topic_counts: Optional[Dict[str, int]] = None


class IngestPayload(BaseModel):
    camara: Literal["DIPUTADO", "SENADOR"]
    items: List[ParliamentarianIn]
