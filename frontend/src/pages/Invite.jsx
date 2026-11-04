import { useEffect, useState } from "react";
import { api } from "../api.js";
import { navigate } from "../router.jsx";

// Tela aberta pelo link /convite/<token>.
export default function Invite({ token, user, onUser }) {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ display_name: "", username: "", password: "" });

  useEffect(() => {
    api(`/invite-links/${token}`).then(setInfo).catch((e) => setError(e.message));
  }, [token]);

  function done(tripId) {
    navigate(tripId ? `/album/${tripId}` : "/amigos");
  }

  async function acceptLoggedIn() {
    try {
      const r = await api(`/invite-links/${token}/accept`, { method: "POST" });
      done(r.trip_id);
    } catch (e) {
      setError(e.message);
    }
  }

  async function signup(e) {
    e.preventDefault();
    try {
      const r = await api(`/invite-links/${token}/signup`, { method: "POST", body: form });
      onUser(r.user);
      done(r.trip_id);
    } catch (e) {
      setError(e.message);
    }
  }

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  if (!info) {
    return <main className="center"><p className={error ? "error" : "muted"}>{error || "Carregando…"}</p></main>;
  }

  const title = info.trip_name
    ? <>{info.inviter} te chamou para <b>{info.trip_name}</b></>
    : <>{info.inviter} te chamou para o Rewind</>;

  return (
    <main className="center">
      <div className="card stack">
        <h1 className="brand">Rewind</h1>
        <p>{title}</p>
        {error && <p className="error">{error}</p>}
        {user ? (
          <button onClick={acceptLoggedIn}>Aceitar como {user.display_name}</button>
        ) : (
          <form className="stack" onSubmit={signup}>
            <label>Seu nome<input value={form.display_name} onChange={set("display_name")} maxLength={64} required /></label>
            <label>Usuário<input value={form.username} onChange={set("username")} autoCapitalize="none"
              autoComplete="username" required /></label>
            <label>Senha (mínimo 8)<input type="password" value={form.password} onChange={set("password")}
              autoComplete="new-password" minLength={8} required /></label>
            <button>Criar conta e entrar</button>
            <p className="muted small">Já tem conta? Entre primeiro e abra o link de novo.</p>
          </form>
        )}
      </div>
    </main>
  );
}
