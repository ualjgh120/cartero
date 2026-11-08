# -*- coding: utf-8 -*-
"""dialogos.py — Ficha de cliente, asignar una factura a mano y confirmar un envío."""

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout,
)

from interfaz.estilo import caja, poner_tipo
from nucleo.emparejar import emails_de, normalizar, normalizar_nif


def _botonera(dialogo, texto_ok: str = "Guardar") -> tuple[QHBoxLayout, QPushButton]:
    fila = QHBoxLayout()
    fila.addStretch()
    cancelar = QPushButton("Cancelar")
    cancelar.clicked.connect(dialogo.reject)
    ok = QPushButton(texto_ok)
    ok.setObjectName("principal")
    ok.setDefault(True)
    fila.addWidget(cancelar)
    fila.addWidget(ok)
    return fila, ok


class DialogoCliente(QDialog):
    def __init__(self, cliente: dict | None = None, parent=None):
        super().__init__(parent)
        self.cliente = dict(cliente or {})
        self.setWindowTitle("Editar cliente" if cliente else "Nuevo cliente")
        self.setMinimumWidth(500)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(22, 20, 22, 18)
        f = QFormLayout()
        f.setSpacing(10)
        self.campos = {}
        for clave, etiqueta, ejemplo in (
                ("nombre", "Nombre o razón social *", "Como sale en las facturas"),
                ("email", "Email", "Varios separados por ;"),
                ("telefono", "Teléfono", "Para los que no tienen email"),
                ("nif", "NIF / CIF", "Si sale en sus facturas, es la forma más segura de reconocerlo"),
                ("nota", "Nota", "Persona de contacto, etc.")):
            campo = QLineEdit(self.cliente.get(clave, ""))
            campo.setPlaceholderText(ejemplo)
            campo.textChanged.connect(self._comprobar)
            f.addRow(etiqueta, campo)
            self.campos[clave] = campo
        raiz.addLayout(f)
        if self.cliente.get("alias"):
            alias = QLabel("También se reconoce como: " + ", ".join(f"«{a}»" for a in self.cliente["alias"]))
            alias.setObjectName("suave")
            alias.setWordWrap(True)
            raiz.addWidget(alias)
            self.borrar_alias = QCheckBox("Olvidar estos nombres aprendidos")
            raiz.addWidget(self.borrar_alias)
        else:
            self.borrar_alias = None
        self.aviso = caja("", "aviso")
        self.aviso.hide()
        raiz.addWidget(self.aviso)
        fila, self.ok = _botonera(self)
        self.ok.clicked.connect(self._guardar)
        raiz.addLayout(fila)
        self._comprobar()

    def _comprobar(self):
        nombre = self.campos["nombre"].text().strip()
        texto_email = self.campos["email"].text().strip()
        malos = [e for e in texto_email.replace(",", ";").split(";") if e.strip() and "@" not in e]
        aviso = ""
        if malos:
            aviso = f"Esto no parece un email: {malos[0].strip()}"
        elif texto_email and not emails_de(texto_email):
            aviso = "El email no es válido."
        poner_tipo(self.aviso, "aviso", aviso)
        self.ok.setEnabled(bool(nombre) and not aviso)

    def _guardar(self):
        for clave, campo in self.campos.items():
            self.cliente[clave] = campo.text().strip()
        self.cliente["email"] = "; ".join(emails_de(self.cliente["email"]))
        self.cliente["nif"] = normalizar_nif(self.cliente["nif"])
        if self.borrar_alias and self.borrar_alias.isChecked():
            self.cliente["alias"] = []
        self.accept()


