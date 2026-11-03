"""Fase 4: streak, cutucadas, status do dia e galeria."""

from datetime import timedelta

import pytest

from test_photos import ana_bia_trip, jpeg, send_selfie  # noqa: F401 (fixture)


def set_day(conn, photo_id, day):
    conn.execute("UPDATE photos SET day = ? WHERE id = ?", (day, photo_id))
    conn.commit()


def ago(settings, n):
    return (settings.today() - timedelta(days=n)).isoformat()


def selfie_on(c, conn, day):
    set_day(conn, send_selfie(c).json()["id"], day)


def test_today_summary_streak(make_user, conn, settings):
    ana = make_user("ana")
    t = ana.get("/api/today").json()
    assert t["streak"] == 0 and t["sent_today"] is False and 0 < t["seconds_left"] <= 86400
    selfie_on(ana, conn, ago(settings, 2))
    selfie_on(ana, conn, ago(settings, 1))
    assert ana.get("/api/today").json()["streak"] == 2     # ainda vale até o fim do dia
    send_selfie(ana)
    t = ana.get("/api/today").json()
    assert t["streak"] == 3 and t["sent_today"] is True


def test_friends_list_shows_status_and_pair_streak(ana_bia_trip, conn, settings):
    ana, bia, caio, _ = ana_bia_trip
    for d in (2, 1):
        selfie_on(ana, conn, ago(settings, d))
    selfie_on(bia, conn, ago(settings, 1))
    send_selfie(bia)
    friends = {f["username"]: f for f in ana.get("/api/friends").json()["friends"]}
    assert friends["bia"]["sent_today"] is True and friends["bia"]["streak"] == 2
    assert friends["bia"]["pair_streak"] == 1      # só ontem os duas tiraram
    assert friends["caio"]["streak"] == 0
    assert "url" not in str(friends)               # amigo não recebe fotos por aqui


def test_nudge_flow(ana_bia_trip):
    ana, bia, _, _ = ana_bia_trip
    assert ana.post(f"/api/friends/{bia.user_id}/nudge").status_code == 200
    assert ana.post(f"/api/friends/{bia.user_id}/nudge").status_code == 400   # 1 por dia
    nudges = bia.get("/api/today").json()["nudges"]
    assert nudges[0]["from"]["username"] == "ana" and nudges[0]["seen"] is False
    bia.post("/api/today/nudges/seen")
    assert bia.get("/api/today").json()["nudges"][0]["seen"] is True
    friends = {f["username"]: f for f in ana.get("/api/friends").json()["friends"]}
    assert friends["bia"]["nudged_today"] is True


def test_cannot_nudge_who_already_sent_or_non_friend(ana_bia_trip, make_user):
    ana, bia, _, _ = ana_bia_trip
    send_selfie(bia)
    assert ana.post(f"/api/friends/{bia.user_id}/nudge").status_code == 400
    dani = make_user("dani")
    assert ana.post(f"/api/friends/{dani.user_id}/nudge").status_code == 404


def test_trip_today_status(ana_bia_trip):
    ana, bia, _, trip_id = ana_bia_trip
    send_selfie(ana)
    members = {m["username"]: m for m in bia.get(f"/api/trips/{trip_id}").json()["members"]}
    assert members["ana"]["sent_today"] is True and members["ana"]["today_photo"]
    assert members["bia"]["sent_today"] is False and members["bia"]["today_photo"] is None
    assert bia.get(members["ana"]["today_photo"]["url"]).status_code == 200


def test_gallery_groups_by_day_and_respects_period(ana_bia_trip, conn, settings):
    ana, bia, caio, trip_id = ana_bia_trip
    send_selfie(ana)
    send_selfie(bia)
    ana.post(f"/api/trips/{trip_id}/extras", files={"file": ("e.jpg", jpeg(), "image/jpeg")})
    selfie_on(caio, conn, settings.today().isoformat())   # Caio não é da viagem
    # Selfie antiga da Ana, de antes de entrar na viagem: não aparece.
    old = send_selfie(ana).json()  # substitui a de hoje...
    set_day(conn, old["id"], "2020-01-01")
    send_selfie(ana)               # ...e tira outra hoje

    g = bia.get(f"/api/trips/{trip_id}/gallery").json()
    assert [d["day"] for d in g["days"]] == [settings.today().isoformat()]
    today = g["days"][0]
    assert {p["user_id"] for p in today["selfies"]} == {ana.user_id, bia.user_id}
    assert len(today["extras"]) == 1
    # Filtrar por pessoa
    only_bia = bia.get(f"/api/trips/{trip_id}/gallery", params={"user_id": bia.user_id}).json()
    assert [p["user_id"] for p in only_bia["days"][0]["selfies"]] == [bia.user_id]
    assert only_bia["days"][0]["extras"] == []
    # Quem não é membro não vê a galeria
    assert caio.get(f"/api/trips/{trip_id}/gallery").status_code == 404


def test_gallery_pagination(ana_bia_trip, conn, settings):
    ana, _, _, trip_id = ana_bia_trip
    conn.execute("UPDATE trip_members SET joined_day = '2000-01-01'")
    conn.commit()
    # Do mais antigo pro mais novo: cada envio é "hoje" e depois é empurrado pro passado.
    for d in range(4, -1, -1):
        selfie_on(ana, conn, ago(settings, d))
    first = ana.get(f"/api/trips/{trip_id}/gallery", params={"days": 3}).json()
    assert len(first["days"]) == 3
    rest = ana.get(f"/api/trips/{trip_id}/gallery",
                   params={"days": 3, "before": first["next_before"]}).json()
    assert len(rest["days"]) == 2
