import Link from "next/link";
import { getParliamentarian } from "../../../lib/api";
import { computeTransparencyScore, scoreTier } from "../../../lib/scoring";

export default async function ParliamentarianPage({ params }: { params: { id: string } }) {
  const data = await getParliamentarian(params.id);
  const p = data.parlamentario;
  const score = computeTransparencyScore(p);
  const attended = p.sesiones_totales == null || p.sesiones_ausentes == null
    ? null
    : p.sesiones_totales - p.sesiones_ausentes;

  return (
    <main>
      <Link className="top-link" href="/">Volver al listado</Link>

      <section className="hero profile-header">
        <h1 className="profile-name">{p.nombre}</h1>
        <p className="profile-meta">{p.camara} | {p.partido} | {p.periodo}</p>
      </section>

      <div className="grid kpis">
        <article className="metric-box">
          <div className="metric-label">Score público</div>
          <div className={`metric-value score ${scoreTier(score)}`}>{score.toFixed(2)}</div>
          <div className="progress"><span style={{ width: `${Math.max(0, Math.min(100, score))}%` }} /></div>
        </article>

        <article className="metric-box">
          <div className="metric-label">Asistencia</div>
          <div className="metric-value">{p.asistencia_pct == null ? "N/D" : `${Number(p.asistencia_pct).toFixed(2)}%`}</div>
          <div className="progress">
            <span style={{ width: `${Math.max(0, Math.min(100, Number(p.asistencia_pct ?? 0)))}%` }} />
          </div>
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

        <article className="metric-box">
          <div className="metric-label">Fuente de datos</div>
          <div className="metric-value" style={{ fontSize: "1rem" }}>{p.source}</div>
        </article>
      </div>

      <section className="legend">
        <div className="legend-item blue">Este perfil muestra datos observables y auditables desde fuentes públicas.</div>
        <div className="legend-item red">Los campos en N/D se completan a medida que integramos nuevas fuentes oficiales.</div>
        <div className="legend-item green">Próxima etapa: votaciones, proyectos de ley y transparencia (lobby).</div>
      </section>
    </main>
  );
}
