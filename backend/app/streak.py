"""Streak: dias seguidos com selfie. Calculada na hora a partir das fotos.

Nada fica salvo: assim ela nunca fica dessincronizada (substituir ou apagar uma
foto, mudar o fuso... a conta sempre bate).

Regra, igual ao Duolingo: se você ainda não tirou a de hoje, a streak não zera
até o dia acabar. Ela conta até ontem e fica "em risco".
"""

import sqlite3
from datetime import date, datetime, timedelta

from .config import Settings


def selfie_days(conn: sqlite3.Connection, user_id: int) -> set[date]:
    rows = conn.execute("SELECT day FROM photos WHERE user_id = ? AND kind = 'selfie'", (user_id,))
    return {date.fromisoformat(r[0]) for r in rows}


def count_streak(days: set[date], today: date) -> int:
    day = today if today in days else today - timedelta(days=1)
    n = 0
    while day in days:
        n += 1
        day -= timedelta(days=1)
    return n


def user_streak(conn: sqlite3.Connection, settings: Settings, user_id: int) -> dict:
    days, today = selfie_days(conn, user_id), settings.today()
    return {"streak": count_streak(days, today), "sent_today": today in days}


def pair_streak(conn: sqlite3.Connection, settings: Settings, a: int, b: int) -> int:
    """Streak em dupla: dias seguidos em que OS DOIS tiraram a selfie."""
    return count_streak(selfie_days(conn, a) & selfie_days(conn, b), settings.today())


def seconds_left_today(settings: Settings) -> int:
    """Quanto falta pra acabar o dia (no fuso do Rewind)."""
    now = datetime.now(settings.tz)
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), settings.tz)
    return int((midnight - now).total_seconds())
