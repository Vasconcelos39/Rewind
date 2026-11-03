"""Fase 5: fila de timelapse, cache, ffmpeg e acesso ao vídeo."""

import shutil
from datetime import timedelta

import pytest

from app import timelapse
from test_photos import ana_bia_trip, jpeg, send_selfie  # noqa: F401 (fixture)

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg não instalado")


def selfies(c, conn, settings, n):
    """N selfies em dias seguidos terminando hoje (e a pessoa 'entrou' na viagem antes)."""
    conn.execute("UPDATE trip_members SET joined_day = '2000-01-01'")
    conn.commit()
    for d in range(n - 1, -1, -1):
        pid = send_selfie(c, jpeg((d * 40 % 255, 100, 150), size=(300, 400))).json()["id"]
        conn.execute("UPDATE photos SET day = ? WHERE id = ?",
                     ((settings.today() - timedelta(days=d)).isoformat(), pid))
        conn.commit()


def run_queue(client):
    st = client.app.state
    while timelapse.process_next(st.settings, st.storage):
        pass


def ask(c, trip_id, user_id, **kw):
    return c.post(f"/api/trips/{trip_id}/timelapses", json={"user_id": user_id, **kw})


def test_needs_two_selfies(ana_bia_trip):
    ana, _, _, trip_id = ana_bia_trip
    send_selfie(ana)
    assert ask(ana, trip_id, ana.user_id).status_code == 400


def test_only_members(ana_bia_trip, conn, settings):
    ana, bia, caio, trip_id = ana_bia_trip
    selfies(ana, conn, settings, 3)
    assert ask(caio, trip_id, ana.user_id).status_code == 404     # Caio não é da viagem
    assert ask(ana, trip_id, caio.user_id).status_code == 404     # nem dá pra pedir o dele
    job = ask(bia, trip_id, ana.user_id).json()                    # Bia pode pedir o da Ana
    assert job["status"] == "queued" and job["frame_count"] == 3
    assert caio.get(f"/api/timelapses/{job['id']}").status_code == 404


@needs_ffmpeg
def test_render_and_watch(ana_bia_trip, conn, settings, client):
    ana, bia, caio, trip_id = ana_bia_trip
    selfies(ana, conn, settings, 4)
    job = ask(ana, trip_id, ana.user_id, fps=4).json()
    run_queue(client)

    done = bia.get(f"/api/timelapses/{job['id']}").json()
    assert done["status"] == "done" and done["progress"] == 1, done
    video = bia.get(done["url"])
    assert video.status_code == 200 and video.headers["content-type"] == "video/mp4"
    assert video.content[4:8] == b"ftyp"                         # é um MP4 de verdade
    assert caio.get(done["url"]).status_code == 404

    # Range: o Safari pede pedaços do vídeo.
    part = bia.get(done["url"], headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100
    assert part.headers["content-range"].startswith("bytes 0-99/")

    # A pasta temporária ficou vazia: nenhuma foto aberta largada no disco.
    assert list(settings.tmp_dir.glob("rewind-*")) == []


@needs_ffmpeg
def test_cache_and_invalidation(ana_bia_trip, conn, settings, client):
    ana, _, _, trip_id = ana_bia_trip
    selfies(ana, conn, settings, 2)
    first = ask(ana, trip_id, ana.user_id).json()
    run_queue(client)
    # Mesmo pedido, mesmas fotos: devolve o vídeo pronto, sem gerar de novo.
    again = ask(ana, trip_id, ana.user_id).json()
    assert again["id"] == first["id"] and again["status"] == "done"

    send_selfie(ana)  # troca a de hoje: as fotos mudaram
    newer = ask(ana, trip_id, ana.user_id).json()
    assert newer["id"] != first["id"] and newer["status"] == "queued"
    assert ana.get(f"/api/timelapses/{first['id']}").status_code == 404   # o velho foi apagado
    # FPS diferente é outro vídeo.
    assert ask(ana, trip_id, ana.user_id, fps=12).json()["fps"] == 12


def test_ffmpeg_error_is_reported(ana_bia_trip, conn, settings, client, monkeypatch):
    ana, _, _, trip_id = ana_bia_trip
    selfies(ana, conn, settings, 2)
    job = ask(ana, trip_id, ana.user_id).json()
    import dataclasses
    broken = dataclasses.replace(settings, ffmpeg="ffmpeg-que-nao-existe")
    timelapse.process_next(broken, client.app.state.storage)
    j = ana.get(f"/api/timelapses/{job['id']}").json()
    assert j["status"] == "error" and j["error"]
    assert list(settings.tmp_dir.glob("rewind-*")) == []       # limpou mesmo com erro
    # Pedir de novo depois de um erro cria outro pedido.
    assert ask(ana, trip_id, ana.user_id).json()["status"] == "queued"


def test_list_latest_per_member(ana_bia_trip, conn, settings):
    ana, bia, _, trip_id = ana_bia_trip
    selfies(ana, conn, settings, 2)
    ask(ana, trip_id, ana.user_id)
    rows = bia.get(f"/api/trips/{trip_id}/timelapses").json()
    assert [r["user_id"] for r in rows] == [ana.user_id]
