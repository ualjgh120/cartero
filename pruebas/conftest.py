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


# PySide6 a veces se cae (segmentation fault) al destruir los widgets cuando Python
# se cierra después de las pruebas de interfaz. No afecta a la app, pero en macOS sale
# el aviso de «Python se ha cerrado inesperadamente» y en GitHub puede dar fallos al azar.
# Cuando pytest ya ha escrito el resultado, salimos sin pasar por ese cierre.
_estado_final = {"codigo": 0}


def pytest_sessionfinish(session, exitstatus):
    _estado_final["codigo"] = int(exitstatus)


def pytest_unconfigure(config):
    import os
    import sys
    if "PySide6.QtWidgets" in sys.modules:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_estado_final["codigo"])
