import { useEffect, useState } from "react";
import { api } from "../api.js";

// Fotos da viagem por dia (mais novo primeiro), carregando aos poucos.
export default function Gallery({ tripId, members }) {
  const [days, setDays] = useState([]);
  const [next, setNext] = useState(null);
  const [who, setWho] = useState("");
  const names = Object.fromEntries(members.map((m) => [m.id, m.display_name]));

  async function load(before = null) {
    const params = new URLSearchParams({ days: "7" });
    if (before) params.set("before", before);
    if (who) params.set("user_id", who);
    const page = await api(`/trips/${tripId}/gallery?${params}`);
    setDays((old) => (before ? [...old, ...page.days] : page.days));
    // Página com menos de 7 dias = chegou no começo.
    setNext(page.days.length === 7 ? page.next_before : null);
  }
  useEffect(() => { load(); }, [tripId, who]);

  return (
    <section className="card stack">
      <div className="row">
        <h2>Galeria</h2>
        <select value={who} onChange={(e) => setWho(e.target.value)} aria-label="Filtrar por pessoa">
          <option value="">Todo mundo</option>
          {members.map((m) => <option key={m.id} value={m.id}>{m.display_name}</option>)}
        </select>
      </div>
      {days.length === 0 && <p className="muted">Nenhuma foto ainda.</p>}
      {days.map((d) => (
        <div key={d.day} className="gallery-day">
          <b>{new Date(d.day + "T12:00").toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "short" })}</b>
          <div className="grid">
            {d.selfies.map((p) => (
              <img key={p.id} src={p.url} alt={`Selfie de ${names[p.user_id] ?? ""}`} title={names[p.user_id]} loading="lazy" />
            ))}
            {d.extras.map((p) => (
              <img key={p.id} src={p.url} alt={`Foto extra de ${names[p.user_id] ?? ""}`} title={names[p.user_id]} loading="lazy" />
            ))}
          </div>
        </div>
      ))}
      {next && <button className="ghost" onClick={() => load(next)}>Carregar mais</button>}
    </section>
  );
}
