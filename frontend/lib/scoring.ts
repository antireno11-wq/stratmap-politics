export function computeTransparencyScore(item: {
  asistencia_pct?: number | null;
  committee_score?: number | null;
}): number {
  return computePublicScoreBreakdown(item).total_score ?? 0;
}

export function computePublicScoreBreakdown(item: {
  asistencia_pct?: number | null;
  committee_score?: number | null;
}) {
  const attendanceRaw = item.asistencia_pct == null ? null : Number(item.asistencia_pct);
  const attendanceScore =
    attendanceRaw == null || Number.isNaN(attendanceRaw)
      ? null
      : Math.max(0, Math.min(100, attendanceRaw));
  const committeeRaw = item.committee_score == null ? null : Number(item.committee_score);
  const committeeScore = committeeRaw == null || Number.isNaN(committeeRaw)
    ? null
    : Math.max(0, Math.min(100, committeeRaw));

  const components = {
    attendance: {
      value: attendanceScore,
      weight: 0.6,
      applicable: attendanceScore != null,
      effective_weight: 0,
      weighted_value: null as number | null,
    },
    committees: {
      value: committeeScore,
      weight: 0.4,
      applicable: committeeScore != null,
      effective_weight: 0,
      weighted_value: null as number | null,
    },
  };

  const applicableWeight = Object.values(components)
    .filter((component) => component.applicable && component.value != null)
    .reduce((acc, component) => acc + component.weight, 0);

  let total: number | null = null;
  if (applicableWeight > 0) {
    total = 0;
    for (const component of Object.values(components)) {
      if (!component.applicable || component.value == null) continue;
      component.effective_weight = component.weight / applicableWeight;
      component.weighted_value = component.value * component.effective_weight;
      total += component.weighted_value;
    }
  }

  const attendanceWeight = components.attendance.effective_weight;
  const committeeWeight = components.committees.effective_weight;
  const weightedAttendance = components.attendance.weighted_value ?? 0;
  const weightedCommittee = components.committees.weighted_value ?? 0;

  return {
    attendance_score: attendanceScore == null ? null : Math.round(attendanceScore * 100) / 100,
    committee_score: committeeScore == null ? null : Math.round(committeeScore * 100) / 100,
    components,
    attendance_weight: attendanceWeight,
    committee_weight: committeeWeight,
    weighted_attendance: Math.round(weightedAttendance * 100) / 100,
    weighted_committee: Math.round(weightedCommittee * 100) / 100,
    applicable_weight_sum: Math.round(applicableWeight * 10000) / 10000,
    total_score: total == null ? null : Math.round(total * 100) / 100,
  };
}

export function scoreTier(score: number): "alto" | "medio" | "bajo" {
  if (score >= 80) return "alto";
  if (score >= 60) return "medio";
  return "bajo";
}
