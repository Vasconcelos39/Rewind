"""Configuração lida das variáveis de ambiente (veja .env.example)."""

import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _bool(valor: str) -> bool:
    return valor.strip().lower() in ("1", "true", "sim", "yes")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    timezone: str = "America/Cuiaba"
    cookie_secure: bool = True
    session_days: int = 30
    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"
    # A chave fica FORA da pasta de dados: quem levar o HDD não leva a chave junto.
    key_file: Path = BACKEND_DIR / "rewind.key"
    max_upload_mb: int = 10
    extras_per_day: int = 10
    # Timelapse
    ffmpeg: str = "ffmpeg"
    default_fps: int = 8
    # Onde as fotos ficam abertas enquanto o ffmpeg trabalha. No Docker, um tmpfs (RAM).
    tmp_dir: Path = Path(tempfile.gettempdir()) / "rewind"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "rewind.db"

    @property
    def photos_dir(self) -> Path:
        return self.data_dir / "photos"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def today(self) -> date:
        """O "dia" do Rewind: sempre pelo relógio do servidor, no fuso configurado."""
        return datetime.now(self.tz).date()

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.environ.get("REWIND_DATA_DIR", BACKEND_DIR / "data")),
            timezone=os.environ.get("REWIND_TIMEZONE", "America/Cuiaba"),
            cookie_secure=_bool(os.environ.get("REWIND_COOKIE_SECURE", "true")),
            session_days=int(os.environ.get("REWIND_SESSION_DAYS", "30")),
            frontend_dist=Path(
                os.environ.get("REWIND_FRONTEND_DIST", BACKEND_DIR.parent / "frontend" / "dist")
            ),
            key_file=Path(os.environ.get("REWIND_KEY_FILE", BACKEND_DIR / "rewind.key")),
            max_upload_mb=int(os.environ.get("REWIND_MAX_UPLOAD_MB", "10")),
            extras_per_day=int(os.environ.get("REWIND_EXTRAS_PER_DAY", "10")),
            ffmpeg=os.environ.get("REWIND_FFMPEG", "ffmpeg"),
            default_fps=int(os.environ.get("REWIND_FPS", "8")),
            tmp_dir=Path(os.environ.get("REWIND_TMP_DIR", Path(tempfile.gettempdir()) / "rewind")),
        )


def now_iso() -> str:
    """Instantes são guardados em UTC, no formato ISO (texto ordena certo no SQLite)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
