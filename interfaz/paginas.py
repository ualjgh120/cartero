# -*- coding: utf-8 -*-
"""
paginas.py — Las páginas de configuración: empresa, correo, mensaje,
facturas y clientes. Las usa el asistente de la primera vez y, las mismas,
la pestaña Ajustes.

Cada página sabe cargar() sus datos, decir si está completa (falta()) y
guardar() lo que el usuario ha escrito.
"""

import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from interfaz.estilo import caja, poner_tipo
from interfaz.trabajador import Tarea
from nucleo import analisis as A
from nucleo.config import NOMBRE_APP, carpeta_datos
from nucleo.correo import (
    HUECOS, OTRO, PROVEEDORES, adivinar_proveedor, explicar_error, guardar_clave, leer_clave, probar,
    proveedor_por_nombre, rellenar, valores_para,
)
from nucleo.datos import Datos
from nucleo.envio import ajustes_correo, ajustes_mensaje


class Pagina(QWidget):
    titulo = ""
    explicacion = ""
    cambiada = Signal()

    def __init__(self, datos: Datos, parent=None):
        super().__init__(parent)
        self.datos = datos
        self.raiz = QVBoxLayout(self)
        self.raiz.setContentsMargins(0, 0, 0, 0)
        self.raiz.setSpacing(12)
        if self.titulo:
            t = QLabel(self.titulo)
            t.setObjectName("tituloPaso")
            self.raiz.addWidget(t)
        if self.explicacion:
            e = QLabel(self.explicacion)
            e.setWordWrap(True)
            e.setObjectName("suave")
            self.raiz.addWidget(e)

    def cargar(self):
        pass

    def falta(self) -> str:
        """Lo que falta por rellenar, o '' si está todo."""
        return ""

    def guardar(self):
        pass


def _formulario() -> QFormLayout:
    f = QFormLayout()
    f.setSpacing(10)
    f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return f


# ====================================================================== bienvenida
class PaginaBienvenida(Pagina):
    titulo = f"Bienvenido a {NOMBRE_APP}"

    def __init__(self, datos, parent=None):
        super().__init__(datos, parent)
        texto = QLabel(
            f"{NOMBRE_APP} manda a cada cliente <b>su</b> factura en PDF por email. Lee cada PDF, averigua "
            "de qué cliente es y se la envía a él. Los que no tienen email los apunta para que los avises "
            "por teléfono, y lleva la cuenta de lo enviado para no repetir nunca un envío.<br><br>"
            "Antes de empezar te voy a pedir cinco cosas, en unos 3 minutos:"
            "<ol><li><b>Tu empresa</b>: nombre y logo</li>"
            "<li><b>Tu correo</b>: desde qué email se envían las facturas</li>"
            "<li><b>El mensaje</b>: qué texto recibe el cliente</li>"
            "<li><b>Tus facturas</b>: en qué carpeta las deja tu programa de facturación</li>"
            "<li><b>Tus clientes</b>: su email y teléfono (se pueden importar de un Excel o un Word)</li></ol>"
            "Todo se guarda solo en este ordenador y puedes cambiarlo luego en <b>Ajustes</b>.")
        texto.setWordWrap(True)
        texto.setTextFormat(Qt.RichText)
        self.raiz.addWidget(texto)
        self.raiz.addStretch()


