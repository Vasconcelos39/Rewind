"""Upload e leitura de fotos. Toda foto passa por aqui: nunca existe link direto pro arquivo."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response

from .. import images
from ..config import Settings, now_iso
from ..deps import current_user, get_conn, get_settings, require_member

router = APIRouter(prefix="/api")


def photo_out(p: sqlite3.Row) -> dict:
    return {"id": p["id"], "user_id": p["user_id"], "day": p["day"], "kind": p["kind"],
            "trip_id": p["trip_id"], "width": p["width"], "height": p["height"],
            "url": f"/api/photos/{p['id']}"}


async def _read_upload(file: UploadFile, settings: Settings) -> images.Processed:
    limit = settings.max_upload_mb * 1024 * 1024
    raw = await file.read(limit + 1)  # lê no máximo 1 byte além do limite
    if len(raw) > limit:
        raise HTTPException(413, f"Imagem maior que {settings.max_upload_mb} MB")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "Envie uma imagem")
    try:
        return images.process(raw)  # o tipo de verdade é conferido aqui, pelo conteúdo
    except images.BadImage as e:
        raise HTTPException(400, str(e))


def _insert(conn, storage, user_id, day, kind, trip_id, img: images.Processed) -> sqlite3.Row:
    name = storage.save(img.data)
    try:
        cur = conn.execute(
            "INSERT INTO photos (user_id, day, kind, trip_id, file_name, width, height, size_bytes, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, day, kind, trip_id, name, img.width, img.height, len(img.data), now_iso()))
    except Exception:
        storage.delete(name)  # banco falhou: não deixa arquivo órfão
        raise
    return conn.execute("SELECT * FROM photos WHERE id = ?", (cur.lastrowid,)).fetchone()


def can_view(conn: sqlite3.Connection, viewer_id: int, photo: sqlite3.Row) -> bool:
    """A regra de quem vê o quê. Toda foto servida passa por aqui."""
    if photo["user_id"] == viewer_id:
        return True
    if photo["kind"] == "extra":
        # Foto extra: qualquer membro do álbum onde ela foi publicada.
        return conn.execute("SELECT 1 FROM trip_members WHERE trip_id = ? AND user_id = ?",
                            (photo["trip_id"], viewer_id)).fetchone() is not None
    # Rosto e corpo: você e o dono estão num mesmo álbum, e o dia da foto está no período
    # dela (do dia em que o dono entrou até a data final). Amigo fora da viagem não vê.
    return conn.execute(
        "SELECT 1 FROM trip_members owner"
        " JOIN trip_members viewer ON viewer.trip_id = owner.trip_id AND viewer.user_id = ?"
        " JOIN trips t ON t.id = owner.trip_id"
        " WHERE owner.user_id = ? AND ? BETWEEN owner.joined_day AND COALESCE(t.end_date, '9999-12-31')",
        (viewer_id, photo["user_id"], photo["day"])).fetchone() is not None


# --- Fotos do dia: rosto (obrigatória) e corpo (opcional, depois do rosto) -----------

def _daily_photo(conn, user_id: int, kind: str, day: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM photos WHERE user_id = ? AND kind = ? AND day = ?",
                        (user_id, kind, day)).fetchone()


def _previous(conn, user_id: int, kind: str, day: str) -> sqlite3.Row | None:
    """A última foto desse tipo antes de hoje: a que aparece por cima da câmera."""
    return conn.execute(
        "SELECT * FROM photos WHERE user_id = ? AND kind = ? AND day < ? ORDER BY day DESC LIMIT 1",
        (user_id, kind, day)).fetchone()


@router.get("/photos/today")
def today(user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn),
          settings: Settings = Depends(get_settings)):
    """As fotos de hoje (se já tirou) e as anteriores de cada tipo."""
    day = settings.today().isoformat()
    out = lambda p: photo_out(p) if p else None
    return {
        "day": day,
        "selfie": out(_daily_photo(conn, user["id"], "selfie", day)),
        "previous": out(_previous(conn, user["id"], "selfie", day)),
        "body": out(_daily_photo(conn, user["id"], "body", day)),
        "previous_body": out(_previous(conn, user["id"], "body", day)),
    }


async def _upload_daily(kind: str, file: UploadFile, request: Request, user, conn, settings) -> dict:
    # O dia é o do servidor: mudar o relógio do celular não muda nada.
    day = settings.today().isoformat()
    if kind == "body" and _daily_photo(conn, user["id"], "selfie", day) is None:
        # Regra do Rewind: o rosto vem primeiro. Ele é o que conta pra streak.
        raise HTTPException(400, "Tire primeiro a foto do rosto de hoje")
    img = await _read_upload(file, settings)
    storage = request.app.state.storage
    old = _daily_photo(conn, user["id"], kind, day)
    if old:
        # Substituir enquanto o dia não acabou: sai a antiga, entra a nova (com id novo,
        # assim o navegador não mostra a antiga do cache).
        conn.execute("DELETE FROM photos WHERE id = ?", (old["id"],))
    photo = _insert(conn, storage, user["id"], day, kind, None, img)
    conn.commit()
    if old:
        storage.delete(old["file_name"])
    return photo_out(photo)


@router.post("/photos/selfie")
async def upload_selfie(file: UploadFile, request: Request, user=Depends(current_user),
                        conn: sqlite3.Connection = Depends(get_conn),
                        settings: Settings = Depends(get_settings)):
    return await _upload_daily("selfie", file, request, user, conn, settings)


@router.post("/photos/body")
async def upload_body(file: UploadFile, request: Request, user=Depends(current_user),
                      conn: sqlite3.Connection = Depends(get_conn),
                      settings: Settings = Depends(get_settings)):
    return await _upload_daily("body", file, request, user, conn, settings)


# --- Fotos extras (publicadas numa viagem) -------------------------------------------

@router.post("/trips/{trip_id}/extras")
async def upload_extra(trip_id: int, file: UploadFile, request: Request, user=Depends(current_user),
                       conn: sqlite3.Connection = Depends(get_conn),
                       settings: Settings = Depends(get_settings)):
    require_member(conn, trip_id, user["id"])
    day = settings.today().isoformat()
    end = conn.execute("SELECT end_date FROM trips WHERE id = ?", (trip_id,)).fetchone()[0]
    if end is not None and day > end:  # sem data final, o álbum nunca encerra sozinho
        raise HTTPException(400, "Esse álbum já foi encerrado")
    count = conn.execute(
        "SELECT COUNT(*) FROM photos WHERE user_id = ? AND trip_id = ? AND day = ? AND kind = 'extra'",
        (user["id"], trip_id, day)).fetchone()[0]
    if count >= settings.extras_per_day:
        raise HTTPException(400, f"Limite de {settings.extras_per_day} fotos extras por dia")
    img = await _read_upload(file, settings)
    photo = _insert(conn, request.app.state.storage, user["id"], day, "extra", trip_id, img)
    conn.commit()
    return photo_out(photo)


@router.get("/trips/{trip_id}/extras")
def list_extras(trip_id: int, day: str | None = None, user=Depends(current_user),
                conn: sqlite3.Connection = Depends(get_conn),
                settings: Settings = Depends(get_settings)):
    require_member(conn, trip_id, user["id"])
    rows = conn.execute(
        "SELECT * FROM photos WHERE trip_id = ? AND kind = 'extra' AND day = ? ORDER BY created_at",
        (trip_id, day or settings.today().isoformat())).fetchall()
    return [photo_out(p) for p in rows]


# --- Galeria da viagem ---------------------------------------------------------------

# As fotos do dia (rosto e corpo) que pertencem ao álbum: de cada membro, do dia em
# que entrou até a data final.
_TRIP_SELFIES = (
    "SELECT p.* FROM photos p"
    " JOIN trip_members m ON m.user_id = p.user_id AND m.trip_id = :trip"
    " JOIN trips t ON t.id = m.trip_id"
    " WHERE p.kind IN ('selfie', 'body') AND p.day BETWEEN m.joined_day AND COALESCE(t.end_date, '9999-12-31')"
)
_TRIP_EXTRAS = "SELECT p.* FROM photos p WHERE p.kind = 'extra' AND p.trip_id = :trip"


@router.get("/trips/{trip_id}/gallery")
def gallery(trip_id: int, before: str | None = None, days: int = 14, user_id: int | None = None,
            user=Depends(current_user), conn: sqlite3.Connection = Depends(get_conn)):
    """Fotos da viagem agrupadas por dia, do mais novo pro mais antigo, aos poucos.

    `before`: pega os dias anteriores a esse (pra carregar mais). `user_id`: só de uma pessoa.
    """
    require_member(conn, trip_id, user["id"])
    params = {"trip": trip_id, "before": before or "9999-12-31", "who": user_id}
    filters = " AND p.day < :before AND (:who IS NULL OR p.user_id = :who)"
    union = f"{_TRIP_SELFIES}{filters} UNION ALL {_TRIP_EXTRAS}{filters}"
    day_list = [r[0] for r in conn.execute(
        f"SELECT DISTINCT day FROM ({union}) ORDER BY day DESC LIMIT :n",
        {**params, "n": max(1, min(days, 60))})]
    if not day_list:
        return {"days": [], "next_before": None}

    rows = conn.execute(f"SELECT * FROM ({union}) WHERE day >= :oldest ORDER BY created_at",
                        {**params, "oldest": day_list[-1]}).fetchall()
    grouped = {d: {"day": d, "selfies": [], "bodies": [], "extras": []} for d in day_list}
    bucket = {"selfie": "selfies", "body": "bodies", "extra": "extras"}
    for p in rows:
        grouped[p["day"]][bucket[p["kind"]]].append(photo_out(p))
    return {"days": list(grouped.values()), "next_before": day_list[-1]}


# --- Ler e apagar --------------------------------------------------------------------

@router.get("/photos/{photo_id}")
def get_photo(photo_id: int, request: Request, user=Depends(current_user),
              conn: sqlite3.Connection = Depends(get_conn)):
    photo = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
    # 404 tanto pra "não existe" quanto pra "não é pra você".
    if photo is None or not can_view(conn, user["id"], photo):
        raise HTTPException(404, "Foto não encontrada")
    data = request.app.state.storage.load(photo["file_name"])  # descriptografa na memória
    # "private": só o navegador de quem pediu guarda; nenhum proxy no meio.
    # Uma foto nunca muda (substituir gera id novo), então pode ficar no cache.
    return Response(data, media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=604800, immutable"})


@router.delete("/photos/{photo_id}")
def delete_photo(photo_id: int, request: Request, user=Depends(current_user),
                 conn: sqlite3.Connection = Depends(get_conn)):
    photo = conn.execute("SELECT * FROM photos WHERE id = ? AND user_id = ?",
                         (photo_id, user["id"])).fetchone()
    if photo is None:
        raise HTTPException(404, "Foto não encontrada")
    if photo["kind"] == "selfie":
        # Apagar selfie quebraria a streak sem querer; pra trocar, é só tirar outra.
        raise HTTPException(400, "A selfie do dia não pode ser apagada, só substituída")
    conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    conn.commit()
    request.app.state.storage.delete(photo["file_name"])
    return {"ok": True}
