import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { ApiError } from "./api.js";
import "./lib/install.js"; // começa a escutar o "pode instalar" do navegador o quanto antes
import "./styles.css";

// Quando a sessão cai, cada tela aberta recebe um 401 nas chamadas dela. O App já volta
// pro login sozinho (evento LOGGED_OUT_EVENT), então esses erros não precisam virar
// "Uncaught (in promise)" no console.
window.addEventListener("unhandledrejection", (e) => {
  if (e.reason instanceof ApiError && e.reason.status === 401) e.preventDefault();
});

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
