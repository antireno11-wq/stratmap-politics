from __future__ import annotations

from typing import Any, Dict, List, Optional

def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


ROLE_SCORES = {
    "president": 100.0,
    "vice_president": 85.0,
    "full_member": 70.0,
    "substitute_member": 40.0,
}

TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "economia_hacienda": [
        "hacienda",
        "econom",
        "presupuesto",
        "finanza",
        "tribut",
        "mineria",
        "energia",
        "obra publica",
        "transporte",
        "pesca",
        "agric",
    ],
    "social_educacion_salud": [
        "salud",
        "educ",
        "vivienda",
        "trabajo",
        "mujer",
        "ninez",
        "niñez",
        "deporte",
        "cultura",
        "adulto mayor",
        "discapacidad",
    ],
    "justicia_seguridad": [
        "justicia",
        "constitucion",
        "constitución",
        "seguridad",
        "defensa",
        "inteligencia",
        "derechos humanos",
        "gobierno interior",
    ],
    "medioambiente_territorio": [
        "medio ambiente",
        "recursos hidricos",
        "recursos hídricos",
        "zonas extremas",
        "territorio",
        "descentralizacion",
        "descentralización",
        "marit",
        "acuicultura",
    ],
    "relaciones_exteriores": [
        "relaciones exteriores",
        "interparlament",
        "integracion latinoamericana",
        "integración latinoamericana",
        "rr.ee",
    ],
    "otros": [],
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: Optional[int] = 0) -> Optional[int]:
    try:
        if value is None:
            return default
        return int(float(value))
    except Exception:
        return default


