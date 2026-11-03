"""Configuração lida das variáveis de ambiente (veja .env.example)."""

import os
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

    @property
    def db_path(self) -> Path:
        return self.data_dir / "rewind.db"

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
        )


def now_iso() -> str:
    """Instantes são guardados em UTC, no formato ISO (texto ordena certo no SQLite)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
