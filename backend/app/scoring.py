from __future__ import annotations


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


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

    commission_participation = _clamp(float(metrics.get("commission_participation_pct", 0)))
    commissions_score = commission_participation

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
        "total_score": round(total_score, 2),
    }
