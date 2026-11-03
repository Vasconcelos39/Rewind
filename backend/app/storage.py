"""Guarda e lê arquivos criptografados na pasta de fotos."""

import os
import secrets
from pathlib import Path

from .crypto import Box


class Storage:
    def __init__(self, root: Path, box: Box):
        self.root = root
        self.box = box
        root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        # Os nomes são sempre gerados por nós (hex), mas conferimos mesmo assim.
        if not name.isalnum():
            raise ValueError("nome de arquivo inválido")
        return self.root / name[:2] / f"{name}.enc"  # subpastas pra não ter 10 mil arquivos juntos

    def save(self, data: bytes) -> str:
        """Criptografa e grava. Devolve o nome aleatório do arquivo."""
        name = secrets.token_hex(16)  # aleatório: o nome não revela dono nem data
        path = self._path(name)
        path.parent.mkdir(exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(self.box.encrypt(data, name))
        os.replace(tmp, path)  # troca atômica: nunca fica um arquivo pela metade
        return name

    def load(self, name: str) -> bytes:
        return self.box.decrypt(self._path(name).read_bytes(), name)

    def delete(self, name: str) -> None:
        self._path(name).unlink(missing_ok=True)
