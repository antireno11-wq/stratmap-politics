from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel


class ParliamentarianIn(BaseModel):
    external_id: str
    nombre: str
    partido: Optional[str] = "Sin dato"
    distrito_circunscripcion: Optional[str] = "Sin dato"
    region: Optional[str] = "Sin dato"
    periodo: Optional[str] = "Sin dato"
    asistencia_pct: Optional[float] = None
    sesiones_totales: Optional[int] = None
    sesiones_ausentes: Optional[int] = None


class IngestPayload(BaseModel):
    camara: Literal["DIPUTADO", "SENADOR"]
    items: List[ParliamentarianIn]
