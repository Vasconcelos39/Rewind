import { useEffect, useState } from "react";
import { api } from "./api.js";
import Login from "./pages/Login.jsx";
import Home from "./pages/Home.jsx";

export default function App() {
  // undefined = ainda perguntando ao servidor; null = não logado.
  const [user, setUser] = useState(undefined);

  useEffect(() => {
    api("/auth/me").then(setUser).catch(() => setUser(null));
  }, []);

  if (user === undefined) return <main className="center muted">Carregando…</main>;
  if (user === null) return <Login onLogin={setUser} />;
  return <Home user={user} onLogout={() => setUser(null)} />;
}
