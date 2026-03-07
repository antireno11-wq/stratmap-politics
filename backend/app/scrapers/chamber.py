from __future__ import annotations

import os
import re
import unicodedata
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
        nombre = _first_present(
            row,
            ["nombre", "dipnombre", "nombreparlamentario", "dip_nom", "parlamentario", "nombres"],
        )
        partido = _first_present(
            row,
            ["partido", "militancia", "partidonombre", "pactopolitico", "siglapartido", "bancada"],
        )
        distrito = _first_present(
            row,
            ["distrito", "distritonombre", "nrodistrito", "regiondistrito", "distritoelectoral"],
        )
        region = _first_present(row, ["region", "regionnombre", "nomregion"]) or distrito

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


def build_deputy_profiles() -> List[Dict[str, Any]]:
    return fetch_deputies_periodo_actual()
