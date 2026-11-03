import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { resizeFile } from "../lib/image.js";

// Fotos extras do dia nesta viagem. Podem vir da galeria e não contam pra streak.
export default function Extras({ tripId }) {
  const [photos, setPhotos] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const input = useRef(null);

  const load = () => api(`/trips/${tripId}/extras`).then(setPhotos);
  useEffect(() => { load(); }, [tripId]);

  async function upload(e) {
    const files = [...e.target.files];
    e.target.value = ""; // permite escolher a mesma foto de novo
    setBusy(true);
    setError("");
    try {
      for (const f of files) {
        await api(`/trips/${tripId}/extras`, { method: "POST", file: await resizeFile(f) });
      }
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
    load();
  }

  return (
    <section className="card stack">
      <h2>Fotos extras de hoje</h2>
      {photos.length > 0 && (
        <div className="grid">
          {photos.map((p) => <img key={p.id} src={p.url} alt="" loading="lazy" />)}
        </div>
      )}
      {error && <p className="error">{error}</p>}
      <input ref={input} type="file" accept="image/*" multiple hidden onChange={upload} />
      <button className="ghost" onClick={() => input.current.click()} disabled={busy}>
        {busy ? "Enviando…" : "Adicionar fotos"}
      </button>
    </section>
  );
}
