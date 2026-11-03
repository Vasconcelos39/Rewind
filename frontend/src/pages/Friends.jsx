import { useEffect, useState } from "react";
import { api } from "../api.js";
import Nav from "../components/Nav.jsx";
import InviteLink from "../components/InviteLink.jsx";

export default function Friends() {
  const [data, setData] = useState({ friends: [], incoming: [], outgoing: [] });
  const [username, setUsername] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => api("/friends").then(setData);
  useEffect(() => { load(); }, []);

  async function add(e) {
    e.preventDefault();
    try {
      const r = await api("/friends", { method: "POST", body: { username } });
      setMsg(r.status === "accepted" ? "Agora vocês são amigos!" : "Pedido enviado.");
      setUsername("");
      load();
    } catch (err) {
      setMsg(err.message);
    }
  }

  async function act(userId, accept) {
    if (accept) await api(`/friends/${userId}/accept`, { method: "POST" });
    else await api(`/friends/${userId}`, { method: "DELETE" });
    load();
  }

  return (
    <main className="page stack">
      <Nav />

      {data.incoming.length > 0 && (
        <section className="card stack">
          <h2>Pedidos de amizade</h2>
          {data.incoming.map((u) => (
            <div key={u.id} className="row">
              <span>{u.display_name} <span className="muted">@{u.username}</span></span>
              <span className="row">
                <button onClick={() => act(u.id, true)}>Aceitar</button>
                <button className="ghost" onClick={() => act(u.id, false)}>Recusar</button>
              </span>
            </div>
          ))}
        </section>
      )}

      <section className="card stack">
        <h2>Amigos</h2>
        {data.friends.length === 0 && <p className="muted">Nenhum amigo ainda.</p>}
        {data.friends.map((u) => (
          <div key={u.id} className="row">
            <span>{u.display_name} <span className="muted">@{u.username}</span></span>
            <button className="ghost" onClick={() => confirm(`Desfazer amizade com ${u.display_name}?`) && act(u.id, false)}>
              Remover
            </button>
          </div>
        ))}
        {data.outgoing.map((u) => (
          <div key={u.id} className="row">
            <span className="muted">{u.display_name}: aguardando</span>
            <button className="ghost" onClick={() => act(u.id, false)}>Cancelar</button>
          </div>
        ))}
      </section>

      <form className="card stack" onSubmit={add}>
        <h2>Adicionar amigo</h2>
        <label>Nome de usuário<input value={username} onChange={(e) => setUsername(e.target.value)}
          autoCapitalize="none" required /></label>
        {msg && <p className="muted">{msg}</p>}
        <button>Enviar pedido</button>
      </form>

      <section className="card stack">
        <h2>Chamar alguém que ainda não tem conta</h2>
        <InviteLink label="Gerar link de convite" />
      </section>
    </main>
  );
}
