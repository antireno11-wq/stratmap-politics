import Image from "next/image";
import Link from "next/link";
import { getParliamentarian } from "../../../lib/api";
import { computePublicScoreBreakdown, scoreTier } from "../../../lib/scoring";

function safeValue(value: any) {
  if (value == null) return "N/D";
  const text = String(value).trim();
  return text ? text : "N/D";
}

function safeDate(value: any) {
  if (!value) return "N/D";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "N/D";
  return dt.toLocaleString("es-CL");
}

function safeBiography(value: any) {
  if (value == null) return null;
  const text = String(value).trim();
  return text ? text : null;
}

function pct(value: number | null, digits = 1) {
  if (value == null || Number.isNaN(value)) return "N/D";
  return `${value.toFixed(digits)}%`;
}

function clampPercent(value: number | null) {
  if (value == null || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

function donutSegments(items: Array<{ value: number; color: string }>, radius: number) {
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return items.map((item) => {
    const length = (item.value / 100) * circumference;
    const segment = {
      ...item,
      circumference,
      dashArray: `${length} ${Math.max(circumference - length, 0)}`,
      dashOffset: -offset,
    };
    offset += length;
    return segment;
  });
}

export default async function ParliamentarianPage({ params }: any) {
  const data = await getParliamentarian(params.id);
  const p = data.parlamentario;

  const scoreBreakdown = computePublicScoreBreakdown(p);
  const score = scoreBreakdown.total_score ?? 0;
  const attendance = scoreBreakdown.attendance_score;
  const votingScore = scoreBreakdown.voting_score;
  const committeeScore = scoreBreakdown.committee_score;
  const biography = safeBiography(p.biografia);
  const rawBiographyUrl = String(p.biografia_url ?? "").trim();
  const biographyUrl = !rawBiographyUrl || rawBiographyUrl === "Sin dato" ? null : rawBiographyUrl;

  const totalSessions = p.sesiones_totales == null ? null : Number(p.sesiones_totales);
  const absentSessions = p.sesiones_ausentes == null ? null : Number(p.sesiones_ausentes);
  const attendedSessions =
    totalSessions == null || absentSessions == null ? null : Math.max(0, totalSessions - absentSessions);
  const absentPct =
    totalSessions == null || absentSessions == null || totalSessions <= 0
      ? null
      : (absentSessions / totalSessions) * 100;

  const votesYes = p.votes_yes_total == null ? 0 : Number(p.votes_yes_total);
  const votesNo = p.votes_no_total == null ? 0 : Number(p.votes_no_total);
  const votesAbstention = p.votes_abstention_total == null ? 0 : Number(p.votes_abstention_total);
  const votesTotal = votesYes + votesNo + votesAbstention;

  const donutData = votesTotal > 0
    ? donutSegments(
        [
          { value: (votesYes / votesTotal) * 100, color: "#16a34a" },
          { value: (votesNo / votesTotal) * 100, color: "#dc2626" },
          { value: (votesAbstention / votesTotal) * 100, color: "#f59e0b" },
        ],
        68
      )
    : [];

  const attendanceBars = [
    {
      label: "Asistencia oficial",
      value: attendance,
      tone: "positive",
      caption: totalSessions == null ? "Sin sesiones registradas" : `${attendedSessions ?? 0} de ${totalSessions} sesiones`,
    },
    {
      label: "Sesiones asistidas",
      value:
        totalSessions == null || attendedSessions == null || totalSessions <= 0
          ? null
          : (attendedSessions / totalSessions) * 100,
      tone: "positive",
      caption: attendedSessions == null ? "Sin dato" : `${attendedSessions} asistidas`,
    },
    {
      label: "Inasistencias",
      value: absentPct,
      tone: "negative",
      caption: absentSessions == null ? "Sin dato" : `${absentSessions} ausencias`,
    },
  ];

  return (
    <main>
      <Link className="top-link" href="/">
        Volver al ranking
      </Link>

      <section className="hero profile-hero">
        <div className="brand-wrap">
          <div>
            <span className="hero-kicker">Ficha Individual</span>
            <h1 className="profile-name">{p.nombre}</h1>
            <p className="profile-meta">
              {p.camara} | {p.partido} | {p.periodo}
            </p>
            <div className="profile-pill-row">
              <span className="profile-pill">{p.region}</span>
              <span className="profile-pill">{p.distrito_circunscripcion}</span>
            </div>
          </div>
          <div className="profile-score-panel">
            <Image
              src="/stratmap-politics-logo.svg"
              alt="Stratmap Politics"
              width={82}
              height={82}
              className="brand-logo"
            />
            <div className={`profile-score-value ${scoreTier(score)}`}>
              {scoreBreakdown.total_score == null ? "N/D" : score.toFixed(1)}
            </div>
            <div className="profile-score-caption">Score público</div>
          </div>
        </div>
      </section>

      <section className="dashboard-grid detail-kpi-grid">
        <article className="card metric-panel">
          <div className="metric-label">Asistencia</div>
          <div className="metric-value">{pct(attendance)}</div>
        </article>
        <article className="card metric-panel">
          <div className="metric-label">Participación en votaciones</div>
          <div className="metric-value">{pct(votingScore)}</div>
        </article>
        <article className="card metric-panel">
          <div className="metric-label">Score comisiones</div>
          <div className="metric-value">{committeeScore == null ? "N/D" : committeeScore.toFixed(1)}</div>
        </article>
        <article className="card metric-panel">
          <div className="metric-label">Historial de votos</div>
          <div className="metric-value">{votesTotal > 0 ? votesTotal : "N/D"}</div>
        </article>
      </section>

      <section className="dashboard-grid detail-analytics-grid">
        <article className="card analytics-card">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Asistencia</h3>
              <p className="panel-subtitle">Gráfico de barras para entender rápido presencia y ausencias.</p>
            </div>
          </div>
          <div className="attendance-chart">
            {attendanceBars.map((bar) => (
              <div key={bar.label} className="attendance-row">
                <div className="attendance-copy">
                  <strong>{bar.label}</strong>
                  <span>{bar.caption}</span>
                </div>
                <div className="attendance-bar-track">
                  <span
                    className={bar.tone === "negative" ? "attendance-bar-negative" : "attendance-bar-positive"}
                    style={{ width: `${clampPercent(bar.value)}%` }}
                  />
                </div>
                <div className="attendance-bar-value">{pct(bar.value)}</div>
              </div>
            ))}
          </div>
        </article>

        <article className="card analytics-card">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Histórico de votaciones</h3>
              <p className="panel-subtitle">Circular por opción: A favor, En contra y Abstención.</p>
            </div>
          </div>
          <div className="vote-donut-layout">
            <div className="vote-donut-wrap">
              <svg className="vote-donut" viewBox="0 0 180 180" aria-label="Histórico de votaciones">
                <circle cx="90" cy="90" r="68" className="vote-donut-base" />
                {donutData.map((segment, index) => (
                  <circle
                    key={`${segment.color}-${index}`}
                    cx="90"
                    cy="90"
                    r="68"
                    fill="none"
                    stroke={segment.color}
                    strokeWidth="18"
                    strokeLinecap="butt"
                    strokeDasharray={segment.dashArray}
                    strokeDashoffset={segment.dashOffset}
                    transform="rotate(-90 90 90)"
                  />
                ))}
              </svg>
              <div className="vote-donut-center">
                <strong>{votesTotal > 0 ? votesTotal : "N/D"}</strong>
                <span>votos</span>
              </div>
            </div>

            <div className="vote-legend">
              <div className="vote-legend-item">
                <span className="legend-dot vote-yes" />
                <div>
                  <strong>A favor</strong>
                  <span>
                    {votesYes} {votesTotal > 0 ? `(${((votesYes / votesTotal) * 100).toFixed(1)}%)` : ""}
                  </span>
                </div>
              </div>
              <div className="vote-legend-item">
                <span className="legend-dot vote-no" />
                <div>
                  <strong>En contra</strong>
                  <span>
                    {votesNo} {votesTotal > 0 ? `(${((votesNo / votesTotal) * 100).toFixed(1)}%)` : ""}
                  </span>
                </div>
              </div>
              <div className="vote-legend-item">
                <span className="legend-dot vote-abstention" />
                <div>
                  <strong>Abstención</strong>
                  <span>
                    {votesAbstention}{" "}
                    {votesTotal > 0 ? `(${((votesAbstention / votesTotal) * 100).toFixed(1)}%)` : ""}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section className="dashboard-grid detail-secondary-grid">
        <article className="card analytics-card">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Composición del score</h3>
              <p className="panel-subtitle">
                Los pesos se redistribuyen automáticamente entre componentes aplicables.
              </p>
            </div>
          </div>
          <div className="score-breakdown-list">
            <div className="score-breakdown-row">
              <span>Asistencia</span>
              <strong>{scoreBreakdown.attendance_weight.toFixed(2)}</strong>
            </div>
            <div className="score-breakdown-row">
              <span>Votaciones</span>
              <strong>{scoreBreakdown.voting_weight.toFixed(2)}</strong>
            </div>
            <div className="score-breakdown-row">
              <span>Comisiones</span>
              <strong>{scoreBreakdown.committee_weight.toFixed(2)}</strong>
            </div>
          </div>
          <div className="score-stack-block">
            <div className="score-stack-track">
              <span className="score-segment-att" style={{ width: `${clampPercent(scoreBreakdown.weighted_attendance)}%` }} />
              <span className="score-segment-vot" style={{ width: `${clampPercent(scoreBreakdown.weighted_voting)}%` }} />
              <span className="score-segment-com" style={{ width: `${clampPercent(scoreBreakdown.weighted_committee)}%` }} />
            </div>
            <div className="score-legend-grid">
              <div className="score-legend-item">
                <span className="legend-dot att" />
                <span>Aporte asistencia: {scoreBreakdown.weighted_attendance.toFixed(2)}</span>
              </div>
              <div className="score-legend-item">
                <span className="legend-dot vot" />
                <span>Aporte votaciones: {scoreBreakdown.weighted_voting.toFixed(2)}</span>
              </div>
              <div className="score-legend-item">
                <span className="legend-dot com" />
                <span>Aporte comisiones: {scoreBreakdown.weighted_committee.toFixed(2)}</span>
              </div>
            </div>
          </div>
        </article>

        <article className="card analytics-card">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Biografía</h3>
              <p className="panel-subtitle">Contexto básico del parlamentario y fuente oficial.</p>
            </div>
          </div>
          {biography ? <p className="bio-text">{biography}</p> : <p className="profile-meta">Sin biografía disponible.</p>}
          {biographyUrl ? (
            <p className="profile-meta">
              Fuente:{" "}
              <a href={biographyUrl} target="_blank" rel="noreferrer">
                Perfil oficial
              </a>
            </p>
          ) : null}
        </article>
      </section>

      <section className="card">
        <div className="panel-header">
          <div>
            <h3 className="filter-title">Ficha técnica</h3>
            <p className="panel-subtitle">Metadatos del registro y estado de cobertura.</p>
          </div>
        </div>
        <div className="detail-grid">
          <div className="detail-item">
            <div className="detail-label">ID interno</div>
            <div className="detail-value">{safeValue(p.id)}</div>
          </div>
          <div className="detail-item">
            <div className="detail-label">ID externo</div>
            <div className="detail-value">{safeValue(p.external_id)}</div>
          </div>
          <div className="detail-item">
            <div className="detail-label">Fuente</div>
            <div className="detail-value">{safeValue(p.source)}</div>
          </div>
          <div className="detail-item">
            <div className="detail-label">Última actualización</div>
            <div className="detail-value">{safeDate(p.updated_at)}</div>
          </div>
          <div className="detail-item">
            <div className="detail-label">Creación del registro</div>
            <div className="detail-value">{safeDate(p.created_at)}</div>
          </div>
          <div className="detail-item">
            <div className="detail-label">Sesiones asistidas</div>
            <div className="detail-value">
              {attendedSessions == null || totalSessions == null ? "N/D" : `${attendedSessions}/${totalSessions}`}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
