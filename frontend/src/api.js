// Chamadas à API. O cookie de sessão vai sozinho (mesma origem), e o JavaScript
// nunca enxerga o token, porque o cookie é httpOnly.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

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
  const res = await fetch(`/api${path}`, { method, headers, body: payload });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // FastAPI manda {detail: "..."}; erros de validação vêm como lista.
    const msg = typeof data.detail === "string" ? data.detail : "Algo deu errado";
    throw new ApiError(res.status, msg);
  }
  return data;
}
