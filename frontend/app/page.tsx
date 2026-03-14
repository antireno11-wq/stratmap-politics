import Image from "next/image";
import Link from "next/link";
import { getParliamentarians } from "../lib/api";
import { computeTransparencyScore, scoreTier } from "../lib/scoring";

type SortBy =
  | "score"
  | "nombre"
  | "camara"
  | "partido"
  | "distrito"
  | "region"
  | "asistencia"
  | "sesiones";
type SortOrder = "asc" | "desc";

function isSortBy(value: string): value is SortBy {
  return ["score", "nombre", "camara", "partido", "distrito", "region", "asistencia", "sesiones"].includes(value);
}

function isSortOrder(value: string): value is SortOrder {
  return value === "asc" || value === "desc";
}

function defaultOrderFor(sortBy: SortBy): SortOrder {
  return ["nombre", "camara", "partido", "distrito", "region"].includes(sortBy) ? "asc" : "desc";
}

function normalizeText(value: unknown) {
  const text = String(value ?? "").trim();
  if (!text || text.toLowerCase() === "sin dato") return "";
  return text;
}

function compareText(a: unknown, b: unknown) {
  const va = normalizeText(a);
  const vb = normalizeText(b);
  if (!va && !vb) return 0;
  if (!va) return 1;
  if (!vb) return -1;
  return va.localeCompare(vb, "es", { sensitivity: "base" });
}

function compareNullableNumber(a: unknown, b: unknown) {
  const na = a == null ? null : Number(a);
  const nb = b == null ? null : Number(b);
  const va = na != null && Number.isFinite(na) ? na : null;
  const vb = nb != null && Number.isFinite(nb) ? nb : null;

  if (va == null && vb == null) return 0;
  if (va == null) return 1;
  if (vb == null) return -1;
  return va - vb;
}

function sortRows(rows: any[], sortBy: SortBy, sortOrder: SortOrder) {
  const out = [...rows];
  const direction = sortOrder === "asc" ? 1 : -1;

  return out.sort((a, b) => {
    let result = 0;
    if (sortBy === "score") result = compareNullableNumber(a.score, b.score);
    if (sortBy === "nombre") result = compareText(a.nombre, b.nombre);
    if (sortBy === "camara") result = compareText(a.camara, b.camara);
    if (sortBy === "partido") result = compareText(a.partido, b.partido);
    if (sortBy === "distrito") result = compareText(a.distrito_circunscripcion, b.distrito_circunscripcion);
    if (sortBy === "region") result = compareText(a.region, b.region);
    if (sortBy === "asistencia") result = compareNullableNumber(a.asistencia_pct, b.asistencia_pct);
    if (sortBy === "sesiones") result = compareNullableNumber(a.sesiones_totales, b.sesiones_totales);

    if (result === 0) {
      return compareText(a.nombre, b.nombre);
    }
    return result * direction;
  });
}

