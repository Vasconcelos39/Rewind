// Chamadas à API. O cookie de sessão vai sozinho (mesma origem), e o JavaScript
// nunca enxerga o token, porque o cookie é httpOnly.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status; // 0 = não deu nem pra falar com o servidor
  }
}

// O App escuta este evento e volta pra tela de login.
export const LOGGED_OUT_EVENT = "rewind:logged-out";

export async function api(path, { method = "GET", body, file } = {}) {
  let headers, payload;
  if (file) {
    // Upload: o navegador monta o multipart sozinho (não definir Content-Type à mão).
    payload = new FormData();
    payload.append("file", file, "foto.jpg");
  } else if (body) {
    headers = { "Content-Type": "application/json" };
    payload = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(`/api${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "Sem conexão com o servidor. Confira a internet.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // Sessão venceu ou foi encerrada (ex.: trocou a senha em outro aparelho): volta pro login.
    // O próprio login errado também dá 401, mas esse a tela de login trata sozinha.
    if (res.status === 401 && path !== "/auth/login") {
      window.dispatchEvent(new Event(LOGGED_OUT_EVENT));
    }
    // FastAPI manda {detail: "..."}; erros de validação vêm como lista.
    const msg = typeof data.detail === "string" ? data.detail : "Algo deu errado";
    throw new ApiError(res.status, msg);
  }
  return data;
}
