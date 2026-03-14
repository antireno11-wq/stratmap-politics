from __future__ import annotations

import json
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


SENATE_URL = os.getenv(
    "SENATE_LIST_URL",
    "https://www.senado.cl/senadoras-y-senadores/listado-de-senadoras-y-senadores",
)
SENATE_ATTENDANCE_URL = os.getenv(
    "SENATE_ATTENDANCE_URL",
    "https://www.senado.cl/actividad-legislativa/sala/asistencia",
)
SENATE_BACKEND_BASE = os.getenv("SENATE_BACKEND_BASE", "https://web-back.senado.cl").rstrip("/")
HEMICYCLE_ENDPOINT = os.getenv("SENATE_HEMICYCLE_ENDPOINT", "/api/hemicycle")
ATTENDANCE_ENDPOINT = os.getenv("SENATE_ATTENDANCE_ENDPOINT", "/api/sessions/attendance")
SESSIONS_ENDPOINT = os.getenv("SENATE_SESSIONS_ENDPOINT", "/api/sessions")
VOTES_ENDPOINT = os.getenv("SENATE_VOTES_ENDPOINT", "/api/votes")
PARLIAMENTARIAN_COMMISSIONS_ENDPOINT = os.getenv("SENATE_PARLIAMENTARIAN_COMMISSIONS_ENDPOINT", "/api/parliamentarians/commissions")
PARLIAMENTARIAN_COMMITTEE_ATTENDANCE_ENDPOINT = os.getenv(
    "SENATE_PARLIAMENTARIAN_COMMITTEE_ATTENDANCE_ENDPOINT",
    "/api/parliamentarians/attendance_committees",
)
PARLIAMENTARIANS_JSONAPI_ENDPOINT = os.getenv("SENATE_PARLIAMENTARIANS_JSONAPI_ENDPOINT", "/jsonapi/node/parlamentarios")
COMMISSION_SESSIONS_ENDPOINT = os.getenv("SENATE_COMMISSION_SESSIONS_ENDPOINT", "/api/commission_sessions")
COMMISSION_SUBJECTS_ENDPOINT = os.getenv("SENATE_COMMISSION_SUBJECTS_ENDPOINT", "/api/commission_subjects")
COMMISSION_ACTIVITIES_ENDPOINT = os.getenv("SENATE_COMMISSION_ACTIVITIES_ENDPOINT", "/api/commission_activities")
REQUEST_TIMEOUT = int(os.getenv("SENATE_REQUEST_TIMEOUT", "45"))
COMMITTEE_MAX_WORKERS = max(1, int(os.getenv("SENATE_COMMITTEE_MAX_WORKERS", "8")))
BIOGRAPHY_BULK_LIMIT = max(50, int(os.getenv("SENATE_BIOGRAPHY_BULK_LIMIT", "200")))
ENABLE_COMMITTEE_ATTENDANCE = os.getenv("SENATE_ENABLE_COMMITTEE_ATTENDANCE", "0").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_COMMITTEE_TOTAL_SESSIONS = os.getenv("SENATE_ENABLE_COMMITTEE_TOTAL_SESSIONS", "0").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_COMMITTEE_ACTIVITY = os.getenv("SENATE_ENABLE_COMMITTEE_ACTIVITY", "0").strip().lower() in {"1", "true", "yes", "on"}

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


def _normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFD", str(name or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def _name_richness(name: Any) -> Tuple[int, int]:
    text = str(name or "").strip()
    if not text:
        return (0, 0)
    tokens = [token for token in text.split() if token]
    return (len(tokens), len(text))


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _backend_url(endpoint: str) -> str:
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    return f"{SENATE_BACKEND_BASE}{endpoint}"


