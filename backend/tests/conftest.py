import pytest
from fastapi.testclient import TestClient

from app import crypto, db, security
from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    key = tmp_path / "chave" / "rewind.key"
    crypto.generate_key_file(key)
    # TestClient fala HTTP puro, então o cookie não pode exigir HTTPS aqui.
    return Settings(data_dir=tmp_path / "dados", cookie_secure=False,
                    frontend_dist=tmp_path / "dist", key_file=key, tmp_dir=tmp_path / "tmp")


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))


@pytest.fixture
def conn(settings, client):  # client garante que as migrações já rodaram
    c = db.connect(settings.db_path)
    yield c
    c.close()


@pytest.fixture
def ana(conn):
    security.create_user(conn, "ana", "senha-da-ana", "Ana", is_admin=True)
    return {"username": "ana", "password": "senha-da-ana"}


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
