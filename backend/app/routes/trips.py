"""Álbuns (no código, "trips"): criar, listar, ver, editar, convidar amigos e sair.

A data final é opcional. Sem ela, o álbum fica aberto até alguém encerrar.
Com ela, o álbum fica "encerrado" depois desse dia (o próprio dia ainda vale).
"""

import sqlite3
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..config import Settings, now_iso
from ..deps import (are_friends, current_user, get_conn, get_settings, is_member,
                    public_user, require_member)
from ..streak import user_streak
from .photos import photo_out

router = APIRouter(prefix="/api")


class TripIn(BaseModel):
    name: str
    end_date: date | None = None


class TripUpdateIn(BaseModel):
    name: str | None = None
    end_date: date | None = None  # mandar null tira a data final


def _clean_name(raw: str) -> str:
    name = raw.strip()
    if not 1 <= len(name) <= 80:
        raise HTTPException(400, "Nome deve ter de 1 a 80 caracteres")
    return name


def start_day(trip: sqlite3.Row, settings: Settings) -> date:
    """O primeiro dia do álbum: o dia (no fuso do Rewind) em que ele foi criado."""
    return datetime.fromisoformat(trip["created_at"]).astimezone(settings.tz).date()


class TripInviteIn(BaseModel):
    user_id: int


def add_member(conn: sqlite3.Connection, settings: Settings, trip_id: int, user_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO trip_members (trip_id, user_id, joined_at, joined_day)"
        " VALUES (?, ?, ?, ?)", (trip_id, user_id, now_iso(), settings.today().isoformat()))
    conn.execute("DELETE FROM trip_invites WHERE trip_id = ? AND to_user_id = ?", (trip_id, user_id))


def _trip_out(conn: sqlite3.Connection, trip: sqlite3.Row, settings: Settings) -> dict:
    today, start = settings.today(), start_day(trip, settings)
    end = date.fromisoformat(trip["end_date"]) if trip["end_date"] else None
    ended = end is not None and today > end
    count = conn.execute("SELECT COUNT(*) FROM trip_members WHERE trip_id = ?", (trip["id"],)).fetchone()[0]
    return {
        "id": trip["id"], "name": trip["name"], "end_date": trip["end_date"],
        "start_day": start.isoformat(),
        "status": "ended" if ended else "active",
        # "dia 12" do álbum (num encerrado, quantos dias ele durou)
        "day_number": ((end if ended else today) - start).days + 1,
        "days_left": (end - today).days if end and not ended else None,
        "member_count": count,
    }


@router.post("/trips")
def create_trip(body: TripIn, user=Depends(current_user),
                conn: sqlite3.Connection = Depends(get_conn),
                settings: Settings = Depends(get_settings)):
    name = _clean_name(body.name)
    if body.end_date is not None and body.end_date <= settings.today():
        raise HTTPException(400, "A data final precisa ser no futuro")
    end = body.end_date.isoformat() if body.end_date else None
    cur = conn.execute("INSERT INTO trips (name, end_date, created_by, created_at) VALUES (?, ?, ?, ?)",
                       (name, end, user["id"], now_iso()))
    add_member(conn, settings, cur.lastrowid, user["id"])
    conn.commit()
    trip = conn.execute("SELECT * FROM trips WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _trip_out(conn, trip, settings)


@router.get("/trips")
def list_trips(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn),
               settings: Settings = Depends(get_settings)):
    rows = conn.execute(
        "SELECT t.* FROM trips t JOIN trip_members m ON m.trip_id = t.id"
        " WHERE m.user_id = ? ORDER BY t.created_at DESC", (user["id"],)).fetchall()
    # O front separa em "em andamento" e "encerrados" pelo campo status.
    return [_trip_out(conn, t, settings) for t in rows]


@router.patch("/trips/{trip_id}")
def update_trip(trip_id: int, body: TripUpdateIn, user=Depends(current_user),
                conn: sqlite3.Connection = Depends(get_conn),
                settings: Settings = Depends(get_settings)):
    """Renomear, pôr/tirar a data final ou encerrar (data final = hoje). Qualquer membro pode."""
    require_member(conn, trip_id, user["id"])
    trip = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    if body.name is not None:
        conn.execute("UPDATE trips SET name = ? WHERE id = ?", (_clean_name(body.name), trip_id))
    # model_fields_set diferencia "não mandou end_date" de "mandou end_date: null".
    if "end_date" in body.model_fields_set:
        if body.end_date is not None and body.end_date < start_day(trip, settings):
            raise HTTPException(400, "A data final não pode ser antes do começo do álbum")
        conn.execute("UPDATE trips SET end_date = ? WHERE id = ?",
                     (body.end_date.isoformat() if body.end_date else None, trip_id))
    conn.commit()
    return _trip_out(conn, conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone(), settings)


