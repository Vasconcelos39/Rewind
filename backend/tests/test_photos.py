"""Fase 3: upload, criptografia em repouso e quem pode ver cada foto."""

import io
from datetime import date, timedelta

import pytest
from PIL import Image

from app import crypto


def jpeg(color=(200, 80, 40), size=(64, 48), exif_gps=False) -> bytes:
    img = Image.new("RGB", size, color)
    out = io.BytesIO()
    if exif_gps:
        exif = Image.Exif()
        exif[0x010F] = "MarcaDoCelular"  # Make
        img.save(out, "JPEG", exif=exif)
    else:
        img.save(out, "JPEG")
    return out.getvalue()


def send_selfie(c, data=None, ctype="image/jpeg"):
    return c.post("/api/photos/selfie", files={"file": ("s.jpg", data or jpeg(), ctype)})


def future(days=30):
    return (date.today() + timedelta(days=days)).isoformat()


@pytest.fixture
def ana_bia_trip(make_user):
    """Ana e Bia amigas e na mesma viagem; Caio é amigo da Ana, mas fora da viagem."""
    ana, bia, caio = make_user("ana"), make_user("bia"), make_user("caio")
    for other, name in ((bia, "bia"), (caio, "caio")):
        ana.post("/api/friends", json={"username": name})
        other.post(f"/api/friends/{ana.user_id}/accept")
    trip_id = ana.post("/api/trips", json={"name": "Praia", "end_date": future()}).json()["id"]
    ana.post(f"/api/trips/{trip_id}/invites", json={"user_id": bia.user_id})
    bia.post(f"/api/trip-invites/{bia.get('/api/trip-invites').json()[0]['id']}/accept")
    return ana, bia, caio, trip_id


# --- Selfie --------------------------------------------------------------------

