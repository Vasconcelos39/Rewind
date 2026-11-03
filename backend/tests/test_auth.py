import hashlib
import io

from fastapi.testclient import TestClient

from app import cli
from app.config import Settings
from app.main import COOKIE_NAME, create_app


def test_migrations_set_version(conn):
    assert conn.execute("PRAGMA user_version").fetchone()[0] >= 1


def test_login_and_me(client, ana):
    assert client.get("/api/auth/me").status_code == 401
    r = client.post("/api/auth/login", json=ana)
    assert r.status_code == 200
    assert r.json()["is_admin"] is True
    assert "password_hash" not in r.json()
    assert client.get("/api/auth/me").json()["username"] == "ana"


def test_username_is_case_insensitive(client, ana):
    r = client.post("/api/auth/login", json={"username": "ANA", "password": ana["password"]})
    assert r.status_code == 200


def test_wrong_password_and_unknown_user_look_the_same(client, ana):
    a = client.post("/api/auth/login", json={"username": "ana", "password": "errada123"})
    b = client.post("/api/auth/login", json={"username": "ninguem", "password": "errada123"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_cookie_flags(settings, ana):
    # App com cookie_secure=True, como em produção.
    app = create_app(Settings(data_dir=settings.data_dir, cookie_secure=True))
    r = TestClient(app).post("/api/auth/login", json=ana)
    header = r.headers["set-cookie"].lower()
    assert "httponly" in header and "secure" in header and "samesite=lax" in header

def test_only_token_hash_is_stored(client, ana, conn):
    client.post("/api/auth/login", json=ana)
    token = client.cookies[COOKIE_NAME]
    row = conn.execute("SELECT token_hash FROM sessions").fetchone()
    assert row["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in row["token_hash"]


def test_password_never_stored_plain(conn, ana):
    stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored.startswith("$argon2id$") and ana["password"] not in stored


def test_logout_kills_session(client, ana):
    client.post("/api/auth/login", json=ana)
    token = client.cookies[COOKIE_NAME]
    client.post("/api/auth/logout")
    client.cookies.set(COOKIE_NAME, token)  # tentar reaproveitar o token antigo
    assert client.get("/api/auth/me").status_code == 401


def test_rate_limit_per_user(client, ana):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "ana", "password": "errada123"})
    # Mesmo com a senha certa, a conta fica travada por um tempo.
    assert client.post("/api/auth/login", json=ana).status_code == 429


def test_cross_origin_post_blocked(client, ana):
    r = client.post("/api/auth/login", json=ana, headers={"Origin": "https://malvado.example"})
    assert r.status_code == 403
    r = client.post("/api/auth/login", json=ana, headers={"Origin": "http://testserver"})
    assert r.status_code == 200


def test_change_password_logs_out_other_devices(settings, client, ana):
    other = TestClient(client.app)
    other.post("/api/auth/login", json=ana)
    client.post("/api/auth/login", json=ana)

    r = client.post("/api/auth/password",
                    json={"current_password": "errada123", "new_password": "nova-senha-1"})
    assert r.status_code == 400
    r = client.post("/api/auth/password",
                    json={"current_password": ana["password"], "new_password": "nova-senha-1"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200   # este aparelho continua
    assert other.get("/api/auth/me").status_code == 401    # o outro saiu


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/nada")
    assert r.status_code == 404 and r.json()["detail"]


def test_frontend_cannot_escape_dist(settings, client):
    dist = settings.frontend_dist
    dist.mkdir()
    (dist / "index.html").write_text("<p>app</p>")
    (settings.data_dir / "segredo.txt").write_text("não")
    assert client.get("/qualquer/rota").text == "<p>app</p>"
    r = client.get("/..%2Fsegredo.txt")
    assert "não" not in r.text
    r = client.get("/rewind.db")
    assert r.text == "<p>app</p>"


def test_cli_create_admin(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REWIND_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("senha-forte-1\n"))
    cli.main(["create-admin", "--username", "bia"])
    app = create_app(Settings(data_dir=tmp_path, cookie_secure=False))
    r = TestClient(app).post("/api/auth/login", json={"username": "bia", "password": "senha-forte-1"})
    assert r.status_code == 200 and r.json()["is_admin"]
