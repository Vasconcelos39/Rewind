"""Amizades: pedir, aceitar, recusar e desfazer."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..config import Settings, now_iso
from ..deps import current_user, get_conn, get_settings, public_user
from ..streak import count_streak, selfie_days

router = APIRouter(prefix="/api/friends")


class FriendRequestIn(BaseModel):
    username: str


def _pair(conn: sqlite3.Connection, a: int, b: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM friendships WHERE"
        " (requester_id = ? AND addressee_id = ?) OR (requester_id = ? AND addressee_id = ?)",
        (a, b, b, a),
    ).fetchone()


def make_friends(conn: sqlite3.Connection, a: int, b: int) -> None:
    """Deixa A e B amigos na hora (usado pelos links de convite)."""
    row = _pair(conn, a, b)
    if row is None:
        conn.execute(
            "INSERT INTO friendships (requester_id, addressee_id, status, created_at, accepted_at)"
            " VALUES (?, ?, 'accepted', ?, ?)", (a, b, now_iso(), now_iso()))
    elif row["status"] == "pending":
        conn.execute("UPDATE friendships SET status = 'accepted', accepted_at = ? WHERE id = ?",
                     (now_iso(), row["id"]))


@router.get("")
def list_friends(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn),
                 settings: Settings = Depends(get_settings)):
    day = settings.today().isoformat()
    my_days = selfie_days(conn, user["id"])
    nudged = {r[0] for r in conn.execute(
        "SELECT to_user_id FROM nudges WHERE from_user_id = ? AND day = ?", (user["id"], day))}
    rows = conn.execute(
        "SELECT f.status, f.requester_id, u.* FROM friendships f"
        " JOIN users u ON u.id = CASE WHEN f.requester_id = ? THEN f.addressee_id ELSE f.requester_id END"
        " WHERE ? IN (f.requester_id, f.addressee_id) ORDER BY u.display_name COLLATE NOCASE",
        (user["id"], user["id"]),
    ).fetchall()
    out = {"friends": [], "incoming": [], "outgoing": []}
    for r in rows:
        if r["status"] == "accepted":
            # Amigo vê só o status do dia e a streak; as fotos ficam nas viagens.
            days = selfie_days(conn, r["id"])
            out["friends"].append({
                **public_user(r),
                "sent_today": settings.today() in days,
                "streak": count_streak(days, settings.today()),
                "pair_streak": count_streak(days & my_days, settings.today()),
                "nudged_today": r["id"] in nudged,
            })
        elif r["requester_id"] == user["id"]:
            out["outgoing"].append(public_user(r))
        else:
            out["incoming"].append(public_user(r))
    return out


@router.post("")
def send_request(body: FriendRequestIn, user=Depends(current_user),
                 conn: sqlite3.Connection = Depends(get_conn)):
    other = conn.execute("SELECT * FROM users WHERE username = ?", (body.username.strip(),)).fetchone()
    if other is None:
        raise HTTPException(404, "Usuário não encontrado")
    if other["id"] == user["id"]:
        raise HTTPException(400, "Você não pode adicionar você mesmo")

    row = _pair(conn, user["id"], other["id"])
    if row is None:
        conn.execute(
            "INSERT INTO friendships (requester_id, addressee_id, status, created_at)"
            " VALUES (?, ?, 'pending', ?)", (user["id"], other["id"], now_iso()))
        status = "pending"
    elif row["status"] == "pending" and row["addressee_id"] == user["id"]:
        # O outro já tinha te pedido: pedir de volta = aceitar.
        conn.execute("UPDATE friendships SET status = 'accepted', accepted_at = ? WHERE id = ?",
                     (now_iso(), row["id"]))
        status = "accepted"
    else:
        status = row["status"]  # já pedido ou já amigos: nada muda
    conn.commit()
    return {"status": status, "user": public_user(other)}


@router.post("/{user_id}/accept")
def accept(user_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    cur = conn.execute(
        "UPDATE friendships SET status = 'accepted', accepted_at = ?"
        " WHERE requester_id = ? AND addressee_id = ? AND status = 'pending'",
        (now_iso(), user_id, user["id"]))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "Pedido não encontrado")
    return {"ok": True}


@router.delete("/{user_id}")
def remove(user_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    """Recusa um pedido, cancela um pedido seu ou desfaz a amizade."""
    conn.execute(
        "DELETE FROM friendships WHERE"
        " (requester_id = ? AND addressee_id = ?) OR (requester_id = ? AND addressee_id = ?)",
        (user["id"], user_id, user_id, user["id"]))
    # Convites de viagem pendentes entre os dois perdem o sentido.
    conn.execute(
        "DELETE FROM trip_invites WHERE"
        " (from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?)",
        (user["id"], user_id, user_id, user["id"]))
    conn.commit()
    return {"ok": True}
