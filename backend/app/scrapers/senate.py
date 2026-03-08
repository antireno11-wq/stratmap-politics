from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup


SENATE_URL = os.getenv(
    "SENATE_LIST_URL",
    "https://www.senado.cl/senadoras-y-senadores/listado-de-senadoras-y-senadores",
)

DEFAULT_URLS = [
    SENATE_URL,
    "https://www.senado.cl/senadoras-y-senadores/listado-de-senadoras-y-senadores",
    "https://www.senado.cl/senadoras-y-senadores",
]


def _slug_to_name(slug: str) -> str:
    clean = slug.strip().strip("/")
    clean = re.sub(r"[^a-zA-Z0-9-]", "", clean)
    parts = [p for p in clean.split("-") if p]
    return " ".join(w.capitalize() for w in parts)


def _name_to_id(name: str) -> str:
    base = name.lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    return base.strip("-")


def _download_html() -> str:
    last_error: Optional[Exception] = None
    for url in DEFAULT_URLS:
        try:
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No se pudo descargar el listado del Senado")


def fetch_senators() -> List[Dict[str, str]]:
    soup = BeautifulSoup(_download_html(), "html.parser")
    out: List[Dict[str, str]] = []

    # 1) Extraer por enlaces de perfil cuando existan.
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        text = (a.get_text(" ", strip=True) or "").strip()

        if "/senadores/" not in href and "/senadoras-y-senadores/" not in href:
            continue

        if "/senadores/" in href:
            slug = href.split("/senadores/", 1)[1].split("?", 1)[0].strip("/")
        else:
            slug = href.split("/senadoras-y-senadores/", 1)[1].split("?", 1)[0].strip("/")

        if not slug:
            continue

        external_id = slug.lower()
        nombre = text if len(text.split()) >= 2 else _slug_to_name(slug)

        # Limpiar enlaces genéricos que no son perfiles.
        if nombre.lower() in {"senadores", "senador", "comisiones", "noticias"}:
            continue

        out.append(
            {
                "external_id": external_id,
                "nombre": nombre,
                "partido": "Sin dato",
                "distrito_circunscripcion": "Sin dato",
                "region": "Sin dato",
                "periodo": f"{datetime.now().year}-ACTUAL",
                "asistencia_pct": None,
                "sesiones_totales": None,
                "sesiones_ausentes": None,
            }
        )

    # 2) Fallback: parseo por texto estructurado del listado.
    # Patrón esperado por bloque:
    #   Nombre
    #   Circunscripción X
    #   Región ...
    #   Partido ...
    strings = [s.strip() for s in soup.stripped_strings if s.strip()]
    for i, token in enumerate(strings):
        if not token.startswith("Circunscripción"):
            continue

        if i == 0:
            continue
        nombre = strings[i - 1].strip()
        if len(nombre.split()) < 2:
            continue

        region = "Sin dato"
        partido = "Sin dato"
        circ = token

        if i + 1 < len(strings) and strings[i + 1].startswith("Región"):
            region = strings[i + 1]
        if i + 2 < len(strings) and strings[i + 2].startswith("Partido"):
            partido = strings[i + 2].replace("Partido", "", 1).strip() or "Sin dato"
        elif i + 2 < len(strings) and strings[i + 2].startswith("Independiente"):
            partido = "Independiente"

        out.append(
            {
                "external_id": _name_to_id(nombre),
                "nombre": nombre,
                "partido": partido,
                "distrito_circunscripcion": circ,
                "region": region,
                "periodo": f"{datetime.now().year}-ACTUAL",
                "asistencia_pct": None,
                "sesiones_totales": None,
                "sesiones_ausentes": None,
            }
        )

    dedup = {}
    for item in out:
        dedup[item["external_id"]] = item

    return list(dedup.values())
