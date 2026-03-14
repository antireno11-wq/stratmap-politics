import Link from "next/link";
import Image from "next/image";

import { getParliamentarians } from "../../lib/api";

function normalizeText(value: unknown) {
  const text = String(value ?? "").trim();
  if (!text || text.toLowerCase() === "sin dato") return "";
  return text;
}

function compareText(a: unknown, b: unknown) {
  return String(a ?? "").localeCompare(String(b ?? ""), "es", { sensitivity: "base" });
}

function uniqueSortedStrings(values: unknown[]): string[] {
  const out = Array.from(
    new Set(
      values
        .map((value) => normalizeText(value))
        .filter((value): value is string => value.length > 0)
    )
  );
  return out.sort((a, b) => compareText(a, b));
}

function pct(value: number | null) {
  if (value == null || Number.isNaN(value)) return "N/D";
  return `${value.toFixed(2)}%`;
}

function averageOf(values: Array<number | null>) {
  const clean = values.filter((value): value is number => value != null && Number.isFinite(value));
  if (!clean.length) return null;
  return clean.reduce((acc, value) => acc + value, 0) / clean.length;
}

function clampPercent(value: number | null) {
  if (value == null || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

function attendanceTone(value: number | null) {
  if (value == null) return "tone-neutral";
  if (value >= 95) return "tone-positive";
  if (value < 85) return "tone-negative";
  return "tone-neutral";
}

export default async function AttendancePage({ searchParams }: any) {
  const selectedCamera = typeof searchParams.camara === "string" ? searchParams.camara : "";
  const selectedParty = typeof searchParams.partido === "string" ? searchParams.partido : "";
  const selectedRegion = typeof searchParams.region === "string" ? searchParams.region : "";

  const data = await getParliamentarians("limit=1000&unique_people=true");
  const baseRows = (data.items || [])
    .map((row: any) => ({
      ...row,
      attendance: row.asistencia_pct == null ? null : Number(row.asistencia_pct),
      sesionesTotales: row.sesiones_totales == null ? null : Number(row.sesiones_totales),
      sesionesAusentes: row.sesiones_ausentes == null ? null : Number(row.sesiones_ausentes),
    }))
    .filter((row: any) => row.attendance != null);

  const partyOptions = uniqueSortedStrings(baseRows.map((row: any) => row.partido));
  const regionOptions = uniqueSortedStrings(baseRows.map((row: any) => row.region));

  const filteredRows = baseRows.filter((row: any) => {
    if (selectedCamera && row.camara !== selectedCamera) return false;
    if (selectedParty && normalizeText(row.partido) !== selectedParty) return false;
    if (selectedRegion && normalizeText(row.region) !== selectedRegion) return false;
    return true;
  });

  const orderedRows = [...filteredRows].sort((a, b) => {
    const diff = Number(b.attendance) - Number(a.attendance);
    if (diff === 0) return compareText(a.nombre, b.nombre);
    return diff;
  });

  const topFive = orderedRows.slice(0, 5);
  const bottomFive = [...orderedRows].reverse().slice(0, 5).reverse();
  const avgAttendance = averageOf(orderedRows.map((row: any) => row.attendance));
  const deputiesCount = orderedRows.filter((row: any) => row.camara === "DIPUTADO").length;
  const senatorsCount = orderedRows.filter((row: any) => row.camara === "SENADOR").length;

  return (
    <main>
      <section className="hero dashboard-hero">
        <div className="brand-wrap">
          <div>
            <span className="hero-kicker">Asistencia Congreso</span>
            <h1>Monitoreo de asistencia parlamentaria</h1>
            <p>
              Una vista dedicada para revisar asistencia oficial, sesiones registradas y ausencias del Congreso
              sin pasar por el ranking general.
            </p>
            <div className="hero-actions">
              <Link className="hero-action-link hero-action-link-primary" href="/">
                Volver al ranking general
              </Link>
              <Link className="hero-action-link" href="/attendance">
                Reiniciar filtros
              </Link>
            </div>
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
          <div className="kpi-label">Parlamentarios con asistencia</div>
          <div className="kpi-value">{orderedRows.length}</div>
          <div className="kpi-foot">Solo perfiles con asistencia oficial disponible</div>
        </article>
        <article className="card kpi-panel">
          <div className="kpi-label">Asistencia promedio</div>
          <div className="kpi-value">{pct(avgAttendance)}</div>
          <div className="kpi-foot kpi-good">Lectura consolidada del filtro activo</div>
        </article>
        <article className="card kpi-panel">
          <div className="kpi-label">Diputados visibles</div>
          <div className="kpi-value">{deputiesCount}</div>
          <div className="kpi-foot">Dentro del filtro actual</div>
        </article>
        <article className="card kpi-panel">
          <div className="kpi-label">Senadores visibles</div>
          <div className="kpi-value">{senatorsCount}</div>
          <div className="kpi-foot">Dentro del filtro actual</div>
        </article>
      </section>

      <section className="dashboard-grid dashboard-main">
        <article className="card filter-panel">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Filtros de asistencia</h3>
              <p className="panel-subtitle">Aísla cámara, partido o región para reconstruir la tabla.</p>
            </div>
          </div>
          <form className="dashboard-filters" method="GET">
            <label className="filter-field">
              <span>Cámara</span>
              <select name="camara" defaultValue={selectedCamera}>
                <option value="">Ambas</option>
                <option value="DIPUTADO">Diputados</option>
                <option value="SENADOR">Senadores</option>
              </select>
            </label>
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
                Actualizar asistencia
              </button>
              <Link className="filter-reset" href="/attendance">
                Limpiar filtros
              </Link>
            </div>
          </form>
        </article>

        <article className="card rank-card rank-card-positive">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Top asistencia</h3>
              <p className="panel-subtitle">Los registros más altos dentro del filtro activo.</p>
            </div>
          </div>
          <div className="rank-list">
            {topFive.map((row: any, index: number) => (
              <Link key={row.id} href={`/parliamentarians/${row.id}`} className="rank-item">
                <div className="rank-order">{index + 1}</div>
                <div className="rank-copy">
                  <div className="rank-name">{row.nombre}</div>
                  <div className="rank-meta">
                    {row.camara} | {row.partido}
                  </div>
                  <div className="rank-bar">
                    <span style={{ width: `${clampPercent(row.attendance)}%` }} />
                  </div>
                </div>
                <div className="rank-score alto">{pct(row.attendance)}</div>
              </Link>
            ))}
          </div>
        </article>

        <article className="card rank-card rank-card-negative">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Bottom asistencia</h3>
              <p className="panel-subtitle">Los niveles más bajos para detectar alertas rápidas.</p>
            </div>
          </div>
          <div className="rank-list">
            {bottomFive.map((row: any, index: number) => (
              <Link key={row.id} href={`/parliamentarians/${row.id}`} className="rank-item">
                <div className="rank-order">{index + 1}</div>
                <div className="rank-copy">
                  <div className="rank-name">{row.nombre}</div>
                  <div className="rank-meta">
                    {row.camara} | {row.partido}
                  </div>
                  <div className="rank-bar rank-bar-negative">
                    <span style={{ width: `${clampPercent(row.attendance)}%` }} />
                  </div>
                </div>
                <div className="rank-score bajo">{pct(row.attendance)}</div>
              </Link>
            ))}
          </div>
        </article>
      </section>

      <section className="dashboard-grid dashboard-secondary">
        <article className="card ranking-chart-card">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Lectura rápida</h3>
              <p className="panel-subtitle">Top 10 por asistencia con una barra visual simple.</p>
            </div>
          </div>
          <div className="score-chart dashboard-score-chart">
            {orderedRows.slice(0, 10).map((row: any) => (
              <div key={row.id} className="score-bar-row">
                <div className="score-bar-label">
                  <strong>{row.nombre}</strong>
                  <span>
                    {row.camara} | {row.region}
                  </span>
                </div>
                <div className="score-bar-track tone-track">
                  <span className={attendanceTone(row.attendance)} style={{ width: `${clampPercent(row.attendance)}%` }} />
                </div>
                <div className="score-bar-value">{pct(row.attendance)}</div>
              </div>
            ))}
          </div>
        </article>

        <article className="card table-card">
          <div className="panel-header">
            <div>
              <h3 className="filter-title">Tabla completa de asistencia</h3>
              <p className="panel-subtitle">Haz clic en el nombre para abrir la ficha individual.</p>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Asistencia</th>
                  <th>Nombre</th>
                  <th>Cámara</th>
                  <th>Partido</th>
                  <th>Región</th>
                  <th>Sesiones</th>
                  <th>Ausencias</th>
                </tr>
              </thead>
              <tbody>
                {orderedRows.map((row: any) => (
                  <tr key={row.id}>
                    <td className={row.attendance >= 95 ? "score alto" : row.attendance < 85 ? "score bajo" : "score medio"}>
                      {pct(row.attendance)}
                    </td>
                    <td className="row-name">
                      <Link href={`/parliamentarians/${row.id}`}>{row.nombre}</Link>
                    </td>
                    <td>{row.camara}</td>
                    <td>{row.partido}</td>
                    <td>{row.region}</td>
                    <td>{row.sesionesTotales == null ? "N/D" : row.sesionesTotales}</td>
                    <td>{row.sesionesAusentes == null ? "N/D" : row.sesionesAusentes}</td>
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
