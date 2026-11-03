"""Banco SQLite com SQL puro e migrações numeradas.

Cada arquivo em app/migrations chama NNNN_nome.sql. O número da última
migração aplicada fica no próprio banco, em `PRAGMA user_version`.
"""

import re
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row  # linhas acessíveis por nome: row["username"]
    conn.execute("PRAGMA foreign_keys = ON")  # o SQLite vem com isso desligado
    conn.execute("PRAGMA journal_mode = WAL")  # leituras não esperam escritas
    return conn


def migrate(db_path: Path) -> int:
    """Aplica as migrações que faltam e devolve a versão final do banco."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            number = int(re.match(r"(\d+)_", path.name).group(1))
            if number <= current:
                continue
            sql = path.read_text(encoding="utf-8")
            # Tudo numa transação: ou a migração entra inteira, ou nada muda.
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
            current = number
        return current
    finally:
        conn.close()
