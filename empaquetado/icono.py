# -*- coding: utf-8 -*-
"""icono.py — Dibuja el icono de la app (un sobre) y lo guarda en .png, .icns (Mac) y .ico (Windows)."""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

RECURSOS = Path(__file__).resolve().parent.parent / "recursos"


def dibujar(lado: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    m = lado * 0.08
    # fondo: cuadrado redondeado azul con degradado vertical
    fondo = Image.new("RGBA", (lado, lado))
    fd = ImageDraw.Draw(fondo)
    for y in range(lado):
        t = y / lado
        fd.line([(0, y), (lado, y)], fill=(int(46 - 16 * t), int(108 - 30 * t), int(156 - 40 * t), 255))
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([m, m, lado - m, lado - m], radius=lado * 0.2, fill=255)
    img.paste(fondo, (0, 0), mascara)
    d = ImageDraw.Draw(img)

    # factura asomando por detrás del sobre
    fx0, fx1, fy0 = lado * 0.33, lado * 0.67, lado * 0.2
    d.rounded_rectangle([fx0, fy0, fx1, lado * 0.6], radius=lado * 0.02, fill=(255, 255, 255, 255))
    for i, ancho in enumerate([0.22, 0.16, 0.2]):
        y = lado * (0.27 + i * 0.065)
        d.rounded_rectangle([fx0 + lado * 0.05, y, fx0 + lado * (0.05 + ancho), y + lado * 0.028],
                            radius=lado * 0.014, fill=(190, 208, 224, 255))

    # sobre
    x0, x1, y0, y1 = lado * 0.2, lado * 0.8, lado * 0.42, lado * 0.8
    sobre = (238, 243, 247, 255)
    d.rounded_rectangle([x0, y0, x1, y1], radius=lado * 0.035, fill=sobre)
    # solapas laterales (algo más oscuras) y la de abajo
    d.polygon([(x0, y0 + lado * 0.02), (lado * 0.5, lado * 0.63), (x0, y1 - lado * 0.02)], fill=(222, 231, 239, 255))
    d.polygon([(x1, y0 + lado * 0.02), (lado * 0.5, lado * 0.63), (x1, y1 - lado * 0.02)], fill=(222, 231, 239, 255))
    d.polygon([(x0 + lado * 0.01, y1), (lado * 0.5, lado * 0.6), (x1 - lado * 0.01, y1)], fill=(250, 251, 253, 255))
    # sello naranja
    r = lado * 0.075
    cx, cy = x1 - lado * 0.02, y0 + lado * 0.0
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(232, 127, 48, 255))
    w = int(lado * 0.022)
    d.line([(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)],
           fill=(255, 255, 255, 255), width=w, joint="curve")
    return img


def main():
    RECURSOS.mkdir(exist_ok=True)
    img = dibujar()
    img.save(RECURSOS / "icono.png")
    img.save(RECURSOS / "icono.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    if sys.platform == "darwin":
        with tempfile.TemporaryDirectory() as tmp:
            conjunto = Path(tmp) / "icono.iconset"
            conjunto.mkdir()
            for tam in (16, 32, 128, 256, 512):
                img.resize((tam, tam), Image.LANCZOS).save(conjunto / f"icon_{tam}x{tam}.png")
                img.resize((tam * 2, tam * 2), Image.LANCZOS).save(conjunto / f"icon_{tam}x{tam}@2x.png")
            subprocess.run(["iconutil", "-c", "icns", str(conjunto), "-o", str(RECURSOS / "icono.icns")], check=True)
    print("icono listo en", RECURSOS)


if __name__ == "__main__":
    main()
