import { useState } from "react";
import { api } from "../api.js";

// Gera um link de convite (uso único, 7 dias). Sem tripId, o link só cria amizade.
export default function InviteLink({ tripId = null, label }) {
  const [url, setUrl] = useState("");
  const [copied, setCopied] = useState(false);

  async function create() {
    const { path } = await api("/invite-links", { method: "POST", body: { trip_id: tripId } });
    setUrl(location.origin + path);
    setCopied(false);
  }

  async function share() {
    // No celular abre o menu de compartilhar; no PC copia.
    if (navigator.share) return navigator.share({ title: "Rewind", url }).catch(() => {});
    await navigator.clipboard.writeText(url);
    setCopied(true);
  }

  return (
    <div className="stack">
      <button className="ghost" onClick={create}>{label}</button>
      {url && (
        <>
          <input readOnly value={url} onFocus={(e) => e.target.select()} />
          <button onClick={share}>{copied ? "Copiado!" : "Compartilhar link"}</button>
          <p className="muted small">Vale para uma pessoa só, por 7 dias.</p>
        </>
      )}
    </div>
  );
}
