"""Senhas, contas e sessões."""

import hashlib
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from .config import now_iso

# argon2id com os parâmetros padrão da biblioteca (64 MiB de memória, 3 passadas):
# lento de propósito, pra que adivinhar senhas copiadas do banco seja caro.
_hasher = PasswordHasher()

# Hash de uma senha qualquer, usado quando o usuário não existe (veja authenticate).
_DUMMY_HASH = _hasher.hash("senha-que-ninguem-usa")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD = 8
MAX_PASSWORD = 256  # evita que alguém mande 10 MB de "senha" pro argon2


class InvalidInput(ValueError):
    pass


def validate_username(username: str) -> str:
    if not USERNAME_RE.match(username):
        raise InvalidInput("Usuário deve ter 3 a 32 caracteres: letras, números, _ . -")
    return username


def validate_password(password: str) -> str:
    if not (MIN_PASSWORD <= len(password) <= MAX_PASSWORD):
        raise InvalidInput(f"Senha deve ter pelo menos {MIN_PASSWORD} caracteres")
    return password


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def create_user(
    conn: sqlite3.Connection,
    username: str,
    password: str,
    display_name: str | None = None,
    is_admin: bool = False,
    commit: bool = True,
) -> int:
    validate_username(username)
    validate_password(password)
    try:
        cur = conn.execute(
            "INSERT INTO users (username, display_name, password_hash, is_admin, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (username, (display_name or username).strip()[:64], hash_password(password),
             int(is_admin), now_iso()),
        )
    except sqlite3.IntegrityError:
        raise InvalidInput("Esse usuário já existe")
    if commit:
        conn.commit()
    return cur.lastrowid


def authenticate(conn: sqlite3.Connection, username: str, password: str) -> sqlite3.Row | None:
    """Devolve o usuário se a senha bater, senão None."""
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    try:
        # Mesmo sem usuário, verificamos contra um hash falso: assim a resposta demora
        # o mesmo tempo e ninguém descobre quais usuários existem medindo o relógio.
        _hasher.verify(user["password_hash"] if user else _DUMMY_HASH, password[:MAX_PASSWORD])
    except VerificationError:
        return None
    if user is None:
        return None
    # Se um dia os parâmetros do argon2 mudarem, o hash é refeito no próximo login.
    if _hasher.check_needs_rehash(user["password_hash"]):
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (hash_password(password), user["id"]))
        conn.commit()
    return user


def set_password(conn: sqlite3.Connection, user_id: int, password: str) -> None:
    validate_password(password)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
    conn.commit()


# --- Sessões -----------------------------------------------------------------

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(conn: sqlite3.Connection, user_id: int, days: int) -> str:
    """Cria a sessão e devolve o token que vai no cookie."""
    token = secrets.token_urlsafe(32)  # 256 bits aleatórios: impossível de adivinhar
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now_iso(),))  # faxina
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token_hash(token), user_id, now_iso(), expires.isoformat(timespec="seconds")),
    )
    conn.commit()
    return token


def user_from_session(conn: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    return conn.execute(
        "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id"
        " WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
        (token_hash(token), now_iso()),
    ).fetchone()


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
    conn.commit()


def delete_other_sessions(conn: sqlite3.Connection, user_id: int, keep_token: str | None) -> None:
    conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
                 (user_id, token_hash(keep_token or "")))
    conn.commit()
