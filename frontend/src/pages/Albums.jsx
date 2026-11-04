import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Link, navigate } from "../router.jsx";
import { albumStatus, localDay } from "../lib/albums.js";
import Nav from "../components/Nav.jsx";
import EndDateField from "../components/EndDateField.jsx";

// Biblioteca: os álbuns em andamento e os que já acabaram.
export default function Albums() {
  const [albums, setAlbums] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/trips").then(setAlbums).catch((e) => setError(e.message));
  }, []);

  const active = albums?.filter((a) => a.status === "active") ?? [];
  const ended = albums?.filter((a) => a.status === "ended") ?? [];

  return (
    <main className="page stack">
      <Nav />
      <h2>Seus álbuns</h2>
      {error && <p className="error">{error}</p>}

      <section className="card stack">
        <h2>Em andamento</h2>
        {albums && active.length === 0 && <p className="muted">Nenhum álbum aberto. Crie um aqui embaixo.</p>}
        {active.map((a) => <AlbumRow key={a.id} album={a} />)}
      </section>

      {ended.length > 0 && (
        <section className="card stack">
          <h2>Encerrados</h2>
          {ended.map((a) => <AlbumRow key={a.id} album={a} />)}
        </section>
      )}

      <NewAlbum onCreated={(a) => navigate(`/album/${a.id}`)} />
    </main>
  );
}

export function AlbumRow({ album }) {
  return (
    <Link to={`/album/${album.id}`} className="row list-item">
      <span>{album.name}</span>
      <span className="muted small">
        {albumStatus(album)} · {album.member_count} {album.member_count === 1 ? "pessoa" : "pessoas"}
      </span>
    </Link>
  );
}

function NewAlbum({ onCreated }) {
  const [name, setName] = useState("");
  const [endDate, setEndDate] = useState("");
  const [error, setError] = useState("");
  const tomorrow = localDay(1); // a data final, se tiver, precisa ser a partir de amanhã

  async function submit(e) {
    e.preventDefault();
    try {
      onCreated(await api("/trips", { method: "POST", body: { name, end_date: endDate || null } }));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form id="novo" className="card stack" onSubmit={submit}>
      <h2>Novo álbum</h2>
      <label>Nome<input value={name} onChange={(e) => setName(e.target.value)} maxLength={80}
        placeholder="Casamento da Lu, Mochilão 2027…" required /></label>
      <EndDateField value={endDate} onChange={setEndDate} min={tomorrow} suggest={localDay(30)} />
      {error && <p className="error">{error}</p>}
      <button>Criar álbum</button>
    </form>
  );
}
