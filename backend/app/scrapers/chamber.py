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


def _normalize_external_id(value: Optional[str]) -> Optional[str]:
    raw = (value or "").strip()
    digits = re.sub(r"[^0-9]", "", raw)
    if not digits:
        return None
    return str(int(digits))


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
        children = list(node)
        if len(children) == 0:
            continue
        if any(len(list(child)) > 0 for child in children):
            continue
        row = _flatten_record(node)
        if sum(1 for v in row.values() if v) >= 2:
            records.append(row)
    return records


def _first_present(row: Dict[str, str], candidates: List[str]) -> Optional[str]:
    for key in candidates:
        if key in row and row[key]:
            return row[key]
    return None


def _value_by_key_tokens(row: Dict[str, str], include_tokens: List[str], exclude_tokens: Optional[List[str]] = None) -> Optional[str]:
    exclude_tokens = exclude_tokens or []
    for key, value in row.items():
        if not value:
            continue
        k = key.lower()
        if all(tok in k for tok in include_tokens) and not any(tok in k for tok in exclude_tokens):
            return value
    return None


def _compose_full_name(row: Dict[str, str]) -> Optional[str]:
    direct = _first_present(
        row,
        [
            "nombreparlamentario",
            "dipnombrecompleto",
            "nombrecompleto",
            "dip_nom_completo",
            "parlamentario",
        ],
    )
    if direct and len(direct.split()) >= 2:
        return direct

    nombres = _first_present(row, ["nombres", "nombre", "dipnombre", "dip_nom"]) or ""
    ap_pat = _first_present(row, ["apellidopaterno", "appaterno", "apellido_paterno", "paterno"]) or ""
    ap_mat = _first_present(row, ["apellidomaterno", "apmaterno", "apellido_materno", "materno"]) or ""

    parts = [p.strip() for p in [nombres, ap_pat, ap_mat] if p and p.strip()]
    if len(parts) >= 2:
        return " ".join(parts)

    if nombres:
        return nombres
    return None


def _looks_like_party_label(nombre: str) -> bool:
    t = _normalize_text(nombre)
    patterns = [
        "partido",
        "federacion",
        "independiente",
        "frente",
        "comite",
        "democrata",
        "social",
        "republicano",
    ]
    return any(p in t for p in patterns)


def _request_xml(path: str, params: Optional[Dict[str, Any]] = None) -> bytes:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    response = requests.get(url, params=params, timeout=45)
    response.raise_for_status()
    return response.content


def _to_int(value: Optional[str], fallback: int = 0) -> int:
    try:
        return int(float((value or "").replace(",", ".")))
    except Exception:
        return fallback


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


def fetch_deputies_periodo_actual() -> List[Dict[str, str]]:
    xml = _request_xml("WSDiputado.asmx/retornarDiputadosPeriodoActual")
    records = _records_from_xml(xml)

    deputies: List[Dict[str, str]] = []
    for row in records:
        external_id = _normalize_external_id(
            _first_present(
                row,
                ["dipid", "dip_id", "iddiputado", "diputadoid", "idparlamentario", "id"],
            )
        )
        nombre = _compose_full_name(row)
        partido = (
            _first_present(row, ["partido", "militancia", "partidonombre", "pactopolitico", "siglapartido", "bancada"])
            or _value_by_key_tokens(row, ["partido"])
            or _value_by_key_tokens(row, ["bancada"])
        )
        distrito = (
            _first_present(row, ["distrito", "distritonombre", "nrodistrito", "regiondistrito", "distritoelectoral"])
            or _value_by_key_tokens(row, ["distrito"])
            or _value_by_key_tokens(row, ["circunscripcion"])
        )
        region = (
            _first_present(row, ["region", "regionnombre", "nomregion"])
            or _value_by_key_tokens(row, ["region"], exclude_tokens=["distrito"])
            or distrito
        )

        if not external_id or not nombre or _looks_like_party_label(nombre):
            continue

        deputies.append(
            {
                "external_id": external_id,
                "nombre": nombre,
                "partido": partido or "Sin dato",
                "distrito_circunscripcion": distrito or "Sin dato",
                "region": region or "Sin dato",
                "periodo": f"{datetime.now().year}-ACTUAL",
            }
        )

    dedup: Dict[str, Dict[str, str]] = {d["external_id"]: d for d in deputies}
    return list(dedup.values())


def fetch_attendance_by_deputy(
    year: int, session_limit: int = 80
) -> tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, int]]]:
    sessions_xml = _request_xml("WSSala.asmx/retornarSesionesXAnno", params={"prmAnno": year})
    session_records = _records_from_xml(sessions_xml)

    session_ids: List[int] = []
    for row in session_records:
        sid = _first_present(row, ["sesid", "ses_id", "idsesion", "sesionid", "id"])
        if sid:
            session_ids.append(_to_int(sid, -1))

    session_ids = [sid for sid in session_ids if sid > 0]
    session_ids = sorted(set(session_ids), reverse=True)[: max(1, session_limit)]

    stats_by_id: Dict[str, Dict[str, int]] = defaultdict(lambda: {"present": 0, "absent": 0, "total": 0})
    stats_by_name: Dict[str, Dict[str, int]] = defaultdict(lambda: {"present": 0, "absent": 0, "total": 0})

    for sid in session_ids:
        xml = _request_xml("WSSala.asmx/retornarSesionAsistencia", params={"prmSesionId": sid})
        attendance_records = _records_from_xml(xml)

        for row in attendance_records:
            external_id = _normalize_external_id(
                _first_present(
                    row,
                    ["dipid", "dip_id", "iddiputado", "diputadoid", "idparlamentario", "id"],
                )
            )
            nombre = _compose_full_name(row) or _first_present(
                row, ["nombre", "dipnombre", "nombreparlamentario", "parlamentario", "nombres"]
            )
            nombre_norm = _normalize_text(nombre)
            status = _first_present(row, ["asistencia", "tipoasistencia", "estado", "descripcion"]) or ""
            if not external_id and not nombre_norm:
                continue

            targets: List[Dict[str, Dict[str, int]]] = []
            target_keys: List[str] = []
            if external_id:
                targets.append(stats_by_id)
                target_keys.append(external_id)
            if nombre_norm:
                targets.append(stats_by_name)
                target_keys.append(nombre_norm)

            for t, k in zip(targets, target_keys):
                t[k]["total"] += 1
                if _attendance_status_is_absent(status):
                    t[k]["absent"] += 1
                else:
                    t[k]["present"] += 1

    return dict(stats_by_id), dict(stats_by_name)


def build_deputy_profiles() -> List[Dict[str, Any]]:
    year = datetime.now().year
    deputies = fetch_deputies_periodo_actual()
    attendance_by_id, attendance_by_name = fetch_attendance_by_deputy(year=year, session_limit=80)

    out: List[Dict[str, Any]] = []
    for deputy in deputies:
        deputy_name_norm = _normalize_text(deputy["nombre"])
        stats = attendance_by_id.get(
            deputy["external_id"],
            attendance_by_name.get(deputy_name_norm, {"present": 0, "absent": 0, "total": 0}),
        )
        total = stats["total"]
        absent = stats["absent"]
        pct = None if total == 0 else round((stats["present"] / total) * 100, 2)

        out.append(
            {
                **deputy,
                "asistencia_pct": pct,
                "sesiones_totales": total if total > 0 else None,
                "sesiones_ausentes": absent if total > 0 else None,
                "nombre_normalizado": _normalize_text(deputy["nombre"]),
            }
        )
    return out