def test_selfie_upload_and_today(make_user):
    ana = make_user("ana")
    assert ana.get("/api/photos/today").json()["selfie"] is None
    r = send_selfie(ana)
    assert r.status_code == 200 and r.json()["kind"] == "selfie"
    today = ana.get("/api/photos/today").json()
    assert today["selfie"]["id"] == r.json()["id"]
    img = ana.get(r.json()["url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert "private" in img.headers["cache-control"]


def test_selfie_replaced_same_day(make_user, settings, conn):
    ana = make_user("ana")
    first = send_selfie(ana, jpeg((255, 0, 0))).json()
    second = send_selfie(ana, jpeg((0, 0, 255))).json()
    assert first["id"] != second["id"]
    assert conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 1
    assert ana.get(first["url"]).status_code == 404
    # O arquivo antigo também sumiu do disco.
    assert len(list(settings.photos_dir.rglob("*.enc"))) == 1


def test_previous_selfie_for_overlay(make_user, conn, settings):
    ana = make_user("ana")
    send_selfie(ana)
    # Finge que a selfie foi ontem.
    yesterday = (settings.today() - timedelta(days=1)).isoformat()
    conn.execute("UPDATE photos SET day = ?", (yesterday,))
    conn.commit()
    t = ana.get("/api/photos/today").json()
    assert t["selfie"] is None and t["previous"]["day"] == yesterday


def test_file_on_disk_is_encrypted_and_exif_removed(make_user, settings, conn):
    ana = make_user("ana")
    original = jpeg(exif_gps=True)
    assert b"MarcaDoCelular" in original
    photo = send_selfie(ana, original).json()

    (path,) = settings.photos_dir.rglob("*.enc")
    blob = path.read_bytes()
    assert blob.startswith(crypto.MAGIC)
    assert b"\xff\xd8" not in blob[:20] and b"JFIF" not in blob  # não é um JPEG legível

    served = ana.get(photo["url"]).content
    assert served.startswith(b"\xff\xd8")            # o servidor entrega o JPEG
    assert b"MarcaDoCelular" not in served           # sem o EXIF original


def test_swapped_file_fails_to_decrypt(settings):
    box = crypto.Box(crypto.load_key(settings.key_file))
    blob = box.encrypt(b"foto", "aaaa")
    with pytest.raises(crypto.DecryptError):
        box.decrypt(blob, "bbbb")  # mesmo conteúdo com outro nome: falha
    other = crypto.Box(b"\x00" * 32)
    with pytest.raises(crypto.DecryptError):
        other.decrypt(blob, "aaaa")  # chave errada: falha


def test_large_image_is_resized(make_user):
    ana = make_user("ana")
    r = send_selfie(ana, jpeg(size=(4000, 3000))).json()
    assert max(r["width"], r["height"]) == 1600


@pytest.mark.parametrize("data,ctype", [
    (b"<?php echo 1; ?>", "image/jpeg"),   # finge ser imagem
    (b"GIF89a" + b"\x00" * 50, "image/gif"),
    (jpeg(), "text/plain"),
])
def test_rejects_non_images(make_user, data, ctype):
    ana = make_user("ana")
    assert send_selfie(ana, data, ctype).status_code == 400


def test_upload_size_limit(make_user, settings):
    ana = make_user("ana")
    big = b"\xff\xd8" + b"\x00" * (settings.max_upload_mb * 1024 * 1024 + 10)
    assert send_selfie(ana, big).status_code == 413


def test_upload_requires_login(client):
    assert send_selfie(client).status_code == 401


# --- Quem vê o quê ---------------------------------------------------------------

def test_trip_member_sees_selfie_but_friend_outside_does_not(ana_bia_trip, make_user):
    ana, bia, caio, _ = ana_bia_trip
    url = send_selfie(ana).json()["url"]
    assert bia.get(url).status_code == 200    # mesma viagem
    assert caio.get(url).status_code == 404   # amigo, mas fora da viagem
    stranger = make_user("dani")
    assert stranger.get(url).status_code == 404


def test_selfie_before_joining_trip_is_hidden(ana_bia_trip, conn):
    ana, bia, _, trip_id = ana_bia_trip
    url = send_selfie(ana).json()["url"]
    # Uma selfie da Ana de antes de ela entrar na viagem não aparece pra Bia.
    conn.execute("UPDATE photos SET day = '2020-01-01'")
    conn.commit()
    assert bia.get(url).status_code == 404


def test_leaving_trip_hides_photos(ana_bia_trip):
    ana, bia, _, trip_id = ana_bia_trip
    url = send_selfie(ana).json()["url"]
    bia.post(f"/api/trips/{trip_id}/leave")
    assert bia.get(url).status_code == 404


# --- Fotos extras --------------------------------------------------------------------

def test_extras_visible_only_in_trip(ana_bia_trip):
    ana, bia, caio, trip_id = ana_bia_trip
    r = ana.post(f"/api/trips/{trip_id}/extras", files={"file": ("e.jpg", jpeg(), "image/jpeg")})
    assert r.status_code == 200
    assert [p["id"] for p in bia.get(f"/api/trips/{trip_id}/extras").json()] == [r.json()["id"]]
    assert bia.get(r.json()["url"]).status_code == 200
    assert caio.get(r.json()["url"]).status_code == 404
    assert caio.get(f"/api/trips/{trip_id}/extras").status_code == 404
    assert caio.post(f"/api/trips/{trip_id}/extras",
                     files={"file": ("e.jpg", jpeg(), "image/jpeg")}).status_code == 404


def test_extras_daily_limit(ana_bia_trip, settings):
    ana, _, _, trip_id = ana_bia_trip
    for _ in range(settings.extras_per_day):
        ana.post(f"/api/trips/{trip_id}/extras", files={"file": ("e.jpg", jpeg(), "image/jpeg")})
    r = ana.post(f"/api/trips/{trip_id}/extras", files={"file": ("e.jpg", jpeg(), "image/jpeg")})
    assert r.status_code == 400


def test_extras_dont_count_as_selfie(ana_bia_trip):
    ana, _, _, trip_id = ana_bia_trip
    ana.post(f"/api/trips/{trip_id}/extras", files={"file": ("e.jpg", jpeg(), "image/jpeg")})
    assert ana.get("/api/photos/today").json()["selfie"] is None


def test_delete_extra_but_not_selfie(ana_bia_trip, settings):
    ana, bia, _, trip_id = ana_bia_trip
    extra = ana.post(f"/api/trips/{trip_id}/extras",
                     files={"file": ("e.jpg", jpeg(), "image/jpeg")}).json()
    selfie = send_selfie(ana).json()
    assert bia.delete(f"/api/photos/{extra['id']}").status_code == 404   # não é dela
    assert ana.delete(f"/api/photos/{selfie['id']}").status_code == 400
    assert ana.delete(f"/api/photos/{extra['id']}").status_code == 200
    assert len(list(settings.photos_dir.rglob("*.enc"))) == 1


def test_deleting_trip_removes_extra_files(make_user, settings):
    ana = make_user("ana")
    trip_id = ana.post("/api/trips", json={"name": "X", "end_date": future()}).json()["id"]
    ana.post(f"/api/trips/{trip_id}/extras", files={"file": ("e.jpg", jpeg(), "image/jpeg")})
    ana.post(f"/api/trips/{trip_id}/leave")
    assert list(settings.photos_dir.rglob("*.enc")) == []


def test_app_refuses_to_start_without_key(settings):
    import dataclasses
    from app.main import create_app
    with pytest.raises(SystemExit):
        create_app(dataclasses.replace(settings, key_file=settings.data_dir / "nao-existe.key"))
