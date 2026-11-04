"""Álbuns com data final opcional, edição/encerramento e as correções de bugs dessa rodada."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app import timelapse
from test_photos import ana_bia_trip, jpeg, send_selfie  # noqa: F401 (fixture)


def day(settings, n=0):
    return (settings.today() + timedelta(days=n)).isoformat()


# --- Data final opcional -----------------------------------------------------------

def test_album_without_end_date(make_user):
    ana = make_user("ana")
    r = ana.post("/api/trips", json={"name": "Sem fim"})
    assert r.status_code == 200
    t = r.json()
    assert t["end_date"] is None and t["days_left"] is None
    assert t["status"] == "active" and t["day_number"] == 1


def test_open_album_photos_are_visible(make_user):
    # Regressão: no SQL, "BETWEEN x AND NULL" é falso. Sem COALESCE, as fotos de um
    # álbum sem data final sumiriam pra todo mundo.
    ana, bia = make_user("ana"), make_user("bia")
    ana.post("/api/friends", json={"username": "bia"})
    bia.post(f"/api/friends/{ana.user_id}/accept")
    trip_id = ana.post("/api/trips", json={"name": "Sem fim"}).json()["id"]
    ana.post(f"/api/trips/{trip_id}/invites", json={"user_id": bia.user_id})
    bia.post(f"/api/trip-invites/{bia.get('/api/trip-invites').json()[0]['id']}/accept")

    url = send_selfie(ana).json()["url"]
    assert bia.get(url).status_code == 200
    g = bia.get(f"/api/trips/{trip_id}/gallery").json()
    assert len(g["days"][0]["selfies"]) == 1
    assert bia.post(f"/api/trips/{trip_id}/extras",
                    files={"file": ("e.jpg", jpeg(), "image/jpeg")}).status_code == 200
    members = {m["username"]: m for m in bia.get(f"/api/trips/{trip_id}").json()["members"]}
    assert members["ana"]["today_photo"] is not None


def test_edit_end_date_set_clear_and_end_today(make_user, settings):
    ana = make_user("ana")
    trip_id = ana.post("/api/trips", json={"name": "Praia"}).json()["id"]

    t = ana.patch(f"/api/trips/{trip_id}", json={"end_date": day(settings, 10)}).json()
    assert t["end_date"] == day(settings, 10) and t["days_left"] == 10

    t = ana.patch(f"/api/trips/{trip_id}", json={"name": "Praia 2027"}).json()
    assert t["name"] == "Praia 2027" and t["end_date"] == day(settings, 10)  # sem end_date: não mexe

    t = ana.patch(f"/api/trips/{trip_id}", json={"end_date": None}).json()
    assert t["end_date"] is None                                               # null: tira a data

    # "Encerrar hoje": hoje é o último dia, ainda em andamento; amanhã vira encerrado.
    t = ana.patch(f"/api/trips/{trip_id}", json={"end_date": day(settings)}).json()
    assert t["status"] == "active" and t["days_left"] == 0


def test_edit_validation_and_permissions(make_user, settings):
    ana, bia = make_user("ana"), make_user("bia")
    trip_id = ana.post("/api/trips", json={"name": "Praia"}).json()["id"]
    r = ana.patch(f"/api/trips/{trip_id}", json={"end_date": day(settings, -5)})
    assert r.status_code == 400                                   # antes do começo do álbum
    assert ana.patch(f"/api/trips/{trip_id}", json={"name": "  "}).status_code == 400
    assert bia.patch(f"/api/trips/{trip_id}", json={"name": "Hackeado"}).status_code == 404


def test_ended_album(make_user, conn, settings):
    ana = make_user("ana")
    trip_id = ana.post("/api/trips", json={"name": "Passado"}).json()["id"]
    # Finge que o álbum começou há 10 dias e acabou ontem.
    conn.execute("UPDATE trips SET created_at = ?, end_date = ?",
                 (f"{day(settings, -10)}T15:00:00+00:00", day(settings, -1)))
    conn.commit()
    t = ana.get(f"/api/trips/{trip_id}").json()
    assert t["status"] == "ended" and t["days_left"] is None and t["day_number"] == 10
    assert [x["status"] for x in ana.get("/api/trips").json()] == ["ended"]
    r = ana.post(f"/api/trips/{trip_id}/extras", files={"file": ("e.jpg", jpeg(), "image/jpeg")})
    assert r.status_code == 400
    # Reabrir: tirar a data final.
    assert ana.patch(f"/api/trips/{trip_id}", json={"end_date": None}).json()["status"] == "active"


# --- Bugs ------------------------------------------------------------------------------

def test_origin_with_port_behind_proxy_is_allowed(client, ana):
    # O Nginx Proxy Manager repassa o Host sem a porta; o navegador manda o Origin com ela.
    r = client.post("/api/auth/login", json=ana,
                    headers={"Origin": "https://rewind.example:8443", "Host": "rewind.example"})
    assert r.status_code == 200
    r = client.post("/api/auth/login", json=ana,
                    headers={"Origin": "https://malvado.example:8443", "Host": "rewind.example"})
    assert r.status_code == 403


def test_huge_upload_rejected_before_reading(make_user, settings):
    ana = make_user("ana")
    too_big = str((settings.max_upload_mb + 2) * 1024 * 1024)
    r = ana.post("/api/photos/selfie", content=b"x", headers={"Content-Length": too_big,
                                                                "Content-Type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413


def test_deleted_job_does_not_leave_orphan_video(ana_bia_trip, conn, settings, client):
    ana, _, _, trip_id = ana_bia_trip
    conn.execute("UPDATE trip_members SET joined_day = '2000-01-01'")
    conn.commit()
    for n in (1, 0):
        pid = send_selfie(ana).json()["id"]
        conn.execute("UPDATE photos SET day = ? WHERE id = ?", (day(settings, -n), pid))
        conn.commit()
    job = ana.post(f"/api/trips/{trip_id}/timelapses", json={"user_id": ana.user_id}).json()
    before = set(settings.photos_dir.rglob("*.enc"))

    # Apaga o pedido no meio do caminho, como se alguém tivesse pedido de novo.
    real_render = timelapse.render

    def render_then_vanish(*args):
        name = real_render(*args)
        conn.execute("DELETE FROM timelapses WHERE id = ?", (job["id"],))
        conn.commit()
        return name

    timelapse.render = render_then_vanish
    try:
        timelapse.process_next(settings, client.app.state.storage)
    finally:
        timelapse.render = real_render
    assert set(settings.photos_dir.rglob("*.enc")) == before    # nenhum vídeo órfão


def test_password_change_is_rate_limited(client, ana):
    client.post("/api/auth/login", json=ana)
    codes = [client.post("/api/auth/password",
                         json={"current_password": "errada123", "new_password": "nova-senha-1"}).status_code
             for _ in range(6)]
    assert codes[:5] == [400] * 5 and codes[5] == 429
