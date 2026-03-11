from __future__ import annotations

import os
import html
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from datetime import date
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup


BASE_URL = os.getenv(
    "CHAMBER_API_BASE",
    "https://opendata.camara.cl/camaradiputados/WServices",
).rstrip("/")
DEPUTY_PROFILE_URL = os.getenv(
    "CHAMBER_DEPUTY_PROFILE_URL",
    "https://www.camara.cl/diputados/detalle/asistencia_sala.aspx",
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


def _find_child(node: Optional[ET.Element], name: str) -> Optional[ET.Element]:
    if node is None:
        return None
    target = name.lower()
    for child in list(node):
        if _local_name(child.tag).lower() == target:
            return child
    return None


def _find_all(node: ET.Element, name: str) -> List[ET.Element]:
    target = name.lower()
    return [el for el in node.iter() if _local_name(el.tag).lower() == target]


def _text(node: Optional[ET.Element]) -> str:
    if node is None:
        return ""
    return (node.text or "").strip()


def _is_missing(value: Optional[str]) -> bool:
    v = (value or "").strip().lower()
    return v in {"", "sin dato", "none", "null"}


def _to_int(value: Optional[str], fallback: int = 0) -> int:
    try:
        return int(float((value or "").replace(",", ".")))
    except Exception:
        return fallback


def _to_date(value: Optional[str]) -> Optional[date]:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
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
    if not t:
        return "desconocido"
    if "pareo" in t:
        return "pareo"
    if "permiso" in t or "licencia" in t or "impedido" in t:
        return "permiso"
    if _attendance_status_is_absent(t):
        return "ausente"
    if any(x in t for x in ["presente", "asiste", "asistio", "asistencia completa"]):
        return "presente"
    return "desconocido"


def _looks_like_admin_attendance_label(name: str) -> bool:
    t = _normalize_text(name)
    blocked_tokens = [
        "art.",
        "codigo del trabajo",
        "comites parlamentarios",
        "permiso",
        "licencia",
        "impedimento",
        "desafuero",
        "salida del pais",
        "mision oficial",
        "actividad oficial",
        "actividad propia",
        "acuerdo de comites",
        "fallecimiento",
        "postnatal",
        "prenatal",
        "labor parlamentaria",
    ]
    return any(tok in t for tok in blocked_tokens)


def _attendance_rows_from_session_xml(xml_bytes: bytes) -> List[Dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    rows: List[Dict[str, str]] = []

    for asistencia_node in _find_all(root, "Asistencia"):
        tipo_asistencia = _text(_find_child(asistencia_node, "TipoAsistencia"))

        diputado_node = _find_child(asistencia_node, "Diputado")
        if diputado_node is None:
            continue

        external_id = _normalize_external_id(_text(_find_child(diputado_node, "Id")))
        nombre_1 = _text(_find_child(diputado_node, "Nombre"))
        nombre_2 = _text(_find_child(diputado_node, "Nombre2"))
        ape_pat = _text(_find_child(diputado_node, "ApellidoPaterno"))
        ape_mat = _text(_find_child(diputado_node, "ApellidoMaterno"))
        nombre = _clean_person_name(" ".join([p for p in [nombre_1, nombre_2, ape_pat, ape_mat] if p]))
        if not nombre:
            continue

        justificacion_node = _find_child(asistencia_node, "Justificacion")
        justificacion = _text(_find_child(justificacion_node, "Nombre"))
        status = " - ".join([p for p in [tipo_asistencia, justificacion] if p]).strip()

        rows.append(
            {
                "external_id": external_id or "",
                "nombre": nombre,
                "status": status,
            }
        )

    return rows


def _clean_person_name(name: str) -> str:
    raw = re.sub(r"\s+", " ", (name or "").strip())
    return raw.strip(" -")


def _manual_territory_overrides() -> Dict[str, Dict[str, str]]:
    # Casos puntuales donde Cámara publica ficha sin territorio en endpoints de asistencia/ficha.
    # Fuente verificada en biografías parlamentarias oficiales.
    return {
        "1115": {
            "distrito_circunscripcion": "Distrito 17",
            "region": "Región del Maule",
        },
        "1124": {
            "distrito_circunscripcion": "Distrito 7",
            "region": "Región de Valparaíso",
        },
    }


def _build_valid_deputy_name_set() -> set[str]:
    deputies = fetch_deputies_periodo_actual(enrich_profile_page=False)
    out: set[str] = set()
    for d in deputies:
        n = _clean_person_name(d.get("nombre", ""))
        if n:
            out.add(_normalize_text(n))
    return out


def fetch_deputies_periodo_actual(
    enrich_profile_page: bool = False,
    enrich_offset: int = 0,
    enrich_limit: int = 0,
) -> List[Dict[str, str]]:
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
    out = list(dedup.values())

    enrich_targets = out
    if enrich_profile_page and enrich_limit > 0:
        start = max(0, enrich_offset)
        end = start + max(1, enrich_limit)
        enrich_targets = out[start:end]

    for d in enrich_targets:
        needs_geo = _is_missing(d.get("distrito_circunscripcion")) or _is_missing(d.get("region"))
        needs_party = _is_missing(d.get("partido"))

        # retornarDiputado ya no trae territorio de forma consistente; usamos API solo para partido faltante.
        api_extra = fetch_deputy_detail(d["external_id"]) if needs_party else None

        if api_extra:
            if _is_missing(d.get("distrito_circunscripcion")) and not _is_missing(api_extra.get("distrito_circunscripcion")):
                d["distrito_circunscripcion"] = api_extra["distrito_circunscripcion"]
            if _is_missing(d.get("region")) and not _is_missing(api_extra.get("region")):
                d["region"] = api_extra["region"]
            if _is_missing(d.get("partido")) and not _is_missing(api_extra.get("partido")):
                d["partido"] = api_extra["partido"]

        needs_page_fallback = (
            enrich_profile_page
            or _is_missing(d.get("distrito_circunscripcion"))
            or _is_missing(d.get("region"))
            or _is_missing(d.get("partido"))
        )
        page_extra = fetch_deputy_detail_from_profile_page(d["external_id"]) if needs_page_fallback else None

        if page_extra:
            if _is_missing(d.get("distrito_circunscripcion")) and not _is_missing(page_extra.get("distrito_circunscripcion")):
                d["distrito_circunscripcion"] = page_extra["distrito_circunscripcion"]
            if _is_missing(d.get("region")) and not _is_missing(page_extra.get("region")):
                d["region"] = page_extra["region"]
            if _is_missing(d.get("partido")) and not _is_missing(page_extra.get("partido")):
                d["partido"] = page_extra["partido"]
            if page_extra.get("periodo"):
                d["periodo"] = str(page_extra["periodo"])
            if page_extra.get("asistencia_pct") is not None:
                d["asistencia_pct"] = page_extra["asistencia_pct"]
    manual_overrides = _manual_territory_overrides()
    for d in out:
        override = manual_overrides.get(d.get("external_id", ""))
        if not override:
            continue
        if _is_missing(d.get("distrito_circunscripcion")) and not _is_missing(override.get("distrito_circunscripcion")):
            d["distrito_circunscripcion"] = override["distrito_circunscripcion"]
        if _is_missing(d.get("region")) and not _is_missing(override.get("region")):
            d["region"] = override["region"]

    return out


def fetch_deputy_detail(external_id: str) -> Optional[Dict[str, str]]:
    root: Optional[ET.Element] = None
    for params in ({"prmDiputadoId": external_id}, {"prmDipId": external_id}):
        try:
            xml = _request_xml("WSDiputado.asmx/retornarDiputado", params=params)
            root = ET.fromstring(xml)
            break
        except Exception:
            continue
    if root is None:
        return None

    distrito = "Sin dato"
    partido = "Sin dato"
    region = "Sin dato"

    distrito_node = _find_first(root, "Distrito")
    distrito_num = _text(_find_first(distrito_node, "Numero")) if distrito_node is not None else ""
    if distrito_num:
        distrito = f"Distrito {distrito_num}"

    comunas = _find_all(distrito_node, "Comuna") if distrito_node is not None else []
    if comunas:
        region_cand = _text(_find_first(comunas[0], "Region"))
        if region_cand:
            region = region_cand

    for m in _find_all(root, "Militancia"):
        partido_nombre = _text(_find_first(m, "Nombre"))
        partido_alias = _text(_find_first(m, "Alias"))
        cand = partido_nombre or partido_alias
        if cand:
            partido = cand

    return {
        "distrito_circunscripcion": distrito,
        "region": region,
        "partido": partido,
    }


def fetch_deputy_detail_from_profile_page(external_id: str) -> Optional[Dict[str, str]]:
    try:
        response = requests.get(DEPUTY_PROFILE_URL, params={"prmId": external_id}, timeout=30)
        response.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    distrito = "Sin dato"
    region = "Sin dato"
    partido = "Sin dato"
    periodo = f"{datetime.now().year}-ACTUAL"
    asistencia_pct: Optional[float] = None

    district_match = re.search(r"Distrito\s*:?\s*(?:N[°º]\s*)?(\d{1,2})", text, re.IGNORECASE)
    if district_match:
        distrito = f"Distrito {district_match.group(1)}"

    region_match = re.search(
        r"Regi[oó]n\s*[:\-]?\s*([A-Za-zÁÉÍÓÚÑáéíóúüÜ'()\-\s]{4,80})",
        text,
        re.IGNORECASE,
    )
    if region_match:
        region_raw = re.sub(r"\s+", " ", region_match.group(1)).strip(" -")
        region_raw = re.split(r"(Comisi[oó]n|Partido|Per[ií]odo|Asistencia)", region_raw, maxsplit=1)[0].strip(" -")
        if region_raw:
            region = region_raw

    party_match = re.search(r"Partido\s*:\s*(.+?)(?:\s+Bancada\s*:|\s+Comit[eé]\s+Parlamentario\s*:)", text, re.IGNORECASE)
    if party_match:
        party_raw = re.sub(r"\s+", " ", party_match.group(1)).strip(" -")
        if party_raw:
            partido = party_raw

    periodo_match = re.search(r"Per[ií]odo\s*:\s*([0-9]{4}\s*[-–]\s*[0-9]{4})", text, re.IGNORECASE)
    if periodo_match:
        periodo = periodo_match.group(1).replace("–", "-").replace(" ", "")

    asistencia_match = re.search(
        r"Porcentaje de Asistencia\s*([0-9]+(?:[\.,][0-9]+)?)%",
        text,
        re.IGNORECASE,
    )
    if asistencia_match:
        try:
            asistencia_pct = float(asistencia_match.group(1).replace(",", "."))
        except ValueError:
            asistencia_pct = None

    return {
        "distrito_circunscripcion": distrito,
        "region": region,
        "partido": partido,
        "periodo": periodo,
        "asistencia_pct": asistencia_pct,
    }


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


def _flatten_leaf_texts(node: ET.Element, prefix: str = "") -> Dict[str, str]:
    out: Dict[str, str] = {}
    for child in list(node):
        key = _local_name(child.tag)
        path = f"{prefix}.{key}" if prefix else key
        if len(list(child)) == 0:
            val = (child.text or "").strip()
            if val:
                out[path] = val
        else:
            out.update(_flatten_leaf_texts(child, path))
    return out


def inspect_deputy_period_structure(sample_limit: int = 3) -> Dict[str, Any]:
    xml = _request_xml("WSDiputado.asmx/retornarDiputadosPeriodoActual")
    root = ET.fromstring(xml)
    period_nodes = _find_all(root, "DiputadoPeriodo")
    sample_nodes = period_nodes[: max(1, min(sample_limit, 10))]

    samples: List[Dict[str, Any]] = []
    for n in sample_nodes:
        flat = _flatten_leaf_texts(n)
        keys = sorted(flat.keys())
        samples.append(
            {
                "keys": keys,
                "values": flat,
            }
        )

    return {"total_period_nodes": len(period_nodes), "samples": samples}



def fetch_attendance_by_deputy(
    from_year: int, to_year: int, session_limit_per_year: int = 300
) -> tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, int]]]:
    all_sessions: List[int] = []
    for year in range(from_year, to_year + 1):
        sessions = fetch_sessions(year=year, limit=session_limit_per_year)
        all_sessions.extend([s["session_id"] for s in sessions])
    session_ids = sorted(set(all_sessions), reverse=True)

    valid_names = _build_valid_deputy_name_set()
    stats_by_id: Dict[str, Dict[str, int]] = defaultdict(lambda: {"present": 0, "absent": 0, "total": 0})
    stats_by_name: Dict[str, Dict[str, int]] = defaultdict(lambda: {"present": 0, "absent": 0, "total": 0})

    for sid in session_ids:
        xml = _request_xml("WSSala.asmx/retornarSesionAsistencia", params={"prmSesionId": sid})
        attendance_records = _attendance_rows_from_session_xml(xml)

        for row in attendance_records:
            external_id = _normalize_external_id(row.get("external_id"))
            nombre = _clean_person_name(row.get("nombre", ""))
            nombre_norm = _normalize_text(nombre)
            if not nombre_norm:
                continue
            if _looks_like_admin_attendance_label(nombre):
                continue
            if nombre_norm not in valid_names:
                continue

            status = row.get("status", "")
            estado = _normalize_attendance_state(status)
            if estado == "desconocido":
                continue

            if external_id:
                stats_by_id[external_id]["total"] += 1
                if estado == "presente":
                    stats_by_id[external_id]["present"] += 1
                else:
                    stats_by_id[external_id]["absent"] += 1

            stats_by_name[nombre_norm]["total"] += 1
            if estado == "presente":
                stats_by_name[nombre_norm]["present"] += 1
            else:
                stats_by_name[nombre_norm]["absent"] += 1

    return dict(stats_by_id), dict(stats_by_name)


