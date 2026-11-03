"""Gera os ícones PNG do PWA (o mesmo desenho do frontend/public/icon.svg).

    backend/.venv/Scripts/python.exe -m pip install pillow
    backend/.venv/Scripts/python.exe scripts/gerar_icones.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parent.parent / "frontend" / "public"
BG, FG = "#0f1115", "#ffb454"

for size in (192, 512):
    s = size / 64  # o desenho original é 64x64
    img = Image.new("RGB", (size, size), BG)  # fundo cheio: serve também como "maskable"
    d = ImageDraw.Draw(img)
    w = round(5 * s)
    d.ellipse([(32 - 19) * s, (32 - 19) * s, (32 + 19) * s, (32 + 19) * s], outline=FG, width=w)
    d.line([(32 * s, 21 * s), (32 * s, 32 * s), (39 * s, 37 * s)], fill=FG, width=w, joint="curve")
    img.save(PUBLIC / f"icon-{size}.png")
    print("gerado", PUBLIC / f"icon-{size}.png")
