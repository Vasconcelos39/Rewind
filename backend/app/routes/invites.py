"""Links de convite: uso único, valem 7 dias.

Quem abre o link pode criar a conta (se ainda não tem) e já entra na viagem
do convite, além de virar amigo de quem convidou.
"""

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from .. import security
from ..config import Settings, now_iso
from ..deps import client_ip, current_user, get_conn, get_settings, require_member, user_out
from .auth import start_session
from .friends import make_friends
from .trips import add_member

router = APIRouter(prefix="/api/invite-links")

VALID_DAYS = 7


class LinkIn(BaseModel):
    trip_id: int | None = None


class SignupIn(BaseModel):
    username: str
    password: str
    display_name: str | None = None


def _limit(request: Request) -> None:
    # Todo acesso a link conta: assim ninguém fica chutando tokens.
    limiter, ip = request.app.state.limits["invite_ip"], client_ip(request)
    if limiter.blocked(ip):
        raise HTTPException(429, "Muitas tentativas. Espere alguns minutos.")
    limiter.hit(ip)


def _valid_link(conn: sqlite3.Connection, token: str) -> sqlite3.Row:
    link = conn.execute(
        "SELECT l.*, t.name AS trip_name, u.display_name AS inviter_name FROM invite_links l"
        " JOIN users u ON u.id = l.created_by LEFT JOIN trips t ON t.id = l.trip_id"
        " WHERE l.token_hash = ?", (security.token_hash(token),)).fetchone()
    # Mesma resposta pra inexistente, usado e vencido: o link simplesmente não vale.
    if link is None or link["used_at"] or link["expires_at"] <= now_iso():
        raise HTTPException(404, "Convite inválido ou expirado")
    return link


def _claim(conn: sqlite3.Connection, link_id: int, user_id: int | None) -> None:
    """Marca o link como usado. O WHERE garante uso único mesmo com dois cliques ao mesmo tempo."""
    cur = conn.execute(
        "UPDATE invite_links SET used_at = ?, used_by = ? WHERE id = ? AND used_at IS NULL",
        (now_iso(), user_id, link_id))
    if cur.rowcount != 1:
        conn.rollback()
        raise HTTPException(404, "Convite inválido ou expirado")


def _apply(conn: sqlite3.Connection, settings: Settings, link: sqlite3.Row, user_id: int) -> None:
    make_friends(conn, link["created_by"], user_id)
    if link["trip_id"] is not None:
        add_member(conn, settings, link["trip_id"], user_id)


@router.post("")
def create_link(body: LinkIn, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    if body.trip_id is not None:
        require_member(conn, body.trip_id, user["id"])  # só membro convida pra viagem
    token = secrets.token_urlsafe(24)
    expires = datetime.now(timezone.utc) + timedelta(days=VALID_DAYS)
    conn.execute(
        "INSERT INTO invite_links (token_hash, created_by, trip_id, created_at, expires_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (security.token_hash(token), user["id"], body.trip_id, now_iso(),
         expires.isoformat(timespec="seconds")))
    conn.commit()
    # O token só aparece agora; o banco guarda só o hash dele.
    return {"path": f"/convite/{token}", "expires_at": expires.isoformat(timespec="seconds")}


@router.get("/{token}")
def link_info(token: str, request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    """O que a tela de convite mostra antes de aceitar."""
    _limit(request)
    link = _valid_link(conn, token)
    return {"inviter": link["inviter_name"], "trip_name": link["trip_name"],
            "expires_at": link["expires_at"]}


@router.post("/{token}/accept")
def accept_logged_in(token: str, request: Request, user=Depends(current_user),
                     conn: sqlite3.Connection = Depends(get_conn),
                     settings: Settings = Depends(get_settings)):
    """Quem já tem conta: só entra na viagem e vira amigo."""
    _limit(request)
    link = _valid_link(conn, token)
    if link["created_by"] == user["id"]:
        raise HTTPException(400, "Esse convite é seu: mande o link pra outra pessoa")
    _claim(conn, link["id"], user["id"])
    _apply(conn, settings, link, user["id"])
    conn.commit()
    return {"trip_id": link["trip_id"]}


@router.post("/{token}/signup")
def accept_with_signup(token: str, body: SignupIn, request: Request, response: Response,
                       conn: sqlite3.Connection = Depends(get_conn),
                       settings: Settings = Depends(get_settings)):
    """Quem ainda não tem conta: cria a conta, já sai logado e entra na viagem."""
    _limit(request)
    link = _valid_link(conn, token)
    try:
        # Valida antes de gastar o convite: um erro de digitação não queima o link.
        security.validate_username(body.username)
        security.validate_password(body.password)
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (body.username,)).fetchone():
            raise security.InvalidInput("Esse usuário já existe")
        # Gasta o convite e cria a conta na mesma transação: ou acontecem os dois, ou nenhum.
        _claim(conn, link["id"], None)
        user_id = security.create_user(conn, body.username, body.password, body.display_name,
                                       commit=False)
    except security.InvalidInput as e:
        conn.rollback()
        raise HTTPException(400, str(e))
    conn.execute("UPDATE invite_links SET used_by = ? WHERE id = ?", (user_id, link["id"]))
    _apply(conn, settings, link, user_id)
    conn.commit()

    start_session(conn, response, settings, user_id)
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return {"user": user_out(user), "trip_id": link["trip_id"]}
