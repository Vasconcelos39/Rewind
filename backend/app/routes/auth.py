"""Login, logout, "quem sou eu" e troca de senha."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from .. import security
from ..config import Settings
from ..deps import COOKIE_NAME, client_ip, current_user, get_conn, get_settings, user_out

router = APIRouter(prefix="/api/auth")


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


def start_session(conn: sqlite3.Connection, response: Response, settings: Settings, user_id: int):
    """Cria a sessão e grava o cookie. Usado no login e ao aceitar um convite."""
    token = security.create_session(conn, user_id, settings.session_days)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,                  # o JavaScript da página não lê o cookie
        secure=settings.cookie_secure,  # só viaja por HTTPS
        samesite="lax",                 # não vai junto em POST vindo de outro site
        path="/",
    )


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response,
          conn: sqlite3.Connection = Depends(get_conn),
          settings: Settings = Depends(get_settings)):
    limits = request.app.state.limits
    ip, user_key = client_ip(request), body.username.lower()
    if limits["login_ip"].blocked(ip) or limits["login_user"].blocked(user_key):
        raise HTTPException(429, "Muitas tentativas. Espere alguns minutos.")
    limits["login_ip"].hit(ip)

    user = security.authenticate(conn, body.username, body.password)
    if user is None:
        limits["login_user"].hit(user_key)
        # Mesma mensagem pra usuário inexistente e senha errada.
        raise HTTPException(401, "Usuário ou senha incorretos")
    limits["login_user"].reset(user_key)

    start_session(conn, response, settings, user["id"])
    return user_out(user)


@router.post("/logout")
def logout(request: Request, response: Response, conn: sqlite3.Connection = Depends(get_conn)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        security.delete_session(conn, token)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: sqlite3.Row = Depends(current_user)):
    return user_out(user)


@router.post("/password")
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
