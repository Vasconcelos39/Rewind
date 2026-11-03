"""Fase 2: amizades, viagens e convites."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import security


@pytest.fixture
def make_user(client, conn):
    """Cria uma conta e devolve um cliente já logado nela."""
    def make(username):
        security.create_user(conn, username, f"senha-{username}", username.title())
        c = TestClient(client.app)
        assert c.post("/api/auth/login",
                      json={"username": username, "password": f"senha-{username}"}).status_code == 200
        c.user_id = c.get("/api/auth/me").json()["id"]
        return c
    return make


def future(days=30):
    return (date.today() + timedelta(days=days)).isoformat()


def befriend(a, b, b_username):
    a.post("/api/friends", json={"username": b_username})
    assert b.post(f"/api/friends/{a.user_id}/accept").status_code == 200


# --- Amizades ------------------------------------------------------------------

def test_friend_request_flow(make_user):
    ana, bia = make_user("ana"), make_user("bia")
    r = ana.post("/api/friends", json={"username": "BIA"})
    assert r.json()["status"] == "pending"
    assert [u["username"] for u in ana.get("/api/friends").json()["outgoing"]] == ["bia"]
    assert [u["username"] for u in bia.get("/api/friends").json()["incoming"]] == ["ana"]

    assert bia.post(f"/api/friends/{ana.user_id}/accept").status_code == 200
    assert [u["username"] for u in ana.get("/api/friends").json()["friends"]] == ["bia"]


def test_cannot_accept_own_request(make_user):
    ana, bia = make_user("ana"), make_user("bia")
    ana.post("/api/friends", json={"username": "bia"})
    assert ana.post(f"/api/friends/{bia.user_id}/accept").status_code == 404


def test_mutual_request_becomes_friendship(make_user):
    ana, bia = make_user("ana"), make_user("bia")
    ana.post("/api/friends", json={"username": "bia"})
    assert bia.post("/api/friends", json={"username": "ana"}).json()["status"] == "accepted"


def test_friend_request_errors(make_user):
    ana = make_user("ana")
    assert ana.post("/api/friends", json={"username": "ninguem"}).status_code == 404
    assert ana.post("/api/friends", json={"username": "ana"}).status_code == 400


def test_unfriend(make_user):
    ana, bia = make_user("ana"), make_user("bia")
    befriend(ana, bia, "bia")
    ana.delete(f"/api/friends/{bia.user_id}")
    assert bia.get("/api/friends").json()["friends"] == []


# --- Viagens -------------------------------------------------------------------

def test_create_and_list_trip(make_user):
    ana = make_user("ana")
    r = ana.post("/api/trips", json={"name": "Casamento", "end_date": future(10)})
    assert r.status_code == 200 and r.json()["member_count"] == 1
    assert [t["name"] for t in ana.get("/api/trips").json()] == ["Casamento"]


def test_trip_end_date_must_be_future(make_user):
    ana = make_user("ana")
    assert ana.post("/api/trips", json={"name": "X", "end_date": date.today().isoformat()}).status_code == 400
    assert ana.post("/api/trips", json={"name": "  ", "end_date": future()}).status_code == 400


def test_non_member_cannot_see_trip(make_user):
    ana, bia = make_user("ana"), make_user("bia")
    trip_id = ana.post("/api/trips", json={"name": "Segredo", "end_date": future()}).json()["id"]
    # 404 igual ao de uma viagem que não existe.
    assert bia.get(f"/api/trips/{trip_id}").status_code == 404
    assert bia.get("/api/trips/9999").status_code == 404
    assert bia.post(f"/api/trips/{trip_id}/invites", json={"user_id": bia.user_id}).status_code == 404


def test_invite_friend_to_trip(make_user):
    ana, bia = make_user("ana"), make_user("bia")
    befriend(ana, bia, "bia")
    trip_id = ana.post("/api/trips", json={"name": "Praia", "end_date": future()}).json()["id"]
    assert ana.post(f"/api/trips/{trip_id}/invites", json={"user_id": bia.user_id}).status_code == 200

    invites = bia.get("/api/trip-invites").json()
    assert invites[0]["trip_name"] == "Praia" and invites[0]["from"]["username"] == "ana"
    assert bia.post(f"/api/trip-invites/{invites[0]['id']}/accept").json()["trip_id"] == trip_id
    assert len(bia.get(f"/api/trips/{trip_id}").json()["members"]) == 2
    assert bia.get("/api/trip-invites").json() == []


def test_only_friends_can_be_invited(make_user):
    ana, bia = make_user("ana"), make_user("bia")
    trip_id = ana.post("/api/trips", json={"name": "Praia", "end_date": future()}).json()["id"]
    assert ana.post(f"/api/trips/{trip_id}/invites", json={"user_id": bia.user_id}).status_code == 400


def test_cannot_accept_someone_elses_invite(make_user):
    ana, bia, caio = make_user("ana"), make_user("bia"), make_user("caio")
    befriend(ana, bia, "bia")
    trip_id = ana.post("/api/trips", json={"name": "Praia", "end_date": future()}).json()["id"]
    ana.post(f"/api/trips/{trip_id}/invites", json={"user_id": bia.user_id})
    invite_id = bia.get("/api/trip-invites").json()[0]["id"]
    assert caio.post(f"/api/trip-invites/{invite_id}/accept").status_code == 404


def test_last_member_leaving_deletes_trip(make_user, conn):
    ana = make_user("ana")
    trip_id = ana.post("/api/trips", json={"name": "Praia", "end_date": future()}).json()["id"]
    ana.post(f"/api/trips/{trip_id}/leave")
    assert conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0] == 0


# --- Links de convite ----------------------------------------------------------

def test_signup_via_trip_link(make_user, client):
    ana = make_user("ana")
    trip_id = ana.post("/api/trips", json={"name": "Casamento", "end_date": future()}).json()["id"]
    path = ana.post("/api/invite-links", json={"trip_id": trip_id}).json()["path"]
    token = path.rsplit("/", 1)[1]

    guest = TestClient(client.app)
    info = guest.get(f"/api/invite-links/{token}").json()
    assert info == {"inviter": "Ana", "trip_name": "Casamento", "expires_at": info["expires_at"]}

    r = guest.post(f"/api/invite-links/{token}/signup",
                   json={"username": "dani", "password": "senha-da-dani", "display_name": "Dani"})
    assert r.status_code == 200 and r.json()["trip_id"] == trip_id
    assert guest.get("/api/auth/me").json()["username"] == "dani"      # já saiu logada
    assert len(guest.get(f"/api/trips/{trip_id}").json()["members"]) == 2
    assert [u["username"] for u in guest.get("/api/friends").json()["friends"]] == ["ana"]

    # Uso único: o mesmo link não vale de novo.
    other = TestClient(client.app)
    assert other.get(f"/api/invite-links/{token}").status_code == 404
    r = other.post(f"/api/invite-links/{token}/signup",
                   json={"username": "edu", "password": "senha-do-edu"})
    assert r.status_code == 404


def test_signup_error_does_not_burn_link(make_user, client):
    ana = make_user("ana")
    token = ana.post("/api/invite-links", json={}).json()["path"].rsplit("/", 1)[1]
    guest = TestClient(client.app)
    assert guest.post(f"/api/invite-links/{token}/signup",
                      json={"username": "ana", "password": "senha-qualquer"}).status_code == 400
    assert guest.post(f"/api/invite-links/{token}/signup",
                      json={"username": "x", "password": "senha-qualquer"}).status_code == 400
    assert guest.get(f"/api/invite-links/{token}").status_code == 200   # ainda vale


def test_logged_in_user_accepts_link(make_user):
    ana, bia = make_user("ana"), make_user("bia")
    trip_id = ana.post("/api/trips", json={"name": "Praia", "end_date": future()}).json()["id"]
    token = ana.post("/api/invite-links", json={"trip_id": trip_id}).json()["path"].rsplit("/", 1)[1]
    assert ana.post(f"/api/invite-links/{token}/accept").status_code == 400  # o próprio dono
    assert bia.post(f"/api/invite-links/{token}/accept").json()["trip_id"] == trip_id
    assert bia.get(f"/api/trips/{trip_id}").status_code == 200


def test_expired_link(make_user, client, conn):
    ana = make_user("ana")
    token = ana.post("/api/invite-links", json={}).json()["path"].rsplit("/", 1)[1]
    conn.execute("UPDATE invite_links SET expires_at = '2000-01-01T00:00:00+00:00'")
    conn.commit()
    assert TestClient(client.app).get(f"/api/invite-links/{token}").status_code == 404


def test_only_members_create_trip_links(make_user):
    ana, bia = make_user("ana"), make_user("bia")
    trip_id = ana.post("/api/trips", json={"name": "Praia", "end_date": future()}).json()["id"]
    assert bia.post("/api/invite-links", json={"trip_id": trip_id}).status_code == 404


def test_link_token_stored_as_hash(make_user, conn):
    ana = make_user("ana")
    token = ana.post("/api/invite-links", json={}).json()["path"].rsplit("/", 1)[1]
    stored = conn.execute("SELECT token_hash FROM invite_links").fetchone()[0]
    assert stored == security.token_hash(token)


def test_invite_rate_limit(client):
    guest = TestClient(client.app)
    codes = [guest.get(f"/api/invite-links/chute{i}").status_code for i in range(31)]
    assert codes[:30] == [404] * 30 and codes[30] == 429
