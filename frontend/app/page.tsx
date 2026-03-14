import Image from "next/image";
import Link from "next/link";
import { getParliamentarians } from "../lib/api";
import { computeTransparencyScore, scoreTier } from "../lib/scoring";

function normalizeText(value: unknown) {
  const text = String(value ?? "").trim();
  if (!text || text.toLowerCase() === "sin dato") return "";
  return text;
}

function isNonEmptyString(value: string): value is string {
  return value.length > 0;
}

function compareText(a: string, b: string) {
  return a.localeCompare(b, "es", { sensitivity: "base" });
}

function formatMaybeNumber(value: number | null, digits = 2) {
  if (value == null || Number.isNaN(value)) return "N/D";
  return value.toFixed(digits);
}

function clampPercent(value: number | null) {
  if (value == null || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

function averageOf(values: Array<number | null>) {
  const clean = values.filter((value): value is number => value != null && Number.isFinite(value));
  if (!clean.length) return null;
  return clean.reduce((acc, value) => acc + value, 0) / clean.length;
}

function rankRows(rows: any[], order: "asc" | "desc") {
  const scored = rows.filter((row) => row.score != null);
  const sorted = [...scored].sort((a, b) => {
    const diff = Number(a.score) - Number(b.score);
    if (diff === 0) return compareText(String(a.nombre ?? ""), String(b.nombre ?? ""));
    return order === "desc" ? -diff : diff;
  });
  return sorted.slice(0, 5);
}

export default async function Home({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const selectedParty = typeof searchParams.partido === "string" ? searchParams.partido : "";
  const selectedRegion = typeof searchParams.region === "string" ? searchParams.region : "";

  const data = await getParliamentarians("limit=1000&unique_people=true");
  const baseRows = (data.items || []).map((row: any) => ({
    ...row,
    score: computeTransparencyScore(row),
  }));

  const partyOptions = [
    ...new Set(baseRows.map((row: any) => normalizeText(row.partido)).filter(isNonEmptyString)),
  ].sort(compareText);
  const regionOptions = [
    ...new Set(baseRows.map((row: any) => normalizeText(row.region)).filter(isNonEmptyString)),
  ].sort(compareText);

  const filteredRows = baseRows.filter((row: any) => {
    if (selectedParty && normalizeText(row.partido) !== selectedParty) return false;
    if (selectedRegion && normalizeText(row.region) !== selectedRegion) return false;
    return true;
  });

  const topFive = rankRows(filteredRows, "desc");
  const bottomFive = rankRows(filteredRows, "asc");
  const avgScore = averageOf(filteredRows.map((row: any) => row.score ?? null));
  const avgAttendance = averageOf(
    filteredRows.map((row: any) => (row.asistencia_pct == null ? null : Number(row.asistencia_pct)))
  );
  const avgVoting = averageOf(
    filteredRows.map((row: any) =>
      row.voting_participation_pct == null ? null : Number(row.voting_participation_pct)
    )
  );
  const highPerformers = filteredRows.filter((row: any) => row.score != null && row.score >= 80).length;
  const lowPerformers = filteredRows.filter((row: any) => row.score != null && row.score < 60).length;
  const tableRows = [...filteredRows].sort((a, b) => {
    const aScore = a.score == null ? -1 : Number(a.score);
    const bScore = b.score == null ? -1 : Number(b.score);
    if (aScore === bScore) return compareText(String(a.nombre ?? ""), String(b.nombre ?? ""));
    return bScore - aScore;
  });

  return (
    <main>
      <section className="hero dashboard-hero">
        <div className="brand-wrap">
          <div>
            <span className="hero-kicker">Monitoreo Legislativo</span>
            <h1>Ranking público de desempeño parlamentario</h1>
            <p>
              Un dashboard de KPIs para detectar rápido quién está arriba, quién está abajo y cómo se
              comporta cada bancada por territorio.
            </p>
          </div>
          <Image
            src="/stratmap-politics-logo.svg"
            alt="Stratmap Politics"
            width={118}
            height={118}
            className="brand-logo"
            priority
          />
        </div>
      </section>

      <section className="dashboard-grid dashboard-overview">
        <article className="card kpi-panel">
          <div className="kpi-label">Parlamentarios visibles</div>
          <div className="kpi-value">{filteredRows.length}</div>
          <div className="kpi-foot">Sobre {data.total_global ?? data.count} registros públicos</div>
        </article>
        <article className="card kpi-panel">
          <div className="kpi-label">Score promedio</div>
          <div className="kpi-value">{formatMaybeNumber(avgScore)}</div>
          <div className="kpi-foot kpi-good">Verde = mejor lectura global</div>
        </article>
        <article className="card kpi-panel">
          <div className="kpi-label">Asistencia promedio</div>
          <div className="kpi-value">{avgAttendance == null ? "N/D" : `${avgAttendance.toFixed(2)}%`}</div>
          <div className="kpi-foot">Promedio sobre quienes tienen dato</div>
        </article>
        <article className="card kpi-panel">
          <div className="kpi-label">Participación en votaciones</div>
          <div className="kpi-value">{avgVoting == null ? "N/D" : `${avgVoting.toFixed(2)}%`}</div>
          <div className="kpi-foot">No reemplaza asistencia, la complementa</div>
        </article>
      </section>

      <section className="dashboard-grid dashboard-main">
        <article className="card filter-panel">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Filtros</h3>
              <p className="panel-subtitle">Cruza partido y región para rehacer el ranking en tiempo real.</p>
            </div>
          </div>
          <form className="dashboard-filters" method="GET">
            <label className="filter-field">
              <span>Partido</span>
              <select name="partido" defaultValue={selectedParty}>
                <option value="">Todos</option>
                {partyOptions.map((party) => (
                  <option key={party} value={party}>
                    {party}
                  </option>
                ))}
              </select>
            </label>
            <label className="filter-field">
              <span>Región</span>
              <select name="region" defaultValue={selectedRegion}>
                <option value="">Todas</option>
                {regionOptions.map((region) => (
                  <option key={region} value={region}>
                    {region}
                  </option>
                ))}
              </select>
            </label>
            <div className="filter-actions">
              <button className="filter-submit" type="submit">
                Actualizar ranking
              </button>
              <Link className="filter-reset" href="/">
                Limpiar filtros
              </Link>
            </div>
          </form>
          <div className="status-grid">
            <div className="status-pill positive">
              <strong>{highPerformers}</strong>
              <span>sobre 80 puntos</span>
            </div>
            <div className="status-pill negative">
              <strong>{lowPerformers}</strong>
              <span>bajo 60 puntos</span>
            </div>
          </div>
        </article>

        <article className="card rank-card rank-card-positive">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Top 5</h3>
              <p className="panel-subtitle">Los mejores calificados dentro del filtro activo.</p>
            </div>
          </div>
          <div className="rank-list">
            {topFive.map((row: any, index: number) => (
              <Link key={row.id} href={`/parliamentarians/${row.id}`} className="rank-item">
                <div className="rank-order">{index + 1}</div>
                <div className="rank-copy">
                  <div className="rank-name">{row.nombre}</div>
                  <div className="rank-meta">
                    {row.partido} | {row.region}
                  </div>
                  <div className="rank-bar">
                    <span style={{ width: `${clampPercent(Number(row.score))}%` }} />
                  </div>
                </div>
                <div className={`rank-score ${scoreTier(Number(row.score))}`}>{Number(row.score).toFixed(1)}</div>
              </Link>
            ))}
          </div>
        </article>

        <article className="card rank-card rank-card-negative">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Bottom 5</h3>
              <p className="panel-subtitle">Los puntajes más bajos para detectar zonas de alerta.</p>
            </div>
          </div>
          <div className="rank-list">
            {bottomFive.map((row: any, index: number) => (
              <Link key={row.id} href={`/parliamentarians/${row.id}`} className="rank-item">
                <div className="rank-order">{index + 1}</div>
                <div className="rank-copy">
                  <div className="rank-name">{row.nombre}</div>
                  <div className="rank-meta">
                    {row.partido} | {row.region}
                  </div>
                  <div className="rank-bar rank-bar-negative">
                    <span style={{ width: `${clampPercent(Number(row.score))}%` }} />
                  </div>
                </div>
                <div className={`rank-score ${scoreTier(Number(row.score))}`}>{Number(row.score).toFixed(1)}</div>
              </Link>
            ))}
          </div>
        </article>
      </section>

      <section className="dashboard-grid dashboard-secondary">
        <article className="card ranking-chart-card">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Lectura rápida del ranking</h3>
              <p className="panel-subtitle">Las barras dejan claro el desempeño sin depender del texto.</p>
            </div>
          </div>
          <div className="score-chart dashboard-score-chart">
            {tableRows.slice(0, 10).map((row: any) => (
              <div key={row.id} className="score-bar-row">
                <div className="score-bar-label">
                  <strong>{row.nombre}</strong>
                  <span>{row.partido}</span>
                </div>
                <div className="score-bar-track tone-track">
                  <span
                    className={row.score != null && row.score >= 80 ? "tone-positive" : row.score != null && row.score < 60 ? "tone-negative" : "tone-neutral"}
                    style={{ width: `${clampPercent(row.score)}%` }}
                  />
                </div>
                <div className={`score-bar-value ${row.score == null ? "" : `score ${scoreTier(Number(row.score))}`}`}>
                  {formatMaybeNumber(row.score)}
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="card table-card">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Listado filtrado</h3>
              <p className="panel-subtitle">Haz clic en cualquier nombre para abrir la ficha individual.</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Score</th>
                  <th>Nombre</th>
                  <th>Partido</th>
                  <th>Región</th>
                  <th>Asistencia</th>
                  <th>Votaciones</th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row: any) => (
                  <tr key={row.id}>
                    <td className={row.score == null ? "" : `score ${scoreTier(Number(row.score))}`}>
                      {formatMaybeNumber(row.score)}
                    </td>
                    <td className="row-name">
                      <Link href={`/parliamentarians/${row.id}`}>{row.nombre}</Link>
                    </td>
                    <td>{row.partido}</td>
                    <td>{row.region}</td>
                    <td>{row.asistencia_pct == null ? "N/D" : `${Number(row.asistencia_pct).toFixed(2)}%`}</td>
                    <td>
                      {row.voting_participation_pct == null
                        ? "N/D"
                        : `${Number(row.voting_participation_pct).toFixed(2)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </main>
  );
}
