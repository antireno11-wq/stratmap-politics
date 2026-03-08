import Link from "next/link";
import { getParliamentarians } from "../lib/api";
import { computeTransparencyScore, scoreTier } from "../lib/scoring";

export default async function Home({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const q = typeof searchParams.q === "string" ? searchParams.q : "";
  const partido = typeof searchParams.partido === "string" ? searchParams.partido : "";
  const region = typeof searchParams.region === "string" ? searchParams.region : "";
  const camara = typeof searchParams.camara === "string" ? searchParams.camara : "";

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

  const avgScore = rows.length === 0 ? 0 : rows.reduce((acc: number, row: any) => acc + row.score, 0) / rows.length;

  return (
    <main>
      <section className="hero">
        <h1>Stratmap Politics</h1>
        <p>Monitor legislativo ciudadano para Chile: parlamentarios, asistencia y score comparativo.</p>
      </section>

      <div className="grid kpis">
        <div className="card">
          <div className="kpi-value">{data.total_global ?? data.count}</div>
          <div className="kpi-label">Total parlamentarios</div>
        </div>
        <div className="card">
          <div className="kpi-value">{diputados}</div>
          <div className="kpi-label">Diputados</div>
        </div>
        <div className="card">
          <div className="kpi-value">{senadores}</div>
          <div className="kpi-label">Senadores</div>
        </div>
        <div className="card">
          <div className="kpi-value">{avgScore.toFixed(2)}</div>
          <div className="kpi-label">Score promedio</div>
        </div>
      </div>

      <section className="card filter-wrap">
        <h3 className="filter-title">Filtros</h3>
        <form className="filter-bar" method="GET">
          <input name="q" placeholder="Buscar nombre" defaultValue={q} />
          <input name="partido" placeholder="Partido" defaultValue={partido} />
          <input name="region" placeholder="Región" defaultValue={region} />
          <input name="camara" placeholder="Cámara (DIPUTADO o SENADOR)" defaultValue={camara} />
        </form>
      </section>

      <section className="card table-card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Cámara</th>
                <th>Partido</th>
                <th>Distrito/Circunscripción</th>
                <th>Región</th>
                <th>Asistencia %</th>
                <th>Sesiones</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: any) => (
                <tr key={row.id}>
                  <td className="row-name"><Link href={`/parliamentarians/${row.id}`}>{row.nombre}</Link></td>
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
                  <td className={`score ${scoreTier(row.score)}`}>{row.score.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="legend">
        <div className="legend-item blue">Score = 80% asistencia + 20% completitud de datos públicos.</div>
        <div className="legend-item red">El score actual es preliminar y se refina al integrar votaciones/proyectos/lobby.</div>
        <div className="legend-item green">Objetivo: comparar desempeño con criterios verificables y trazables.</div>
      </section>
    </main>
  );
}
