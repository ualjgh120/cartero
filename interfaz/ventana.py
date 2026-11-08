# -*- coding: utf-8 -*-
"""
ventana.py — La ventana principal, con cinco pestañas:

  Enviar facturas   elegir la carpeta del mes, buscar, revisar colores, enviar
  Por teléfono      clientes sin email: llamar y marcar como avisados
  Clientes          el directorio: añadir, editar, importar, exportar
  Historial         todo lo enviado y avisado
  Ajustes           lo mismo que el asistente, para cambiarlo
"""

from datetime import date
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from interfaz.dialogos import DialogoAsignar, DialogoCliente, DialogoConfirmar, abrir_archivo
from interfaz.estilo import COLOR_ESTADO, LEYENDA, caja
from interfaz.paginas import PaginaCorreo, PaginaEmpresa, PaginaFacturas, PaginaMensaje
from interfaz.trabajador import Tarea
from nucleo import analisis as A
from nucleo.config import NOMBRE_APP, VERSION, carpeta_datos
from nucleo.correo import leer_clave
from nucleo.datos import AVISADO, ENVIADO, ERROR, Datos
from nucleo.emparejar import normalizar
from nucleo.envio import ajustes_correo, enviar_filas, marcar_avisada

FINALES = (A.YA_ENVIADA, A.YA_AVISADA, A.ENVIADA, A.AVISADA)


def tabla(columnas: list[str], anchos: list[int]) -> QTableWidget:
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.verticalHeader().hide()
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.ExtendedSelection)
    t.setWordWrap(False)
    t.setShowGrid(False)
    for i, ancho in enumerate(anchos):
        t.setColumnWidth(i, ancho)
    t.horizontalHeader().setStretchLastSection(True)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    return t


def celda(texto, fondo: str | None = None, color: str | None = None, consejo: str = "") -> QTableWidgetItem:
    item = QTableWidgetItem(str(texto or ""))
    if fondo:
        item.setBackground(QColor(fondo))
    if color:
        item.setForeground(QColor(color))
    if consejo:
        item.setToolTip(consejo)
    return item


def filas_elegidas(t: QTableWidget) -> list[int]:
    return sorted({i.row() for i in t.selectedIndexes()})


