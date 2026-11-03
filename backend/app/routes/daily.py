"""O dia de hoje: sua streak, quanto tempo falta e as cutucadas dos amigos."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..config import Settings, now_iso
from ..deps import are_friends, current_user, get_conn, get_settings, public_user
from ..streak import seconds_left_today, user_streak

router = APIRouter(prefix="/api")


@router.get("/today")
def today_summary(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn),
                  settings: Settings = Depends(get_settings)):
    day = settings.today().isoformat()
    nudges = conn.execute(
        "SELECT n.id, n.created_at, n.seen_at, u.* FROM nudges n JOIN users u ON u.id = n.from_user_id"
        " WHERE n.to_user_id = ? AND n.day = ? ORDER BY n.created_at", (user["id"], day)).fetchall()
    return {
        "day": day,
        "seconds_left": seconds_left_today(settings),
        **user_streak(conn, settings, user["id"]),
        "nudges": [{"from": public_user(n), "at": n["created_at"], "seen": n["seen_at"] is not None}
                   for n in nudges],
    }


@router.post("/today/nudges/seen")
def mark_nudges_seen(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn),
                     settings: Settings = Depends(get_settings)):
    conn.execute("UPDATE nudges SET seen_at = ? WHERE to_user_id = ? AND day = ? AND seen_at IS NULL",
                 (now_iso(), user["id"], settings.today().isoformat()))
    conn.commit()
    return {"ok": True}


@router.post("/friends/{friend_id}/nudge")
def nudge(friend_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn),
          settings: Settings = Depends(get_settings)):
    if not are_friends(conn, user["id"], friend_id):
        raise HTTPException(404, "Amigo não encontrado")
    if user_streak(conn, settings, friend_id)["sent_today"]:
        raise HTTPException(400, "Já tirou a foto de hoje")
    # INSERT OR IGNORE + UNIQUE: a segunda cutucada do dia simplesmente não entra.
    cur = conn.execute(
        "INSERT OR IGNORE INTO nudges (from_user_id, to_user_id, day, created_at) VALUES (?, ?, ?, ?)",
        (user["id"], friend_id, settings.today().isoformat(), now_iso()))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(400, "Você já cutucou hoje")
    # Fase 7: aqui entra o envio da notificação push.
    return {"ok": True}
