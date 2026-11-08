# -*- coding: utf-8 -*-
"""Punto de entrada: abre el asistente la primera vez y luego la ventana principal."""

import sys


def autoprueba(rutas: list[str]) -> int:
    """Cartero --autoprueba factura.pdf [--salida resultado.txt] (ver nucleo/autoprueba.py)."""
    destino = None
    if "--salida" in rutas:  # en Windows una app con ventana no tiene consola: se escribe a un archivo
        i = rutas.index("--salida")
        destino = open(rutas[i + 1], "w", encoding="utf-8")
        rutas = rutas[:i] + rutas[i + 2:]

    def escribir(texto: str):
        print(texto)
        if destino:
            destino.write(texto + "\n")
            destino.flush()

    from nucleo.autoprueba import ejecutar
    codigo = ejecutar(rutas, escribir)
    if destino:
        destino.close()
    return codigo


def main():
    if "--autoprueba" in sys.argv:
        return autoprueba([a for a in sys.argv[1:] if a != "--autoprueba"])

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from interfaz.asistente import Asistente
    from interfaz.estilo import HOJA_ESTILOS
    from interfaz.ventana import VentanaPrincipal
    from nucleo.config import NOMBRE_APP, ruta_recurso
    from nucleo.datos import Datos

    app = QApplication(sys.argv)
    app.setApplicationName(NOMBRE_APP)
    app.setStyle("Fusion")
    app.setStyleSheet(HOJA_ESTILOS)
    app.setWindowIcon(QIcon(str(ruta_recurso("icono.png"))))

    datos = Datos()
    if not datos.configurada() and not Asistente(datos).exec():
        return 0

    ventana = VentanaPrincipal(datos)
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
