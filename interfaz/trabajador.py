# -*- coding: utf-8 -*-
"""
trabajador.py — Ejecuta una tarea larga (leer la carpeta, enviar correos,
probar la conexión) en un hilo aparte para que la ventana no se congele.

    t = Tarea(funcion, args...)       # funcion(*args, avance=callback)
    t.avance.connect(...)             # (hechas, total, archivo)
    t.terminada.connect(...)          # (resultado)
    t.fallo.connect(...)              # (excepción)
    t.start()
"""

from PySide6.QtCore import QThread, Signal


class Tarea(QThread):
    avance = Signal(int, int, str)
    terminada = Signal(object)
    fallo = Signal(object)

    def __init__(self, funcion, *args, con_avance: bool = True, **kwargs):
        super().__init__()
        self.funcion, self.args, self.kwargs, self.con_avance = funcion, args, kwargs, con_avance
        self.cancelada = False

    def run(self):
        try:
            if self.con_avance:
                self.kwargs["avance"] = lambda h, t, a: self.avance.emit(h, t, a)
            self.terminada.emit(self.funcion(*self.args, **self.kwargs))
        except Exception as e:  # noqa: BLE001 — se muestra en la ventana
            self.fallo.emit(e)
