"""Foto de corpo: opcional, depois do rosto, com o próprio timelapse."""

import shutil
from datetime import timedelta

import pytest

from app import timelapse
from test_photos import ana_bia_trip, jpeg, send_selfie  # noqa: F401 (fixture)


def send_body(c, data=None):
    return c.post("/api/photos/body", files={"file": ("b.jpg", data or jpeg((40, 90, 160)), "image/jpeg")})


def test_body_needs_face_first(make_user):
    ana = make_user("ana")
    r = send_body(ana)
    assert r.status_code == 400 and "rosto" in r.json()["detail"]
    send_selfie(ana)
    r = send_body(ana)
    assert r.status_code == 200 and r.json()["kind"] == "body"
    t = ana.get("/api/photos/today").json()
    assert t["selfie"] and t["body"]["id"] == r.json()["id"]


def test_body_replaced_same_day_and_does_not_count_for_streak(make_user, conn):
    ana = make_user("ana")
    send_selfie(ana)
    first, second = send_body(ana).json(), send_body(ana).json()
    assert first["id"] != second["id"]
    assert conn.execute("SELECT COUNT(*) FROM photos WHERE kind = 'body'").fetchone()[0] == 1
    # A streak é só do rosto: apagar a foto de corpo não mexe nela.
    assert ana.delete(f"/api/photos/{second['id']}").status_code == 200
    assert ana.get("/api/today").json()["streak"] == 1


def test_previous_body_for_overlay(make_user, conn, settings):
    ana = make_user("ana")
    send_selfie(ana)
    send_body(ana)
    yesterday = (settings.today() - timedelta(days=1)).isoformat()
    conn.execute("UPDATE photos SET day = ?", (yesterday,))
    conn.commit()
    t = ana.get("/api/photos/today").json()
    assert t["body"] is None and t["previous_body"]["day"] == yesterday
    assert t["previous"]["kind"] == "selfie"     # cada tipo tem a sua foto de referência


def test_body_visibility_follows_album_rules(ana_bia_trip):
    ana, bia, caio, trip_id = ana_bia_trip
    send_selfie(ana)
    url = send_body(ana).json()["url"]
    assert bia.get(url).status_code == 200      # mesmo álbum
    assert caio.get(url).status_code == 404     # amigo fora do álbum
    day = bia.get(f"/api/trips/{trip_id}/gallery").json()["days"][0]
    assert len(day["selfies"]) == 1 and len(day["bodies"]) == 1


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg não instalado")
def test_body_timelapse_is_separate(ana_bia_trip, conn, settings, client):
    ana, _, _, trip_id = ana_bia_trip
    conn.execute("UPDATE trip_members SET joined_day = '2000-01-01'")
    conn.commit()
    for d in (2, 1, 0):  # 3 dias de rosto, 2 de corpo
        send_selfie(ana)
        if d < 2:
            send_body(ana)
        conn.execute("UPDATE photos SET day = ? WHERE day = ?",
                     ((settings.today() - timedelta(days=d)).isoformat(), settings.today().isoformat()))
        conn.commit()
    face = ana.post(f"/api/trips/{trip_id}/timelapses", json={"user_id": ana.user_id}).json()
    body = ana.post(f"/api/trips/{trip_id}/timelapses", json={"user_id": ana.user_id, "kind": "body"}).json()
    assert (face["kind"], face["frame_count"]) == ("selfie", 3)
    assert (body["kind"], body["frame_count"]) == ("body", 2)
    st = client.app.state
    while timelapse.process_next(st.settings, st.storage):
        pass
    kinds = {j["kind"]: j["status"] for j in ana.get(f"/api/trips/{trip_id}/timelapses").json()}
    assert kinds == {"selfie": "done", "body": "done"}


def test_body_timelapse_needs_two_photos(ana_bia_trip):
    ana, _, _, trip_id = ana_bia_trip
    send_selfie(ana)
    send_body(ana)
    r = ana.post(f"/api/trips/{trip_id}/timelapses", json={"user_id": ana.user_id, "kind": "body"})
    assert r.status_code == 400 and "corpo" in r.json()["detail"]
    r = ana.post(f"/api/trips/{trip_id}/timelapses", json={"user_id": ana.user_id, "kind": "pé"})
    assert r.status_code == 422
