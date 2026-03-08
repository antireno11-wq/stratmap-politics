import Image from "next/image";
import Link from "next/link";
import { getParliamentarian } from "../../../lib/api";
import { computeTransparencyScore, scoreTier } from "../../../lib/scoring";

function dataCoverage(p: any) {
  const checks = [
    p.partido && p.partido !== "Sin dato",
    p.region && p.region !== "Sin dato",
    p.distrito_circunscripcion && p.distrito_circunscripcion !== "Sin dato",
    p.sesiones_totales != null && p.sesiones_ausentes != null,
  ];
  return (checks.filter(Boolean).length / checks.length) * 100;
}

export default async function ParliamentarianPage({ params }: { params: { id: string } }) {
  const data = await getParliamentarian(params.id);
  const p = data.parlamentario;
  const score = computeTransparencyScore(p);
  const coverage = dataCoverage(p);
  const attendance = Number(p.asistencia_pct ?? 0);
  const attended = p.sesiones_totales == null || p.sesiones_ausentes == null
    ? null
    : p.sesiones_totales - p.sesiones_ausentes;

  return (
    <main>
      <Link className="top-link" href="/">Volver al listado</Link>

      <section className="hero profile-header">
        <div className="brand-wrap">
          <div>
            <h1 className="profile-name">{p.nombre}</h1>
            <p className="profile-meta">{p.camara} | {p.partido} | {p.periodo}</p>
          </div>
          <Image src="/stratmap-politics-logo.svg" alt="Stratmap Politics" width={90} height={90} className="brand-logo" />
        </div>
      </section>

      <div className="grid kpis">
        <article className="metric-box">
          <div className="metric-label">Score público</div>
          <div className={`metric-value score ${scoreTier(score)}`}>{score.toFixed(2)}</div>
          <div className="progress"><span style={{ width: `${Math.max(0, Math.min(100, score))}%` }} /></div>
        </article>

        <article className="metric-box">
          <div className="metric-label">Asistencia</div>
          <div className="metric-value">{p.asistencia_pct == null ? "N/D" : `${attendance.toFixed(2)}%`}</div>
          <div className="progress"><span style={{ width: `${Math.max(0, Math.min(100, attendance))}%` }} /></div>
        </article>

        <article className="metric-box">
          <div className="metric-label">Cobertura de datos</div>
          <div className="metric-value">{coverage.toFixed(2)}%</div>
          <div className="progress"><span style={{ width: `${coverage}%` }} /></div>
        </article>

        <article className="metric-box">
          <div className="metric-label">Sesiones asistidas</div>
          <div className="metric-value">{attended == null || p.sesiones_totales == null ? "N/D" : `${attended}/${p.sesiones_totales}`}</div>
        </article>

        <article className="metric-box">
          <div className="metric-label">Región</div>
          <div className="metric-value">{p.region}</div>
        </article>

        <article className="metric-box">
          <div className="metric-label">Distrito/Circunscripción</div>
          <div className="metric-value">{p.distrito_circunscripcion}</div>
        </article>
      </div>

      <section className="card chart-card">
        <h3 className="filter-title">Indicadores</h3>
        <div className="score-chart">
          <div className="score-bar-row">
            <div className="score-bar-label">Score público</div>
            <div className="score-bar-track"><span style={{ width: `${Math.max(0, Math.min(100, score))}%` }} /></div>
            <div className="score-bar-value">{score.toFixed(2)}</div>
          </div>
          <div className="score-bar-row">
            <div className="score-bar-label">Asistencia</div>
            <div className="score-bar-track"><span style={{ width: `${Math.max(0, Math.min(100, attendance))}%` }} /></div>
            <div className="score-bar-value">{p.asistencia_pct == null ? "N/D" : `${attendance.toFixed(2)}%`}</div>
          </div>
          <div className="score-bar-row">
            <div className="score-bar-label">Cobertura de datos</div>
            <div className="score-bar-track"><span style={{ width: `${coverage}%` }} /></div>
            <div className="score-bar-value">{coverage.toFixed(2)}%</div>
          </div>
        </div>
      </section>
    </main>
  );
}
