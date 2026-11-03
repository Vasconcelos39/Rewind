"""Criptografia das fotos em repouso (AES-256-GCM).

O QUE PROTEGE: alguém que leve o HDD (ou uma cópia dele, ou o backup) vê só
arquivos embaralhados. Sem a chave, não dá pra abrir nem saber o que são.

O QUE NÃO PROTEGE: um invasor dentro do servidor ligado. O app precisa da chave
pra mostrar as fotos, então quem controla o servidor rodando controla a chave.

Formato de cada arquivo:  b"RWD1" | nonce (12 bytes) | conteúdo cifrado + tag (16 bytes)
"""

import base64
import os
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"RWD1"
NONCE_SIZE = 12


class DecryptError(Exception):
    pass


def generate_key_file(path: Path) -> None:
    """Cria um arquivo com 32 bytes aleatórios (em base64), legível só pelo dono."""
    if path.exists():
        raise FileExistsError(f"{path} já existe; não vou sobrescrever uma chave")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(base64.b64encode(secrets.token_bytes(32)).decode() + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # no Windows não tem chmod de verdade


def load_key(path: Path) -> bytes:
    key = base64.b64decode(path.read_text().strip())
    if len(key) != 32:
        raise ValueError("A chave precisa ter 32 bytes (AES-256)")
    return key


class Box:
    def __init__(self, key: bytes):
        self._aes = AESGCM(key)

    def encrypt(self, data: bytes, name: str) -> bytes:
        # Nonce novo e aleatório a cada arquivo: repetir nonce com a mesma chave quebra o GCM.
        nonce = secrets.token_bytes(NONCE_SIZE)
        # O nome entra como "dado associado": se alguém trocar dois arquivos de lugar,
        # a leitura falha em vez de mostrar a foto de outra pessoa.
        return MAGIC + nonce + self._aes.encrypt(nonce, data, name.encode())

    def decrypt(self, blob: bytes, name: str) -> bytes:
        if not blob.startswith(MAGIC):
            raise DecryptError("arquivo não é do Rewind")
        nonce = blob[len(MAGIC):len(MAGIC) + NONCE_SIZE]
        try:
            return self._aes.decrypt(nonce, blob[len(MAGIC) + NONCE_SIZE:], name.encode())
        except InvalidTag:
            raise DecryptError("arquivo alterado ou chave errada")
