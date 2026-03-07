import Link from "next/link";
import { getParliamentarians } from "../lib/api";

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

  return (
    <main>
      <h1>Stratmap Politics</h1>
      <p className="subtitle">Base pública de diputados y senadores en Chile</p>

      <div className="grid kpis">
        <div className="card"><strong>{data.count}</strong><br />Registros filtrados</div>
        <div className="card"><strong>{diputados}</strong><br />Diputados</div>
        <div className="card"><strong>{senadores}</strong><br />Senadores</div>
      </div>

      <form className="filter-bar" method="GET" style={{ marginTop: "1rem" }}>
        <input name="q" placeholder="Buscar nombre" defaultValue={q} />
        <input name="partido" placeholder="Partido" defaultValue={partido} />
        <input name="region" placeholder="Region" defaultValue={region} />
        <input name="camara" placeholder="Camara (DIPUTADO o SENADOR)" defaultValue={camara} />
      </form>

      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Camara</th>
              <th>Partido</th>
              <th>Distrito/Circunscripcion</th>
              <th>Region</th>
              <th>Periodo</th>
            </tr>
          </thead>
          <tbody>
            {(data.items || []).map((row: any) => (
              <tr key={row.id}>
                <td><Link href={`/parliamentarians/${row.id}`}>{row.nombre}</Link></td>
                <td>{row.camara}</td>
                <td>{row.partido}</td>
                <td>{row.distrito_circunscripcion}</td>
                <td>{row.region}</td>
                <td>{row.periodo}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
