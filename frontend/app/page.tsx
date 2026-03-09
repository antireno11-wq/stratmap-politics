import Image from "next/image";
import Link from "next/link";
import { getParliamentarians } from "../lib/api";
import { computeTransparencyScore, scoreTier } from "../lib/scoring";

type SortBy = "score" | "nombre" | "region" | "asistencia" | "camara";

function sortRows(rows: any[], sortBy: SortBy) {
  const out = [...rows];
  if (sortBy === "score") return out.sort((a, b) => b.score - a.score || a.nombre.localeCompare(b.nombre));
  if (sortBy === "nombre") return out.sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  if (sortBy === "region") return out.sort((a, b) => a.region.localeCompare(b.region, "es"));
  if (sortBy === "asistencia") return out.sort((a, b) => (b.asistencia_pct ?? -1) - (a.asistencia_pct ?? -1));
  return out.sort((a, b) => a.camara.localeCompare(b.camara, "es") || a.nombre.localeCompare(b.nombre, "es"));
}

export default async function Home({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const q = typeof searchParams.q === "string" ? searchParams.q : "";
  const partido = typeof searchParams.partido === "string" ? searchParams.partido : "";
  const region = typeof searchParams.region === "string" ? searchParams.region : "";
  const camara = typeof searchParams.camara === "string" ? searchParams.camara : "";
  const sortBy = (typeof searchParams.sort_by === "string" ? searchParams.sort_by : "score") as SortBy;

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (partido) params.set("partido", partido);
  if (region) params.set("region", region);
  if (camara) params.set("camara", camara);

  const data = await getParliamentarians(params.toString());
  const diputados = data.counters?.DIPUTADO ?? 0;
  const senadores = data.counters?.SENADOR ?? 0;

  const rows = (data.items || []).map((row: any) => ({
    ...row,
    score: computeTransparencyScore(row),
  }));

  const sortedRows = sortRows(rows, sortBy);
  const avgScore = rows.length === 0 ? 0 : rows.reduce((acc: number, row: any) => acc + row.score, 0) / rows.length;
  const top10 = [...sortedRows].slice(0, 10);

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
          <div className="kpi-value">{avgScore.toFixed(2)}</div>
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
          <input name="sort_by" placeholder="Orden (score,nombre,region,asistencia,camara)" defaultValue={sortBy} />
        </form>
      </section>

      <section className="card chart-card">
        <h3 className="filter-title">Top 10 por Score</h3>
        <div className="score-chart">
          {top10.map((row: any) => (
            <div key={row.id} className="score-bar-row">
              <div className="score-bar-label">{row.nombre}</div>
              <div className="score-bar-track">
                <span style={{ width: `${Math.max(1, Math.min(100, row.score))}%` }} />
              </div>
              <div className="score-bar-value">{row.score.toFixed(2)}</div>
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
                  <td className={`score ${scoreTier(row.score)}`}>{row.score.toFixed(2)}</td>
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
