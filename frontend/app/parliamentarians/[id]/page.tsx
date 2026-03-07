import Link from "next/link";
import { getParliamentarian } from "../../../lib/api";

export default async function ParliamentarianPage({ params }: { params: { id: string } }) {
  const data = await getParliamentarian(params.id);
  const p = data.parlamentario;

  return (
    <main>
      <p><Link href="/">Volver al listado</Link></p>
      <h1>{p.nombre}</h1>
      <p className="subtitle">{p.camara} - {p.partido}</p>

      <div className="grid kpis">
        <div className="card"><strong>{p.distrito_circunscripcion}</strong><br />Distrito/Circunscripcion</div>
        <div className="card"><strong>{p.region}</strong><br />Region</div>
        <div className="card"><strong>{p.periodo}</strong><br />Periodo</div>
        <div className="card"><strong>{p.source}</strong><br />Fuente</div>
      </div>
    </main>
  );
}
