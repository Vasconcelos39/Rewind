"""API do Rewind (FastAPI). Rode com: uvicorn app.main:create_app --factory"""

from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from . import db
from .config import Settings
from .ratelimit import RateLimiter
from .routes import auth, friends, invites, trips


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db.migrate(settings.db_path)

    app = FastAPI(title="Rewind", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.limits = {
        # Login: 20 tentativas por IP e 5 erros por usuário a cada 15 minutos.
        "login_ip": RateLimiter(20, 15 * 60),
        "login_user": RateLimiter(5, 15 * 60),
        # Links de convite: 30 consultas/usos por IP a cada 15 minutos.
        "invite_ip": RateLimiter(30, 15 * 60),
    }

    # --- Proteções que valem pra todas as rotas -------------------------------

    @app.middleware("http")
    async def protections(request: Request, call_next):
        # Contra CSRF: um site de fora não pode mandar POST/PUT/DELETE pra cá usando o
        # seu cookie. O cookie SameSite=Lax já barra isso; o Origin é uma segunda trava.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Origem não permitida"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"  # não vaza tokens de convite da URL
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # --- API ------------------------------------------------------------------

    @app.get("/api/health")
    def health():
        return {"ok": True}

    for module in (auth, friends, trips, invites):
        app.include_router(module.router)

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def api_not_found(rest: str):
        raise HTTPException(404, "Rota não encontrada")

    # --- Front (o build do Vite) ----------------------------------------------
    # Só a pasta do build é servida; as fotos NUNCA passam por aqui.

    dist = settings.frontend_dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        file = (dist / path).resolve()
        if path and file.is_relative_to(dist) and file.is_file():
            return FileResponse(file)
        index = dist / "index.html"
        if not index.is_file():
            return JSONResponse({"detail": "Front não compilado (rode npm run build)"}, 404)
        # Qualquer outra rota (ex.: /convite/abc) abre o app, que decide a tela.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app
