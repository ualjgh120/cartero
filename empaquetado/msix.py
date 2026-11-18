# -*- coding: utf-8 -*-
"""
msix.py — Prepara la carpeta del paquete MSIX para la Microsoft Store.

Copia la app ya compilada por PyInstaller (dist/<App>), genera los logos que
pide la Store y rellena AppxManifest.xml. Después, en Windows:
    makeappx pack /d build\\msix /p dist\\<App>-<versión>.msix

No se firma: la Store firma el paquete gratis al publicarlo.

Los datos de identidad salen de Partner Center (Producto > Identidad del
producto) y se pasan por variables de entorno:
    MSIX_IDENTIDAD      Package/Identity/Name           p. ej. 12345JuanGonzalezHaro.Cartero
    MSIX_EDITOR         Package/Identity/Publisher      p. ej. CN=XXXXXXXX-XXXX-...
    MSIX_NOMBRE_EDITOR  Package/Properties/PublisherDisplayName
    MSIX_NOMBRE_TIENDA  nombre reservado en la Store (p. ej. Cartero Facturas)
Sin ellas se usan valores de prueba (sirve para comprobar que empaqueta).
"""
import os
import shutil
import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from nucleo.config import NOMBRE_APP, VERSION  # noqa: E402

DESTINO = RAIZ / "build" / "msix"


def logo(icono: Image.Image, ancho: int, alto: int, ocupa: float) -> Image.Image:
    """Icono centrado sobre fondo transparente, ocupando `ocupa` del lado menor."""
    lienzo = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    lado = int(min(ancho, alto) * ocupa)
    pequeno = icono.resize((lado, lado), Image.LANCZOS)
    lienzo.paste(pequeno, ((ancho - lado) // 2, (alto - lado) // 2), pequeno)
    return lienzo


def main() -> None:
    app = RAIZ / "dist" / NOMBRE_APP
    if not (app / f"{NOMBRE_APP}.exe").exists():
        sys.exit(f"No encuentro {app}\\{NOMBRE_APP}.exe: compila antes con PyInstaller")

    shutil.rmtree(DESTINO, ignore_errors=True)
    shutil.copytree(app, DESTINO / NOMBRE_APP)

    assets = DESTINO / "Assets"
    assets.mkdir()
    icono = Image.open(RAIZ / "recursos" / "icono.png").convert("RGBA")
    logo(icono, 50, 50, 1.0).save(assets / "StoreLogo.png")
    logo(icono, 44, 44, 1.0).save(assets / "Square44x44Logo.png")
    logo(icono, 150, 150, 0.8).save(assets / "Square150x150Logo.png")
    logo(icono, 310, 150, 0.8).save(assets / "Wide310x150Logo.png")

    # La Store exige versión de 4 cifras con la última a 0: 0.1.0 -> 0.1.0.0
    partes = (VERSION.split(".") + ["0", "0", "0"])[:3]
    version = ".".join(partes + ["0"])

    manifiesto = (RAIZ / "empaquetado" / "msix" / "AppxManifest.xml").read_text(encoding="utf-8")
    valores = {
        "IDENTIDAD": os.environ.get("MSIX_IDENTIDAD") or f"Prueba.{NOMBRE_APP}",
        "EDITOR": os.environ.get("MSIX_EDITOR") or "CN=Prueba",
        "NOMBRE_EDITOR": os.environ.get("MSIX_NOMBRE_EDITOR") or "Juan González Haro",
        "NOMBRE": NOMBRE_APP,
        "NOMBRE_TIENDA": os.environ.get("MSIX_NOMBRE_TIENDA") or NOMBRE_APP,
        "VERSION": version,
    }
    for clave, valor in valores.items():
        manifiesto = manifiesto.replace("{{" + clave + "}}", valor)
    (DESTINO / "AppxManifest.xml").write_text(manifiesto, encoding="utf-8")
    print(f"Paquete preparado en {DESTINO} (versión {version})")


if __name__ == "__main__":
    main()