def fetch_sessions(year: int, limit: int = 300) -> List[Dict[str, Any]]:
    sessions_xml = _request_xml("WSSala.asmx/retornarSesionesXAnno", params={"prmAnno": year})
    session_records = _records_from_xml(sessions_xml)

    sessions: List[Dict[str, Any]] = []
    for row in session_records:
        session_id = _to_int(
            _first_present(
                row,
                ["sesid", "ses_id", "idsesion", "id_sesion", "sesionid", "sessionid", "id"],
            ),
            -1,
        )
        if session_id <= 0:
            continue

        estado = _normalize_text(_first_present(row, ["estado"]))
        if estado and "celebrada" not in estado:
            continue

        fecha = _to_date(
            _first_present(
                row,
                ["fechainicio", "fecha_inicio", "fecha", "f_sesion", "fecha_sesion", "sesfecha"],
            )
        )
        sessions.append({"session_id": session_id, "fecha": fecha})

    # Fallback robusto: parsea hojas XML por nombre de tag y texto escapado
    if not sessions:
        try:
            root = ET.fromstring(sessions_xml)
            for el in root.iter():
                if len(list(el)) != 0:
                    continue
                key = _local_name(el.tag).lower()
                value = (el.text or "").strip()
                if not value:
                    continue
                if ("ses" in key and "id" in key) or key in {"idsesion", "id_sesion", "sesionid", "sessionid"}:
                    sid = _to_int(value, -1)
                    if sid > 0:
                        sessions.append({"session_id": sid, "fecha": None})
        except Exception:
            pass

    if not sessions:
        try:
            raw = html.unescape(sessions_xml.decode("utf-8", errors="ignore"))
            for m in re.finditer(r"<(?:sesid|ses_id|idsesion|id_sesion|sesionid|sessionid)>\s*(\d+)\s*</", raw, re.IGNORECASE):
                sid = _to_int(m.group(1), -1)
                if sid > 0:
                    sessions.append({"session_id": sid, "fecha": None})
        except Exception:
            pass

    dedup = {s["session_id"]: s for s in sessions if s.get("session_id", 0) > 0}
    ordered = sorted(dedup.values(), key=lambda x: x["session_id"], reverse=True)
    return ordered[: max(1, limit)]


