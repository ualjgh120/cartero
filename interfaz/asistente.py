# -*- coding: utf-8 -*-
"""
asistente.py — La primera vez que se abre la app, guía paso a paso para
dejarla configurada: empresa, correo, mensaje, facturas y clientes.

Cada paso se guarda al pulsar «Siguiente», así que si se cierra a medias
lo ya rellenado no se pierde.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout,
)

from interfaz.estilo import caja, poner_tipo
from interfaz.paginas import (
    PaginaBienvenida, PaginaClientes, PaginaCorreo, PaginaEmpresa, PaginaFacturas, PaginaListo, PaginaMensaje,
)
from nucleo.config import NOMBRE_APP, ruta_recurso


class Asistente(QDialog):
    PASOS = [("Bienvenida", PaginaBienvenida), ("Tu empresa", PaginaEmpresa), ("Tu correo", PaginaCorreo),
             ("El mensaje", PaginaMensaje), ("Tus facturas", PaginaFacturas), ("Tus clientes", PaginaClientes),
             ("Listo", PaginaListo)]

    def __init__(self, datos, parent=None):
        super().__init__(parent)
        self.datos = datos
        self.setWindowTitle(f"Configurar {NOMBRE_APP}")
        self.resize(900, 640)
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # columna de pasos
        lateral = QFrame()
        lateral.setObjectName("pasos")
        lateral.setFixedWidth(200)
        col = QVBoxLayout(lateral)
        col.setContentsMargins(16, 22, 16, 16)
        icono = QLabel()
        icono.setPixmap(QPixmap(str(ruta_recurso("icono.png"))).scaled(44, 44, Qt.KeepAspectRatio,
                                                                          Qt.SmoothTransformation))
        col.addWidget(icono)
        nombre = QLabel(NOMBRE_APP)
        nombre.setObjectName("nombreEmpresa")
        col.addWidget(nombre)
        col.addSpacing(16)
        self.etiquetas = []
        for i, (titulo, _) in enumerate(self.PASOS):
            e = QLabel(f"{i + 1}.  {titulo}" if 0 < i < len(self.PASOS) - 1 else titulo)
            self.etiquetas.append(e)
            col.addWidget(e)
        col.addStretch()
        raiz.addWidget(lateral)

        # página actual + botones
        derecha = QVBoxLayout()
        derecha.setContentsMargins(30, 24, 30, 20)
        self.pila = QStackedWidget()
        self.paginas = []
        for _, clase in self.PASOS:
            pagina = clase(datos)
            pagina.cambiada.connect(self._pintar)
            self.paginas.append(pagina)
            envoltura = QScrollArea()
            envoltura.setWidgetResizable(True)
            envoltura.setWidget(pagina)
            self.pila.addWidget(envoltura)
        derecha.addWidget(self.pila, 1)
        self.falta = caja("", "aviso")
        self.falta.hide()
        derecha.addWidget(self.falta)
        botones = QHBoxLayout()
        self.atras = QPushButton("Atrás")
        self.atras.clicked.connect(lambda: self._ir(self.actual - 1))
        self.siguiente = QPushButton("Siguiente")
        self.siguiente.setObjectName("principal")
        self.siguiente.setDefault(True)
        self.siguiente.clicked.connect(self._siguiente)
        botones.addWidget(self.atras)
        botones.addStretch()
        botones.addWidget(self.siguiente)
        derecha.addLayout(botones)
        raiz.addLayout(derecha, 1)

        self.actual = 0
        self._ir(0)

    def _ir(self, i):
        self.actual = max(0, min(i, len(self.paginas) - 1))
        self.paginas[self.actual].cargar()
        self.pila.setCurrentIndex(self.actual)
        self.falta.hide()
        self._pintar()

    def _pintar(self):
        for i, e in enumerate(self.etiquetas):
            e.setObjectName("pasoActual" if i == self.actual else "pasoHecho" if i < self.actual else "paso")
            e.style().unpolish(e)
            e.style().polish(e)
        self.atras.setVisible(self.actual > 0)
        ultimo = self.actual == len(self.paginas) - 1
        self.siguiente.setText(f"Empezar a usar {NOMBRE_APP}" if ultimo else
                               "Empezar" if self.actual == 0 else "Siguiente")

    def _siguiente(self):
        pagina = self.paginas[self.actual]
        falta = pagina.falta()
        if falta:
            poner_tipo(self.falta, "aviso", falta)
            return
        if isinstance(pagina, PaginaCorreo) and not pagina.probada:
            r = QMessageBox.question(
                self, "Sin probar", "Todavía no has probado la conexión del correo. Si el email o la contraseña "
                "están mal, las facturas no saldrán.\n\n¿Seguir sin probar? (Se puede probar luego en Ajustes.)",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        resultado = pagina.guardar()
        if isinstance(pagina, PaginaCorreo) and resultado is False:
            QMessageBox.warning(self, "Contraseña", "Este ordenador no tiene un llavero disponible, así que la "
                                "contraseña se ha guardado en la base de datos de la app (protegida solo por tu "
                                "usuario del ordenador).")
        if self.actual == len(self.paginas) - 1:
            self.datos.guardar_ajuste("asistente_completado", True)
            self.accept()
            return
        self._ir(self.actual + 1)

    def closeEvent(self, evento):
        if self.result() != QDialog.Accepted and not self.datos.configurada():
            r = QMessageBox.question(self, "Salir", "La configuración no está terminada. Lo que has rellenado se "
                                     "guarda, y la próxima vez seguirás por aquí.\n\n¿Salir?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                evento.ignore()
                return
        super().closeEvent(evento)
