"""Timelapse: fila + ffmpeg.

Os pedidos ficam na tabela `timelapses`. Uma única thread de trabalho pega um por
vez, o mais antigo primeiro: o Orange Pi é fraco, e dois ffmpeg juntos travariam
o resto do app.

O ffmpeg precisa das fotos abertas, então elas são descriptografadas numa pasta
temporária (de preferência tmpfs, que fica só na RAM) e apagadas logo depois,
deu certo ou não.
"""

import hashlib
import shutil
import sqlite3
import subprocess
import tempfile
import threading
from pathlib import Path

from . import db
from .config import Settings, now_iso
from .storage import Storage

WIDTH, HEIGHT = 720, 960  # 3:4, o mesmo formato das selfies


def trip_selfies(conn: sqlite3.Connection, trip_id: int, user_id: int) -> list[sqlite3.Row]:
    """As selfies da pessoa que valem pra essa viagem, em ordem de dia."""
    return conn.execute(
        "SELECT p.* FROM photos p"
        " JOIN trip_members m ON m.user_id = p.user_id AND m.trip_id = ?"
        " JOIN trips t ON t.id = m.trip_id"
        " WHERE p.user_id = ? AND p.kind = 'selfie' AND p.day BETWEEN m.joined_day AND t.end_date"
        " ORDER BY p.day", (trip_id, user_id)).fetchall()


def fingerprint(photos: list[sqlite3.Row], fps: int) -> str:
    # Cada foto nova (ou substituída) tem id novo, então a lista de ids basta.
    ids = ",".join(str(p["id"]) for p in photos)
    return hashlib.sha256(f"{fps}|{ids}".encode()).hexdigest()


def _ffmpeg_cmd(settings: Settings, frames_dir: Path, fps: int, out: Path) -> list[str]:
    # Fotos de tamanhos diferentes viram todas 720x960 (encaixa e completa com preto).
    scale = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
             f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=yuv420p")
    return [
        settings.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-framerate", str(fps), "-i", str(frames_dir / "%05d.jpg"),
        "-vf", scale,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-movflags", "+faststart",  # o vídeo começa a tocar antes de baixar inteiro
        "-progress", "pipe:1",      # o ffmpeg conta os quadros prontos na saída padrão
        str(out),
    ]


def render(settings: Settings, storage: Storage, conn: sqlite3.Connection, job: sqlite3.Row) -> str:
    """Gera o vídeo de um pedido. Devolve o nome do arquivo criptografado."""
    photos = trip_selfies(conn, job["trip_id"], job["user_id"])
    total = len(photos)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="rewind-", dir=settings.tmp_dir))
    try:
        for i, p in enumerate(photos, start=1):
            (work / f"{i:05d}.jpg").write_bytes(storage.load(p["file_name"]))
        out = work / "out.mp4"
        proc = subprocess.Popen(_ffmpeg_cmd(settings, work, job["fps"], out),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in proc.stdout:
            if line.startswith("frame="):
                done = int(line.split("=", 1)[1] or 0)
                conn.execute("UPDATE timelapses SET progress = ? WHERE id = ?",
                             (min(done / total, 0.99), job["id"]))
                conn.commit()
        if proc.wait() != 0:
            raise RuntimeError(proc.stderr.read().strip()[-500:] or "ffmpeg falhou")
        return storage.save(out.read_bytes())
    finally:
        # Apaga as fotos abertas e o vídeo aberto, aconteça o que acontecer.
        shutil.rmtree(work, ignore_errors=True)


def process_next(settings: Settings, storage: Storage) -> bool:
    """Processa o próximo pedido da fila. Devolve False se a fila estava vazia."""
    conn = db.connect(settings.db_path)
    try:
        job = conn.execute(
            "SELECT * FROM timelapses WHERE status = 'queued' ORDER BY id LIMIT 1").fetchone()
        if job is None:
            return False
        conn.execute("UPDATE timelapses SET status = 'running', progress = 0 WHERE id = ?", (job["id"],))
        conn.commit()
        try:
            name = render(settings, storage, conn, job)
        except Exception as e:  # erro num vídeo não pode derrubar a fila
            conn.execute("UPDATE timelapses SET status = 'error', error = ?, finished_at = ? WHERE id = ?",
                         (str(e)[:500], now_iso(), job["id"]))
            conn.commit()
            return True
        conn.execute(
            "UPDATE timelapses SET status = 'done', progress = 1, file_name = ?, finished_at = ? WHERE id = ?",
            (name, now_iso(), job["id"]))
        conn.commit()
        return True
    finally:
        conn.close()


class Worker:
    """A thread que fica esperando pedidos. `wake()` avisa que entrou um novo."""

    def __init__(self, settings: Settings, storage: Storage):
        self.settings, self.storage = settings, storage
        self._event = threading.Event()
        self._stop = False
        self._thread = threading.Thread(target=self._run, name="timelapse", daemon=True)

    def start(self) -> None:
        # Se o servidor caiu no meio de um vídeo, ele volta pra fila.
        conn = db.connect(self.settings.db_path)
        conn.execute("UPDATE timelapses SET status = 'queued', progress = 0 WHERE status = 'running'")
        conn.commit()
        conn.close()
        self._thread.start()

    def wake(self) -> None:
        self._event.set()

    def stop(self) -> None:
        self._stop = True
        self._event.set()

    def _run(self) -> None:
        while not self._stop:
            while not self._stop and process_next(self.settings, self.storage):
                pass
            self._event.wait(timeout=60)  # dorme até chegar pedido (ou 1 min, por garantia)
            self._event.clear()
