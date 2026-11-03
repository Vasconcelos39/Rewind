"""Comandos de linha. O primeiro admin nasce aqui, nunca pela interface.

    python -m app.cli create-admin --username ana
    python -m app.cli reset-password --username ana
    python -m app.cli generate-key

Sem terminal interativo, a senha é lida da entrada padrão:
    echo "minha-senha" | python -m app.cli create-admin --username ana
"""

import argparse
import getpass
import sys

from pathlib import Path

from . import crypto, db, security
from .config import Settings


def _ask_password() -> str:
    # Sem terminal (script, pipe): lê uma linha da entrada padrão.
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\r\n")
    # getpass não mostra o que você digita.
    first = getpass.getpass("Senha: ")
    if first != getpass.getpass("Repita a senha: "):
        sys.exit("As senhas não conferem.")
    return first


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-admin", help="cria uma conta de administrador")
    create.add_argument("--username", required=True)
    create.add_argument("--display-name")

    reset = sub.add_parser("reset-password", help="troca a senha de uma conta")
    reset.add_argument("--username", required=True)

    key = sub.add_parser("generate-key", help="cria a chave de criptografia das fotos")
    key.add_argument("--out", help="onde salvar (padrão: REWIND_KEY_FILE)")

    args = parser.parse_args(argv)
    settings = Settings.from_env()
    if args.command == "generate-key":
        path = Path(args.out) if args.out else settings.key_file
        try:
            crypto.generate_key_file(path)
        except FileExistsError as e:
            sys.exit(str(e))
        print(f"Chave criada em {path}.")
        print("GUARDE UMA CÓPIA FORA DO SERVIDOR: sem ela, as fotos não abrem nunca mais.")
        return

    db.migrate(settings.db_path)
    conn = db.connect(settings.db_path)
    try:
        if args.command == "create-admin":
            password = _ask_password()
            security.create_user(conn, args.username, password, args.display_name, is_admin=True)
            print(f"Admin '{args.username}' criado em {settings.db_path}")
        elif args.command == "reset-password":
            user = conn.execute("SELECT id FROM users WHERE username = ?", (args.username,)).fetchone()
            if user is None:
                sys.exit("Usuário não encontrado.")
            security.set_password(conn, user["id"], _ask_password())
            # Senha nova = todo mundo que estava logado nessa conta sai.
            security.delete_other_sessions(conn, user["id"], None)
            print("Senha trocada; as sessões abertas foram encerradas.")
    except security.InvalidInput as e:
        sys.exit(str(e))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
