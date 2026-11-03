import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { navigate } from "../router.jsx";
import { captureVideo } from "../lib/image.js";

function savedOpacity() {
  try {
    return Number(localStorage.getItem("overlayOpacity") ?? 0.35);
  } catch {
    return 0.35; // aba anônima ou armazenamento bloqueado
  }
}

export default function Camera() {
  const videoRef = useRef(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [previous, setPrevious] = useState(null);
  const [opacity, setOpacity] = useState(savedOpacity);
  const [shot, setShot] = useState(null); // { blob, url } depois de tirar
  const [sending, setSending] = useState(false);

  // Liga a câmera frontal ao abrir a tela e desliga ao sair.
  useEffect(() => {
    let stream;
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: "user", width: { ideal: 1920 }, height: { ideal: 1920 } }, audio: false })
      .then((s) => {
        stream = s;
        videoRef.current.srcObject = s;
      })
      .catch(() => setError("Não consegui abrir a câmera. Confira a permissão do navegador."));
    if (!navigator.mediaDevices) setError("Este navegador não dá acesso à câmera (precisa de HTTPS).");
    api("/photos/today").then((t) => setPrevious(t.previous));
    return () => stream?.getTracks().forEach((t) => t.stop());
  }, []);

  useEffect(() => {
    try { localStorage.setItem("overlayOpacity", String(opacity)); } catch {}
  }, [opacity]);

  async function take() {
    const blob = await captureVideo(videoRef.current);
    setShot({ blob, url: URL.createObjectURL(blob) });
  }

  function retake() {
    URL.revokeObjectURL(shot.url);
    setShot(null);
  }

  async function send() {
    setSending(true);
    try {
      await api("/photos/selfie", { method: "POST", file: shot.blob });
      navigate("/");
    } catch (e) {
      setError(e.message);
      setSending(false);
    }
  }

  return (
    <main className="page stack">
      <header className="row">
        <h2>Foto de hoje</h2>
        <button className="ghost" onClick={() => navigate("/")}>Voltar</button>
      </header>

      {error && <p className="error">{error}</p>}

      <div className="camera-box">
        {shot ? (
          // A foto como foi salva: sem espelho, como os outros te veem.
          <img src={shot.url} alt="Sua selfie" />
        ) : (
          <>
            <video ref={videoRef} className="mirrored" autoPlay playsInline muted
              onLoadedMetadata={() => setReady(true)} />
            {previous && (
              // A foto de ontem foi salva sem espelho; espelhamos aqui pra bater com o preview.
              <img src={previous.url} className="mirrored overlay" style={{ opacity }} alt="" />
            )}
            <svg className="face-guide" viewBox="0 0 300 400" aria-hidden="true">
              <ellipse cx="150" cy="185" rx="92" ry="125" />
            </svg>
          </>
        )}
      </div>

      {shot ? (
        <div className="row">
          <button className="ghost" onClick={retake} disabled={sending}>Tirar outra</button>
          <button onClick={send} disabled={sending}>{sending ? "Enviando…" : "Enviar"}</button>
        </div>
      ) : (
        <>
          {previous && (
            <label>
              Foto anterior por cima: {Math.round(opacity * 100)}%
              <input type="range" min="0" max="0.8" step="0.05" value={opacity}
                onChange={(e) => setOpacity(Number(e.target.value))} />
            </label>
          )}
          <button onClick={take} disabled={!ready}>Tirar foto</button>
        </>
      )}
    </main>
  );
}
