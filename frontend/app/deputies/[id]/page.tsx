import Link from "next/link";
import { getDeputy } from "../../../lib/api";

export default async function DeputyPage({ params }: { params: { id: string } }) {
  const data = await getDeputy(params.id);
  const d = data.diputado;
  const s = data.score;

  return (
    <main>
      <p><Link href="/">Volver al ranking</Link></p>
      <h1>{d.nombre}</h1>
      <p className="subtitle">{d.partido} - {d.distrito} - Periodo {d.periodo}</p>

      <div className="grid kpis">
        <div className="card"><strong>{s ? Number(s.total_score).toFixed(2) : "0.00"}</strong><br />Transparency score</div>
        <div className="card"><strong>{s ? Number(s.attendance_score).toFixed(2) : "0.00"}</strong><br />Asistencia</div>
        <div className="card"><strong>{s ? Number(s.voting_score).toFixed(2) : "0.00"}</strong><br />Votaciones</div>
        <div className="card"><strong>{s ? Number(s.legislative_score).toFixed(2) : "0.00"}</strong><br />Actividad legislativa</div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>Comisiones</h3>
        <table>
          <thead>
            <tr><th>Periodo</th><th>Comision</th><th>Participacion %</th></tr>
          </thead>
          <tbody>
            {(data.comisiones || []).map((c: any, idx: number) => (
              <tr key={`${c.periodo}-${c.comision}-${idx}`}>
                <td>{c.periodo}</td>
                <td>{c.comision}</td>
                <td>{Number(c.participacion_pct).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
