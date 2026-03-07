from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CommissionIn(BaseModel):
    name: str
    participation_pct: float = Field(default=0, ge=0, le=100)


class DeputySnapshotIn(BaseModel):
    external_id: str
    nombre: str
    partido: str
    distrito: str
    region: Optional[str] = None
    periodo: str
    attendance_pct: float = Field(default=0, ge=0, le=100)
    sesiones_ausentes: int = Field(default=0, ge=0)
    sesiones_totales: int = Field(default=0, ge=0)
    votaciones_participadas: int = Field(default=0, ge=0)
    votaciones_ausentes: int = Field(default=0, ge=0)
    party_alignment_pct: float = Field(default=0, ge=0, le=100)
    bills_presented: int = Field(default=0, ge=0)
    bills_approved: int = Field(default=0, ge=0)
    bills_in_progress: int = Field(default=0, ge=0)
    lobby_compliance_pct: float = Field(default=0, ge=0, le=100)
    meetings_registered: int = Field(default=0, ge=0)
    official_trips: int = Field(default=0, ge=0)
    interventions: int = Field(default=0, ge=0)
    commissions: List[CommissionIn] = []


class IngestPayload(BaseModel):
    items: List[DeputySnapshotIn]