@router.get("/trips/{trip_id}")
def get_trip(trip_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn),
             settings: Settings = Depends(get_settings)):
    require_member(conn, trip_id, user["id"])
    trip = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    members = conn.execute(
        "SELECT u.*, m.joined_day FROM trip_members m JOIN users u ON u.id = m.user_id"
        " WHERE m.trip_id = ? ORDER BY m.joined_at", (trip_id,)).fetchall()
    pending = conn.execute(
        "SELECT u.* FROM trip_invites i JOIN users u ON u.id = i.to_user_id WHERE i.trip_id = ?",
        (trip_id,)).fetchall()
    today = settings.today().isoformat()
    in_period = trip["end_date"] is None or today <= trip["end_date"]

    def member_out(m):
        # Quem já mandou hoje, a streak e a selfie de hoje (se o dia está no período da viagem).
        selfie = conn.execute("SELECT * FROM photos WHERE user_id = ? AND kind = 'selfie' AND day = ?",
                              (m["id"], today)).fetchone()
        return {**public_user(m), "joined_day": m["joined_day"],
                **user_streak(conn, settings, m["id"]),
                "today_photo": photo_out(selfie) if selfie and in_period else None}

    return {
        **_trip_out(conn, trip, settings),
        "members": [member_out(m) for m in members],
        "pending_invites": [public_user(u) for u in pending],
    }


@router.post("/trips/{trip_id}/invites")
def invite_friend(trip_id: int, body: TripInviteIn, user=Depends(current_user),
                  conn: sqlite3.Connection = Depends(get_conn)):
    require_member(conn, trip_id, user["id"])
    # Só dá pra convidar amigos: ninguém recebe convite de um desconhecido.
    if not are_friends(conn, user["id"], body.user_id):
        raise HTTPException(400, "Só dá pra convidar amigos")
    if is_member(conn, trip_id, body.user_id):
        raise HTTPException(400, "Essa pessoa já está no álbum")
    conn.execute(
        "INSERT OR IGNORE INTO trip_invites (trip_id, from_user_id, to_user_id, created_at)"
        " VALUES (?, ?, ?, ?)", (trip_id, user["id"], body.user_id, now_iso()))
    conn.commit()
    return {"ok": True}


@router.get("/trip-invites")
def my_trip_invites(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    rows = conn.execute(
        "SELECT i.id, t.name AS trip_name, t.end_date, u.* FROM trip_invites i"
        " JOIN trips t ON t.id = i.trip_id JOIN users u ON u.id = i.from_user_id"
        " WHERE i.to_user_id = ? ORDER BY i.created_at DESC", (user["id"],)).fetchall()
    return [{"id": r[0], "trip_name": r["trip_name"], "end_date": r["end_date"],
             "from": public_user(r)} for r in rows]


def _my_invite(conn: sqlite3.Connection, invite_id: int, user_id: int) -> sqlite3.Row:
    invite = conn.execute("SELECT * FROM trip_invites WHERE id = ? AND to_user_id = ?",
                          (invite_id, user_id)).fetchone()
    if invite is None:
        raise HTTPException(404, "Convite não encontrado")
    return invite


@router.post("/trip-invites/{invite_id}/accept")
def accept_trip_invite(invite_id: int, user=Depends(current_user),
                       conn: sqlite3.Connection = Depends(get_conn),
                       settings: Settings = Depends(get_settings)):
    invite = _my_invite(conn, invite_id, user["id"])
    add_member(conn, settings, invite["trip_id"], user["id"])
    conn.commit()
    return {"trip_id": invite["trip_id"]}


@router.delete("/trip-invites/{invite_id}")
def decline_trip_invite(invite_id: int, user=Depends(current_user),
                        conn: sqlite3.Connection = Depends(get_conn)):
    _my_invite(conn, invite_id, user["id"])
    conn.execute("DELETE FROM trip_invites WHERE id = ?", (invite_id,))
    conn.commit()
    return {"ok": True}


@router.post("/trips/{trip_id}/leave")
def leave_trip(trip_id: int, request: Request, user=Depends(current_user),
               conn: sqlite3.Connection = Depends(get_conn)):
    require_member(conn, trip_id, user["id"])
    conn.execute("DELETE FROM trip_members WHERE trip_id = ? AND user_id = ?", (trip_id, user["id"]))
    conn.execute("DELETE FROM trip_invites WHERE trip_id = ? AND from_user_id = ?", (trip_id, user["id"]))
    # O último a sair apaga o álbum (e, pelo ON DELETE CASCADE, os convites dela).
    left = conn.execute("SELECT COUNT(*) FROM trip_members WHERE trip_id = ?", (trip_id,)).fetchone()[0]
    files = []
    if left == 0:
        files = [r[0] for r in conn.execute(
            "SELECT file_name FROM photos WHERE trip_id = ?"
            " UNION ALL SELECT file_name FROM timelapses WHERE trip_id = ? AND file_name IS NOT NULL",
            (trip_id, trip_id))]
        conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))  # as linhas das fotos vão junto
    conn.commit()
    for name in files:  # e os arquivos também, depois que o banco confirmou
        request.app.state.storage.delete(name)
    return {"ok": True}
