from __future__ import annotations

import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import requests


BASE_URL = os.getenv(
    "CHAMBER_API_BASE",
    "https://opendata.camara.cl/camaradiputados/WServices",
).rstrip("/")


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _normalize_text(value: Optional[str]) -> str:
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def _flatten_record(node: ET.Element) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for child in list(node):
        key = _local_name(child.tag).lower()
        out[key] = (child.text or "").strip()
    return out


def _records_from_xml(xml_bytes: bytes) -> List[Dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    records: List[Dict[str, str]] = []
    for node in root.iter():
        if len(list(node)) == 0:
            continue
        row = _flatten_record(node)
        if row:
            records.append(row)
    return records


def _first_present(row: Dict[str, str], candidates: List[str]) -> Optional[str]:
    for key in candidates:
        if key in row and row[key]:
            return row[key]
    return None


def _to_int(value: Optional[str], fallback: int = 0) -> int:
    try:
        return int(float((value or "").replace(",", ".")))
    except Exception:
        return fallback


def _request_xml(path: str, params: Optional[Dict[str, Any]] = None) -> bytes:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    response = requests.get(url, params=params, timeout=45)
    response.raise_for_status()
    return response.content


def fetch_deputies_periodo_actual() -> List[Dict[str, str]]:
    xml = _request_xml("WSDiputado.asmx/retornarDiputadosPeriodoActual")
    records = _records_from_xml(xml)
    deputies: List[Dict[str, str]] = []

    for row in records:
        external_id = _first_present(row, ["dipid", "dip_id", "iddiputado", "diputadoid", "id"])
        nombre = _first_present(row, ["nombre", "dipnombre", "nombreparlamentario", "dip_nom", "parlamentario"])
        partido = _first_present(row, ["partido", "militancia", "partidonombre", "pactopolitico"])
        distrito = _first_present(row, ["distrito", "distritonombre", "nrodistrito", "regiondistrito"])
        region = _first_present(row, ["region", "regionnombre"]) or distrito

        if not external_id or not nombre:
            continue

        deputies.append(
            {
                "external_id": external_id,
                "nombre": nombre,
                "partido": partido or "Sin dato",
                "distrito": distrito or "Sin dato",
                "region": region or "Sin dato",
            }
        )

    dedup: Dict[str, Dict[str, str]] = {d["external_id"]: d for d in deputies}
    return list(dedup.values())


def fetch_comisiones_vigentes() -> Dict[str, List[str]]:
    xml = _request_xml("WSComision.asmx/retornarComisionesVigentes")
    records = _records_from_xml(xml)

    by_deputy: Dict[str, List[str]] = defaultdict(list)
    for row in records:
        external_id = _first_present(row, ["dipid", "dip_id", "iddiputado", "diputadoid", "idparlamentario"])
        comision = _first_present(row, ["comision", "comisionnombre", "nombrecomision", "descripcion"])
        if external_id and comision and comision not in by_deputy[external_id]:
            by_deputy[external_id].append(comision)

    return by_deputy


def _attendance_status_is_absent(status: str) -> bool:
    t = _normalize_text(status)
    absent_patterns = [
        "ausente",
        "inasistencia",
        "permiso",
        "impedido",
        "no asiste",
        "sin justificacion",
    ]
    return any(p in t for p in absent_patterns)


def fetch_attendance_by_deputy(year: int, session_limit: int = 80) -> Dict[str, Dict[str, int]]:
    sessions_xml = _request_xml("WSSala.asmx/retornarSesionesXAnno", params={"prmAnno": year})
    session_records = _records_from_xml(sessions_xml)

    session_ids: List[int] = []
    for row in session_records:
        sid = _first_present(row, ["sesid", "ses_id", "idsesion", "sesionid", "id"])
        if sid:
            session_ids.append(_to_int(sid, -1))

    session_ids = [sid for sid in session_ids if sid > 0]
    session_ids = sorted(set(session_ids), reverse=True)[: max(1, session_limit)]

    stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"present": 0, "absent": 0, "total": 0})

    for sid in session_ids:
        xml = _request_xml("WSSala.asmx/retornarSesionAsistencia", params={"prmSesionId": sid})
        attendance_records = _records_from_xml(xml)

        for row in attendance_records:
            external_id = _first_present(row, ["dipid", "dip_id", "iddiputado", "diputadoid", "idparlamentario"])
            status = _first_present(row, ["asistencia", "tipoasistencia", "estado", "descripcion"]) or ""
            if not external_id:
                continue

            stats[external_id]["total"] += 1
            if _attendance_status_is_absent(status):
                stats[external_id]["absent"] += 1
            else:
                stats[external_id]["present"] += 1

    return stats


def build_deputy_snapshots(year: Optional[int] = None, session_limit: int = 80) -> List[Dict[str, Any]]:
    target_year = year or datetime.now().year
    periodo = f"{target_year}-ANUAL"

    deputies = fetch_deputies_periodo_actual()
    comisiones_map = fetch_comisiones_vigentes()
    attendance_map = fetch_attendance_by_deputy(target_year, session_limit=session_limit)

    items: List[Dict[str, Any]] = []
    for deputy in deputies:
        external_id = deputy["external_id"]
        attendance = attendance_map.get(external_id, {"present": 0, "absent": 0, "total": 0})
        total_sessions = attendance["total"]
        absent_sessions = attendance["absent"]
        attendance_pct = 0.0 if total_sessions == 0 else (attendance["present"] / total_sessions) * 100

        commissions = [
            {"name": name, "participation_pct": round(attendance_pct, 2)}
            for name in comisiones_map.get(external_id, [])
        ]

        items.append(
            {
                "external_id": external_id,
                "nombre": deputy["nombre"],
                "partido": deputy["partido"],
                "distrito": deputy["distrito"],
                "region": deputy.get("region") or deputy["distrito"],
                "periodo": periodo,
                "attendance_pct": round(attendance_pct, 2),
                "sesiones_ausentes": absent_sessions,
                "sesiones_totales": total_sessions,
                "votaciones_participadas": 0,
                "votaciones_ausentes": 0,
                "party_alignment_pct": 0,
                "bills_presented": 0,
                "bills_approved": 0,
                "bills_in_progress": 0,
                "lobby_compliance_pct": 0,
                "meetings_registered": 0,
                "official_trips": 0,
                "interventions": 0,
                "commissions": commissions,
            }
        )

    return items
