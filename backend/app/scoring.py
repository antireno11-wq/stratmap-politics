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


def _round_or_none(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return default


def _normalize_weighted_components(
    components: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    normalized: Dict[str, Dict[str, Any]] = {}
    total_applicable_weight = 0.0

    for key, component in components.items():
        raw_value = component.get("value")
        raw_weight = _safe_float(component.get("weight"), 0.0)
        raw_weight = max(0.0, raw_weight)
        declared_applicable = _safe_bool(component.get("applicable"), False)

        value: Optional[float]
        if raw_value is None:
            value = None
        else:
            value = _clamp(_safe_float(raw_value, 0.0))

        applicable = bool(declared_applicable and value is not None)
        if applicable:
            total_applicable_weight += raw_weight

        normalized[key] = {
            "value": _round_or_none(value, 4),
            "weight": round(raw_weight, 4),
            "applicable": applicable,
        }

    final_score: Optional[float] = None
    if total_applicable_weight > 0:
        acc = 0.0
        for component in normalized.values():
            if component["applicable"]:
                effective_weight = component["weight"] / total_applicable_weight
                weighted_value = float(component["value"]) * effective_weight
                component["effective_weight"] = round(effective_weight, 4)
                component["weighted_value"] = round(weighted_value, 4)
                acc += weighted_value
            else:
                component["effective_weight"] = 0.0
                component["weighted_value"] = None
        final_score = _clamp(acc)
    else:
        for component in normalized.values():
            component["effective_weight"] = 0.0
            component["weighted_value"] = None

    return {
        "final_score": _round_or_none(final_score, 2),
        "components": normalized,
        "applicable_weight_sum": round(total_applicable_weight, 4),
    }


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
    committee_attendance_score = _clamp(attendance_rate_raw) if attendance_rate_raw is not None else None

    chamber_avg_committee_count = _safe_float(metrics.get("chamber_average_committee_count"), 0.0)
    committee_count_score = None
    if chamber_avg_committee_count > 0 and committee_count > 0:
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
    committee_role_score = _clamp(_avg(role_values)) if role_values else None

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
    committee_activity_score = None if activity_index is None else _clamp((activity_index / activity_reference) * 100.0)

    topic_counts = _topic_distribution(memberships, metrics.get("committee_topic_counts"))
    total_topics = sum(topic_counts.values())
    concentration_raw = None if total_topics <= 0 else (max(topic_counts.values()) / total_topics) * 100.0
    specialization_score = _clamp(concentration_raw) if concentration_raw is not None else None

    has_committee_participation = bool(
        committee_count > 0
        or memberships
        or (sessions_attended is not None and sessions_attended > 0)
        or role_values
        or topic_counts
    )

    component_payload = _normalize_weighted_components(
        {
            "committee_attendance": {
                "value": committee_attendance_score,
                "weight": 0.40,
                "applicable": attendance_rate_raw is not None,
            },
            "committee_count": {
                "value": committee_count_score,
                "weight": 0.20,
                "applicable": committee_count > 0 and chamber_avg_committee_count > 0,
            },
            "committee_role": {
                "value": committee_role_score,
                "weight": 0.20,
                "applicable": len(role_values) > 0,
            },
            "committee_activity": {
                "value": committee_activity_score,
                "weight": 0.15,
                "applicable": activity_index is not None,
            },
            "specialization": {
                "value": specialization_score,
                "weight": 0.05,
                "applicable": total_topics > 0,
            },
        }
    )
    committee_score = component_payload["final_score"] if has_committee_participation else None

    breakdown = {
        "formula": "sum(component_score * component_weight) / sum(component_weight), only applicable components",
        "weights": {
            "committee_attendance": 0.40,
            "committee_count": 0.20,
            "committee_role": 0.20,
            "committee_activity": 0.15,
            "specialization": 0.05,
        },
        "applicability_mode": "exclude_not_applicable",
        "has_committee_participation": has_committee_participation,
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
            "topic_concentration_pct": round(concentration_raw, 4) if concentration_raw is not None else None,
        },
        "normalized": {
            "committee_attendance_score": _round_or_none(committee_attendance_score, 4),
            "committee_count_score": _round_or_none(committee_count_score, 4),
            "committee_role_score": _round_or_none(committee_role_score, 4),
            "committee_activity_score": _round_or_none(committee_activity_score, 4),
            "specialization_score": _round_or_none(specialization_score, 4),
        },
        "components": component_payload["components"],
        "weighted_components": {
            key: component_payload["components"][key]["weighted_value"]
            for key in component_payload["components"]
        },
        "applicable_weight_sum": component_payload["applicable_weight_sum"],
    }

    return {
        "committee_score": _round_or_none(committee_score, 2),
        "committee_score_breakdown": breakdown,
    }


def calc_voting_score(metrics: Dict[str, Any]) -> Dict[str, Any]:
    votes_cast = _safe_int(
        metrics.get("votes_cast_total", metrics.get("voting_votes_cast")),
        None,
    )
    votes_expected = _safe_int(
        metrics.get("votes_expected_total", metrics.get("voting_votes_expected")),
        None,
    )

    voting_participation_raw = metrics.get("voting_participation_pct")
    if voting_participation_raw is None and votes_cast is not None and votes_expected is not None and votes_expected > 0:
        voting_participation_raw = (votes_cast / votes_expected) * 100.0

    voting_participation_score = (
        _clamp(_safe_float(voting_participation_raw, 0.0)) if voting_participation_raw is not None else None
    )

    party_alignment_raw = metrics.get("party_alignment_pct")
    party_alignment_score = _clamp(_safe_float(party_alignment_raw, 0.0)) if party_alignment_raw is not None else None

    component_payload = _normalize_weighted_components(
        {
            "voting_participation": {
                "value": voting_participation_score,
                "weight": 0.70,
                "applicable": voting_participation_score is not None,
            },
            "party_alignment": {
                "value": party_alignment_score,
                "weight": 0.30,
                "applicable": party_alignment_score is not None,
            },
        }
    )

    breakdown = {
        "formula": "sum(component_score * component_weight) / sum(component_weight), only applicable components",
        "weights": {
            "voting_participation": 0.70,
            "party_alignment": 0.30,
        },
        "applicability_mode": "exclude_not_applicable",
        "raw": {
            "votes_cast_total": votes_cast,
            "votes_expected_total": votes_expected,
            "voting_participation_pct": (
                round(float(voting_participation_raw), 4) if voting_participation_raw is not None else None
            ),
            "party_alignment_pct": _round_or_none(party_alignment_score, 4),
        },
        "normalized": {
            "voting_participation_score": _round_or_none(voting_participation_score, 4),
            "party_alignment_score": _round_or_none(party_alignment_score, 4),
        },
        "components": component_payload["components"],
        "weighted_components": {
            key: component_payload["components"][key]["weighted_value"]
            for key in component_payload["components"]
        },
        "applicable_weight_sum": component_payload["applicable_weight_sum"],
    }

    return {
        "voting_score": component_payload["final_score"],
        "voting_score_breakdown": breakdown,
    }


def calc_scores(metrics: dict) -> dict:
    attendance_raw = metrics.get("attendance_pct")
    attendance_score = _clamp(_safe_float(attendance_raw, 0.0)) if attendance_raw is not None else None

    voting = calc_voting_score(metrics)
    voting_score = voting["voting_score"]

    bills_presented_raw = metrics.get("bills_presented")
    bills_approved_raw = metrics.get("bills_approved")
    bills_in_progress_raw = metrics.get("bills_in_progress")
    legislative_score = None
    if any(value is not None for value in [bills_presented_raw, bills_approved_raw, bills_in_progress_raw]):
        bills_presented = max(0.0, _safe_float(bills_presented_raw, 0.0))
        bills_approved = max(0.0, _safe_float(bills_approved_raw, 0.0))
        bills_in_progress = max(0.0, _safe_float(bills_in_progress_raw, 0.0))

        approval_ratio = 0.0 if bills_presented == 0 else _clamp((bills_approved / bills_presented) * 100)
        productivity = _clamp(bills_presented * 4)
        progress_ratio = 0.0 if bills_presented == 0 else _clamp((bills_in_progress / bills_presented) * 100)
        legislative_score = _clamp((approval_ratio * 0.5) + (productivity * 0.3) + (progress_ratio * 0.2))

    lobby_compliance_raw = metrics.get("lobby_compliance_pct")
    meetings_registered_raw = metrics.get("meetings_registered")
    official_trips_raw = metrics.get("official_trips")
    transparency_score = None
    if any(value is not None for value in [lobby_compliance_raw, meetings_registered_raw, official_trips_raw]):
        lobby_compliance = _clamp(_safe_float(lobby_compliance_raw, 0.0))
        meetings_registered = max(0.0, _safe_float(meetings_registered_raw, 0.0))
        official_trips = max(0.0, _safe_float(official_trips_raw, 0.0))
        records_score = _clamp((meetings_registered * 4) + (official_trips * 6))
        transparency_score = _clamp((lobby_compliance * 0.75) + (records_score * 0.25))

    committee = calc_committee_score(metrics)
    committee_score = committee.get("committee_score")
    commissions_score = committee_score

    total_payload = _normalize_weighted_components(
        {
            "attendance": {"value": attendance_score, "weight": 0.30, "applicable": attendance_score is not None},
            "voting": {"value": voting_score, "weight": 0.20, "applicable": voting_score is not None},
            "legislative_activity": {
                "value": legislative_score,
                "weight": 0.25,
                "applicable": legislative_score is not None,
            },
            "transparency": {"value": transparency_score, "weight": 0.15, "applicable": transparency_score is not None},
            "committees": {"value": commissions_score, "weight": 0.10, "applicable": commissions_score is not None},
        }
    )
    total_score = total_payload["final_score"]

    return {
        "attendance_score": _round_or_none(attendance_score, 2),
        "voting_score": _round_or_none(voting_score, 2),
        "voting_score_breakdown": voting["voting_score_breakdown"],
        "legislative_score": _round_or_none(legislative_score, 2),
        "transparency_score": _round_or_none(transparency_score, 2),
        "commissions_score": _round_or_none(commissions_score, 2),
        "committee_score": _round_or_none(committee_score, 2),
        "committee_score_breakdown": committee["committee_score_breakdown"],
        "components": total_payload["components"],
        "total_score": _round_or_none(total_score, 2),
        "applicable_weight_sum": total_payload["applicable_weight_sum"],
    }


def calc_public_score(metrics: Dict[str, Any]) -> Dict[str, Any]:
    attendance_raw = metrics.get("attendance_pct")
    if attendance_raw is None:
        attendance_raw = metrics.get("asistencia_pct")

    attendance_score = _clamp(_safe_float(attendance_raw, 0.0)) if attendance_raw is not None else None
    voting = calc_voting_score(metrics)
    voting_score = voting["voting_score"]
    committee_raw = metrics.get("committee_score")
    committee_score = _clamp(_safe_float(committee_raw, 0.0)) if committee_raw is not None else None

    payload = _normalize_weighted_components(
        {
            "attendance": {"value": attendance_score, "weight": 0.50, "applicable": attendance_score is not None},
            "voting": {"value": voting_score, "weight": 0.30, "applicable": voting_score is not None},
            "committees": {"value": committee_score, "weight": 0.20, "applicable": committee_score is not None},
        }
    )
    return {
        "final_score": payload["final_score"],
        "voting_score": _round_or_none(voting_score, 2),
        "voting_score_breakdown": voting["voting_score_breakdown"],
        "components": payload["components"],
        "applicable_weight_sum": payload["applicable_weight_sum"],
        "formula": "sum(component_score * component_weight) / sum(component_weight), only applicable components",
        "applicability_mode": "exclude_not_applicable",
    }
