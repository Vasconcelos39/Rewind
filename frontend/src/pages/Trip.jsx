import { useEffect, useState } from "react";
import { api } from "../api.js";
import { navigate } from "../router.jsx";
import Nav from "../components/Nav.jsx";
import InviteLink from "../components/InviteLink.jsx";
import Extras from "../components/Extras.jsx";

export default function Trip({ id }) {
  const [trip, setTrip] = useState(null);
  const [friends, setFriends] = useState([]);
  const [error, setError] = useState("");

  function load() {
    api(`/trips/${id}`).then(setTrip).catch((e) => setError(e.message));
    api("/friends").then((d) => setFriends(d.friends));
  }
  useEffect(load, [id]);

  async function invite(userId) {
    await api(`/trips/${id}/invites`, { method: "POST", body: { user_id: userId } });
    load();
  }

  async function leave() {
    if (!confirm("Sair desta viagem?")) return;
    await api(`/trips/${id}/leave`, { method: "POST" });
    navigate("/");
  }

  if (error) return <main className="page stack"><Nav /><p className="error">{error}</p></main>;
  if (!trip) return <main className="page stack"><Nav /><p className="muted">Carregando…</p></main>;

  const inTrip = new Set([...trip.members, ...trip.pending_invites].map((u) => u.id));
  const invitable = friends.filter((f) => !inTrip.has(f.id));

  return (
    <main className="page stack">
      <Nav />
      <section className="card stack">
        <h2>{trip.name}</h2>
        <p className="muted">Faltam {trip.days_left} dias ({trip.end_date})</p>
      </section>

      <Extras tripId={id} />

      <section className="card stack">
        <h2>Pessoas</h2>
        {trip.members.map((m) => <div key={m.id}>{m.display_name}</div>)}
        {trip.pending_invites.map((u) => <div key={u.id} className="muted">{u.display_name}: convidado</div>)}
      </section>

      <section className="card stack">
        <h2>Convidar</h2>
        {invitable.map((f) => (
          <div key={f.id} className="row">
            <span>{f.display_name}</span>
            <button className="ghost" onClick={() => invite(f.id)}>Convidar</button>
          </div>
        ))}
        {invitable.length === 0 && <p className="muted">Todos os seus amigos já estão aqui.</p>}
        <InviteLink tripId={id} label="Gerar link para quem não tem conta" />
      </section>

      <button className="ghost" onClick={leave}>Sair da viagem</button>
    </main>
  );
}