def scrape_attendance_rows(from_year: int, to_year: int, session_limit_per_year: int = 300) -> List[Dict[str, Any]]:
    sessions: List[Dict[str, Any]] = []
    for year in range(from_year, to_year + 1):
        sessions.extend(fetch_sessions(year=year, limit=session_limit_per_year))
    sessions = sorted({s["session_id"]: s for s in sessions}.values(), key=lambda x: x["session_id"], reverse=True)
    valid_names = _build_valid_deputy_name_set()
    out: List[Dict[str, Any]] = []

    for session in sessions:
        sid = session["session_id"]
        fecha = session.get("fecha")
        xml = _request_xml("WSSala.asmx/retornarSesionAsistencia", params={"prmSesionId": sid})
        attendance_records = _attendance_rows_from_session_xml(xml)

        for row in attendance_records:
            nombre = _clean_person_name(row.get("nombre", ""))
            if not nombre:
                continue
            if _looks_like_admin_attendance_label(nombre):
                continue

            nombre_norm = _normalize_text(nombre)
            if nombre_norm not in valid_names:
                continue

            status = row.get("status", "")
            estado = _normalize_attendance_state(status)
            if estado == "desconocido":
                continue

            out.append(
                {
                    "session_id": sid,
                    "fecha": fecha,
                    "diputado_nombre": nombre,
                    "estado": estado,
                }
            )

    return out