def _backend_get_json(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    response = requests.get(_backend_url(endpoint), params=params or {}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _senator_profile_url(slug: str) -> Optional[str]:
    clean_slug = str(slug or "").strip().strip("/")
    if not clean_slug:
        return None
    return f"https://www.senado.cl/senadoras-y-senadores/listado-de-senadoras-y-senadores/{clean_slug}"


def _clean_html_text(html_content: Any) -> Optional[str]:
    raw = str(html_content or "").strip()
    if not raw:
        return None
    soup = BeautifulSoup(raw, "html.parser")
    text = " ".join(soup.stripped_strings)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text or None


def _payload_total(payload: Dict[str, Any]) -> int:
    data = payload.get("data")
    if isinstance(data, dict):
        return _to_int(data.get("total"), 0)
    return 0


def _payload_data_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, dict):
        rows = data.get("data")
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def _committee_topic_from_name(name: str) -> str:
    text = _normalize_name(name)
    if any(k in text for k in ["hacienda", "econom", "presupuesto", "finanza", "tribut", "mineria", "energia"]):
        return "economia_hacienda"
    if any(k in text for k in ["salud", "educ", "vivienda", "mujer", "trabajo", "ninez", "niñez", "cultura"]):
        return "social_educacion_salud"
    if any(k in text for k in ["justicia", "constitucion", "constitución", "seguridad", "defensa", "inteligencia"]):
        return "justicia_seguridad"
    if any(k in text for k in ["medio ambiente", "territorio", "zonas extremas", "acuicultura", "marit", "hidric"]):
        return "medioambiente_territorio"
    if any(k in text for k in ["relaciones exteriores", "interparlament", "integracion latinoamericana", "integración latinoamericana"]):
        return "relaciones_exteriores"
    return "otros"


def _normalize_role(role: str) -> str:
    text = _normalize_name(role)
    if "vice" in text:
        return "Vice President"
    if "president" in text or "presidente" in text:
        return "President"
    if "reemplazante" in text or "suplente" in text:
        return "Substitute member"
    return "Full member"


def _download_html(urls: Optional[List[str]] = None) -> str:
    target_urls = urls or DEFAULT_URLS
    last_error: Optional[Exception] = None
    for url in target_urls:
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No se pudo descargar el listado del Senado")


def _extract_period(periodos: Any) -> str:
    if not isinstance(periodos, list) or not periodos:
        return f"{datetime.now().year}-ACTUAL"

    vigente = None
    for p in periodos:
        if isinstance(p, dict) and int(p.get("VIGENTE") or 0) == 1:
            vigente = p
            break
    chosen = vigente or periodos[0]
    if not isinstance(chosen, dict):
        return f"{datetime.now().year}-ACTUAL"

    desde = str(chosen.get("DESDE") or "").strip()
    hasta = str(chosen.get("HASTA") or "").strip()
    if desde and hasta:
        return f"{desde}-{hasta}"
    if desde:
        return f"{desde}-ACTUAL"
    return f"{datetime.now().year}-ACTUAL"


def _empty_committee_fields() -> Dict[str, Any]:
    return {
        "votes_cast_total": None,
        "votes_expected_total": None,
        "voting_participation_pct": None,
        "votes_yes_total": None,
        "votes_no_total": None,
        "votes_abstention_total": None,
        "committee_memberships": [],
        "committee_sessions_attended": None,
        "committee_total_sessions": None,
        "committee_count": None,
        "committee_activity_bills_discussed": None,
        "committee_activity_bills_sponsored": None,
        "committee_activity_interventions": None,
        "committee_topic_counts": None,
    }


def _parse_senate_date(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _parse_senate_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _senator_full_name_from_vote_row(row: Dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            str(row.get("NOMBRE") or "").strip(),
            str(row.get("APELLIDO_PATERNO") or "").strip(),
            str(row.get("APELLIDO_MATERNO") or "").strip(),
        ]
        if part
    ).strip()


def _fetch_sessions_for_year(year: int) -> List[Dict[str, Any]]:
    limit = 200
    offset = 0
    out: List[Dict[str, Any]] = []

    while True:
        payload = _backend_get_json(SESSIONS_ENDPOINT, {"limit": limit, "offset": offset})
        rows = _payload_data_rows(payload)
        if not rows:
            break

        stop = False
        for row in rows:
            session_dt = _parse_senate_date(row.get("FECHA"))
            if session_dt is None:
                continue
            if session_dt.year > year:
                continue
            if session_dt.year < year:
                stop = True
                continue
            out.append(row)

        if stop or len(rows) < limit:
            break
        offset += limit

    return out


def _fetch_votes_for_legislature(legislature_id: int) -> List[Dict[str, Any]]:
    limit = 200
    offset = 0
    out: List[Dict[str, Any]] = []

    while True:
        payload = _backend_get_json(
            VOTES_ENDPOINT,
            {"id_legislatura": legislature_id, "limit": limit, "offset": offset},
        )
        rows = _payload_data_rows(payload)
        if not rows:
            break
        out.extend(rows)
        if len(rows) < limit:
            break
        offset += limit

    return out


def fetch_voting_stats_by_senator(year: int) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, int]], Dict[str, Dict[str, int]]]:
    sessions = _fetch_sessions_for_year(year)
    if not sessions:
        return {}, {}, {}

    session_legislature_by_id: Dict[int, int] = {}
    legislature_ids: List[int] = []
    for row in sessions:
        session_id = _to_int(row.get("ID_SESION"), 0)
        legislature_id = _to_int(row.get("ID_LEGISLATURA"), 0)
        if session_id <= 0 or legislature_id <= 0:
            continue
        session_legislature_by_id[session_id] = legislature_id
        if legislature_id not in legislature_ids:
            legislature_ids.append(legislature_id)

    if not legislature_ids:
        return {}, {}, {}

    stats_by_id: Dict[str, Dict[str, Any]] = {}
    stats_by_slug: Dict[str, Dict[str, Any]] = {}
    stats_by_name: Dict[str, Dict[str, Any]] = {}
    total_votes_by_legislature: Dict[int, int] = {}

    def _bucket(target: Dict[str, Dict[str, Any]], key: str) -> Dict[str, Any]:
        if key not in target:
            target[key] = {
                "votes_cast": 0,
                "votes_yes": 0,
                "votes_no": 0,
                "votes_abstention": 0,
                "_legislatures": set(),
            }
        return target[key]

    for legislature_id in legislature_ids:
        votes = _fetch_votes_for_legislature(legislature_id)
        filtered_votes: List[Dict[str, Any]] = []
        for vote in votes:
            session_id = _to_int(vote.get("ID_SESION"), 0)
            vote_dt = _parse_senate_datetime(vote.get("FECHA_VOTACION"))
            if session_id <= 0 or session_legislature_by_id.get(session_id) != legislature_id:
                continue
            if vote_dt is not None and vote_dt.year != year:
                continue
            filtered_votes.append(vote)

        total_votes_by_legislature[legislature_id] = len(filtered_votes)

        for vote in filtered_votes:
            categories = vote.get("VOTACIONES")
            if not isinstance(categories, dict):
                continue
            for category_name, normalized in (
                ("SI", "yes"),
                ("NO", "no"),
                ("ABSTENCION", "abstention"),
                ("PAREO", "other"),
            ):
                entries = categories.get(category_name)
                if not isinstance(entries, list):
                    continue
                for person in entries:
                    if not isinstance(person, dict):
                        continue
                    senate_id = str(person.get("PARLID") or "").strip()
                    slug = str(person.get("SLUG") or "").strip().lower()
                    nombre = _senator_full_name_from_vote_row(person)
                    nombre_norm = _normalize_name(nombre)

                    for container, key in (
                        (stats_by_id, senate_id),
                        (stats_by_slug, slug),
                        (stats_by_name, nombre_norm),
                    ):
                        if not key:
                            continue
                        bucket = _bucket(container, key)
                        bucket["votes_cast"] += 1
                        if normalized == "yes":
                            bucket["votes_yes"] += 1
                        elif normalized == "no":
                            bucket["votes_no"] += 1
                        elif normalized == "abstention":
                            bucket["votes_abstention"] += 1
                        bucket["_legislatures"].add(legislature_id)

    def _finalize(raw: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for key, stats in raw.items():
            legislatures = stats.get("_legislatures") or set()
            votes_expected = sum(
                total_votes_by_legislature.get(int(legislature_id), 0)
                for legislature_id in legislatures
            )
            out[key] = {
                "votes_cast": int(stats.get("votes_cast", 0)),
                "votes_expected": int(votes_expected),
                "votes_yes": int(stats.get("votes_yes", 0)),
                "votes_no": int(stats.get("votes_no", 0)),
                "votes_abstention": int(stats.get("votes_abstention", 0)),
            }
        return out

    return _finalize(stats_by_id), _finalize(stats_by_slug), _finalize(stats_by_name)


def _committee_totals_for_id(
    committee_id: int,
    cache_sessions_total: Dict[int, int],
    cache_subjects_total: Dict[int, int],
    cache_activities_total: Dict[int, int],
) -> Tuple[int, int, int]:
    if not ENABLE_COMMITTEE_TOTAL_SESSIONS and not ENABLE_COMMITTEE_ACTIVITY:
        return (0, 0, 0)
    if committee_id not in cache_sessions_total:
        if ENABLE_COMMITTEE_TOTAL_SESSIONS:
            try:
                payload = _backend_get_json(COMMISSION_SESSIONS_ENDPOINT, {"id_comision": committee_id, "limit": 1})
                cache_sessions_total[committee_id] = _payload_total(payload)
            except Exception:
                cache_sessions_total[committee_id] = 0
        else:
            cache_sessions_total[committee_id] = 0
    if committee_id not in cache_subjects_total:
        if ENABLE_COMMITTEE_ACTIVITY:
            try:
                payload = _backend_get_json(COMMISSION_SUBJECTS_ENDPOINT, {"id_comision": committee_id, "limit": 1})
                data = payload.get("data", {})
                projects = data.get("proyectos") if isinstance(data, dict) else None
                cache_subjects_total[committee_id] = _to_int(projects, _payload_total(payload))
            except Exception:
                cache_subjects_total[committee_id] = 0
        else:
            cache_subjects_total[committee_id] = 0
    if committee_id not in cache_activities_total:
        if ENABLE_COMMITTEE_ACTIVITY:
            try:
                payload = _backend_get_json(COMMISSION_ACTIVITIES_ENDPOINT, {"id_comision": committee_id, "limit": 1})
                cache_activities_total[committee_id] = _payload_total(payload)
            except Exception:
                cache_activities_total[committee_id] = 0
        else:
            cache_activities_total[committee_id] = 0
    return (
        cache_sessions_total[committee_id],
        cache_subjects_total[committee_id],
        cache_activities_total[committee_id],
    )


def _fetch_committee_fields_for_senator(
    senate_id: str,
    cache_sessions_total: Optional[Dict[int, int]] = None,
    cache_subjects_total: Optional[Dict[int, int]] = None,
    cache_activities_total: Optional[Dict[int, int]] = None,
) -> Dict[str, Any]:
    cache_sessions_total = cache_sessions_total if cache_sessions_total is not None else {}
    cache_subjects_total = cache_subjects_total if cache_subjects_total is not None else {}
    cache_activities_total = cache_activities_total if cache_activities_total is not None else {}

    memberships: List[Dict[str, Any]] = []
    topic_counts: Dict[str, int] = {}
    committee_total_sessions = 0
    bills_discussed_total = 0
    interventions_total = 0

    rows: List[Dict[str, Any]] = []
    if senate_id:
        try:
            commissions_payload = _backend_get_json(
                PARLIAMENTARIAN_COMMISSIONS_ENDPOINT,
                {"id_parlamentario": senate_id, "vigentes": 1, "limit": 100},
            )
            rows = _payload_data_rows(commissions_payload)
        except Exception:
            rows = []

    for row in rows:
        committee_id = _to_int(row.get("ID_COMISION"), 0)
        committee_name = str(row.get("NOMBRE") or "").strip()
        role_raw = str(row.get("CARGO") or "").strip() or "Integrante"
        topic = _committee_topic_from_name(committee_name)
        topic_counts[topic] = topic_counts.get(topic, 0) + 1

        if committee_id > 0 and (ENABLE_COMMITTEE_TOTAL_SESSIONS or ENABLE_COMMITTEE_ACTIVITY):
            total_sessions, discussed_count, activities_count = _committee_totals_for_id(
                committee_id,
                cache_sessions_total,
                cache_subjects_total,
                cache_activities_total,
            )
            committee_total_sessions += total_sessions
            bills_discussed_total += discussed_count
            interventions_total += activities_count

        memberships.append(
            {
                "committee_id": committee_id if committee_id > 0 else None,
                "committee_name": committee_name or "Sin dato",
                "role": _normalize_role(role_raw),
                "role_raw": role_raw,
                "topic": topic,
                "type": str(row.get("DESCRIPCION") or "").strip() or None,
                "start_date": str(row.get("FECHAINI") or "").strip() or None,
                "end_date": str(row.get("FECHAFIN") or "").strip() or None,
            }
        )

    sessions_attended = None
    if senate_id and ENABLE_COMMITTEE_ATTENDANCE:
        try:
            attendance_payload = _backend_get_json(
                PARLIAMENTARIAN_COMMITTEE_ATTENDANCE_ENDPOINT,
                {"id_parlamentario": senate_id, "limit": 1000, "offset": 0},
            )
            sessions_attended = _payload_total(attendance_payload)
        except Exception:
            sessions_attended = None

    if (
        sessions_attended is not None
        and committee_total_sessions > 0
        and sessions_attended > committee_total_sessions
    ):
        committee_total_sessions = sessions_attended

    total_sessions_value = committee_total_sessions if committee_total_sessions > 0 else None
    if total_sessions_value is None and sessions_attended is not None:
        total_sessions_value = sessions_attended

    return {
        "committee_memberships": memberships,
        "committee_sessions_attended": sessions_attended,
        "committee_total_sessions": total_sessions_value,
        "committee_count": len(memberships) if memberships else None,
        "committee_activity_bills_discussed": bills_discussed_total if bills_discussed_total > 0 else None,
        "committee_activity_bills_sponsored": None,
        "committee_activity_interventions": interventions_total if interventions_total > 0 else None,
        "committee_topic_counts": topic_counts or None,
    }


def _fetch_biography_for_senator(senate_id: str, slug: str) -> Tuple[Optional[str], Optional[str]]:
    params: Dict[str, Any] = {"fields[node--parlamentarios]": "title,body,field_trayectoria,slug,field_id"}
    if senate_id:
        params["filter[field_id]"] = senate_id
    elif slug:
        params["filter[slug]"] = slug
    else:
        return None, None

    try:
        payload = _backend_get_json(PARLIAMENTARIANS_JSONAPI_ENDPOINT, params=params)
    except Exception:
        return None, _senator_profile_url(slug)

    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return None, _senator_profile_url(slug)
    first = data[0] if isinstance(data[0], dict) else {}
    attrs = first.get("attributes", {}) if isinstance(first.get("attributes"), dict) else {}
    slug_value = str(attrs.get("slug") or slug or "").strip().lower()
    profile_url = _senator_profile_url(slug_value)

    bio_html = ""
    field_trayectoria = attrs.get("field_trayectoria")
    if isinstance(field_trayectoria, dict):
        bio_html = str(field_trayectoria.get("processed") or field_trayectoria.get("value") or "").strip()
    if not bio_html:
        body = attrs.get("body")
        if isinstance(body, dict):
            bio_html = str(body.get("processed") or body.get("value") or "").strip()

    return _clean_html_text(bio_html), profile_url


def _fetch_biography_index() -> Tuple[Dict[str, Tuple[Optional[str], Optional[str]]], Dict[str, Tuple[Optional[str], Optional[str]]]]:
    params: Dict[str, Any] = {
        "page[limit]": BIOGRAPHY_BULK_LIMIT,
        "fields[node--parlamentarios]": "title,body,field_trayectoria,slug,field_id",
    }
    by_id: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    by_slug: Dict[str, Tuple[Optional[str], Optional[str]]] = {}

    try:
        payload = _backend_get_json(PARLIAMENTARIANS_JSONAPI_ENDPOINT, params=params)
    except Exception:
        return by_id, by_slug

    data = payload.get("data")
    if not isinstance(data, list):
        return by_id, by_slug

    for row in data:
        if not isinstance(row, dict):
            continue
        attrs = row.get("attributes", {})
        if not isinstance(attrs, dict):
            continue
        slug = str(attrs.get("slug") or "").strip().lower()
        senate_id = str(attrs.get("field_id") or "").strip()
        bio_html = ""
        field_trayectoria = attrs.get("field_trayectoria")
        if isinstance(field_trayectoria, dict):
            bio_html = str(field_trayectoria.get("processed") or field_trayectoria.get("value") or "").strip()
        if not bio_html:
            body = attrs.get("body")
            if isinstance(body, dict):
                bio_html = str(body.get("processed") or body.get("value") or "").strip()
        bio = _clean_html_text(bio_html)
        url = _senator_profile_url(slug)
        value = (bio, url)
        if senate_id:
            by_id[senate_id] = value
        if slug:
            by_slug[slug] = value
    return by_id, by_slug


def _merge_biographies(senators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id, by_slug = _fetch_biography_index()
    cache: Dict[str, Tuple[Optional[str], Optional[str]]] = {}

    for item in senators:
        senate_id = str(item.get("_senate_id") or "").strip()
        slug = str(item.get("external_id") or "").strip().lower()
        key = senate_id or slug
        if not key:
            continue

        bio_url = by_id.get(senate_id) if senate_id else None
        if bio_url is None and slug:
            bio_url = by_slug.get(slug)
        if bio_url is None:
            if key not in cache:
                cache[key] = _fetch_biography_for_senator(senate_id, slug)
            bio_url = cache[key]

        bio, url = bio_url
        if bio:
            item["biografia"] = bio
        if url:
            item["biografia_url"] = url
    return senators


def _merge_committee_fields(senators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not senators:
        return senators

    jobs: Dict[Any, int] = {}
    with ThreadPoolExecutor(max_workers=COMMITTEE_MAX_WORKERS) as executor:
        for idx, item in enumerate(senators):
            senate_id = str(item.get("_senate_id") or "").strip()
            jobs[executor.submit(_fetch_committee_fields_for_senator, senate_id)] = idx

        for future in as_completed(jobs):
            idx = jobs[future]
            try:
                committee_fields = future.result()
            except Exception:
                committee_fields = _empty_committee_fields()
            senators[idx].update(committee_fields)

    return senators


def _fetch_senators_from_hemicycle() -> List[Dict[str, Any]]:
    url = _backend_url(HEMICYCLE_ENDPOINT)
    response = requests.get(
        url,
        params={"vigentes": 1, "camara": "S", "limit": 200},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    data = (
        payload.get("data", {})
        .get("parlamentarios", {})
        .get("data", [])
    )
    if not isinstance(data, list):
        return []

    out: List[Dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        nombre = (
            str(row.get("NOMBRE_COMPLETO") or "").strip()
            or " ".join(
                part
                for part in [
                    str(row.get("NOMBRE") or "").strip(),
                    str(row.get("APELLIDO_PATERNO") or "").strip(),
                    str(row.get("APELLIDO_MATERNO") or "").strip(),
                ]
                if part
            ).strip()
        )
        if len(nombre.split()) < 2:
            continue

        slug = str(row.get("SLUG") or "").strip().lower()
        external_id = slug or str(row.get("ID_PARLAMENTARIO") or _name_to_id(nombre)).strip()
        partido = str(row.get("PARTIDO") or "").strip()
        if not partido:
            comite = row.get("COMITE")
            if isinstance(comite, dict):
                partido = str(comite.get("ABREVIATURA") or comite.get("NOMBRE") or "").strip()
        partido = partido or "Sin dato"

        region = str(row.get("REGION") or "").strip() or "Sin dato"
        circ = str(row.get("CIRCUNSCRIPCION") or "").strip()
        if not circ:
            circ_id = _to_int(row.get("CIRCUNSCRIPCION_ID"), 0)
            circ = f"Circunscripción {circ_id}" if circ_id > 0 else "Sin dato"

        out.append(
            {
                "external_id": external_id,
                "nombre": nombre,
                "partido": partido,
                "distrito_circunscripcion": circ,
                "region": region,
                "periodo": _extract_period(row.get("PERIODOS")),
                "biografia": None,
                "biografia_url": _senator_profile_url(slug),
                "asistencia_pct": None,
                "sesiones_totales": None,
                "sesiones_ausentes": None,
                "_senate_id": str(row.get("ID_PARLAMENTARIO") or "").strip(),
                **_empty_committee_fields(),
            }
        )
    return out


def _extract_attendance_config() -> Tuple[str, Dict[str, str]]:
    default_params = {"limit": "200"}
    try:
        html = _download_html([SENATE_ATTENDANCE_URL])
        soup = BeautifulSoup(html, "html.parser")
        next_data = soup.find("script", id="__NEXT_DATA__")
        if not next_data or not next_data.string:
            return ATTENDANCE_ENDPOINT, default_params
        data = json.loads(next_data.string)
    except Exception:
        return ATTENDANCE_ENDPOINT, default_params

    stack: List[Any] = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            ref = node.get("reference")
            if (
                isinstance(ref, dict)
                and str(ref.get("endpointUrl") or "").strip().lower() == ATTENDANCE_ENDPOINT.lower()
            ):
                params: Dict[str, str] = {}
                for item in node.get("items", []):
                    if not isinstance(item, dict):
                        continue
                    k = str(item.get("key") or "").strip()
                    v = str(item.get("value") or "").strip()
                    if k and v:
                        params[k] = v
                if "limit" not in params:
                    params["limit"] = "200"
                return ATTENDANCE_ENDPOINT, params
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)

    return ATTENDANCE_ENDPOINT, default_params


def _fetch_attendance_maps() -> Dict[str, Any]:
    endpoint, params = _extract_attendance_config()
    url = _backend_url(endpoint)
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data", {}).get("DATA", [])
    if not isinstance(rows, list):
        rows = []

    by_id: Dict[str, Dict[str, Optional[float]]] = {}
    by_slug: Dict[str, Dict[str, Optional[float]]] = {}
    by_name: Dict[str, Dict[str, Optional[float]]] = {}
    rows_out: List[Dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        total = _to_int(row.get("TOTAL_SESIONES_TOTAL"), 0)
        if total <= 0:
            total = _to_int(row.get("TOTAL_SESIONES"), 0)
        present = _to_int(row.get("ASISTIO_A"), 0)
        absent = _to_int(row.get("JUSTIFICADO"), 0) + _to_int(row.get("SIN_JUSTIFICAR"), 0)
        if absent <= 0 and total > 0:
            absent = max(0, total - present)

        stats: Dict[str, Optional[float]] = {
            "asistencia_pct": round((present / total) * 100, 2) if total > 0 else None,
            "sesiones_totales": total if total > 0 else None,
            "sesiones_ausentes": absent if total > 0 else None,
        }

        sid = str(row.get("ID_PARLAMENTARIO") or "").strip()
        if sid:
            by_id[sid] = stats
        slug = str(row.get("SLUG") or "").strip().lower()
        if slug:
            by_slug[slug] = stats

        full_name = " ".join(
            part
            for part in [
                str(row.get("NOMBRE") or "").strip(),
                str(row.get("APELLIDO_PATERNO") or "").strip(),
                str(row.get("APELLIDO_MATERNO") or "").strip(),
            ]
            if part
        ).strip()
        if full_name:
            by_name[_normalize_name(full_name)] = stats

        external_id = slug or sid or _name_to_id(full_name)
        if not full_name and slug:
            full_name = _slug_to_name(slug)
        if len(full_name.split()) >= 2 and external_id:
            rows_out.append(
                {
                    "external_id": external_id,
                    "nombre": full_name,
                    "partido": "Sin dato",
                    "distrito_circunscripcion": "Sin dato",
                    "region": "Sin dato",
                    "periodo": f"{datetime.now().year}-ACTUAL",
                    "biografia": None,
                    "biografia_url": _senator_profile_url(slug),
                    "asistencia_pct": stats.get("asistencia_pct"),
                    "sesiones_totales": stats.get("sesiones_totales"),
                    "sesiones_ausentes": stats.get("sesiones_ausentes"),
                    "_senate_id": sid,
                    **_empty_committee_fields(),
                }
            )

    return {"id": by_id, "slug": by_slug, "name": by_name, "rows": rows_out}


def _fetch_senators_from_html() -> List[Dict[str, Any]]:
    soup = BeautifulSoup(_download_html(), "html.parser")
    out: List[Dict[str, Any]] = []

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
                "biografia": None,
                "biografia_url": _senator_profile_url(external_id),
                "asistencia_pct": None,
                "sesiones_totales": None,
                "sesiones_ausentes": None,
                "_senate_id": None,
                **_empty_committee_fields(),
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
                "biografia": None,
                "biografia_url": _senator_profile_url(_name_to_id(nombre)),
                "asistencia_pct": None,
                "sesiones_totales": None,
                "sesiones_ausentes": None,
                "_senate_id": None,
                **_empty_committee_fields(),
            }
        )

    return out


def _dedup_senators(out: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _is_missing(v: str) -> bool:
        return (v or "").strip() in {"", "Sin dato"}

    dedup: Dict[str, Dict[str, Any]] = {}
    for item in out:
        key = item["external_id"]
        if key not in dedup:
            dedup[key] = item
            continue
        current = dedup[key]
        if _name_richness(item.get("nombre")) > _name_richness(current.get("nombre")):
            current["nombre"] = item["nombre"]
        # Conserva la versión más rica campo a campo.
        for field in ["nombre", "partido", "distrito_circunscripcion", "region", "periodo"]:
            if _is_missing(current.get(field, "")) and not _is_missing(item.get(field, "")):
                current[field] = item[field]
        for field in ["biografia", "biografia_url"]:
            if not current.get(field) and item.get(field):
                current[field] = item[field]
        for field in [
            "asistencia_pct",
            "sesiones_totales",
            "sesiones_ausentes",
            "votes_cast_total",
            "votes_expected_total",
            "voting_participation_pct",
            "votes_yes_total",
            "votes_no_total",
            "votes_abstention_total",
            "committee_sessions_attended",
            "committee_total_sessions",
            "committee_count",
            "committee_activity_bills_discussed",
            "committee_activity_bills_sponsored",
            "committee_activity_interventions",
        ]:
            if current.get(field) is None and item.get(field) is not None:
                current[field] = item[field]
        if (not current.get("committee_memberships")) and item.get("committee_memberships"):
            current["committee_memberships"] = item["committee_memberships"]
        if (not current.get("committee_topic_counts")) and item.get("committee_topic_counts"):
            current["committee_topic_counts"] = item["committee_topic_counts"]
        if (not current.get("_senate_id")) and item.get("_senate_id"):
            current["_senate_id"] = item["_senate_id"]
        dedup[key] = current

    return list(dedup.values())


def _merge_attendance(senators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        attendance = _fetch_attendance_maps()
    except Exception:
        return senators

    by_id = attendance["id"]
    by_slug = attendance["slug"]
    by_name = attendance["name"]

    for item in senators:
        stats: Optional[Dict[str, Optional[float]]] = None
        senate_id = str(item.get("_senate_id") or "").strip()
        if senate_id and senate_id in by_id:
            stats = by_id[senate_id]
        if stats is None:
            external_id = str(item.get("external_id") or "").strip().lower()
            if external_id and external_id in by_slug:
                stats = by_slug[external_id]
        if stats is None:
            norm_name = _normalize_name(item.get("nombre", ""))
            if norm_name in by_name:
                stats = by_name[norm_name]
        if stats:
            item["asistencia_pct"] = stats.get("asistencia_pct")
            item["sesiones_totales"] = stats.get("sesiones_totales")
            item["sesiones_ausentes"] = stats.get("sesiones_ausentes")

    # Incluye filas presentes solo en la fuente de asistencia.
    known_external_ids = {
        str(item.get("external_id") or "").strip().lower()
        for item in senators
        if str(item.get("external_id") or "").strip()
    }
    for extra in attendance.get("rows", []):
        key = str(extra.get("external_id") or "").strip().lower()
        if not key or key in known_external_ids:
            continue
        senators.append(extra)
        known_external_ids.add(key)

    return senators


def _merge_voting_fields(senators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not senators:
        return senators

    try:
        stats_by_id, stats_by_slug, stats_by_name = fetch_voting_stats_by_senator(datetime.now().year)
    except Exception:
        return senators

    for item in senators:
        stats: Optional[Dict[str, int]] = None
        senate_id = str(item.get("_senate_id") or "").strip()
        if senate_id and senate_id in stats_by_id:
            stats = stats_by_id[senate_id]
        if stats is None:
            slug = str(item.get("external_id") or "").strip().lower()
            if slug and slug in stats_by_slug:
                stats = stats_by_slug[slug]
        if stats is None:
            norm_name = _normalize_name(item.get("nombre", ""))
            if norm_name in stats_by_name:
                stats = stats_by_name[norm_name]
        if not stats:
            continue

        votes_expected = int(stats.get("votes_expected", 0))
        votes_cast = int(stats.get("votes_cast", 0))
        if votes_expected <= 0:
            continue

        item["votes_cast_total"] = votes_cast
        item["votes_expected_total"] = votes_expected
        item["voting_participation_pct"] = round((votes_cast / votes_expected) * 100.0, 2)
        item["votes_yes_total"] = int(stats.get("votes_yes", 0))
        item["votes_no_total"] = int(stats.get("votes_no", 0))
        item["votes_abstention_total"] = int(stats.get("votes_abstention", 0))

    return senators


def fetch_senators() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        out = _fetch_senators_from_hemicycle()
    except Exception:
        out = []

    # Fallback por HTML por si cambia o cae el endpoint de hemiciclo.
    if not out:
        out = _fetch_senators_from_html()

    out = _merge_attendance(out)
    out = _merge_voting_fields(out)
    out = _merge_biographies(out)
    out = _merge_committee_fields(out)
    out = _dedup_senators(out)
    for item in out:
        item.pop("_senate_id", None)
    return out
