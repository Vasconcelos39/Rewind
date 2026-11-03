import { useEffect, useState } from "react";
import { api } from "../api.js";

const FPS_OPTIONS = [4, 8, 12, 24];

// Um timelapse por pessoa da viagem. Pedir entra numa fila; a tela vai
// perguntando o progresso até o vídeo ficar pronto.
export default function Timelapses({ tripId, members }) {
  const [jobs, setJobs] = useState({}); // user_id -> pedido mais recente
  const [fps, setFps] = useState(8);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/trips/${tripId}/timelapses`).then((list) =>
      setJobs(Object.fromEntries(list.map((j) => [j.user_id, j]))));
  }, [tripId]);

  // Enquanto houver vídeo na fila ou rodando, pergunta de novo a cada 1,5 s.
  const pending = Object.values(jobs).filter((j) => j.status === "queued" || j.status === "running");
  useEffect(() => {
    if (pending.length === 0) return;
    const timer = setTimeout(async () => {
      const fresh = await Promise.all(pending.map((j) => api(`/timelapses/${j.id}`)));
      setJobs((old) => ({ ...old, ...Object.fromEntries(fresh.map((j) => [j.user_id, j])) }));
    }, 1500);
    return () => clearTimeout(timer);
  }, [jobs]);

  async function generate(userId) {
    setError("");
    try {
      const job = await api(`/trips/${tripId}/timelapses`, { method: "POST", body: { user_id: userId, fps } });
      setJobs((old) => ({ ...old, [userId]: job }));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <section className="card stack">
      <div className="row">
        <h2>Timelapse</h2>
        <select value={fps} onChange={(e) => setFps(Number(e.target.value))} aria-label="Fotos por segundo">
          {FPS_OPTIONS.map((f) => <option key={f} value={f}>{f} fotos/s</option>)}
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      {members.map((m) => {
        const job = jobs[m.id];
        return (
          <div key={m.id} className="stack list-item">
            <div className="row">
              <span>{m.display_name}</span>
              <button className="ghost" onClick={() => generate(m.id)}
                disabled={job && (job.status === "queued" || job.status === "running")}>
                {job?.status === "done" ? "Atualizar" : "Gerar"}
              </button>
            </div>
            {job?.status === "queued" && (
              <p className="muted small">
                Na fila{job.queue_ahead ? ` (${job.queue_ahead} antes)` : ""}…
              </p>
            )}
            {job?.status === "running" && (
              <progress value={job.progress} max="1">{Math.round(job.progress * 100)}%</progress>
            )}
            {job?.status === "error" && <p className="error small">Deu erro: {job.error}</p>}
            {job?.status === "done" && (
              <video src={job.url} controls playsInline loop className="timelapse" />
            )}
          </div>
        );
      })}
    </section>
  );
}
