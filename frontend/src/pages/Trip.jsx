import { useEffect, useState } from "react";
import { api } from "../api.js";
import { navigate } from "../router.jsx";
import { albumStatus, formatDay, localDay } from "../lib/albums.js";
import Nav from "../components/Nav.jsx";
import InviteLink from "../components/InviteLink.jsx";
import Extras from "../components/Extras.jsx";
import Gallery from "../components/Gallery.jsx";
import Timelapses from "../components/Timelapses.jsx";
import EndDateField from "../components/EndDateField.jsx";

// Um álbum (no código e na API ainda se chama "trip").
export default function Trip({ id }) {
  const [trip, setTrip] = useState(null);
  const [friends, setFriends] = useState([]);
  const [error, setError] = useState("");

  function load() {
    api(`/trips/${id}`).then(setTrip).catch((e) => setError(e.message));
    api("/friends").then((d) => setFriends(d.friends)).catch(() => {});
  }
  useEffect(load, [id]);

  async function invite(userId) {
    await api(`/trips/${id}/invites`, { method: "POST", body: { user_id: userId } }).catch((e) => setError(e.message));
    load();
  }

  async function leave() {
    const last = trip.members.length === 1;
    const msg = last
      ? "Você é a última pessoa: sair apaga o álbum e as fotos extras dele. Continuar?"
      : "Sair deste álbum?";
    if (!confirm(msg)) return;
    await api(`/trips/${id}/leave`, { method: "POST" });
    navigate("/albuns");
  }

  if (error && !trip) return <main className="page stack"><Nav /><p className="error">{error}</p></main>;
  if (!trip) return <main className="page stack"><Nav /><p className="muted">Carregando…</p></main>;

  const ended = trip.status === "ended";
  const inTrip = new Set([...trip.members, ...trip.pending_invites].map((u) => u.id));
  const invitable = friends.filter((f) => !inTrip.has(f.id));

  return (
    <main className="page stack">
      <Nav />
      <section className="card stack">
        <h2>{trip.name}</h2>
        <p className="muted">
          {albumStatus(trip)}
          {trip.end_date && !ended && trip.days_left > 0 && ` (até ${formatDay(trip.end_date)})`}
          {ended && ` · ${formatDay(trip.start_day)} a ${formatDay(trip.end_date)}`}
        </p>
        {error && <p className="error">{error}</p>}
      </section>

      {!ended && (
        <section className="card stack">
          <h2>Hoje: {trip.members.filter((m) => m.sent_today).length} de {trip.members.length}</h2>
          {trip.members.map((m) => (
            <div key={m.id} className="member">
              {m.today_photo
                ? <img className="avatar" src={m.today_photo.url} alt="" />
                : <span className="avatar" />}
              <span className="stack" style={{ gap: 0 }}>
                <span>{m.display_name} <span className="streak">🔥 {m.streak}</span></span>
                <span className={m.sent_today ? "status-ok small" : "status-missing small"}>
                  {m.sent_today ? "✓ Já tirou" : "Falta tirar"}
                </span>
              </span>
            </div>
          ))}
          {trip.pending_invites.map((u) => <div key={u.id} className="muted">{u.display_name}: convidado</div>)}
        </section>
      )}

      {!ended && <Extras tripId={id} />}

      <Gallery tripId={id} members={trip.members} />

      <Timelapses tripId={id} members={trip.members} />

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

      <AlbumSettings trip={trip} onSaved={setTrip} />

      <button className="ghost" onClick={leave}>Sair do álbum</button>
    </main>
  );
}

// Nome, data final (opcional) e encerrar. Qualquer membro pode mexer.
function AlbumSettings({ trip, onSaved }) {
  const [name, setName] = useState(trip.name);
  const [endDate, setEndDate] = useState(trip.end_date ?? "");
  const [msg, setMsg] = useState(null);

  async function save(changes) {
    try {
      onSaved({ ...trip, ...(await api(`/trips/${trip.id}`, { method: "PATCH", body: changes })) });
      setMsg({ ok: true, text: "Salvo." });
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    }
  }

  function submit(e) {
    e.preventDefault();
    save({ name, end_date: endDate || null });
  }

  function endToday() {
    if (!confirm("Encerrar o álbum? Hoje vira o último dia. Dá pra reabrir depois aqui mesmo.")) return;
    setEndDate(localDay());
    save({ end_date: localDay() });
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Configurações do álbum</h2>
      <label>Nome<input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required /></label>
      <EndDateField value={endDate} onChange={setEndDate} min={trip.start_day} suggest={localDay(30)} />
      {msg && <p className={msg.ok ? "success" : "error"} role="status">{msg.text}</p>}
      <div className="row">
        <button>Salvar</button>
        {trip.status === "active" && trip.days_left !== 0 && (
          <button type="button" className="ghost" onClick={endToday}>Encerrar hoje</button>
        )}
      </div>
    </form>
  );
}
