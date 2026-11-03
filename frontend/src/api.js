// Chamadas à API. O cookie de sessão vai sozinho (mesma origem), e o JavaScript
// nunca enxerga o token, porque o cookie é httpOnly.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // FastAPI manda {detail: "..."}; erros de validação vêm como lista.
    const msg = typeof data.detail === "string" ? data.detail : "Algo deu errado";
    throw new ApiError(res.status, msg);
  }
  return data;
}
