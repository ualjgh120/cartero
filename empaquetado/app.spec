# -*- mode: python ; coding: utf-8 -*-
"""
Receta de PyInstaller para Mac (.app) y Windows (.exe). Se lanza desde la raíz:
    pyinstaller empaquetado/app.spec --noconfirm
El nombre sale de nucleo/config.py.
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

RAIZ = Path(SPECPATH).parent
sys.path.insert(0, str(RAIZ))
from nucleo.config import NOMBRE_APP, VERSION  # noqa: E402

es_mac = sys.platform == "darwin"

datos = [(str(RAIZ / "recursos"), "recursos")] + collect_data_files("certifi")
ocultos = ["keyring.backends.macOS" if es_mac else "keyring.backends.Windows", "keyring.backends.fail"]
excluir = ["tkinter", "pytest", "IPython", "matplotlib", "pandas", "scipy", "pymupdf", "fitz",
           "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia"]

a = Analysis(
    [str(RAIZ / "main.py")],
    pathex=[str(RAIZ)],
    datas=datos,
    hiddenimports=ocultos,
    excludes=excluir,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=NOMBRE_APP,
    console=False,
    icon=str(RAIZ / "recursos" / ("icono.icns" if es_mac else "icono.ico")),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NOMBRE_APP, upx=False)
if es_mac:
    app = BUNDLE(
        coll,
        name=f"{NOMBRE_APP}.app",
        icon=str(RAIZ / "recursos" / "icono.icns"),
        bundle_identifier=f"es.{NOMBRE_APP.lower()}.app",
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "CFBundleDevelopmentRegion": "es",
        },
    )