def inspect_attendance_source(year: int, session_limit: int = 10, sample_limit: int = 10) -> Dict[str, Any]:
    sessions = fetch_sessions(year=year, limit=session_limit)
    if not sessions:
        return {"sessions_count": 0, "sample_keys": [], "sample_rows": []}

    sid = sessions[0]["session_id"]
    xml = _request_xml("WSSala.asmx/retornarSesionAsistencia", params={"prmSesionId": sid})
    records = _attendance_rows_from_session_xml(xml)
    sample_rows = records[: max(1, min(sample_limit, 30))]
    sample_keys = sorted({k for r in sample_rows for k in r.keys()})
    statuses = sorted({(r.get("status") or "").strip() for r in sample_rows if r})
    return {
        "sessions_count": len(sessions),
        "sample_session_id": sid,
        "sample_keys": sample_keys,
        "sample_status_values": [s for s in statuses if s],
        "sample_rows": sample_rows,
    }

def build_deputy_profiles(
    enrich_profile_page: bool = False,
    enrich_offset: int = 0,
    enrich_limit: int = 0,
    include_attendance: bool = True,
) -> List[Dict[str, Any]]:
    current_year = datetime.now().year
    from_year = int(os.getenv("CHAMBER_ATTENDANCE_FROM_YEAR", "2022"))
    deputies = fetch_deputies_periodo_actual(
        enrich_profile_page=enrich_profile_page,
        enrich_offset=enrich_offset,
        enrich_limit=enrich_limit,
    )
    attendance_by_id: Dict[str, Dict[str, int]] = {}
    attendance_by_name: Dict[str, Dict[str, int]] = {}
    if include_attendance:
        attendance_by_id, attendance_by_name = fetch_attendance_by_deputy(
            from_year=from_year,
            to_year=current_year,
            session_limit_per_year=300,
        )

    out: List[Dict[str, Any]] = []
    for deputy in deputies:
        deputy_name_norm = _normalize_text(deputy["nombre"])
        stats = attendance_by_id.get(
            deputy["external_id"],
            attendance_by_name.get(deputy_name_norm, {"present": 0, "absent": 0, "total": 0}),
        ) if include_attendance else {"present": 0, "absent": 0, "total": 0}
        total = stats["total"]
        absent = stats["absent"]
        pct_from_sessions = None if total == 0 else round((stats["present"] / total) * 100, 2)
        pct_from_profile = deputy.get("asistencia_pct")
        pct = pct_from_profile if pct_from_profile is not None else pct_from_sessions

        out.append(
            {
                **deputy,
                "asistencia_pct": pct if include_attendance else None,
                "sesiones_totales": total if (include_attendance and total > 0) else None,
                "sesiones_ausentes": absent if (include_attendance and total > 0) else None,
                "nombre_normalizado": _normalize_text(deputy["nombre"]),
            }
        )
    return out
