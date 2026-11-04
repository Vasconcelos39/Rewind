import { useEffect, useState } from "react";
import { api, LOGGED_OUT_EVENT } from "./api.js";
import { usePath } from "./router.jsx";
import Login from "./pages/Login.jsx";
import Home from "./pages/Home.jsx";
import Friends from "./pages/Friends.jsx";
import Trip from "./pages/Trip.jsx";
import Albums from "./pages/Albums.jsx";
import Invite from "./pages/Invite.jsx";
import Account from "./pages/Account.jsx";
import Camera from "./pages/Camera.jsx";

export default function App() {
  // undefined = ainda perguntando ao servidor; null = não logado.
  const [user, setUser] = useState(undefined);
  const [offline, setOffline] = useState(false);
  const path = usePath();

  function checkSession() {
    setOffline(false);
    api("/auth/me")
      .then(setUser)
      .catch((e) => (e.status === 0 ? setOffline(true) : setUser(null)));
  }

  useEffect(() => {
    checkSession();
    // Qualquer 401 no meio do uso (sessão venceu) derruba pra tela de login.
    const onLoggedOut = () => setUser(null);
    window.addEventListener(LOGGED_OUT_EVENT, onLoggedOut);
    return () => window.removeEventListener(LOGGED_OUT_EVENT, onLoggedOut);
  }, []);

  if (offline) {
    return (
      <main className="center">
        <div className="card stack">
          <h1 className="brand">Rewind</h1>
          <p>Sem conexão com o servidor.</p>
          <button onClick={checkSession}>Tentar de novo</button>
        </div>
      </main>
    );
  }
  if (user === undefined) return <main className="center muted">Carregando…</main>;

  // A tela de convite funciona com ou sem login (é por ela que se cria a conta).
  const invite = path.match(/^\/convite\/([\w-]+)$/);
  if (invite) return <Invite token={invite[1]} user={user} onUser={setUser} />;

  // Fora o convite, nada do app aparece sem login. (A API também recusa: isto é só a tela.)
  if (user === null) return <Login onLogin={setUser} />;

  const album = path.match(/^\/(?:album|viagem)\/(\d+)$/);
  if (album) return <Trip id={Number(album[1])} />;
  if (path === "/albuns") return <Albums />;
  // key diferente: trocar de rosto pra corpo monta uma câmera nova, sem herdar o estado.
  if (path === "/camera") return <Camera kind="selfie" key="selfie" />;
  if (path === "/camera/corpo") return <Camera kind="body" key="body" />;
  if (path === "/amigos") return <Friends />;
  if (path === "/conta") return <Account user={user} onLogout={() => setUser(null)} />;
  return <Home user={user} />;
}
