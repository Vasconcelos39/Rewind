"""Pedir um timelapse, acompanhar o progresso e assistir."""

import re
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import timelapse
from ..config import Settings, now_iso
from ..deps import current_user, get_conn, get_settings, is_member, require_member

router = APIRouter(prefix="/api")


class TimelapseIn(BaseModel):
    user_id: int
    fps: int | None = Field(default=None, ge=1, le=30)
    kind: Literal["selfie", "body"] = "selfie"  # rosto ou corpo: cada um tem o seu vídeo


def job_out(j: sqlite3.Row) -> dict:
    return {"id": j["id"], "trip_id": j["trip_id"], "user_id": j["user_id"], "kind": j["kind"], "fps": j["fps"],
            "status": j["status"], "progress": j["progress"], "frame_count": j["frame_count"],
            "error": j["error"], "finished_at": j["finished_at"],
            "url": f"/api/timelapses/{j['id']}/video" if j["status"] == "done" else None}


def _job_for_viewer(conn: sqlite3.Connection, job_id: int, user_id: int) -> sqlite3.Row:
    job = conn.execute("SELECT * FROM timelapses WHERE id = ?", (job_id,)).fetchone()
    # Só membro da viagem vê (e de novo 404, pra não revelar que existe).
    if job is None or not is_member(conn, job["trip_id"], user_id):
        raise HTTPException(404, "Timelapse não encontrado")
    return job


@router.post("/trips/{trip_id}/timelapses")
def request_timelapse(trip_id: int, body: TimelapseIn, request: Request, user=Depends(current_user),
                      conn: sqlite3.Connection = Depends(get_conn),
                      settings: Settings = Depends(get_settings)):
    require_member(conn, trip_id, user["id"])
    if not is_member(conn, trip_id, body.user_id):
        raise HTTPException(404, "Essa pessoa não está na viagem")
    fps = body.fps or settings.default_fps
    photos = timelapse.trip_selfies(conn, trip_id, body.user_id, body.kind)
    if len(photos) < 2:
        what = "selfies do rosto" if body.kind == "selfie" else "fotos de corpo"
        raise HTTPException(400, f"Precisa de pelo menos 2 {what} no álbum")
    fp = timelapse.fingerprint(photos, fps)

    # Cache: se já existe (pronto, na fila ou rodando) com as mesmas fotos, reaproveita.
    same = conn.execute(
        "SELECT * FROM timelapses WHERE trip_id = ? AND user_id = ? AND kind = ? AND fps = ? AND fingerprint = ?"
        " AND status != 'error' ORDER BY id DESC LIMIT 1", (trip_id, body.user_id, body.kind, fps, fp)).fetchone()
    if same:
        return job_out(same)

    # Foto nova = vídeo velho não vale mais: apaga os antigos dessa pessoa nesse fps.
    # (Um que esteja rodando agora termina e é apagado no próximo pedido.)
    old = conn.execute(
        "SELECT id, file_name FROM timelapses WHERE trip_id = ? AND user_id = ? AND kind = ? AND fps = ?"
        " AND status != 'running'", (trip_id, body.user_id, body.kind, fps)).fetchall()
    conn.executemany("DELETE FROM timelapses WHERE id = ?", [(o["id"],) for o in old])
    cur = conn.execute(
        "INSERT INTO timelapses (trip_id, user_id, kind, requested_by, fps, fingerprint, frame_count, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?)",
        (trip_id, body.user_id, body.kind, user["id"], fps, fp, len(photos), now_iso()))
    conn.commit()
    for o in old:
        if o["file_name"]:
            request.app.state.storage.delete(o["file_name"])
    worker = getattr(request.app.state, "worker", None)
    if worker:
        worker.wake()
    return job_out(conn.execute("SELECT * FROM timelapses WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.get("/trips/{trip_id}/timelapses")
def list_timelapses(trip_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    """O pedido mais recente de cada pessoa do álbum, de cada tipo (rosto e corpo)."""
    require_member(conn, trip_id, user["id"])
    rows = conn.execute(
        "SELECT * FROM timelapses WHERE id IN"
        " (SELECT MAX(id) FROM timelapses WHERE trip_id = ? GROUP BY user_id, kind)", (trip_id,)).fetchall()
    return [job_out(j) for j in rows]


@router.get("/timelapses/{job_id}")
def get_timelapse(job_id: int, user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    job = _job_for_viewer(conn, job_id, user["id"])
    # Posição na fila, pra mostrar "esperando 2 vídeos".
    ahead = conn.execute("SELECT COUNT(*) FROM timelapses WHERE status IN ('queued', 'running') AND id < ?",
                         (job_id,)).fetchone()[0] if job["status"] == "queued" else 0
    return {**job_out(job), "queue_ahead": ahead}


@router.get("/timelapses/{job_id}/video")
def get_video(job_id: int, request: Request, user=Depends(current_user),
              conn: sqlite3.Connection = Depends(get_conn)):
    job = _job_for_viewer(conn, job_id, user["id"])
    if job["status"] != "done":
        raise HTTPException(404, "Vídeo ainda não está pronto")
    data = request.app.state.storage.load(job["file_name"])
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=604800, immutable"}

    # O Safari só toca vídeo se o servidor aceitar pedidos de "pedaços" (Range).
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", request.headers.get("range", ""))
    if m and (m[1] or m[2]):
        size = len(data)
        if m[1]:
            start, end = int(m[1]), min(int(m[2]) if m[2] else size - 1, size - 1)
        else:  # "bytes=-500" = os últimos 500 bytes
            start, end = max(size - int(m[2]), 0), size - 1
        if start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        return Response(data[start:end + 1], status_code=206, media_type="video/mp4",
                        headers={**headers, "Content-Range": f"bytes {start}-{end}/{size}"})
    return Response(data, media_type="video/mp4", headers=headers)
