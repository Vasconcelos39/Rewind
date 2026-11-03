"""Dependências das rotas: conexão com o banco, usuário logado e checagens comuns."""

import sqlite3
from typing import Iterator

from fastapi import Depends, HTTPException, Request

from . import db, security
from .config import Settings

COOKIE_NAME = "rewind_session"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_conn(settings: Settings = Depends(get_settings)) -> Iterator[sqlite3.Connection]:
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


def client_ip(request: Request) -> str:
    # Atrás do proxy, o uvicorn já troca isso pelo IP real (veja --forwarded-allow-ips na fase 6).
    return request.client.host if request.client else "?"


def user_out(user: sqlite3.Row) -> dict:
    # Só o que o front precisa; o hash da senha nunca sai daqui.
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "is_admin": bool(user["is_admin"]),
    }


def public_user(user: sqlite3.Row) -> dict:
    """O que outra pessoa pode ver de você."""
    return {"id": user["id"], "username": user["username"], "display_name": user["display_name"]}


def is_member(conn: sqlite3.Connection, trip_id: int, user_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM trip_members WHERE trip_id = ? AND user_id = ?", (trip_id, user_id)
    ).fetchone() is not None


def require_member(conn: sqlite3.Connection, trip_id: int, user_id: int) -> None:
    # 404 e não 403: quem não é membro nem fica sabendo que a viagem existe.
    if not is_member(conn, trip_id, user_id):
        raise HTTPException(404, "Viagem não encontrada")


def are_friends(conn: sqlite3.Connection, a: int, b: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM friendships WHERE status = 'accepted' AND"
        " ((requester_id = ? AND addressee_id = ?) OR (requester_id = ? AND addressee_id = ?))",
        (a, b, b, a),
    ).fetchone() is not None
