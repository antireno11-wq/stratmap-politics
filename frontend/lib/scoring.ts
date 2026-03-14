export function computeTransparencyScore(item: {
  final_score?: number | null;
  asistencia_pct?: number | null;
  committee_score?: number | null;
  score_components?: {
    attendance?: {
      value?: number | null;
      weight?: number;
      applicable?: boolean;
      effective_weight?: number;
      weighted_value?: number | null;
    };
    committees?: {
      value?: number | null;
      weight?: number;
      applicable?: boolean;
      effective_weight?: number;
      weighted_value?: number | null;
    };
  } | null;
}): number | null {
  const backendScore = item.final_score == null ? null : Number(item.final_score);
  if (backendScore != null && Number.isFinite(backendScore)) {
    return Math.max(0, Math.min(100, backendScore));
  }
  return computePublicScoreBreakdown(item).total_score;
}

export function computePublicScoreBreakdown(item: {
  final_score?: number | null;
  asistencia_pct?: number | null;
  committee_score?: number | null;
  score_components?: {
    attendance?: {
      value?: number | null;
      weight?: number;
      applicable?: boolean;
      effective_weight?: number;
      weighted_value?: number | null;
    };
    committees?: {
      value?: number | null;
      weight?: number;
      applicable?: boolean;
      effective_weight?: number;
      weighted_value?: number | null;
    };
  } | null;
}) {
  const backendFinalScore = item.final_score == null ? null : Number(item.final_score);
  const backendComponents = item.score_components ?? null;
  if (backendComponents && typeof backendComponents === "object") {
    const attendance = backendComponents.attendance ?? null;
    const committees = backendComponents.committees ?? null;
    const attendanceScore = attendance?.value == null ? null : Number(attendance.value);
    const committeeScore = committees?.value == null ? null : Number(committees.value);
    return {
      attendance_score: attendanceScore == null || Number.isNaN(attendanceScore)
        ? null
        : Math.round(attendanceScore * 100) / 100,
      committee_score: committeeScore == null || Number.isNaN(committeeScore)
        ? null
        : Math.round(committeeScore * 100) / 100,
      components: {
        attendance: {
          value: attendanceScore == null || Number.isNaN(attendanceScore) ? null : attendanceScore,
          weight: Number(attendance?.weight ?? 0.6),
          applicable: Boolean(attendance?.applicable),
          effective_weight: Number(attendance?.effective_weight ?? 0),
          weighted_value: attendance?.weighted_value == null ? null : Number(attendance.weighted_value),
        },
        committees: {
          value: committeeScore == null || Number.isNaN(committeeScore) ? null : committeeScore,
          weight: Number(committees?.weight ?? 0.4),
          applicable: Boolean(committees?.applicable),
          effective_weight: Number(committees?.effective_weight ?? 0),
          weighted_value: committees?.weighted_value == null ? null : Number(committees.weighted_value),
        },
      },
      attendance_weight: Number(attendance?.effective_weight ?? 0),
      committee_weight: Number(committees?.effective_weight ?? 0),
      weighted_attendance: Number(attendance?.weighted_value ?? 0),
      weighted_committee: Number(committees?.weighted_value ?? 0),
      applicable_weight_sum:
        Number(attendance?.applicable ? attendance?.weight ?? 0 : 0) +
        Number(committees?.applicable ? committees?.weight ?? 0 : 0),
      total_score: backendFinalScore == null || Number.isNaN(backendFinalScore)
        ? null
        : Math.round(backendFinalScore * 100) / 100,
    };
  }

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
