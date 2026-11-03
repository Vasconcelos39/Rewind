import { useState } from "react";
import { api } from "../api.js";
import { navigate } from "../router.jsx";
import Nav from "../components/Nav.jsx";

export default function Account({ user, onLogout }) {
  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    navigate("/");
    onLogout();
  }

  return (
    <main className="page stack">
      <Nav />
      <section className="card stack">
        <h2>{user.display_name}</h2>
        <p className="muted">@{user.username}</p>
        <button className="ghost" onClick={logout}>Sair</button>
      </section>
      <ChangePassword />
    </main>
  );
}

function ChangePassword() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState(null);

  async function submit(e) {
    e.preventDefault();
    try {
      await api("/auth/password", {
        method: "POST",
        body: { current_password: current, new_password: next },
      });
      setMsg({ ok: true, text: "Senha trocada. Os outros aparelhos foram desconectados." });
      setCurrent("");
      setNext("");
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Trocar senha</h2>
      <label>
        Senha atual
        <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)}
          autoComplete="current-password" required />
      </label>
      <label>
        Senha nova (mínimo 8 caracteres)
        <input type="password" value={next} onChange={(e) => setNext(e.target.value)}
          autoComplete="new-password" minLength={8} required />
      </label>
      {msg && <p className={msg.ok ? "success" : "error"} role="status">{msg.text}</p>}
      <button>Salvar</button>
    </form>
  );
}
