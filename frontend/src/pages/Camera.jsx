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

const MODES = {
  // Rosto: câmera da frente, contorno oval. Obrigatória, conta pra streak.
  selfie: { title: "Foto do rosto", facing: "user", previousKey: "previous", endpoint: "/photos/selfie" },
  // Corpo: opcional, depois do rosto. Começa na câmera de trás, pra foto no espelho.
  body: { title: "Foto de corpo", facing: "environment", previousKey: "previous_body", endpoint: "/photos/body" },
};

export default function Camera({ kind = "selfie" }) {
  const mode = MODES[kind];
  const videoRef = useRef(null);
  const [facing, setFacing] = useState(mode.facing);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [previous, setPrevious] = useState(null);
  const [opacity, setOpacity] = useState(savedOpacity);
  const [shot, setShot] = useState(null); // { blob, url } depois de tirar
  const [sending, setSending] = useState(false);

  // A foto de referência (a última desse tipo) que aparece por cima.
  useEffect(() => {
    api("/photos/today").then((t) => setPrevious(t[mode.previousKey])).catch(() => {});
  }, [kind]);

  // Liga a câmera ao abrir a tela (e ao trocar de câmera) e desliga ao sair.
  useEffect(() => {
    let stream;
    let closed = false; // a tela pode fechar antes da permissão da câmera responder
    setReady(false);
    if (!navigator.mediaDevices) {
      setError("Este navegador não dá acesso à câmera (precisa de HTTPS).");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1920 } }, audio: false })
      .then((s) => {
        stream = s;
        // Saiu da tela antes da câmera abrir: desliga na hora, senão a luz fica acesa.
        if (closed || !videoRef.current) return s.getTracks().forEach((t) => t.stop());
        videoRef.current.srcObject = s;
      })
      .catch(() => !closed && setError("Não consegui abrir a câmera. Confira a permissão do navegador."));
    return () => {
      closed = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [facing]);

  // Libera a memória da prévia quando ela é trocada ou a tela fecha.
  useEffect(() => () => shot && URL.revokeObjectURL(shot.url), [shot]);

  useEffect(() => {
    try { localStorage.setItem("overlayOpacity", String(opacity)); } catch {}
  }, [opacity]);

  async function take() {
    const blob = await captureVideo(videoRef.current);
    setShot({ blob, url: URL.createObjectURL(blob) });
  }

  async function send() {
    setSending(true);
    try {
      await api(mode.endpoint, { method: "POST", file: shot.blob });
      navigate("/");
    } catch (e) {
      setError(e.message);
      setSending(false);
    }
  }

  // Só a câmera da frente aparece espelhada (como um espelho). A foto salva nunca é
  // espelhada; por isso a de referência só é espelhada quando a prévia também é.
  const mirrored = facing === "user" ? "mirrored" : "";

  return (
    <main className="page stack">
      <header className="row">
        <h2>{mode.title}</h2>
        <button className="ghost" onClick={() => navigate("/")}>Voltar</button>
      </header>

      {error && <p className="error">{error}</p>}

      <div className="camera-box">
        {/* O vídeo fica sempre montado (só some atrás da prévia). Se ele saísse da tela,
            o "Tirar outra" voltaria com a câmera preta: o elemento novo não tem o stream. */}
        <video ref={videoRef} className={mirrored} autoPlay playsInline muted
          onLoadedMetadata={() => setReady(true)} hidden={!!shot} />
        {!shot && previous && (
          <img src={previous.url} className={`${mirrored} overlay`} style={{ opacity }} alt="" />
        )}
        {!shot && kind === "selfie" && (
          <svg className="face-guide" viewBox="0 0 300 400" aria-hidden="true">
            <ellipse cx="150" cy="185" rx="92" ry="125" />
          </svg>
        )}
        {shot && <img src={shot.url} alt="Sua foto, como ela vai ficar salva" />}
      </div>

      {shot ? (
        <div className="row">
          <button className="ghost" onClick={() => setShot(null)} disabled={sending}>Tirar outra</button>
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
          <div className="row">
            {kind === "body" && (
              <button className="ghost" onClick={() => setFacing(facing === "user" ? "environment" : "user")}>
                {facing === "user" ? "Usar câmera de trás" : "Usar câmera da frente"}
              </button>
            )}
            <button onClick={take} disabled={!ready}>Tirar foto</button>
          </div>
          {kind === "body" && (
            <p className="muted small">
              Dica: use sempre o mesmo espelho e a mesma distância. O timelapse de corpo fica bem melhor.
            </p>
          )}
        </>
      )}
    </main>
  );
}
