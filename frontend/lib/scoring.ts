export function computeTransparencyScore(item: {
  asistencia_pct?: number | null;
  sesiones_totales?: number | null;
  sesiones_ausentes?: number | null;
  partido?: string | null;
  distrito_circunscripcion?: string | null;
  region?: string | null;
}): number {
  const asistencia = item.asistencia_pct == null ? 0 : Number(item.asistencia_pct);
  const attendanceScore = Math.max(0, Math.min(100, asistencia));

  const hasParty = !!item.partido && item.partido !== "Sin dato";
  const hasDistrict = !!item.distrito_circunscripcion && item.distrito_circunscripcion !== "Sin dato";
  const hasRegion = !!item.region && item.region !== "Sin dato";
  const hasSessions = item.sesiones_totales != null && item.sesiones_ausentes != null;

  const coverageRaw = [hasParty, hasDistrict, hasRegion, hasSessions].filter(Boolean).length;
  const coverageScore = (coverageRaw / 4) * 100;

  const total = (attendanceScore * 0.8) + (coverageScore * 0.2);
  return Math.round(total * 100) / 100;
}

export function scoreTier(score: number): "alto" | "medio" | "bajo" {
  if (score >= 80) return "alto";
  if (score >= 60) return "medio";
  return "bajo";
}
