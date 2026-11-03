import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Link, navigate } from "../router.jsx";
import Nav from "../components/Nav.jsx";

export default function Home({ user }) {
  const [trips, setTrips] = useState([]);
  const [invites, setInvites] = useState([]);
  const [today, setToday] = useState(null);
  const [summary, setSummary] = useState(null);

  function load() {
    api("/photos/today").then(setToday);
    api("/today").then((s) => {
      setSummary(s);
      // Viu as cutucadas: marca como vistas (elas continuam aparecendo hoje).
      if (s.nudges.some((n) => !n.seen)) api("/today/nudges/seen", { method: "POST" });
    });
    api("/trips").then(setTrips);
    api("/trip-invites").then(setInvites);
  }
  useEffect(load, []);

  async function respond(invite, accept) {
    if (accept) {
      const { trip_id } = await api(`/trip-invites/${invite.id}/accept`, { method: "POST" });
      navigate(`/viagem/${trip_id}`);
    } else {
      await api(`/trip-invites/${invite.id}`, { method: "DELETE" });
      load();
    }
  }

  return (
    <main className="page stack">
      <Nav />
      <h2>Olá, {user.display_name}!</h2>

      {summary && !summary.sent_today && summary.nudges.length > 0 && (
        <section className="card nudge" role="status">
          {summary.nudges.map((n) => n.from.display_name).join(", ")} te cutucou!
          Faltam {formatLeft(summary.seconds_left)} pra tirar a foto.
        </section>
      )}

      <section className="card stack">
        <div className="row">
          <h2>Foto de hoje</h2>
          {summary && (
            <span className={summary.sent_today ? "streak" : "streak at-risk"}
              title={summary.sent_today ? "Streak garantida hoje" : "Tire a foto pra não perder a streak"}>
              🔥 {summary.streak}
            </span>
          )}
        </div>
        {summary && !summary.sent_today && (
          <p className="muted">Faltam {formatLeft(summary.seconds_left)} pro dia acabar.</p>
        )}
        {today?.selfie ? (
          <>
            <img className="thumb-large" src={today.selfie.url} alt="Sua selfie de hoje" />
            <button className="ghost" onClick={() => navigate("/camera")}>Tirar de novo</button>
          </>
        ) : (
          <button onClick={() => navigate("/camera")}>Tirar a foto de hoje</button>
        )}
      </section>

      {invites.length > 0 && (
        <section className="card stack">
          <h2>Convites</h2>
          {invites.map((i) => (
            <div key={i.id} className="row">
              <span>{i.from.display_name} te chamou para <b>{i.trip_name}</b></span>
              <span className="row">
                <button onClick={() => respond(i, true)}>Entrar</button>
                <button className="ghost" onClick={() => respond(i, false)}>Recusar</button>
              </span>
            </div>
          ))}
        </section>
      )}

      <section className="card stack">
        <h2>Suas viagens</h2>
        {trips.length === 0 && <p className="muted">Nenhuma viagem ainda.</p>}
        {trips.map((t) => (
          <Link key={t.id} to={`/viagem/${t.id}`} className="row list-item">
            <span>{t.name}</span>
            <span className="muted">{t.days_left} dias · {t.member_count} pessoas</span>
          </Link>
        ))}
      </section>

      <NewTrip onCreated={(t) => navigate(`/viagem/${t.id}`)} />
    </main>
  );
}

function NewTrip({ onCreated }) {
  const [name, setName] = useState("");
  const [endDate, setEndDate] = useState("");
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    try {
      onCreated(await api("/trips", { method: "POST", body: { name, end_date: endDate } }));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Nova viagem</h2>
      <label>Nome<input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required /></label>
      <label>Data final (a meta)<input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} required /></label>
      {error && <p className="error">{error}</p>}
      <button>Criar</button>
    </form>
  );
}

function formatLeft(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h${String(m).padStart(2, "0")}` : `${m} min`;
}
