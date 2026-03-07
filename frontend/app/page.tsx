import Link from "next/link";
import { getRanking } from "../lib/api";

export default async function Home({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const q = typeof searchParams.q === "string" ? searchParams.q : "";
  const partido = typeof searchParams.partido === "string" ? searchParams.partido : "";
  const region = typeof searchParams.region === "string" ? searchParams.region : "";
  const comision = typeof searchParams.comision === "string" ? searchParams.comision : "";

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (partido) params.set("partido", partido);
  if (region) params.set("region", region);
  if (comision) params.set("comision", comision);

  const data = await getRanking(params.toString());
  const topScore = data.items?.[0]?.score ?? 0;

  return (
    <main>
      <h1>Stratmap Politics</h1>
      <p className="subtitle">Ranking de transparencia y actividad de diputados en Chile</p>

      <div className="grid kpis">
        <div className="card"><strong>{data.count}</strong><br />Diputados listados</div>
        <div className="card"><strong>{Number(topScore).toFixed(2)}</strong><br />Top score</div>
      </div>

      <form className="filter-bar" method="GET" style={{ marginTop: "1rem" }}>
        <input name="q" placeholder="Buscar diputado" defaultValue={q} />
        <input name="partido" placeholder="Partido" defaultValue={partido} />
        <input name="region" placeholder="Region" defaultValue={region} />
        <input name="comision" placeholder="Comision" defaultValue={comision} />
      </form>

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Diputado</th>
              <th>Partido</th>
              <th>Distrito</th>
              <th>Score</th>
              <th>Asistencia %</th>
              <th>Proyectos</th>
            </tr>
          </thead>
          <tbody>
            {(data.items || []).map((row: any) => (
              <tr key={row.id}>
                <td><Link href={`/deputies/${row.id}`}>{row.nombre}</Link></td>
                <td>{row.partido}</td>
                <td>{row.distrito}</td>
                <td className="score">{Number(row.score).toFixed(2)}</td>
                <td>{Number(row.asistencia_pct).toFixed(2)}</td>
                <td>{row.proyectos_presentados}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
