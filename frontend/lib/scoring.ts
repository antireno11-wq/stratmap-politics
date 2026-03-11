export function computeTransparencyScore(item: {
  asistencia_pct?: number | null;
  committee_score?: number | null;
}): number {
  return computePublicScoreBreakdown(item).total_score;
}

export function computePublicScoreBreakdown(item: {
  asistencia_pct?: number | null;
  committee_score?: number | null;
}) {
  const attendanceScore = Math.max(0, Math.min(100, Number(item.asistencia_pct ?? 0)));
  const committeeRaw = item.committee_score == null ? null : Number(item.committee_score);
  const committeeScore = committeeRaw == null || Number.isNaN(committeeRaw)
    ? null
    : Math.max(0, Math.min(100, committeeRaw));

  // Mientras no exista score de comisiones para todos, evitamos castigar con cero:
  // si no hay dato de comisiones, el score se apoya en asistencia.
  const hasCommitteeScore = committeeScore != null;
  const attendanceWeight = hasCommitteeScore ? 0.6 : 1.0;
  const committeeWeight = hasCommitteeScore ? 0.4 : 0.0;

  const weightedAttendance = attendanceScore * attendanceWeight;
  const weightedCommittee = (committeeScore ?? 0) * committeeWeight;
  const total = weightedAttendance + weightedCommittee;

  return {
    attendance_score: Math.round(attendanceScore * 100) / 100,
    committee_score: committeeScore == null ? null : Math.round(committeeScore * 100) / 100,
    attendance_weight: attendanceWeight,
    committee_weight: committeeWeight,
    weighted_attendance: Math.round(weightedAttendance * 100) / 100,
    weighted_committee: Math.round(weightedCommittee * 100) / 100,
    total_score: Math.round(total * 100) / 100,
  };
}

export function scoreTier(score: number): "alto" | "medio" | "bajo" {
  if (score >= 80) return "alto";
  if (score >= 60) return "medio";
  return "bajo";
}
