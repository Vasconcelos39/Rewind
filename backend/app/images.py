"""Confere e recodifica as imagens enviadas.

Recodificar (abrir e salvar de novo) faz três coisas de uma vez:
- garante que o arquivo é mesmo uma imagem, e não algo disfarçado com extensão .jpg;
- joga fora o EXIF (GPS, modelo do celular, data...), porque só os pixels são salvos;
- limita o tamanho, mesmo que o cliente não tenha redimensionado.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Barra "bombas" de descompressão: arquivo pequeno que vira uma imagem gigante na memória.
Image.MAX_IMAGE_PIXELS = 50_000_000


class BadImage(ValueError):
    pass


@dataclass
class Processed:
    data: bytes
    width: int
    height: int


def process(raw: bytes) -> Processed:
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ALLOWED_FORMATS:
            raise BadImage("Formato não aceito (use JPEG, PNG ou WebP)")
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise BadImage("Arquivo não é uma imagem válida")

    # Fotos da galeria guardam a rotação no EXIF; aplicamos antes de jogá-lo fora.
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAX_SIDE, MAX_SIDE))  # só diminui, nunca aumenta
    if img.mode != "RGB":
        img = img.convert("RGB")

    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)  # sem exif=..., então sai sem EXIF
    return Processed(out.getvalue(), img.width, img.height)
