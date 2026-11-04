import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Link, navigate } from "../router.jsx";
import Nav from "../components/Nav.jsx";
import InstallApp from "../components/InstallApp.jsx";
import { AlbumRow } from "./Albums.jsx";

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
      navigate(`/album/${trip_id}`);
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
            <div className="today-pair">
              <img className="thumb-large" src={today.selfie.url} alt="Sua selfie de hoje" />
              {today.body && <img className="thumb-large" src={today.body.url} alt="Sua foto de corpo de hoje" />}
            </div>
            <div className="row">
              <button className="ghost" onClick={() => navigate("/camera")}>Refazer o rosto</button>
              {/* O corpo é opcional e só libera depois do rosto. */}
              <button className={today.body ? "ghost" : ""} onClick={() => navigate("/camera/corpo")}>
                {today.body ? "Refazer o corpo" : "Foto de corpo (opcional)"}
              </button>
            </div>
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
              <span>{i.from.display_name} te chamou pro álbum <b>{i.trip_name}</b></span>
              <span className="row">
                <button onClick={() => respond(i, true)}>Entrar</button>
                <button className="ghost" onClick={() => respond(i, false)}>Recusar</button>
              </span>
            </div>
          ))}
        </section>
      )}

      <section className="card stack">
        <div className="row">
          <h2>Álbuns abertos</h2>
          <Link to="/albuns" className="small">Ver todos</Link>
        </div>
        {trips.filter((t) => t.status === "active").map((t) => <AlbumRow key={t.id} album={t} />)}
        {trips.every((t) => t.status !== "active") && (
          <p className="muted">Nenhum álbum aberto.</p>
        )}
        <button className="ghost" onClick={() => navigate("/albuns")}>Novo álbum</button>
      </section>

      <InstallApp compact />
    </main>
  );
}

function formatLeft(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h${String(m).padStart(2, "0")}` : `${m} min`;
}
