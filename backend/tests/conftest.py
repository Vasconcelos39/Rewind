import pytest
from fastapi.testclient import TestClient

from app import db, security
from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    # TestClient fala HTTP puro, então o cookie não pode exigir HTTPS aqui.
    return Settings(data_dir=tmp_path, cookie_secure=False, frontend_dist=tmp_path / "dist")


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
