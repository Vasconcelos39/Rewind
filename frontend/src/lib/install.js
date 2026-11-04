// Instalar o PWA na tela inicial.
//
// Chrome/Edge/Android disparam "beforeinstallprompt" quando o app pode ser instalado.
// O evento chega cedo (às vezes antes de qualquer tela montar), então ele é guardado
// aqui assim que o app carrega. O iPhone não tem esse evento: lá é pelo menu do Safari.

let deferred = null;
const listeners = new Set();
const notify = () => listeners.forEach((fn) => fn());

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault(); // não mostra o banner do navegador; o botão do app decide quando
  deferred = e;
  notify();
});
window.addEventListener("appinstalled", () => {
  deferred = null;
  notify();
});

export function onInstallChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function installState() {
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if (standalone) return "installed";
  if (!window.isSecureContext) return "needs-https"; // o navegador só instala com HTTPS
  if (deferred) return "ready";
  if (/iPhone|iPad|iPod/.test(navigator.userAgent)) return "ios";
  return "unavailable";
}

export async function promptInstall() {
  if (!deferred) return false;
  deferred.prompt();
  const { outcome } = await deferred.userChoice;
  deferred = null; // cada evento só pode ser usado uma vez
  notify();
  return outcome === "accepted";
}
