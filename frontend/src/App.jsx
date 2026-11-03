import { useEffect, useState } from "react";
import { api } from "./api.js";
import { usePath } from "./router.jsx";
import Login from "./pages/Login.jsx";
import Home from "./pages/Home.jsx";
import Friends from "./pages/Friends.jsx";
import Trip from "./pages/Trip.jsx";
import Invite from "./pages/Invite.jsx";
import Account from "./pages/Account.jsx";
import Camera from "./pages/Camera.jsx";

export default function App() {
  // undefined = ainda perguntando ao servidor; null = não logado.
  const [user, setUser] = useState(undefined);
  const path = usePath();

  useEffect(() => {
    api("/auth/me").then(setUser).catch(() => setUser(null));
  }, []);

  if (user === undefined) return <main className="center muted">Carregando…</main>;

  // A tela de convite funciona com ou sem login.
  const invite = path.match(/^\/convite\/([\w-]+)$/);
  if (invite) return <Invite token={invite[1]} user={user} onUser={setUser} />;

  if (user === null) return <Login onLogin={setUser} />;

  const trip = path.match(/^\/viagem\/(\d+)$/);
  if (trip) return <Trip id={Number(trip[1])} />;
  if (path === "/camera") return <Camera />;
  if (path === "/amigos") return <Friends />;
  if (path === "/conta") return <Account user={user} onLogout={() => setUser(null)} />;
  return <Home user={user} />;
}