export default async function Home({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const q = typeof searchParams.q === "string" ? searchParams.q : "";
  const partido = typeof searchParams.partido === "string" ? searchParams.partido : "";
  const region = typeof searchParams.region === "string" ? searchParams.region : "";
  const camara = typeof searchParams.camara === "string" ? searchParams.camara : "";
  const rawSortBy = typeof searchParams.sort_by === "string" ? searchParams.sort_by : "score";
  const sortBy: SortBy = isSortBy(rawSortBy) ? rawSortBy : "score";
  const rawSortOrder = typeof searchParams.sort_order === "string" ? searchParams.sort_order : defaultOrderFor(sortBy);
  const sortOrder: SortOrder = isSortOrder(rawSortOrder) ? rawSortOrder : defaultOrderFor(sortBy);

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (partido) params.set("partido", partido);
  if (region) params.set("region", region);
  if (camara) params.set("camara", camara);
  params.set("sort_by", sortBy);
  params.set("sort_order", sortOrder);

  const data = await getParliamentarians(params.toString());
  const diputados = data.counters?.DIPUTADO ?? 0;
  const senadores = data.counters?.SENADOR ?? 0;

  const rows = (data.items || []).map((row: any) => ({
    ...row,
    score: computeTransparencyScore(row),
  }));

  const sortedRows = sortRows(rows, sortBy, sortOrder);
  const rowsWithScore = rows.filter((row: any) => row.score != null);
  const avgScore = rowsWithScore.length === 0
    ? null
    : rowsWithScore.reduce((acc: number, row: any) => acc + row.score, 0) / rowsWithScore.length;
  const top10 = sortRows(rowsWithScore, "score", "desc").slice(0, 10);

  return (
    <main>
      <section className="hero">
        <div className="brand-wrap">
          <div>
            <h1>Stratmap Politics</h1>
            <p>Monitor legislativo ciudadano para Chile: parlamentarios, asistencia histórica y score comparativo.</p>
          </div>
          <Image
            src="/stratmap-politics-logo.svg"
            alt="Stratmap Politics"
            width={110}
            height={110}
            className="brand-logo"
            priority
          />
        </div>
      </section>

      <div className="grid kpis">
        <div className="card">
          <div className="kpi-value">{data.total_global ?? data.count}</div>
          <div className="kpi-label">Total parlamentarios</div>
        </div>
        <div className="card">
          <div className="kpi-value">{avgScore == null ? "N/D" : avgScore.toFixed(2)}</div>
          <div className="kpi-label">Score promedio</div>
        </div>
        <div className="card">
          <div className="kpi-value">{diputados}</div>
          <div className="kpi-label">Diputados</div>
        </div>
        <div className="card">
          <div className="kpi-value">{senadores}</div>
          <div className="kpi-label">Senadores</div>
        </div>
      </div>

      <section className="card filter-wrap">
        <h3 className="filter-title">Filtros y Orden</h3>
        <form className="filter-bar" method="GET">
          <input name="q" placeholder="Buscar nombre" defaultValue={q} />
          <input name="partido" placeholder="Partido" defaultValue={partido} />
          <input name="region" placeholder="Región" defaultValue={region} />
          <input name="camara" placeholder="Cámara (DIPUTADO o SENADOR)" defaultValue={camara} />
          <select name="sort_by" defaultValue={sortBy}>
            <option value="score">Score</option>
            <option value="nombre">Nombre</option>
            <option value="camara">Cámara</option>
            <option value="partido">Partido</option>
            <option value="distrito">Distrito/Circunscripción</option>
            <option value="region">Región</option>
            <option value="asistencia">Asistencia</option>
            <option value="sesiones">Sesiones</option>
          </select>
          <select name="sort_order" defaultValue={sortOrder}>
            <option value="asc">Ascendente</option>
            <option value="desc">Descendente</option>
          </select>
          <button className="filter-submit" type="submit">Aplicar</button>
        </form>
      </section>

      <section className="card chart-card">
        <h3 className="filter-title">Top 10 por Score</h3>
        <div className="score-chart">
          {top10.map((row: any) => (
            <div key={row.id} className="score-bar-row">
              <div className="score-bar-label">{row.nombre}</div>
              <div className="score-bar-track">
                <span style={{ width: `${Math.max(1, Math.min(100, Number(row.score ?? 0))) }%` }} />
              </div>
              <div className="score-bar-value">{row.score == null ? "N/D" : row.score.toFixed(2)}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="card table-card">
        <p className="profile-meta">Haz clic en el nombre para abrir la ficha completa del parlamentario.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Score</th>
                <th>Nombre</th>
                <th>Cámara</th>
                <th>Partido</th>
                <th>Distrito/Circunscripción</th>
                <th>Región</th>
                <th>Asistencia %</th>
                <th>Sesiones</th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row: any) => (
                <tr key={row.id}>
                  <td className={row.score == null ? "" : `score ${scoreTier(row.score)}`}>
                    {row.score == null ? "N/D" : row.score.toFixed(2)}
                  </td>
                  <td className="row-name"><Link href={`/parliamentarians/${row.id}`} title="Ver ficha completa">{row.nombre}</Link></td>
                  <td><span className="chamber-pill">{row.camara}</span></td>
                  <td>{row.partido}</td>
                  <td>{row.distrito_circunscripcion}</td>
                  <td>{row.region}</td>
                  <td>{row.asistencia_pct == null ? "N/D" : Number(row.asistencia_pct).toFixed(2)}</td>
                  <td>
                    {row.sesiones_totales == null || row.sesiones_ausentes == null
                      ? "N/D"
                      : `${row.sesiones_totales - row.sesiones_ausentes}/${row.sesiones_totales}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
