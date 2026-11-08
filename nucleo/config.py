# -*- coding: utf-8 -*-
"""
config.py — Nombre de la app y carpetas donde guarda sus datos.

Cambiar NOMBRE_APP aquí lo cambia en toda la app (ventana, carpeta de datos,
llavero). El empaquetado (.dmg/.exe) lee el mismo valor.
"""

import os
import platform
import sys
from pathlib import Path

NOMBRE_APP = "Cartero"
VERSION = "0.1.0"


def carpeta_datos() -> Path:
    """
    Carpeta del usuario donde se guarda la base de datos (empresa, clientes,
    historial de envíos) y el logo. Es la habitual de cada sistema:
      Mac:     ~/Library/Application Support/<App>
      Windows: %APPDATA%\\<App>
      Linux:   ~/.local/share/<App>
    Con la variable CARTERO_DATOS se puede usar otra (pruebas, o una carpeta de red).
    """
    if os.environ.get("CARTERO_DATOS"):
        carpeta = Path(os.environ["CARTERO_DATOS"])
    else:
        sistema = platform.system()
        if sistema == "Darwin":
            base = Path.home() / "Library" / "Application Support"
        elif sistema == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        carpeta = base / NOMBRE_APP
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def ruta_recurso(relativa: str) -> Path:
    """Ruta a un archivo de recursos/ tanto en desarrollo como dentro del .app/.exe."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "recursos" / relativa
