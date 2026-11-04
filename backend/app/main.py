"""API do Rewind (FastAPI). Rode com: uvicorn app.main:create_app --factory"""

from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from . import crypto, db
from .config import Settings
from .ratelimit import RateLimiter
from .routes import auth, daily, friends, invites, photos, timelapses, trips
from .storage import Storage
from .timelapse import Worker


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db.migrate(settings.db_path)

    if not settings.key_file.is_file():
        raise SystemExit(
            f"Chave de criptografia não encontrada em {settings.key_file}. "
            "Crie uma com: python -m app.cli generate-key (e guarde uma cópia fora do servidor!)")
    storage = Storage(settings.photos_dir, crypto.Box(crypto.load_key(settings.key_file)))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # A fila de timelapse liga junto com o servidor e desliga junto.
        app.state.worker = Worker(settings, storage)
        app.state.worker.start()
        yield
        app.state.worker.stop()

    app = FastAPI(title="Rewind", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.settings = settings
    app.state.storage = storage
    app.state.limits = {
        # Login: 20 tentativas por IP e 5 erros por usuário a cada 15 minutos.
        "login_ip": RateLimiter(20, 15 * 60),
        "login_user": RateLimiter(5, 15 * 60),
        # Links de convite: 30 consultas/usos por IP a cada 15 minutos.
        "invite_ip": RateLimiter(30, 15 * 60),
    }

    # --- Proteções que valem pra todas as rotas -------------------------------

    max_body = (settings.max_upload_mb + 1) * 1024 * 1024  # a foto + folga pro resto do formulário

    @app.middleware("http")
    async def protections(request: Request, call_next):
        # Contra CSRF: um site de fora não pode mandar POST/PUT/DELETE pra cá usando o
        # seu cookie. O cookie SameSite=Lax já barra isso; o Origin é uma segunda trava.
        # Comparamos só o nome do site, sem a porta: o Nginx Proxy Manager repassa o Host
        # sem a porta (https://site:8443 chega aqui como "site").
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            host = urlsplit("//" + request.headers.get("host", "")).hostname
            if origin and urlsplit(origin).hostname != host:
                return JSONResponse({"detail": "Origem não permitida"}, status_code=403)
            # Recusa upload gigante ANTES de ler: senão o servidor gravaria tudo em disco
            # (arquivo temporário) só pra descobrir depois que passou do limite.
            length = request.headers.get("content-length", "")
            if length.isdigit() and int(length) > max_body:
                return JSONResponse({"detail": f"Arquivo maior que {settings.max_upload_mb} MB"},
                                    status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"  # não vaza tokens de convite da URL
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/"):
            # Dados pessoais não ficam em cache, a não ser que a rota diga outra coisa (fotos).
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    # --- API ------------------------------------------------------------------

    @app.get("/api/health")
    def health():
        return {"ok": True}

    for module in (auth, friends, trips, invites, photos, daily, timelapses):
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
