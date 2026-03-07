from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Dict, List

import requests
from bs4 import BeautifulSoup


SENATE_URL = os.getenv("SENATE_LIST_URL", "https://www.senado.cl/senadores")


def _slug_to_name(slug: str) -> str:
    clean = slug.strip().strip("/")
    clean = re.sub(r"[^a-zA-Z0-9-]", "", clean)
    parts = [p for p in clean.split("-") if p]
    return " ".join(w.capitalize() for w in parts)


def fetch_senators() -> List[Dict[str, str]]:
    response = requests.get(SENATE_URL, timeout=45)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    out: List[Dict[str, str]] = []

    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        text = (a.get_text(" ", strip=True) or "").strip()

        if "/senadores/" not in href:
            continue

        slug = href.split("/senadores/", 1)[1].split("?", 1)[0].strip("/")
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
            }
        )

    dedup = {}
    for item in out:
        dedup[item["external_id"]] = item

    return list(dedup.values())