class VentanaPrincipal(QMainWindow):
    def __init__(self, datos: Datos):
        super().__init__()
        self.datos = datos
        self.filas: list[A.Fila] = []
        self._tarea = None
        self.setWindowTitle(NOMBRE_APP)
        self.resize(1180, 760)

        fondo = QWidget()
        fondo.setObjectName("fondo")
        raiz = QVBoxLayout(fondo)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._cabecera())
        self.pestanas = QTabWidget()
        self.pestanas.setDocumentMode(True)
        self.pestanas.addTab(self._pestana_enviar(), "Enviar facturas")
        self.pestanas.addTab(self._pestana_telefono(), "Por teléfono")
        self.pestanas.addTab(self._pestana_clientes(), "Clientes")
        self.pestanas.addTab(self._pestana_historial(), "Historial")
        self.pestanas.addTab(self._pestana_ajustes(), "Ajustes")
        self.pestanas.currentChanged.connect(self._al_cambiar_pestana)
        contenedor = QVBoxLayout()
        contenedor.setContentsMargins(18, 10, 18, 14)
        contenedor.addWidget(self.pestanas)
        raiz.addLayout(contenedor, 1)
        self.setCentralWidget(fondo)

        self._pintar_cabecera()
        self._carpeta_por_defecto()
        self._pintar_clientes()

    # ================================================================ cabecera
    def _cabecera(self):
        caja_cab = QFrame()
        caja_cab.setObjectName("cabecera")
        fila = QHBoxLayout(caja_cab)
        fila.setContentsMargins(20, 12, 20, 12)
        self.logo = QLabel()
        fila.addWidget(self.logo)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        self.nombre_empresa = QLabel()
        self.nombre_empresa.setObjectName("nombreEmpresa")
        self.dato_empresa = QLabel()
        self.dato_empresa.setObjectName("suave")
        textos.addWidget(self.nombre_empresa)
        textos.addWidget(self.dato_empresa)
        fila.addLayout(textos)
        fila.addStretch()
        marca = QLabel(f"{NOMBRE_APP} {VERSION}")
        marca.setObjectName("suave")
        fila.addWidget(marca)
        return caja_cab

    def _pintar_cabecera(self):
        e = self.datos.empresa()
        logo = e.get("logo")
        if logo and Path(logo).exists():
            self.logo.setPixmap(QPixmap(logo).scaled(120, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.logo.show()
        else:
            self.logo.hide()
        self.nombre_empresa.setText(e.get("nombre", ""))
        correo = ajustes_correo(self.datos)
        self.dato_empresa.setText(f"Envía desde {correo['email']}" if correo["email"] else
                                  "⚠ Falta configurar el correo (pestaña Ajustes)")

    # ================================================================ enviar
    def _pestana_enviar(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 12, 0, 0)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Carpeta:"))
        self.carpeta = QLineEdit()
        self.carpeta.setPlaceholderText("Carpeta con los PDF de las facturas")
        self.carpeta.returnPressed.connect(self._buscar)
        fila.addWidget(self.carpeta, 1)
        for texto, accion in (("Elegir…", self._elegir_carpeta), ("Este mes", lambda: self._poner_mes(date.today())),
                              ("Mes pasado", lambda: self._poner_mes(A.mes_pasado()))):
            b = QPushButton(texto)
            b.clicked.connect(accion)
            fila.addWidget(b)
        self.boton_buscar = QPushButton("Buscar facturas")
        self.boton_buscar.setObjectName("principal")
        self.boton_buscar.clicked.connect(self._buscar)
        fila.addWidget(self.boton_buscar)
        v.addLayout(fila)

        leyenda = QHBoxLayout()
        for estado, que in LEYENDA:
            fondo, color = COLOR_ESTADO[estado]
            e = QLabel(estado)
            e.setObjectName("leyenda")
            e.setStyleSheet(f"background: {fondo}; color: {color};")
            e.setToolTip(que)
            leyenda.addWidget(e)
            q = QLabel(que)
            q.setObjectName("suave")
            leyenda.addWidget(q)
            leyenda.addSpacing(6)
        leyenda.addStretch()
        v.addLayout(leyenda)

        self.tabla_envio = tabla(["Archivo", "Cliente", "Email", "Estado", "Detalle"], [150, 260, 240, 110])
        self.tabla_envio.doubleClicked.connect(self._doble_clic_envio)
        self.tabla_envio.itemSelectionChanged.connect(self._pintar_botones)
        v.addWidget(self.tabla_envio, 1)
        self.vacio = caja("Elige la carpeta del mes y pulsa «Buscar facturas». La app leerá cada PDF y te dirá de "
                          "quién es. No se envía nada hasta que tú lo confirmes.")
        v.addWidget(self.vacio)

        botones = QHBoxLayout()
        self.boton_todas = QPushButton("Enviar todas las listas")
        self.boton_todas.setObjectName("principal")
        self.boton_todas.clicked.connect(lambda: self._enviar([f for f in self.filas if f.estado == A.OK]))
        self.boton_sel = QPushButton("Enviar seleccionadas")
        self.boton_sel.clicked.connect(self._enviar_seleccionadas)
        self.boton_asignar = QPushButton("Asignar cliente…")
        self.boton_asignar.clicked.connect(self._asignar)
        self.boton_pdf = QPushButton("Abrir PDF")
        self.boton_pdf.clicked.connect(lambda: [abrir_archivo(self.filas[i].ruta)
                                                for i in filas_elegidas(self.tabla_envio)[:5]])
        for b in (self.boton_todas, self.boton_sel, self.boton_asignar, self.boton_pdf):
            botones.addWidget(b)
        botones.addStretch()
        self.resumen = QLabel()
        self.resumen.setObjectName("suave")
        botones.addWidget(self.resumen)
        v.addLayout(botones)
        self.progreso = QProgressBar()
        self.progreso.setTextVisible(False)
        self.progreso.hide()
        v.addWidget(self.progreso)
        self.estado = QLabel()
        self.estado.setObjectName("suave")
        v.addWidget(self.estado)
        self._pintar_botones()
        return p

    def _carpeta_por_defecto(self):
        a = A.ajustes_facturas(self.datos)
        if not a["carpeta_base"]:
            return
        # en la primera quincena se suelen enviar las del mes anterior
        mes = A.mes_pasado() if a["patron_mes"] and date.today().day <= 15 else date.today()
        self._poner_mes(mes)

    def _poner_mes(self, dia: date):
        a = A.ajustes_facturas(self.datos)
        if not a["carpeta_base"]:
            QMessageBox.information(self, "Carpeta", "Primero di dónde están las facturas: Ajustes → Facturas.")
            return
        ruta = A.carpeta_del_mes(a["carpeta_base"], a["patron_mes"], dia)
        self.carpeta.setText(ruta)
        if not Path(ruta).is_dir():
            self.estado.setText(f"⚠ La carpeta de {A.MESES[dia.month - 1]} todavía no existe: {ruta}")
        else:
            self.estado.setText(f"{len(A.pdfs_de(ruta))} PDF en la carpeta de {A.MESES[dia.month - 1]}.")

    def _elegir_carpeta(self):
        ruta = QFileDialog.getExistingDirectory(self, "Carpeta de facturas", self.carpeta.text())
        if ruta:
            self.carpeta.setText(ruta)
            self._buscar()

    def _ocupado(self) -> bool:
        if self._tarea and self._tarea.isRunning():
            QMessageBox.information(self, "Un momento", "Espera a que termine lo que está haciendo.")
            return True
        return False

    def _buscar(self):
        if self._ocupado():
            return
        carpeta = self.carpeta.text().strip()
        if not carpeta or not Path(carpeta).is_dir():
            QMessageBox.warning(self, "Carpeta", "Esa carpeta no existe. Elige otra o comprueba que el servidor esté conectado.")
            return
        if not A.pdfs_de(carpeta):
            QMessageBox.information(self, "Sin facturas", "No hay archivos PDF en esa carpeta.")
            return
        if not self.datos.clientes():
            QMessageBox.information(self, "Sin clientes", "Aún no hay clientes en el directorio: la app no podrá "
                                    "saber de quién es cada factura. Añádelos o impórtalos en la pestaña Clientes.")
        self._empezar(A.analizar_carpeta, carpeta, self.datos, fin=self._busqueda_hecha, texto="Leyendo")

    def _empezar(self, funcion, *args, fin, texto):
        self.boton_buscar.setEnabled(False)
        self.boton_todas.setEnabled(False)
        self.boton_sel.setEnabled(False)
        self.progreso.setValue(0)
        self.progreso.show()
        self._tarea = Tarea(funcion, *args)
        self._tarea.avance.connect(lambda h, t, a: (self.progreso.setMaximum(max(t, 1)), self.progreso.setValue(h),
                                                    self.estado.setText(f"{texto} {a}…" if a else "")))
        self._tarea.terminada.connect(fin)
        self._tarea.fallo.connect(self._fallo_tarea)
        self._tarea.start()

    def _fallo_tarea(self, e):
        self._fin_tarea()
        QMessageBox.critical(self, "Error", f"Algo ha fallado: {e}")

    def _fin_tarea(self):
        self.progreso.hide()
        self.boton_buscar.setEnabled(True)
        self._pintar_botones()

    def _busqueda_hecha(self, filas):
        self.filas = filas
        self._fin_tarea()
        self._pintar_envio()
        n = {e: sum(1 for f in filas if f.estado == e) for e in COLOR_ESTADO}
        partes = [f"{len(filas)} PDF leídos", f"{n[A.OK]} listos para enviar"]
        if n[A.SIN_EMAIL]:
            partes.append(f"{n[A.SIN_EMAIL]} para avisar por teléfono")
        revisar = n[A.DUDOSA] + n[A.SIN_COINCIDENCIA] + n[A.ERROR_LECTURA]
        if revisar:
            partes.append(f"{revisar} por revisar")
        if n[A.YA_ENVIADA] + n[A.YA_AVISADA]:
            partes.append(f"{n[A.YA_ENVIADA] + n[A.YA_AVISADA]} ya hechas")
        self.estado.setText(" · ".join(partes) + ".")

    def _pintar_envio(self):
        t = self.tabla_envio
        t.setRowCount(len(self.filas))
        for i, f in enumerate(self.filas):
            fondo, color = COLOR_ESTADO.get(f.estado, ("#FFFFFF", "#000000"))
            consejo = f.detalle
            for j, texto in enumerate((f.archivo, f.cliente, f.email or (f"☎ {f.telefono}" if f.telefono else ""),
                                       f.estado, f.detalle)):
                t.setItem(i, j, celda(texto, fondo, color if j == 3 else None, consejo))
        self.vacio.setVisible(not self.filas)
        self._pintar_telefono()
        self._pintar_botones()

    def _pintar_botones(self):
        ocupado = bool(self._tarea and self._tarea.isRunning())
        n_ok = sum(1 for f in self.filas if f.estado == A.OK)
        sel = filas_elegidas(self.tabla_envio)
        self.boton_todas.setText(f"Enviar todas las listas ({n_ok})" if n_ok else "Enviar todas las listas")
        self.boton_todas.setEnabled(n_ok > 0 and not ocupado)
        self.boton_sel.setEnabled(any(self.filas[i].estado == A.OK for i in sel) and not ocupado)
        self.boton_asignar.setEnabled(len(sel) == 1 and not ocupado)
        self.boton_pdf.setEnabled(bool(sel))
        hechas = sum(1 for f in self.filas if f.estado in FINALES)
        self.resumen.setText(f"{hechas} de {len(self.filas)} hechas" if self.filas else "")

    def _doble_clic_envio(self, indice):
        f = self.filas[indice.row()]
        if f.estado in (A.SIN_COINCIDENCIA, A.DUDOSA, A.ERROR_LECTURA):
            self._asignar()
        else:
            abrir_archivo(f.ruta)

    def _asignar(self):
        sel = filas_elegidas(self.tabla_envio)
        if len(sel) != 1:
            return
        fila = self.filas[sel[0]]
        if fila.estado in FINALES:
            QMessageBox.information(self, "Ya hecha", "Esta factura ya está enviada o avisada.")
            return
        d = DialogoAsignar(fila, self.datos.clientes(), self)
        if not d.exec() or not d.elegido:
            return
        cliente = d.elegido
        if d.nuevo:
            cliente["id"] = self.datos.guardar_cliente(cliente)
        aprender = d.aprendizaje()
        if aprender:
            tipo, valor = aprender
            if tipo == "nif":
                cliente = {**self.datos.cliente(cliente["id"]), "nif": valor}
                self.datos.guardar_cliente(cliente)
            else:
                self.datos.aprender_alias(cliente["id"], valor)
        fila.asignar(self.datos.cliente(cliente["id"]), "manual")
        fila.detalle = "Asignada a mano"
        self._pintar_envio()
        self._pintar_clientes()
        self.tabla_envio.selectRow(sel[0])

    def _enviar_seleccionadas(self):
        sel = [self.filas[i] for i in filas_elegidas(self.tabla_envio)]
        listas = [f for f in sel if f.estado == A.OK]
        if len(listas) < len(sel):
            r = QMessageBox.question(self, "Algunas no", f"{len(sel) - len(listas)} de las seleccionadas no están "
                                     f"listas (no tienen cliente con email, o ya se enviaron) y se saltarán.\n\n"
                                     f"¿Enviar las otras {len(listas)}?", QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        self._enviar(listas)

    def _enviar(self, filas):
        if not filas or self._ocupado():
            return
        correo = ajustes_correo(self.datos)
        if not correo["email"] or not correo["servidor"] or not leer_clave(self.datos, correo):
            QMessageBox.warning(self, "Correo sin configurar", "Falta el email o la contraseña de envío. "
                                "Ve a Ajustes → Correo y pulsa «Probar conexión».")
            self.pestanas.setCurrentIndex(4)
            return
        if not DialogoConfirmar(filas, correo["email"], self).exec():
            return
        self._empezar(enviar_filas, filas, self.datos, fin=self._envio_hecho, texto="Enviando")

    def _envio_hecho(self, resultado):
        enviadas, fallidas = resultado
        self._fin_tarea()
        self._pintar_envio()
        if fallidas:
            motivos = {f.detalle for f in self.filas if f.estado == A.ERROR_ENVIO}
            QMessageBox.warning(self, "Envío con errores",
                                f"Enviadas: {enviadas}. Con error: {fallidas}.\n\n" + "\n".join(sorted(motivos)[:3])
                                + "\n\nLas que fallaron siguen pendientes: puedes volver a intentarlo.")
        else:
            QMessageBox.information(self, "Hecho", f"✓ {enviadas} factura{'s' if enviadas != 1 else ''} "
                                    f"enviada{'s' if enviadas != 1 else ''}.")
        self.estado.setText(f"Envío terminado: {enviadas} enviadas" + (f", {fallidas} con error." if fallidas else "."))

    # ================================================================ teléfono
    def _pestana_telefono(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 12, 0, 0)
        v.addWidget(caja("Facturas de clientes que no tienen email. Llámalos o mándales un WhatsApp y pulsa "
                         "«Marcar como avisado» para que no vuelvan a salir. Si te dan un email, añádelo y la "
                         "factura pasa a «Lista» para enviarla."))
        self.tabla_tel = tabla(["Archivo", "Cliente", "Teléfono", "Nota"], [150, 300, 160])
        v.addWidget(self.tabla_tel, 1)
        botones = QHBoxLayout()
        avisar = QPushButton("Marcar como avisado")
        avisar.setObjectName("principal")
        avisar.clicked.connect(self._marcar_avisado)
        email = QPushButton("Añadir su email…")
        email.clicked.connect(self._email_desde_telefono)
        pdf = QPushButton("Abrir PDF")
        pdf.clicked.connect(lambda: [abrir_archivo(self._filas_tel[i].ruta) for i in filas_elegidas(self.tabla_tel)[:5]])
        for b in (avisar, email, pdf):
            botones.addWidget(b)
        botones.addStretch()
        v.addLayout(botones)
        self._filas_tel: list[A.Fila] = []
        return p

    def _pintar_telefono(self):
        self._filas_tel = [f for f in self.filas if f.estado == A.SIN_EMAIL]
        notas = {c["id"]: c["nota"] for c in self.datos.clientes()}
        t = self.tabla_tel
        t.setRowCount(len(self._filas_tel))
        for i, f in enumerate(self._filas_tel):
            for j, texto in enumerate((f.archivo, f.cliente, f.telefono or "— sin teléfono —", notas.get(f.cliente_id, ""))):
                t.setItem(i, j, celda(texto))
        n = len(self._filas_tel)
        self.pestanas.setTabText(1, f"Por teléfono ({n})" if n else "Por teléfono")

    def _marcar_avisado(self):
        sel = [self._filas_tel[i] for i in filas_elegidas(self.tabla_tel)]
        if not sel:
            QMessageBox.information(self, "Elige", "Selecciona a quién has avisado ya.")
            return
        for f in sel:
            marcar_avisada(f, self.datos)
        self._pintar_envio()

    def _email_desde_telefono(self):
        sel = filas_elegidas(self.tabla_tel)
        if len(sel) != 1:
            return
        self._editar_cliente(self._filas_tel[sel[0]].cliente_id)

    # ================================================================ clientes
    def _pestana_clientes(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 12, 0, 0)
        arriba = QHBoxLayout()
        self.buscar_cliente = QLineEdit()
        self.buscar_cliente.setPlaceholderText("Buscar por nombre, email, teléfono o NIF…")
        self.buscar_cliente.textChanged.connect(self._pintar_clientes)
        arriba.addWidget(self.buscar_cliente, 1)
        self.cuenta_clientes = QLabel()
        self.cuenta_clientes.setObjectName("suave")
        arriba.addWidget(self.cuenta_clientes)
        v.addLayout(arriba)
        self.tabla_cli = tabla(["Cliente", "Email", "Teléfono", "NIF", "Nota"], [300, 270, 130, 110])
        self.tabla_cli.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla_cli.doubleClicked.connect(lambda i: self._editar_cliente(self._ids_cli[i.row()]))
        v.addWidget(self.tabla_cli, 1)
        botones = QHBoxLayout()
        nuevo = QPushButton("Añadir cliente…")
        nuevo.setObjectName("principal")
        nuevo.clicked.connect(self._nuevo_cliente)
        editar = QPushButton("Editar…")
        editar.clicked.connect(lambda: [self._editar_cliente(self._ids_cli[i]) for i in filas_elegidas(self.tabla_cli)[:1]])
        borrar = QPushButton("Borrar")
        borrar.setObjectName("peligro")
        borrar.clicked.connect(self._borrar_cliente)
        importar = QPushButton("Importar de Excel, CSV o Word…")
        importar.clicked.connect(self._importar_clientes)
        exportar = QPushButton("Exportar a Excel…")
        exportar.clicked.connect(self._exportar_clientes)
        for b in (nuevo, editar, borrar):
            botones.addWidget(b)
        botones.addStretch()
        botones.addWidget(importar)
        botones.addWidget(exportar)
        v.addLayout(botones)
        self._ids_cli: list[int] = []
        return p

    def _pintar_clientes(self):
        buscado = self.buscar_cliente.text().strip().lower() if hasattr(self, "buscar_cliente") else ""
        todos = self.datos.clientes()
        clientes = [c for c in todos if not buscado or buscado in " ".join(
            (c["nombre"], c["email"], c["telefono"], c["nif"], c["nota"])).lower()
            or normalizar(buscado) in normalizar(c["nombre"])]
        self._ids_cli = [c["id"] for c in clientes]
        t = self.tabla_cli
        t.setRowCount(len(clientes))
        for i, c in enumerate(clientes):
            for j, campo in enumerate(("nombre", "email", "telefono", "nif", "nota")):
                color = "#A23B2C" if campo == "email" and not c["email"] else None
                t.setItem(i, j, celda(c[campo] or ("sin email" if campo == "email" else ""), color=color))
        sin_email = sum(1 for c in todos if not c["email"])
        self.cuenta_clientes.setText(f"{len(todos)} clientes · {sin_email} sin email")

    def _nuevo_cliente(self):
        d = DialogoCliente(None, self)
        if d.exec():
            self.datos.guardar_cliente(d.cliente)
            self._pintar_clientes()

    def _editar_cliente(self, id_cliente):
        actual = self.datos.cliente(id_cliente)
        if not actual:
            return
        d = DialogoCliente(actual, self)
        if not d.exec():
            return
        self.datos.guardar_cliente(d.cliente)
        # las facturas ya buscadas de este cliente se actualizan (p. ej. si se le ha añadido el email)
        nuevo = self.datos.cliente(id_cliente)
        for f in self.filas:
            if f.cliente_id == id_cliente and f.estado in (A.OK, A.SIN_EMAIL, A.ERROR_ENVIO):
                f.asignar(nuevo, f.metodo, f.puntuacion)
        self._pintar_clientes()
        self._pintar_envio()

    def _borrar_cliente(self):
        sel = filas_elegidas(self.tabla_cli)
        if not sel:
            return
        c = self.datos.cliente(self._ids_cli[sel[0]])
        if QMessageBox.question(self, "Borrar", f"¿Borrar a «{c['nombre']}» del directorio?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.datos.borrar_cliente(c["id"])
            for f in self.filas:
                if f.cliente_id == c["id"] and f.estado not in FINALES:
                    f.asignar(None, "")
            self._pintar_clientes()
            self._pintar_envio()

    def _importar_clientes(self):
        from nucleo.importar import leer_clientes
        ruta, _ = QFileDialog.getOpenFileName(self, "Lista de clientes", "",
                                              "Excel, CSV o Word (*.xlsx *.xlsm *.csv *.txt *.docx)")
        if not ruta:
            return
        try:
            nuevos = leer_clientes(ruta)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Importar", f"No se ha podido leer ese archivo: {e}")
            return
        if not nuevos:
            QMessageBox.warning(self, "Importar", "No he encontrado clientes. Comprueba que tenga una columna con el "
                                "nombre del cliente y otra con el email.")
            return
        anadidos, completados = self.datos.importar_clientes(nuevos)
        self._pintar_clientes()
        QMessageBox.information(self, "Importar", f"{len(nuevos)} clientes leídos: {anadidos} nuevos, {completados} "
                                "completados con datos que les faltaban. Los que ya estaban no se tocan.")

    def _exportar_clientes(self):
        from nucleo.importar import exportar_xlsx
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar clientes", str(Path.home() / "clientes.xlsx"), "Excel (*.xlsx)")
        if ruta:
            exportar_xlsx(self.datos.clientes(), ruta)
            QMessageBox.information(self, "Exportar", f"Guardado en {ruta}")

    # ================================================================ historial
    def _pestana_historial(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(0, 12, 0, 0)
        self.buscar_hist = QLineEdit()
        self.buscar_hist.setPlaceholderText("Buscar por archivo, cliente o email…")
        self.buscar_hist.textChanged.connect(self._pintar_historial)
        v.addWidget(self.buscar_hist)
        self.tabla_hist = tabla(["Fecha", "Archivo", "Cliente", "Email", "Resultado", "Detalle"], [140, 140, 250, 230, 110])
        v.addWidget(self.tabla_hist, 1)
        return p

    def _pintar_historial(self):
        buscado = self.buscar_hist.text().strip().lower()
        nombres = {ENVIADO: ("Enviada", A.YA_ENVIADA), AVISADO: ("Avisada", A.YA_AVISADA), ERROR: ("Error", A.ERROR_ENVIO)}
        filas = [h for h in self.datos.historial()
                 if not buscado or buscado in f"{h['archivo']} {h['cliente']} {h['email']}".lower()]
        t = self.tabla_hist
        t.setRowCount(len(filas))
        for i, h in enumerate(filas):
            nombre, estado = nombres.get(h["resultado"], (h["resultado"], None))
            fondo, color = COLOR_ESTADO.get(estado, (None, None))
            for j, texto in enumerate((h["fecha"][:16], h["archivo"], h["cliente"], h["email"], nombre, h["detalle"])):
                t.setItem(i, j, celda(texto, fondo if j == 4 else None, color if j == 4 else None, h["detalle"]))

    # ================================================================ ajustes
    def _pestana_ajustes(self):
        p = QTabWidget()
        self.paginas_ajustes = []
        for clase, nombre in ((PaginaEmpresa, "Empresa"), (PaginaCorreo, "Correo"), (PaginaMensaje, "Mensaje"),
                              (PaginaFacturas, "Facturas")):
            pagina = clase(self.datos)
            pagina.cargar()
            envoltura = QWidget()
            v = QVBoxLayout(envoltura)
            v.setContentsMargins(4, 14, 4, 4)
            v.addWidget(pagina)
            aviso = caja("", "aviso")
            aviso.hide()
            v.addWidget(aviso)
            fila = QHBoxLayout()
            fila.addStretch()
            guardar = QPushButton("Guardar")
            guardar.setObjectName("principal")
            guardar.clicked.connect(lambda _=False, pg=pagina, av=aviso: self._guardar_ajustes(pg, av))
            fila.addWidget(guardar)
            v.addLayout(fila)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(envoltura)
            p.addTab(scroll, nombre)
            self.paginas_ajustes.append(pagina)
        p.addTab(self._ajustes_mas(), "Más")
        return p

    def _guardar_ajustes(self, pagina, aviso):
        from interfaz.estilo import poner_tipo
        falta = pagina.falta()
        if falta:
            poner_tipo(aviso, "aviso", falta)
            return
        resultado = pagina.guardar()
        poner_tipo(aviso, "bien", "✓ Guardado." + (" La contraseña se ha guardado en la base de datos porque este "
                                                   "ordenador no tiene llavero." if resultado is False else ""))
        self._pintar_cabecera()

    def _ajustes_mas(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setContentsMargins(4, 14, 4, 4)
        v.setSpacing(12)
        titulo = QLabel("Pasar desde la versión anterior")
        titulo.setObjectName("tituloPanel")
        v.addWidget(titulo)
        v.addWidget(caja("Si usabas la app antigua de envío de facturas (la de iniciar.bat), importa su "
                         "<b>log_envios.csv</b> para que no se reenvíe nada de lo que ya se mandó, y su "
                         "<b>directorio_clientes.xlsx</b> en la pestaña Clientes."))
        log = QPushButton("Importar historial (log_envios.csv)…")
        log.clicked.connect(self._importar_log)
        v.addWidget(log, alignment=Qt.AlignLeft)

        titulo = QLabel("Dónde se guardan los datos")
        titulo.setObjectName("tituloPanel")
        v.addWidget(titulo)
        v.addWidget(caja(f"Clientes, historial y ajustes están en:<br><b>{escape(str(self.datos.ruta))}</b><br>"
                         "La contraseña del correo va aparte, en el llavero del sistema."))
        abrir = QPushButton("Abrir la carpeta")
        abrir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(carpeta_datos()))))
        v.addWidget(abrir, alignment=Qt.AlignLeft)

        titulo = QLabel("Volver a empezar")
        titulo.setObjectName("tituloPanel")
        v.addWidget(titulo)
        asistente = QPushButton("Abrir otra vez el asistente de configuración")
        asistente.clicked.connect(self._reabrir_asistente)
        v.addWidget(asistente, alignment=Qt.AlignLeft)
        v.addStretch()
        return p

    def _importar_log(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "log_envios.csv de la versión anterior", "", "CSV (*.csv)")
        if not ruta:
            return
        try:
            n = self.datos.importar_log_antiguo(ruta)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Importar", f"No se ha podido leer: {e}")
            return
        QMessageBox.information(self, "Importar", f"{n} registros importados. Las facturas ya enviadas o avisadas "
                                "saldrán como hechas y no se repetirán.")

    def _reabrir_asistente(self):
        from interfaz.asistente import Asistente
        if Asistente(self.datos, self).exec():
            for pagina in self.paginas_ajustes:
                pagina.cargar()
            self._pintar_cabecera()
            self._pintar_clientes()

    # ================================================================ general
    def _al_cambiar_pestana(self, i):
        if i == 3:
            self._pintar_historial()
        elif i == 4:
            for pagina in self.paginas_ajustes:
                pagina.cargar()

    def closeEvent(self, evento):
        if self._tarea and self._tarea.isRunning():
            if QMessageBox.question(self, "Salir", "Todavía está trabajando. Si sales ahora, puede quedar a medias "
                                    "(lo ya enviado queda apuntado). ¿Salir?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                evento.ignore()
                return
            self._tarea.wait(5000)
        super().closeEvent(evento)