class DialogoAsignar(QDialog):
    """Elegir a mano de quién es una factura. Arriba salen los candidatos que vio la app."""

    def __init__(self, fila, clientes: list[dict], parent=None):
        super().__init__(parent)
        self.fila = fila
        self.clientes = clientes
        self.por_id = {c["id"]: c for c in clientes}
        self.elegido: dict | None = None
        self.nuevo = False
        self.setWindowTitle("Asignar cliente")
        self.resize(560, 560)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(22, 20, 22, 18)
        titulo = QLabel(f"¿De quién es <b>{escape(fila.archivo)}</b>?")
        titulo.setObjectName("tituloPanel")
        raiz.addWidget(titulo)
        pistas = []
        if fila.nombre_leido:
            pistas.append(f"En el PDF pone: «{escape(fila.nombre_leido)}»")
        if fila.nifs:
            pistas.append("NIF que salen en el PDF: " + ", ".join(sorted(fila.nifs)))
        if fila.detalle:
            pistas.append(escape(fila.detalle))
        if pistas:
            raiz.addWidget(caja("<br>".join(pistas)))
        abrir = QPushButton("Abrir el PDF para mirarlo")
        abrir.setObjectName("plano")
        abrir.clicked.connect(lambda: abrir_archivo(fila.ruta))
        raiz.addWidget(abrir, alignment=Qt.AlignLeft)

        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar cliente…")
        self.buscar.textChanged.connect(self._filtrar)
        raiz.addWidget(self.buscar)
        self.lista = QListWidget()
        self.lista.itemDoubleClicked.connect(lambda _: self._aceptar())
        self.lista.currentItemChanged.connect(lambda *_: self._pintar_recordar())
        raiz.addWidget(self.lista, 1)

        self.recordar = QCheckBox()
        self.recordar.setChecked(True)
        raiz.addWidget(self.recordar)

        fila_botones, self.ok = _botonera(self, "Asignar")
        nuevo = QPushButton("Cliente nuevo…")
        nuevo.clicked.connect(self._nuevo)
        fila_botones.insertWidget(0, nuevo)
        self.ok.clicked.connect(self._aceptar)
        raiz.addLayout(fila_botones)
        self._filtrar("")

    def _filtrar(self, texto):
        self.lista.clear()
        buscado = normalizar(texto)
        from nucleo.analisis import PISTA_MINIMA
        sugeridos = [i for i, p, _ in self.fila.candidatos if p >= PISTA_MINIMA] if not texto else []
        orden = [self.por_id[i] for i in sugeridos if i in self.por_id] + \
                [c for c in self.clientes if c["id"] not in sugeridos]
        for c in orden:
            if buscado and buscado not in normalizar(c["nombre"]) and texto.lower() not in c["email"].lower():
                continue
            sugerido = c["id"] in sugeridos
            texto_item = ("★ " if sugerido else "") + c["nombre"] + (f"  —  {c['email']}" if c["email"] else "  —  sin email")
            item = QListWidgetItem(texto_item)
            item.setData(Qt.UserRole, c["id"])
            self.lista.addItem(item)
        if self.lista.count():
            self.lista.setCurrentRow(0)
        self._pintar_recordar()

    def que_aprender(self, cliente: dict | None) -> tuple[str, str] | None:
        """Qué se guardará para reconocer solo la próxima factura de este cliente."""
        if not cliente:
            return None
        if len(self.fila.nifs) == 1 and not cliente.get("nif"):
            return "nif", next(iter(self.fila.nifs))
        if self.fila.nombre_leido and normalizar(self.fila.nombre_leido) != normalizar(cliente["nombre"]):
            return "alias", self.fila.nombre_leido
        return None

    def _cliente_actual(self):
        item = self.lista.currentItem()
        return self.por_id.get(item.data(Qt.UserRole)) if item else None

    def _pintar_recordar(self):
        aprender = self.que_aprender(self._cliente_actual())
        self.recordar.setVisible(bool(aprender))
        if aprender:
            tipo, valor = aprender
            self.recordar.setText(f"Guardar el NIF {valor} en su ficha, para reconocerlo solo la próxima vez"
                                  if tipo == "nif" else f"Recordar que «{valor}» es este cliente")
        self.ok.setEnabled(self.lista.currentItem() is not None)

    def _nuevo(self):
        d = DialogoCliente({"nombre": self.fila.nombre_leido,
                            "nif": next(iter(self.fila.nifs)) if len(self.fila.nifs) == 1 else ""}, self)
        if d.exec():
            self.elegido, self.nuevo = d.cliente, True
            self.accept()

    def _aceptar(self):
        self.elegido = self._cliente_actual()
        if self.elegido:
            self.accept()

    def aprendizaje(self):
        return self.que_aprender(self.elegido) if self.recordar.isVisible() and self.recordar.isChecked() else None


class DialogoConfirmar(QDialog):
    def __init__(self, filas, remitente: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirmar envío")
        self.setMinimumWidth(560)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(22, 20, 22, 18)
        n = len(filas)
        titulo = QLabel(f"Se van a enviar <b>{n} factura{'s' if n != 1 else ''}</b> desde {escape(remitente)}.")
        titulo.setObjectName("tituloPanel")
        titulo.setWordWrap(True)
        raiz.addWidget(titulo)
        lista = QListWidget()
        for f in filas:
            lista.addItem(f"{f.archivo}  →  {f.cliente}  <{f.email}>")
        raiz.addWidget(lista, 1)
        raiz.addWidget(caja("Cada cliente recibe solo su PDF. Esto no se puede deshacer.", "aviso"))
        fila, ok = _botonera(self, f"Enviar {n}")
        ok.clicked.connect(self.accept)
        raiz.addLayout(fila)


def abrir_archivo(ruta: str) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))
