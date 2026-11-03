"""API do Rewind (FastAPI). Rode com: uvicorn app.main:create_app --factory"""

import sqlite3
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import db, security
from .config import Settings
from .ratelimit import RateLimiter

COOKIE_NAME = "rewind_session"


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


def user_out(user: sqlite3.Row) -> dict:
    # Só o que o front precisa; o hash da senha nunca sai daqui.
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "is_admin": bool(user["is_admin"]),
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db.migrate(settings.db_path)

    app = FastAPI(title="Rewind", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    # Login: no máximo 20 tentativas por IP e 5 erros por usuário a cada 15 minutos.
    login_ip_limit = RateLimiter(20, 15 * 60)
    login_user_limit = RateLimiter(5, 15 * 60)

    # --- Dependências: cada rota pede o que precisa ---------------------------

    def get_conn() -> Iterator[sqlite3.Connection]:
        conn = db.connect(settings.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def current_user(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> sqlite3.Row:
        user = security.user_from_session(conn, request.cookies.get(COOKIE_NAME))
        if user is None:
            raise HTTPException(401, "Faça login")
        return user

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

    # --- Rotas de autenticação ------------------------------------------------

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.post("/api/auth/login")
    def login(body: LoginIn, request: Request, response: Response,
              conn: sqlite3.Connection = Depends(get_conn)):
        ip = request.client.host if request.client else "?"
        user_key = body.username.lower()
        if login_ip_limit.blocked(ip) or login_user_limit.blocked(user_key):
            raise HTTPException(429, "Muitas tentativas. Espere alguns minutos.")
        login_ip_limit.hit(ip)

        user = security.authenticate(conn, body.username, body.password)
        if user is None:
            login_user_limit.hit(user_key)
            # Mesma mensagem pra usuário inexistente e senha errada.
            raise HTTPException(401, "Usuário ou senha incorretos")
        login_user_limit.reset(user_key)

        token = security.create_session(conn, user["id"], settings.session_days)
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=settings.session_days * 86400,
            httponly=True,                  # o JavaScript da página não lê o cookie
            secure=settings.cookie_secure,  # só viaja por HTTPS
            samesite="lax",                 # não vai junto em POST vindo de outro site
            path="/",
        )
        return user_out(user)

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, conn: sqlite3.Connection = Depends(get_conn)):
        token = request.cookies.get(COOKIE_NAME)
        if token:
            security.delete_session(conn, token)
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"ok": True}

    @app.get("/api/auth/me")
    def me(user: sqlite3.Row = Depends(current_user)):
        return user_out(user)

    @app.post("/api/auth/password")
    def change_password(body: PasswordIn, request: Request,
                        user: sqlite3.Row = Depends(current_user),
                        conn: sqlite3.Connection = Depends(get_conn)):
        if security.authenticate(conn, user["username"], body.current_password) is None:
            raise HTTPException(400, "Senha atual incorreta")
        try:
            security.set_password(conn, user["id"], body.new_password)
        except security.InvalidInput as e:
            raise HTTPException(400, str(e))
        # Trocou a senha: derruba as sessões dos outros aparelhos.
        security.delete_other_sessions(conn, user["id"], request.cookies.get(COOKIE_NAME))
        return {"ok": True}

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
