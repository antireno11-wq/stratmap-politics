type ScoreComponent = {
  value?: number | null;
  weight?: number;
  applicable?: boolean;
  effective_weight?: number;
  weighted_value?: number | null;
};

type PublicScoreItem = {
  final_score?: number | null;
  asistencia_pct?: number | null;
  voting_participation_pct?: number | null;
  committee_score?: number | null;
  score_components?: {
    attendance?: ScoreComponent;
    voting?: ScoreComponent;
    committees?: ScoreComponent;
  } | null;
};

function roundMaybe(value: number | null) {
  return value == null || Number.isNaN(value) ? null : Math.round(value * 100) / 100;
}

function clampScore(value: number | null) {
  return value == null || Number.isNaN(value) ? null : Math.max(0, Math.min(100, value));
}

function buildEmptyComponent(value: number | null, weight: number): Required<ScoreComponent> {
  return {
    value,
    weight,
    applicable: value != null,
    effective_weight: 0,
    weighted_value: null,
  };
}

export function computeTransparencyScore(item: PublicScoreItem): number | null {
  const backendScore = item.final_score == null ? null : Number(item.final_score);
  if (backendScore != null && Number.isFinite(backendScore)) {
    return Math.max(0, Math.min(100, backendScore));
  }
  return computePublicScoreBreakdown(item).total_score;
}

export function computePublicScoreBreakdown(item: PublicScoreItem) {
  const backendFinalScore = item.final_score == null ? null : Number(item.final_score);
  const backendComponents = item.score_components ?? null;

  if (backendComponents && typeof backendComponents === "object") {
    const attendance = backendComponents.attendance ?? null;
    const voting = backendComponents.voting ?? null;
    const committees = backendComponents.committees ?? null;

    const attendanceScore = clampScore(attendance?.value == null ? null : Number(attendance.value));
    const votingScore = clampScore(voting?.value == null ? null : Number(voting.value));
    const committeeScore = clampScore(committees?.value == null ? null : Number(committees.value));

    const attendanceWeightedValue =
      attendance?.weighted_value == null ? null : Number(attendance.weighted_value);
    const votingWeightedValue = voting?.weighted_value == null ? null : Number(voting.weighted_value);
    const committeeWeightedValue =
      committees?.weighted_value == null ? null : Number(committees.weighted_value);

    let reconstructedTotal: number | null = null;
    if (backendFinalScore != null && Number.isFinite(backendFinalScore)) {
      reconstructedTotal = clampScore(backendFinalScore);
    } else {
      const weightedParts = [attendanceWeightedValue, votingWeightedValue, committeeWeightedValue].filter(
        (value): value is number => value != null && Number.isFinite(value)
      );
      if (weightedParts.length > 0) {
        reconstructedTotal = clampScore(weightedParts.reduce((acc, value) => acc + value, 0));
      }
    }

    return {
      attendance_score: roundMaybe(attendanceScore),
      voting_score: roundMaybe(votingScore),
      committee_score: roundMaybe(committeeScore),
      components: {
        attendance: {
          value: attendanceScore,
          weight: Number(attendance?.weight ?? 0.5),
          applicable: Boolean(attendance?.applicable),
          effective_weight: Number(attendance?.effective_weight ?? 0),
          weighted_value: attendanceWeightedValue,
        },
        voting: {
          value: votingScore,
          weight: Number(voting?.weight ?? 0.3),
          applicable: Boolean(voting?.applicable),
          effective_weight: Number(voting?.effective_weight ?? 0),
          weighted_value: votingWeightedValue,
        },
        committees: {
          value: committeeScore,
          weight: Number(committees?.weight ?? 0.2),
          applicable: Boolean(committees?.applicable),
          effective_weight: Number(committees?.effective_weight ?? 0),
          weighted_value: committeeWeightedValue,
        },
      },
      attendance_weight: Number(attendance?.effective_weight ?? 0),
      voting_weight: Number(voting?.effective_weight ?? 0),
      committee_weight: Number(committees?.effective_weight ?? 0),
      weighted_attendance: Number(attendanceWeightedValue ?? 0),
      weighted_voting: Number(votingWeightedValue ?? 0),
      weighted_committee: Number(committeeWeightedValue ?? 0),
      applicable_weight_sum:
        Number(attendance?.applicable ? attendance?.weight ?? 0 : 0) +
        Number(voting?.applicable ? voting?.weight ?? 0 : 0) +
        Number(committees?.applicable ? committees?.weight ?? 0 : 0),
      total_score: roundMaybe(reconstructedTotal),
    };
  }

  const attendanceRaw = item.asistencia_pct == null ? null : Number(item.asistencia_pct);
  const votingRaw =
    item.voting_participation_pct == null ? null : Number(item.voting_participation_pct);
  const committeeRaw = item.committee_score == null ? null : Number(item.committee_score);

  const components = {
    attendance: buildEmptyComponent(clampScore(attendanceRaw), 0.5),
    voting: buildEmptyComponent(clampScore(votingRaw), 0.3),
    committees: buildEmptyComponent(clampScore(committeeRaw), 0.2),
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

  return {
    attendance_score: roundMaybe(components.attendance.value),
    voting_score: roundMaybe(components.voting.value),
    committee_score: roundMaybe(components.committees.value),
    components,
    attendance_weight: components.attendance.effective_weight,
    voting_weight: components.voting.effective_weight,
    committee_weight: components.committees.effective_weight,
    weighted_attendance: roundMaybe(components.attendance.weighted_value ?? 0) ?? 0,
    weighted_voting: roundMaybe(components.voting.weighted_value ?? 0) ?? 0,
    weighted_committee: roundMaybe(components.committees.weighted_value ?? 0) ?? 0,
    applicable_weight_sum: Math.round(applicableWeight * 10000) / 10000,
    total_score: roundMaybe(total),
  };
}

export function scoreTier(score: number): "alto" | "medio" | "bajo" {
  if (score >= 80) return "alto";
  if (score >= 60) return "medio";
  return "bajo";
}
