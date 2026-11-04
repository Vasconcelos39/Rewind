import { useEffect, useState } from "react";
import { installState, onInstallChange, promptInstall } from "../lib/install.js";

// Mostra como instalar o Rewind na tela inicial, conforme o navegador.
// compact: só aparece quando dá pra instalar com um toque (pra usar na home).
export default function InstallApp({ compact = false }) {
  const [state, setState] = useState(installState);
  useEffect(() => onInstallChange(() => setState(installState())), []);

  if (compact && state !== "ready") return null;

  return (
    <section className="card stack">
      <h2>Instalar o app</h2>
      {state === "ready" && (
        <>
          <p className="muted">Vira um ícone na tela inicial e abre sem a barra do navegador.</p>
          <button onClick={promptInstall}>Instalar o Rewind</button>
        </>
      )}
      {state === "installed" && <p className="muted">O Rewind já está instalado neste aparelho.</p>}
      {state === "ios" && (
        <p className="muted">
          No iPhone: abra no <b>Safari</b>, toque em <b>Compartilhar</b> (o quadrado com a seta)
          e depois em <b>Adicionar à Tela de Início</b>.
        </p>
      )}
      {state === "needs-https" && (
        <p className="muted">Instalar só funciona pelo endereço com HTTPS (o do servidor, não o IP da rede).</p>
      )}
      {state === "unavailable" && (
        <p className="muted">
          Abra pelo Chrome (Android ou computador) ou pelo Safari (iPhone). No Chrome do computador
          também aparece um ícone de instalar na barra de endereço.
        </p>
      )}
    </section>
  );
}