def _avg(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _norm_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("á", "a").replace("é", "e").replace("í", "i")
    text = text.replace("ó", "o").replace("ú", "u").replace("ü", "u")
    return " ".join(text.split())


def _normalize_role(role: Any) -> str:
    role_text = _norm_text(role)
    if any(token in role_text for token in ["vicepresident", "vice presidente", "vicepresidente", "vice"]):
        return "vice_president"
    if any(token in role_text for token in ["president", "presidente"]):
        return "president"
    if any(token in role_text for token in ["reemplazante", "suplente", "substitute"]):
        return "substitute_member"
    return "full_member"


def _role_score(role: Any) -> float:
    return ROLE_SCORES[_normalize_role(role)]


def _infer_topic_from_committee_name(committee_name: Any) -> str:
    text = _norm_text(committee_name)
    if not text:
        return "otros"
    for topic, keywords in TOPIC_KEYWORDS.items():
        if topic == "otros":
            continue
        if any(keyword in text for keyword in keywords):
            return topic
    return "otros"


def _topic_distribution(memberships: List[Dict[str, Any]], explicit_topic_counts: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    if explicit_topic_counts:
        out: Dict[str, int] = {}
        for k, v in explicit_topic_counts.items():
            iv = _safe_int(v, 0) or 0
            if iv > 0:
                out[str(k)] = iv
        if out:
            return out

    out: Dict[str, int] = {}
    for membership in memberships:
        topic = _norm_text(membership.get("topic"))
        if not topic:
            topic = _infer_topic_from_committee_name(membership.get("committee_name"))
        out[topic] = out.get(topic, 0) + 1
    return out


def calc_committee_score(metrics: Dict[str, Any]) -> Dict[str, Any]:
    memberships = metrics.get("committee_memberships") or []
    if not isinstance(memberships, list):
        memberships = []

    committee_count = _safe_int(metrics.get("committee_count"), None)
    if committee_count is None:
        committee_count = len(memberships)
    committee_count = max(0, committee_count or 0)

    sessions_attended = _safe_int(metrics.get("committee_sessions_attended"), None)
    total_sessions = _safe_int(metrics.get("committee_total_sessions"), None)
    attendance_rate_raw = None
    if sessions_attended is not None and total_sessions is not None and total_sessions > 0:
        attendance_rate_raw = (sessions_attended / total_sessions) * 100.0
    committee_attendance_score = _clamp(attendance_rate_raw if attendance_rate_raw is not None else 0.0)

    chamber_avg_committee_count = _safe_float(metrics.get("chamber_average_committee_count"), 0.0)
    if chamber_avg_committee_count <= 0:
        committee_count_score = 0.0
    else:
        committee_count_score = _clamp((committee_count / chamber_avg_committee_count) * 100.0)

    role_values: List[float] = []
    roles_raw: List[str] = []
    for membership in memberships:
        role = membership.get("role")
        if role is None:
            continue
        roles_raw.append(str(role))
        role_values.append(_role_score(role))
    if not role_values:
        alt_roles = metrics.get("committee_roles") or []
        if isinstance(alt_roles, list):
            for role in alt_roles:
                roles_raw.append(str(role))
                role_values.append(_role_score(role))
    committee_role_score = _clamp(_avg(role_values))

    bills_discussed = _safe_int(metrics.get("committee_activity_bills_discussed"), None)
    bills_sponsored = _safe_int(metrics.get("committee_activity_bills_sponsored"), None)
    interventions = _safe_int(metrics.get("committee_activity_interventions"), None)
    has_activity_data = any(v is not None for v in [bills_discussed, bills_sponsored, interventions])
    activity_index = None
    if has_activity_data:
        activity_index = (
            float(max(0, bills_discussed or 0))
            + float(max(0, bills_sponsored or 0)) * 2.0
            + float(max(0, interventions or 0)) * 0.5
        )
    activity_reference = max(1.0, _safe_float(metrics.get("committee_activity_reference"), 40.0))
    committee_activity_score = 0.0 if activity_index is None else _clamp((activity_index / activity_reference) * 100.0)

    topic_counts = _topic_distribution(memberships, metrics.get("committee_topic_counts"))
    total_topics = sum(topic_counts.values())
    concentration_raw = 0.0 if total_topics <= 0 else (max(topic_counts.values()) / total_topics) * 100.0
    specialization_score = _clamp(concentration_raw)

    committee_score = _clamp(
        (committee_attendance_score * 0.40)
        + (committee_count_score * 0.20)
        + (committee_role_score * 0.20)
        + (committee_activity_score * 0.15)
        + (specialization_score * 0.05)
    )

    weighted = {
        "committee_attendance": round(committee_attendance_score * 0.40, 4),
        "committee_count": round(committee_count_score * 0.20, 4),
        "committee_role": round(committee_role_score * 0.20, 4),
        "committee_activity": round(committee_activity_score * 0.15, 4),
        "specialization": round(specialization_score * 0.05, 4),
    }

    breakdown = {
        "formula": "0.40*attendance + 0.20*count + 0.20*role + 0.15*activity + 0.05*specialization",
        "weights": {
            "committee_attendance": 0.40,
            "committee_count": 0.20,
            "committee_role": 0.20,
            "committee_activity": 0.15,
            "specialization": 0.05,
        },
        "raw": {
            "committee_sessions_attended": sessions_attended,
            "committee_total_sessions": total_sessions,
            "committee_attendance_rate_pct": round(attendance_rate_raw, 4) if attendance_rate_raw is not None else None,
            "committee_count": committee_count,
            "chamber_average_committee_count": round(chamber_avg_committee_count, 4),
            "committee_roles": roles_raw,
            "committee_activity_bills_discussed": bills_discussed,
            "committee_activity_bills_sponsored": bills_sponsored,
            "committee_activity_interventions": interventions,
            "committee_activity_index": round(activity_index, 4) if activity_index is not None else None,
            "topic_distribution": topic_counts,
            "topic_concentration_pct": round(concentration_raw, 4),
        },
        "normalized": {
            "committee_attendance_score": round(committee_attendance_score, 4),
            "committee_count_score": round(committee_count_score, 4),
            "committee_role_score": round(committee_role_score, 4),
            "committee_activity_score": round(committee_activity_score, 4),
            "specialization_score": round(specialization_score, 4),
        },
        "weighted_components": weighted,
    }

    return {
        "committee_score": round(committee_score, 2),
        "committee_score_breakdown": breakdown,
    }


def calc_scores(metrics: dict) -> dict:
    attendance_score = _clamp(float(metrics.get("attendance_pct", 0)))

    voting_participation = _clamp(float(metrics.get("voting_participation_pct", 0)))
    party_alignment = _clamp(float(metrics.get("party_alignment_pct", 0)))
    voting_score = _clamp((voting_participation * 0.7) + (party_alignment * 0.3))

    bills_presented = max(0.0, float(metrics.get("bills_presented", 0)))
    bills_approved = max(0.0, float(metrics.get("bills_approved", 0)))
    bills_in_progress = max(0.0, float(metrics.get("bills_in_progress", 0)))

    approval_ratio = 0.0 if bills_presented == 0 else _clamp((bills_approved / bills_presented) * 100)
    productivity = _clamp(bills_presented * 4)
    progress_ratio = 0.0 if bills_presented == 0 else _clamp((bills_in_progress / bills_presented) * 100)
    legislative_score = _clamp((approval_ratio * 0.5) + (productivity * 0.3) + (progress_ratio * 0.2))

    lobby_compliance = _clamp(float(metrics.get("lobby_compliance_pct", 0)))
    meetings_registered = max(0.0, float(metrics.get("meetings_registered", 0)))
    official_trips = max(0.0, float(metrics.get("official_trips", 0)))
    records_score = _clamp((meetings_registered * 4) + (official_trips * 6))
    transparency_score = _clamp((lobby_compliance * 0.75) + (records_score * 0.25))

    committee = calc_committee_score(metrics)
    committee_score = _clamp(_safe_float(committee.get("committee_score"), 0.0))
    commissions_score = committee_score

    total_score = _clamp(
        (attendance_score * 0.30)
        + (voting_score * 0.20)
        + (legislative_score * 0.25)
        + (transparency_score * 0.15)
        + (commissions_score * 0.10)
    )

    return {
        "attendance_score": round(attendance_score, 2),
        "voting_score": round(voting_score, 2),
        "legislative_score": round(legislative_score, 2),
        "transparency_score": round(transparency_score, 2),
        "commissions_score": round(commissions_score, 2),
        "committee_score": round(committee_score, 2),
        "committee_score_breakdown": committee["committee_score_breakdown"],
        "total_score": round(total_score, 2),
    }