# ====================================================================== empresa
class PaginaEmpresa(Pagina):
    titulo = "Tu empresa"
    explicacion = ("El nombre sale como remitente y en el texto del correo, y el logo en la firma. "
                   "Tu NIF y tu email sirven para que la app no los confunda con los del cliente.")

    def __init__(self, datos, parent=None):
        super().__init__(datos, parent)
        f = _formulario()
        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Ej.: Distribuciones Ejemplo, S.L.")
        self.nif = QLineEdit()
        self.nif.setPlaceholderText("Ej.: B04123456 (recomendado)")
        self.email = QLineEdit()
        self.email.setPlaceholderText("El email que sale en tus facturas (opcional)")
        self.telefono = QLineEdit()
        self.telefono.setPlaceholderText("Opcional")
        for campo in (self.nombre, self.nif, self.email, self.telefono):
            campo.textChanged.connect(self.cambiada)
        f.addRow("Nombre de la empresa *", self.nombre)
        f.addRow("NIF / CIF", self.nif)
        f.addRow("Email de la empresa", self.email)
        f.addRow("Teléfono", self.telefono)

        fila_logo = QHBoxLayout()
        self.vista_logo = QLabel()
        self.vista_logo.setFixedSize(170, 70)
        self.vista_logo.setAlignment(Qt.AlignCenter)
        self.vista_logo.setStyleSheet("border: 1px dashed #B5C0CA; border-radius: 8px; color: #7A8590; background: white;")
        elegir = QPushButton("Elegir logo…")
        elegir.clicked.connect(self._elegir_logo)
        quitar = QPushButton("Quitar")
        quitar.setObjectName("plano")
        quitar.clicked.connect(lambda: self._poner_logo(None))
        fila_logo.addWidget(self.vista_logo)
        fila_logo.addWidget(elegir)
        fila_logo.addWidget(quitar)
        fila_logo.addStretch()
        f.addRow("Logo", fila_logo)
        self.raiz.addLayout(f)
        self.raiz.addWidget(caja("El logo es opcional. Mejor un PNG con fondo transparente o blanco; "
                                 "se ve pequeño, al final del correo."))
        self.raiz.addStretch()
        self._logo = None

    def cargar(self):
        e = self.datos.empresa()
        self.nombre.setText(e.get("nombre", ""))
        self.nif.setText(e.get("nif", ""))
        self.email.setText(e.get("email", ""))
        self.telefono.setText(e.get("telefono", ""))
        self._poner_logo(e.get("logo"))

    def _elegir_logo(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Elige el logo", "", "Imágenes (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
        if not ruta:
            return
        # se copia a la carpeta de la app para que no se pierda si mueves el original
        destino = carpeta_datos() / f"logo{Path(ruta).suffix.lower()}"
        if Path(ruta).suffix.lower() in (".webp", ".bmp"):  # los correos no siempre los muestran: a PNG
            from PIL import Image
            destino = carpeta_datos() / "logo.png"
            Image.open(ruta).save(destino)
        else:
            shutil.copyfile(ruta, destino)
        self._poner_logo(str(destino))

    def _poner_logo(self, ruta):
        self._logo = ruta if ruta and Path(ruta).exists() else None
        if self._logo:
            self.vista_logo.setPixmap(QPixmap(self._logo).scaled(164, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.vista_logo.setPixmap(QPixmap())
            self.vista_logo.setText("Sin logo")
        self.cambiada.emit()

    def falta(self):
        return "" if self.nombre.text().strip() else "Escribe el nombre de tu empresa."

    def guardar(self):
        from nucleo.emparejar import normalizar_nif
        self.datos.guardar_ajuste("empresa", {
            **self.datos.empresa(),
            "nombre": self.nombre.text().strip(), "nif": normalizar_nif(self.nif.text()),
            "email": self.email.text().strip(), "telefono": self.telefono.text().strip(), "logo": self._logo,
        })


# ====================================================================== correo
class PaginaCorreo(Pagina):
    titulo = "Tu correo"
    explicacion = "Desde qué email salen las facturas. Elige quién te lleva el correo y la app rellena el resto."

    def __init__(self, datos, parent=None):
        super().__init__(datos, parent)
        f = _formulario()
        self.proveedor = QComboBox()
        self.proveedor.addItems([p.nombre for p in PROVEEDORES])
        self.proveedor.currentTextChanged.connect(self._cambio_proveedor)
        self.email = QLineEdit()
        self.email.setPlaceholderText("facturas@tuempresa.es")
        self.email.editingFinished.connect(self._adivinar)
        fila_clave = QHBoxLayout()
        self.clave = QLineEdit()
        self.clave.setEchoMode(QLineEdit.Password)
        self.clave.setPlaceholderText("Contraseña de aplicación")
        ver = QPushButton("Ver")
        ver.setObjectName("plano")
        ver.setCheckable(True)
        ver.toggled.connect(lambda v: self.clave.setEchoMode(QLineEdit.Normal if v else QLineEdit.Password))
        fila_clave.addWidget(self.clave)
        fila_clave.addWidget(ver)
        f.addRow("¿Quién te lleva el correo?", self.proveedor)
        f.addRow("Email remitente *", self.email)
        f.addRow("Contraseña *", fila_clave)
        self.raiz.addLayout(f)

        self.ayuda = caja("")
        self.raiz.addWidget(self.ayuda)
        self.boton_enlace = QPushButton("Abrir la página para crear la contraseña")
        self.boton_enlace.setObjectName("plano")
        self.boton_enlace.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(proveedor_por_nombre(
            self.proveedor.currentText()).enlace)))
        self.raiz.addWidget(self.boton_enlace, alignment=Qt.AlignLeft)

        # servidor: a la vista solo con "Otro", o si se pide
        self.ver_avanzado = QCheckBox("Ver datos del servidor y opciones avanzadas")
        self.ver_avanzado.toggled.connect(self._mostrar_avanzado)
        self.raiz.addWidget(self.ver_avanzado)
        self.avanzado = QWidget()
        fa = _formulario()
        fa.setContentsMargins(0, 0, 0, 0)
        self.servidor = QLineEdit()
        self.servidor.setPlaceholderText("smtp.tudominio.es")
        self.puerto = QSpinBox()
        self.puerto.setRange(1, 65535)
        self.seguridad = QComboBox()
        self.seguridad.addItem("STARTTLS (normal con el 587)", "starttls")
        self.seguridad.addItem("SSL (normal con el 465)", "ssl")
        self.seguridad.addItem("Ninguna (no recomendado)", "ninguna")
        self.usuario = QLineEdit()
        self.usuario.setPlaceholderText("Vacío = el mismo email")
        self.nombre_remitente = QLineEdit()
        self.nombre_remitente.setPlaceholderText("Vacío = el nombre de tu empresa")
        self.responder_a = QLineEdit()
        self.responder_a.setPlaceholderText("Si las respuestas deben ir a otro email")
        self.copia_oculta = QLineEdit()
        self.copia_oculta.setPlaceholderText("Ej.: tu propio email, para tener copia de todo")
        fa.addRow("Servidor de salida (SMTP)", self.servidor)
        fa.addRow("Puerto", self.puerto)
        fa.addRow("Seguridad", self.seguridad)
        fa.addRow("Usuario", self.usuario)
        fa.addRow("Nombre que ve el cliente", self.nombre_remitente)
        fa.addRow("Responder a", self.responder_a)
        fa.addRow("Copia oculta (CCO)", self.copia_oculta)
        self.avanzado.setLayout(fa)
        self.raiz.addWidget(self.avanzado)

        fila_prueba = QHBoxLayout()
        self.boton_probar = QPushButton("Probar conexión")
        self.boton_probar.setObjectName("principal")
        self.boton_probar.clicked.connect(self._probar)
        fila_prueba.addWidget(self.boton_probar)
        fila_prueba.addStretch()
        self.raiz.addLayout(fila_prueba)
        self.resultado = caja("", "bien")
        self.resultado.hide()
        self.raiz.addWidget(self.resultado)
        self.raiz.addStretch()
        self.probada = False
        self._tarea = None
        for campo in (self.email, self.clave, self.servidor, self.usuario):
            campo.textChanged.connect(self._sin_probar)
        self.puerto.valueChanged.connect(self._sin_probar)
        self.seguridad.currentIndexChanged.connect(self._sin_probar)

    def cargar(self):
        a = ajustes_correo(self.datos)
        self.proveedor.blockSignals(True)
        self.proveedor.setCurrentText(a["proveedor"])
        self.proveedor.blockSignals(False)
        self.email.setText(a["email"])
        self.servidor.setText(a["servidor"])
        self.puerto.setValue(int(a["puerto"]))
        self.seguridad.setCurrentIndex(max(0, self.seguridad.findData(a["seguridad"])))
        self.usuario.setText(a["usuario"])
        self.nombre_remitente.setText(a["nombre_remitente"])
        self.responder_a.setText(a["responder_a"])
        self.copia_oculta.setText(a["copia_oculta"])
        self.clave.setText(leer_clave(self.datos, a) if a["email"] else "")
        self._pintar_ayuda()
        self.ver_avanzado.setChecked(a["proveedor"] == OTRO.nombre)
        self._mostrar_avanzado(self.ver_avanzado.isChecked())
        self.probada = bool(self.datos.ajuste("correo_probado", False))
        self.resultado.hide()

    def _adivinar(self):
        p = adivinar_proveedor(self.email.text())
        if p and p.nombre != self.proveedor.currentText():
            self.proveedor.setCurrentText(p.nombre)

    def _cambio_proveedor(self, nombre):
        p = proveedor_por_nombre(nombre)
        if p is not OTRO:
            self.servidor.setText(p.servidor)
            self.puerto.setValue(p.puerto)
            self.seguridad.setCurrentIndex(self.seguridad.findData(p.seguridad))
        if p is OTRO:
            self.ver_avanzado.setChecked(True)
        self._pintar_ayuda()

    def _pintar_ayuda(self):
        p = proveedor_por_nombre(self.proveedor.currentText())
        self.ayuda.setText(p.ayuda)
        self.boton_enlace.setVisible(bool(p.enlace))
        self.clave.setPlaceholderText("Contraseña de aplicación" if p.enlace else "Contraseña del buzón")

    def _mostrar_avanzado(self, ver):
        self.avanzado.setVisible(ver)

    def _sin_probar(self):
        self.probada = False
        self.cambiada.emit()

    def _ajustes(self) -> dict:
        return {"proveedor": self.proveedor.currentText(), "email": self.email.text().strip(),
                "servidor": self.servidor.text().strip(), "puerto": self.puerto.value(),
                "seguridad": self.seguridad.currentData(), "usuario": self.usuario.text().strip(),
                "nombre_remitente": self.nombre_remitente.text().strip(),
                "responder_a": self.responder_a.text().strip(), "copia_oculta": self.copia_oculta.text().strip()}

    def _probar(self):
        if self.falta():
            poner_tipo(self.resultado, "mal", self.falta())
            return
        self.boton_probar.setEnabled(False)
        poner_tipo(self.resultado, "ayuda", "Conectando con el servidor…")
        ajustes = self._ajustes()
        self._tarea = Tarea(probar, ajustes, self.clave.text().replace(" ", "") if "gmail" in ajustes["servidor"]
                            else self.clave.text(), con_avance=False)
        self._tarea.terminada.connect(self._prueba_bien)
        self._tarea.fallo.connect(lambda e: self._prueba_mal(e, ajustes))
        self._tarea.start()

    def _prueba_bien(self, _):
        self.boton_probar.setEnabled(True)
        self.probada = True
        poner_tipo(self.resultado, "bien", "✓ Conexión correcta: el servidor acepta tu email y tu contraseña.")
        self.cambiada.emit()

    def _prueba_mal(self, e, ajustes):
        self.boton_probar.setEnabled(True)
        self.probada = False
        poner_tipo(self.resultado, "mal", "✗ " + explicar_error(e, ajustes))
        self.cambiada.emit()

    def falta(self):
        if "@" not in self.email.text():
            return "Escribe el email desde el que se envían las facturas."
        if not self.clave.text():
            return "Escribe la contraseña."
        if not self.servidor.text().strip():
            return "Falta el servidor de salida (SMTP): marca «Ver datos del servidor»."
        return ""

    def guardar(self):
        ajustes = self._ajustes()
        self.datos.guardar_ajuste("correo", ajustes)
        clave = self.clave.text()
        if "gmail" in ajustes["servidor"]:
            clave = clave.replace(" ", "")  # Google la muestra en grupos de 4 con espacios
        en_llavero = guardar_clave(self.datos, ajustes, clave)
        self.datos.guardar_ajuste("correo_probado", self.probada)
        return en_llavero


# ====================================================================== mensaje
class PaginaMensaje(Pagina):
    titulo = "El mensaje"
    explicacion = "Lo que recibe cada cliente. Lo que va entre llaves se cambia solo en cada correo."

    def __init__(self, datos, parent=None):
        super().__init__(datos, parent)
        f = _formulario()
        self.asunto = QLineEdit()
        self.cuerpo = QPlainTextEdit()
        self.cuerpo.setMinimumHeight(150)
        f.addRow("Asunto", self.asunto)
        f.addRow("Texto", self.cuerpo)
        self.raiz.addLayout(f)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("Insertar:"))
        for hueco, que in HUECOS.items():
            b = QPushButton(hueco)
            b.setToolTip(que)
            b.clicked.connect(lambda _=False, h=hueco: self._insertar(h))
            fila.addWidget(b)
        fila.addStretch()
        self.raiz.addLayout(fila)
        self.firma_logo = QCheckBox("Poner el logo de la empresa al final del correo")
        self.raiz.addWidget(self.firma_logo)

        titulo = QLabel("Así lo verá el cliente")
        titulo.setObjectName("tituloPanel")
        self.raiz.addWidget(titulo)
        self.vista = QLabel()
        self.vista.setObjectName("panel")
        self.vista.setWordWrap(True)
        self.vista.setTextFormat(Qt.RichText)
        self.vista.setStyleSheet("padding: 12px;")
        self.raiz.addWidget(self.vista)
        self.raiz.addStretch()
        self.asunto.textChanged.connect(self._previa)
        self.cuerpo.textChanged.connect(self._previa)
        self.firma_logo.toggled.connect(self._previa)

    def cargar(self):
        m = ajustes_mensaje(self.datos)
        self.asunto.setText(m["asunto"])
        self.cuerpo.setPlainText(m["cuerpo"])
        self.firma_logo.setChecked(bool(m["firma_logo"]))
        self._previa()

    def _insertar(self, hueco):
        destino = self.asunto if self.asunto.hasFocus() else self.cuerpo
        destino.insert(hueco) if destino is self.asunto else self.cuerpo.insertPlainText(hueco)
        destino.setFocus()

    def _previa(self):
        from html import escape
        empresa = self.datos.empresa()
        v = valores_para("Agrícola Ejemplo, S.L.", "26-1077.pdf", empresa)
        logo = empresa.get("logo")
        firma = (f"<br><img src='{QUrl.fromLocalFile(logo).toString()}' height='40'>" if self.firma_logo.isChecked() and logo else "")
        remitente = (ajustes_correo(self.datos).get("nombre_remitente") or empresa.get("nombre", "")) or "Tu empresa"
        self.vista.setText(
            f"<span style='color:#66717C'>De:</span> {escape(remitente)}<br>"
            f"<span style='color:#66717C'>Asunto:</span> <b>{escape(rellenar(self.asunto.text(), v))}</b><br>"
            f"<span style='color:#66717C'>Adjunto:</span> 📎 26-1077.pdf<hr>"
            + escape(rellenar(self.cuerpo.toPlainText(), v)).replace("\n", "<br>") + firma)
        self.cambiada.emit()

    def falta(self):
        if not self.asunto.text().strip():
            return "Escribe el asunto del correo."
        if not self.cuerpo.toPlainText().strip():
            return "Escribe el texto del correo."
        return ""

    def guardar(self):
        self.datos.guardar_ajuste("mensaje", {"asunto": self.asunto.text().strip(),
                                              "cuerpo": self.cuerpo.toPlainText().strip(),
                                              "firma_logo": self.firma_logo.isChecked()})


# ====================================================================== facturas
PATRONES = ["FACTURAS {MES} {AA}", "{AAAA}/FACTURAS {MES} {AA}", "{Mes} {AAAA}", "{AAAA}/{MM}", "{AAAA}-{MM}"]


class PaginaFacturas(Pagina):
    titulo = "Tus facturas"
    explicacion = ("Dónde deja los PDF tu programa de facturación. Lo más rápido: pulsa "
                   "«Elegir la carpeta de un mes» y elige la de cualquier mes; la app deduce cómo se llaman las demás.")

    def __init__(self, datos, parent=None):
        super().__init__(datos, parent)
        boton_mes = QPushButton("Elegir la carpeta de un mes…")
        boton_mes.setObjectName("principal")
        boton_mes.clicked.connect(self._elegir_mes)
        self.raiz.addWidget(boton_mes, alignment=Qt.AlignLeft)
        self.deducido = caja("", "bien")
        self.deducido.hide()
        self.raiz.addWidget(self.deducido)

        f = _formulario()
        fila_base = QHBoxLayout()
        self.base = QLineEdit()
        self.base.setPlaceholderText("Carpeta donde están las facturas")
        elegir_base = QPushButton("Elegir…")
        elegir_base.clicked.connect(self._elegir_base)
        fila_base.addWidget(self.base)
        fila_base.addWidget(elegir_base)
        f.addRow("Carpeta de facturas", fila_base)

        self.misma = QRadioButton("Siempre en esa misma carpeta")
        self.por_mes = QRadioButton("Una carpeta para cada mes, dentro de esa")
        grupo = QButtonGroup(self)
        grupo.addButton(self.misma)
        grupo.addButton(self.por_mes)
        caja_modo = QVBoxLayout()
        caja_modo.addWidget(self.misma)
        caja_modo.addWidget(self.por_mes)
        f.addRow("¿Cómo están guardadas?", caja_modo)
        self.patron = QComboBox()
        self.patron.setEditable(True)
        self.patron.addItems(PATRONES)
        f.addRow("Nombre de la carpeta del mes", self.patron)
        self.raiz.addLayout(f)
        self.huecos = QLabel("Huecos: {MES} SEPTIEMBRE · {Mes} Septiembre · {mes} septiembre · {MM} 09 · "
                             "{AAAA} 2026 · {AA} 26 · con / se entra en una subcarpeta")
        self.huecos.setObjectName("suave")
        self.huecos.setWordWrap(True)
        self.raiz.addWidget(self.huecos)
        self.ejemplo = caja("")
        self.raiz.addWidget(self.ejemplo)

        self.ver_avanzado = QCheckBox("Opciones avanzadas")
        self.raiz.addWidget(self.ver_avanzado)
        self.avanzado = QWidget()
        fa = _formulario()
        fa.setContentsMargins(0, 0, 0, 0)
        self.ancla = QLineEdit()
        self.ancla.setPlaceholderText("Vacío (recomendado). Para EjidoSoft: E-MAIL:")
        self.umbral = QSpinBox()
        self.umbral.setRange(50, 100)
        self.umbral.setSuffix(" %")
        fa.addRow("Texto justo antes del nombre del cliente", self.ancla)
        fa.addRow("Parecido mínimo para dar por bueno un cliente", self.umbral)
        self.avanzado.setLayout(fa)
        self.raiz.addWidget(self.avanzado)
        self.raiz.addWidget(caja_ayuda_avanzado := caja(
            "La app busca en cada PDF el NIF, el email o el nombre de tus clientes, esté donde esté. El «texto "
            "antes del nombre» solo hace falta si tu programa pone el cliente siempre debajo de una misma línea "
            "y la búsqueda normal falla."))
        caja_ayuda_avanzado.setVisible(False)
        self.ver_avanzado.toggled.connect(self.avanzado.setVisible)
        self.ver_avanzado.toggled.connect(caja_ayuda_avanzado.setVisible)
        self.avanzado.hide()
        self.raiz.addStretch()

        self.base.textChanged.connect(self._ejemplo)
        self.patron.currentTextChanged.connect(self._ejemplo)
        self.misma.toggled.connect(self._ejemplo)

    def cargar(self):
        a = A.ajustes_facturas(self.datos)
        self.base.setText(a["carpeta_base"])
        (self.por_mes if a["patron_mes"] else self.misma).setChecked(True)
        self.patron.setCurrentText(a["patron_mes"] or PATRONES[0])
        self.ancla.setText(a["ancla"])
        self.umbral.setValue(int(round(float(a["umbral"]) * 100)))
        self._ejemplo()

    def _elegir_mes(self):
        ruta = QFileDialog.getExistingDirectory(self, "Elige la carpeta de las facturas de un mes cualquiera")
        if not ruta:
            return
        deducido = A.inferir_patron(ruta)
        if deducido:
            base, patron = deducido
            self.base.setText(base)
            self.por_mes.setChecked(True)
            self.patron.setCurrentText(patron)
            poner_tipo(self.deducido, "bien", f"✓ Entendido: las carpetas de cada mes se llaman «{patron}» "
                                              f"dentro de {base}. Mira abajo cómo sería la de este mes.")
        else:
            self.base.setText(ruta)
            self.misma.setChecked(True)
            poner_tipo(self.deducido, "aviso", "El nombre de esa carpeta no lleva mes ni año, así que entiendo "
                                               "que las facturas están siempre ahí. Si no es así, cámbialo abajo.")

    def _elegir_base(self):
        ruta = QFileDialog.getExistingDirectory(self, "Carpeta de facturas", self.base.text())
        if ruta:
            self.base.setText(ruta)

    def _patron(self) -> str:
        return self.patron.currentText().strip() if self.por_mes.isChecked() else ""

    def _ejemplo(self):
        self.patron.setEnabled(self.por_mes.isChecked())
        self.huecos.setVisible(self.por_mes.isChecked())
        if not self.base.text().strip():
            self.ejemplo.hide()
            return
        este = A.carpeta_del_mes(self.base.text().strip(), self._patron())
        pasado = A.carpeta_del_mes(self.base.text().strip(), self._patron(), A.mes_pasado())
        lineas = []
        for nombre, ruta in (("Este mes", este), ("Mes pasado", pasado)):
            existe = Path(ruta).is_dir()
            n = len(A.pdfs_de(ruta)) if existe else 0
            lineas.append(f"<b>{nombre}:</b> {ruta}<br>&nbsp;&nbsp;"
                          + (f"✓ existe, con {n} PDF" if existe else "✗ esa carpeta no existe (todavía)"))
        poner_tipo(self.ejemplo, "ayuda", "<br>".join(lineas if self.por_mes.isChecked() else lineas[:1]))
        self.cambiada.emit()

    def falta(self):
        if not self.base.text().strip():
            return "Elige la carpeta donde están las facturas."
        return ""

    def guardar(self):
        self.datos.guardar_ajuste("facturas", {"carpeta_base": self.base.text().strip(), "patron_mes": self._patron(),
                                               "ancla": self.ancla.text().strip(), "umbral": self.umbral.value() / 100})


# ====================================================================== clientes
class PaginaClientes(Pagina):
    titulo = "Tus clientes"
    explicacion = ("Para cada cliente, su email (y su teléfono si no tiene email). Si ya los tienes en un Excel, "
                   "un CSV o una tabla de Word, impórtalos; la app reconoce las columnas sola.")

    def __init__(self, datos, parent=None):
        super().__init__(datos, parent)
        fila = QHBoxLayout()
        importar = QPushButton("Importar de Excel, CSV o Word…")
        importar.setObjectName("principal")
        importar.clicked.connect(self._importar)
        fila.addWidget(importar)
        fila.addStretch()
        self.raiz.addLayout(fila)
        self.estado = caja("")
        self.raiz.addWidget(self.estado)
        self.tabla = QTableWidget(0, 3)
        self.tabla.setHorizontalHeaderLabels(["Cliente", "Email", "Teléfono"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.verticalHeader().hide()
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setColumnWidth(0, 230)
        self.tabla.setColumnWidth(1, 220)
        self.raiz.addWidget(self.tabla, 1)
        self.raiz.addWidget(caja("También puedes saltarte este paso y añadirlos luego, uno a uno, en la pestaña "
                                 "Clientes. Y cuando una factura no encuentre cliente, se lo asignas a mano y la app "
                                 "lo recuerda."))

    def cargar(self):
        clientes = self.datos.clientes()
        self.tabla.setRowCount(len(clientes))
        for i, c in enumerate(clientes):
            for j, campo in enumerate(("nombre", "email", "telefono")):
                self.tabla.setItem(i, j, QTableWidgetItem(c[campo]))
        sin_email = sum(1 for c in clientes if not c["email"])
        if clientes:
            poner_tipo(self.estado, "bien", f"✓ {len(clientes)} clientes en el directorio"
                                            + (f", {sin_email} sin email (se avisarán por teléfono)." if sin_email else "."))
        else:
            poner_tipo(self.estado, "ayuda", "Todavía no hay clientes.")

    def _importar(self):
        from nucleo.importar import leer_clientes
        ruta, _ = QFileDialog.getOpenFileName(self, "Lista de clientes", "",
                                              "Excel, CSV o Word (*.xlsx *.xlsm *.csv *.txt *.docx)")
        if not ruta:
            return
        try:
            nuevos = leer_clientes(ruta)
        except Exception as e:  # noqa: BLE001
            poner_tipo(self.estado, "mal", f"No se ha podido leer ese archivo: {e}")
            return
        if not nuevos:
            poner_tipo(self.estado, "mal", "No he encontrado clientes en ese archivo. Comprueba que tenga una "
                                           "columna con el nombre del cliente y otra con el email.")
            return
        anadidos, completados = self.datos.importar_clientes(nuevos)
        self.cargar()
        self.estado.setText(self.estado.text() + f"<br>Importados de {Path(ruta).name}: {anadidos} nuevos"
                            + (f", {completados} completados" if completados else "") + ".")
        self.cambiada.emit()


# ====================================================================== listo
class PaginaListo(Pagina):
    titulo = "¡Listo!"

    def __init__(self, datos, parent=None):
        super().__init__(datos, parent)
        self.resumen = QLabel()
        self.resumen.setWordWrap(True)
        self.resumen.setTextFormat(Qt.RichText)
        self.raiz.addWidget(self.resumen)
        fila = QHBoxLayout()
        self.boton_prueba = QPushButton("Enviarme un correo de prueba")
        self.boton_prueba.clicked.connect(self._prueba)
        fila.addWidget(self.boton_prueba)
        fila.addStretch()
        self.raiz.addLayout(fila)
        self.resultado = caja("", "bien")
        self.resultado.hide()
        self.raiz.addWidget(self.resultado)
        self.raiz.addStretch()
        self._tarea = None

    def cargar(self):
        e, c = self.datos.empresa(), ajustes_correo(self.datos)
        f = A.ajustes_facturas(self.datos)
        n = len(self.datos.clientes())
        self.resumen.setText(
            f"<b>{e.get('nombre', '')}</b> enviará las facturas desde <b>{c['email']}</b>.<br>"
            f"Facturas en: {A.carpeta_del_mes(f['carpeta_base'], f['patron_mes'])}<br>"
            f"Clientes: {n}<br><br>"
            "Cada mes: abre la app, pulsa <b>Mes pasado</b> (o <b>Este mes</b>), luego <b>Buscar facturas</b>, "
            "revisa los colores y pulsa <b>Enviar todas las listas</b>. Nada se envía sin que lo confirmes.<br><br>"
            f"Te recomiendo mandarte un correo de prueba a <b>{c['email']}</b> para ver cómo le llega al cliente.")

    def _prueba(self):
        from nucleo.envio import enviar_prueba
        para = ajustes_correo(self.datos)["email"]
        self.boton_prueba.setEnabled(False)
        poner_tipo(self.resultado, "ayuda", "Enviando…")
        self._tarea = Tarea(enviar_prueba, self.datos, para, con_avance=False)
        self._tarea.terminada.connect(lambda _: (self.boton_prueba.setEnabled(True), poner_tipo(
            self.resultado, "bien", f"✓ Enviado a {para}. Míralo en tu bandeja de entrada (o en spam).")))
        self._tarea.fallo.connect(lambda e: (self.boton_prueba.setEnabled(True), poner_tipo(
            self.resultado, "mal", "✗ " + explicar_error(e, ajustes_correo(self.datos)))))
        self._tarea.start()
