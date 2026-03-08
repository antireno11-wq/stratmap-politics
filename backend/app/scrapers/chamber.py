from __future__ import annotations

import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from datetime import date
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

    def _looks_like_person_row(row: Dict[str, str]) -> bool:
        keys = {k.lower() for k in row.keys()}
        has_id = any("id" in k for k in keys)
        has_name = any("nombre" in k or "parlament" in k for k in keys)
        return has_id and has_name

    for node in root.iter():
        children = list(node)
        if len(children) == 0:
            continue
        if any(len(list(child)) > 0 for child in children):
            continue
        row = _flatten_record(node)
        if sum(1 for v in row.values() if v) >= 2:
            records.append(row)

    # Fallback: algunos responses traen nodos con estructura irregular.
    if records:
        return records

    for node in root.iter():
        descendants = list(node.iter())
        if len(descendants) <= 1:
            continue
        row: Dict[str, str] = {}
        for leaf in descendants:
            if leaf is node:
                continue
            if len(list(leaf)) > 0:
                continue
            key = _local_name(leaf.tag).lower()
            value = (leaf.text or "").strip()
            if key and value and key not in row:
                row[key] = value
        if len(row) >= 2 and _looks_like_person_row(row):
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
    ap_pat = (
        _first_present(row, ["apellidopaterno", "appaterno", "apellido_paterno", "paterno"])
        or _value_by_key_tokens(row, ["apellido", "paterno"])
        or _value_by_key_tokens(row, ["apellidopaterno"])
        or ""
    )
    ap_mat = (
        _first_present(row, ["apellidomaterno", "apmaterno", "apellido_materno", "materno"])
        or _value_by_key_tokens(row, ["apellido", "materno"])
        or _value_by_key_tokens(row, ["apellidomaterno"])
        or ""
    )

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


def _find_first(node: ET.Element, name: str) -> Optional[ET.Element]:
    target = name.lower()
    for el in node.iter():
        if _local_name(el.tag).lower() == target:
            return el
    return None


def _find_all(node: ET.Element, name: str) -> List[ET.Element]:
    target = name.lower()
    return [el for el in node.iter() if _local_name(el.tag).lower() == target]


def _text(node: Optional[ET.Element]) -> str:
    if node is None:
        return ""
    return (node.text or "").strip()


def _to_int(value: Optional[str], fallback: int = 0) -> int:
    try:
        return int(float((value or "").replace(",", ".")))
    except Exception:
        return fallback


def _to_date(value: Optional[str]) -> Optional[date]:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


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


def _normalize_attendance_state(status: str) -> str:
    t = _normalize_text(status)
    if "pareo" in t:
        return "pareo"
    if "permiso" in t:
        return "permiso"
    if _attendance_status_is_absent(t):
        return "ausente"
    return "presente"


def fetch_deputies_periodo_actual() -> List[Dict[str, str]]:
    xml = _request_xml("WSDiputado.asmx/retornarDiputadosPeriodoActual")
    root = ET.fromstring(xml)
    deputies: List[Dict[str, str]] = []
    for periodo_node in _find_all(root, "DiputadoPeriodo"):
        diputado_node = _find_first(periodo_node, "Diputado")
        if diputado_node is None:
            continue

        external_id = _normalize_external_id(_text(_find_first(diputado_node, "Id")))
        nombre_1 = _text(_find_first(diputado_node, "Nombre"))
        nombre_2 = _text(_find_first(diputado_node, "Nombre2"))
        ape_pat = _text(_find_first(diputado_node, "ApellidoPaterno"))
        ape_mat = _text(_find_first(diputado_node, "ApellidoMaterno"))
        nombre = " ".join([p for p in [nombre_1, nombre_2, ape_pat, ape_mat] if p]).strip()
        if not nombre:
            nombre = " ".join([p for p in [nombre_1, ape_pat, ape_mat] if p]).strip()

        distrito_node = _find_first(periodo_node, "Distrito")
        distrito_num = _text(_find_first(distrito_node, "Numero")) if distrito_node is not None else ""
        distrito = f"Distrito {distrito_num}" if distrito_num else "Sin dato"

        # Partido: toma la última militancia conocida dentro del diputado.
        partido = "Sin dato"
        militancias = _find_all(diputado_node, "Militancia")
        for m in militancias:
            partido_nombre = _text(_find_first(m, "Nombre"))
            partido_alias = _text(_find_first(m, "Alias"))
            candidato = partido_nombre or partido_alias
            if candidato:
                partido = candidato

        region = "Sin dato"
        comunas = _find_all(distrito_node, "Comuna") if distrito_node is not None else []
        if comunas:
            region_cand = _text(_find_first(comunas[0], "Region"))
            if region_cand:
                region = region_cand

        if not external_id or not nombre or _looks_like_party_label(nombre):
            continue
        deputies.append(
            {
                "external_id": external_id,
                "nombre": nombre,
                "partido": partido,
                "distrito_circunscripcion": distrito,
                "region": region,
                "periodo": f"{datetime.now().year}-ACTUAL",
            }
        )

    dedup: Dict[str, Dict[str, str]] = {d["external_id"]: d for d in deputies}
    return list(dedup.values())


def inspect_deputies_source(sample_limit: int = 5) -> Dict[str, Any]:
    xml = _request_xml("WSDiputado.asmx/retornarDiputadosPeriodoActual")
    records = _records_from_xml(xml)
    sample_rows = records[: max(1, min(sample_limit, 20))]
    sample_keys: List[str] = sorted({k for row in sample_rows for k in row.keys()})
    return {
        "records_count": len(records),
        "sample_keys": sample_keys,
        "sample_rows": sample_rows,
    }


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


def fetch_sessions(year: int, limit: int = 80) -> List[Dict[str, Any]]:
    sessions_xml = _request_xml("WSSala.asmx/retornarSesionesXAnno", params={"prmAnno": year})
    session_records = _records_from_xml(sessions_xml)

    sessions: List[Dict[str, Any]] = []
    for row in session_records:
        session_id = _to_int(_first_present(row, ["sesid", "ses_id", "idsesion", "sesionid", "id"]), -1)
        if session_id <= 0:
            continue
        fecha = _to_date(_first_present(row, ["fecha", "f_sesion", "fecha_sesion", "sesfecha"]))
        sessions.append({"session_id": session_id, "fecha": fecha})

    dedup = {s["session_id"]: s for s in sessions}
    ordered = sorted(dedup.values(), key=lambda x: x["session_id"], reverse=True)
    return ordered[: max(1, limit)]


def scrape_attendance_rows(year: int, session_limit: int = 80) -> List[Dict[str, Any]]:
    sessions = fetch_sessions(year=year, limit=session_limit)
    out: List[Dict[str, Any]] = []

    for session in sessions:
        sid = session["session_id"]
        fecha = session.get("fecha")
        xml = _request_xml("WSSala.asmx/retornarSesionAsistencia", params={"prmSesionId": sid})
        attendance_records = _records_from_xml(xml)

        for row in attendance_records:
            nombre = _compose_full_name(row) or _first_present(
                row, ["nombre", "dipnombre", "nombreparlamentario", "parlamentario", "nombres"]
            )
            if not nombre:
                continue
            status = _first_present(row, ["asistencia", "tipoasistencia", "estado", "descripcion"]) or ""
            out.append(
                {
                    "session_id": sid,
                    "fecha": fecha,
                    "diputado_nombre": nombre.strip(),
                    "estado": _normalize_attendance_state(status),
                }
            )

    return out


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
