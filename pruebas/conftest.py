import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "pruebas"))


@pytest.fixture
def datos(tmp_path, monkeypatch):
    monkeypatch.setenv("CARTERO_DATOS", str(tmp_path / "datos"))
    from nucleo.datos import Datos
    d = Datos(tmp_path / "prueba.sqlite")
    d.guardar_ajuste("empresa", {"nombre": "Suministros La Vega, S.L.", "nif": "B04123456",
                                 "email": "info@suministroslavega.es"})
    return d


@pytest.fixture
def correo_falso():
    from utiles import ServidorCorreoFalso
    s = ServidorCorreoFalso()
    yield s
    s.cerrar()


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
