# -*- coding: utf-8 -*-
"""
Prueba de la interfaz sin pantalla (QT_QPA_PLATFORM=offscreen): recorre el
asistente como lo haría una persona y usa la ventana de principio a fin.
"""

import time

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from nucleo import analisis as A
from utiles import factura_ejidosoft


@pytest.fixture(scope="module")
def app():
    from interfaz.estilo import HOJA_ESTILOS
    a = QApplication.instance() or QApplication([])
    a.setStyleSheet(HOJA_ESTILOS)
    return a


@pytest.fixture
def sin_ventanitas(monkeypatch):
    """Los avisos (QMessageBox) se contestan solos con «Sí» y se apuntan."""
    vistos = []

    def apuntar(tipo):
        def f(parent, titulo, texto, *a, **k):
            vistos.append((tipo, titulo, texto))
            return QMessageBox.Yes
        return f

    for tipo in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, tipo, staticmethod(apuntar(tipo)))
    return vistos


def esperar(app, condicion, maximo=20):
    fin = time.time() + maximo
    while not condicion():
        app.processEvents()
        assert time.time() < fin, "tiempo agotado"
        time.sleep(0.01)
    app.processEvents()


def test_asistente_completo(app, datos, tmp_path, correo_falso, sin_ventanitas, monkeypatch):
    from interfaz.asistente import Asistente
    from interfaz.paginas import PaginaCorreo
    import nucleo.correo as correo
    monkeypatch.setattr(correo, "guardar_clave", lambda d, a, c: d.guardar_ajuste("clave_prueba", c) or True)
    monkeypatch.setattr(correo, "leer_clave", lambda d, a: d.ajuste("clave_prueba", ""))
    import interfaz.paginas as paginas
    monkeypatch.setattr(paginas, "guardar_clave", correo.guardar_clave)
    monkeypatch.setattr(paginas, "leer_clave", correo.leer_clave)
    datos.guardar_ajuste("empresa", {})

    # carpeta de un mes al estilo de la distribuidora
    mes = tmp_path / "Facturas" / "2026" / "FACTURAS SEPTIEMBRE 26"
    mes.mkdir(parents=True)
    factura_ejidosoft(mes / "26-1077.pdf", "AGRICOLA FERVALIA S.L.")

    asis = Asistente(datos)
    asis.show()
    assert asis.siguiente.text() == "Empezar"
    asis._siguiente()                                  # bienvenida
    empresa = asis.paginas[1]
    asis._siguiente()
    assert asis.actual == 1 and asis.falta.isVisible()  # sin nombre no deja seguir
    empresa.nombre.setText("Asesoría Mirasol, S.L.")
    empresa.nif.setText("b-04999999")
    asis._siguiente()
    assert datos.empresa()["nif"] == "B04999999"

    c: PaginaCorreo = asis.paginas[2]
    c.email.setText("facturas@gmail.com")
    c._adivinar()
    assert c.proveedor.currentText() == "Gmail" and c.servidor.text() == "smtp.gmail.com"
    assert c.boton_enlace.isVisibleTo(c)
    # para la prueba, al servidor falso
    c.proveedor.setCurrentText("Otro (lo pongo yo)")
    assert c.avanzado.isVisibleTo(c)
    c.servidor.setText("127.0.0.1")
    c.puerto.setValue(correo_falso.puerto)
    c.seguridad.setCurrentIndex(c.seguridad.findData("ninguna"))
    c.clave.setText("x")
    c._probar()
    esperar(app, lambda: c.boton_probar.isEnabled())
    assert c.probada and "Conexión correcta" in c.resultado.text()
    asis._siguiente()
    assert datos.ajuste("correo")["servidor"] == "127.0.0.1"

    m = asis.paginas[3]
    assert "Factura 26-1077 - Asesoría Mirasol" in m.vista.text()
    asis._siguiente()

    f = asis.paginas[4]
    asis._siguiente()
    assert asis.actual == 4  # falta la carpeta
    monkeypatch.setattr("interfaz.paginas.QFileDialog.getExistingDirectory", lambda *a, **k: str(mes))
    f._elegir_mes()
    assert f.patron.currentText() == "{AAAA}/FACTURAS {MES} {AA}" and f.base.text() == str(tmp_path / "Facturas")
    asis._siguiente()

    cl = asis.paginas[5]
    xlsx = tmp_path / "clientes.xlsx"
    from nucleo.importar import exportar_xlsx
    exportar_xlsx([{"nombre": "AGRICOLA FERVALIA S.L", "email": "admin@fervalia.com", "telefono": "", "nif": "", "nota": ""}], xlsx)
    monkeypatch.setattr("interfaz.paginas.QFileDialog.getOpenFileName", lambda *a, **k: (str(xlsx), ""))
    cl._importar()
    assert "1 clientes" in cl.estado.text()
    asis._siguiente()

    listo = asis.paginas[6]
    assert "facturas@gmail.com" in listo.resumen.text()
    listo._prueba()
    esperar(app, lambda: listo.boton_prueba.isEnabled())
    assert "Enviado" in listo.resultado.text(), listo.resultado.text()
    assert correo_falso.mensajes[-1]["mensaje"]["Subject"].startswith("[PRUEBA] Factura 26-0001")
    asis._siguiente()
    assert asis.result() == QDialog.Accepted and datos.configurada()


def test_ventana_de_principio_a_fin(app, datos, tmp_path, correo_falso, sin_ventanitas, monkeypatch):
    import interfaz.ventana as V
    monkeypatch.setattr(V, "leer_clave", lambda d, a: "x")
    import nucleo.envio as envio
    monkeypatch.setattr(envio, "leer_clave", lambda d, a: "")
    datos.guardar_ajuste("correo", correo_falso.ajustes())
    datos.guardar_ajuste("mensaje", {"asunto": "Factura {factura}", "cuerpo": "Hola {cliente}", "firma_logo": False})
    for c in ({"nombre": "AGRICOLA FERVALIA S.L", "email": "admin@fervalia.com"},
              {"nombre": "AGROLUMEN S.L", "telefono": "667 042 506"},
              {"nombre": "BIO SEMILLA SAT", "email": "info@biosemilla.es"}):
        datos.guardar_cliente(c)
    mes = tmp_path / "FACTURAS OCTUBRE 26"
    mes.mkdir()
    factura_ejidosoft(mes / "26-1077.pdf", "AGRICOLA FERVALIA S.L.")
    factura_ejidosoft(mes / "26-1078.pdf", "AGROLUMEN, S.L.")
    factura_ejidosoft(mes / "26-1080.pdf", "HORTALIZAS NUEVAS SL", nif_cliente="B04555555")
    datos.guardar_ajuste("facturas", {"carpeta_base": str(tmp_path), "patron_mes": "FACTURAS {MES} {AA}"})

    v = V.VentanaPrincipal(datos)
    v.show()
    assert "Envía desde yo@miempresa.es" in v.dato_empresa.text()
    v.carpeta.setText(str(mes))
    v._buscar()
    esperar(app, lambda: v.boton_buscar.isEnabled())
    estados = {f.archivo: f.estado for f in v.filas}
    assert estados == {"26-1077.pdf": A.OK, "26-1078.pdf": A.SIN_EMAIL, "26-1080.pdf": A.SIN_COINCIDENCIA}
    assert v.tabla_envio.rowCount() == 3 and v.boton_todas.text() == "Enviar todas las listas (1)"
    assert v.pestanas.tabText(1) == "Por teléfono (1)"

    # asignar a mano la que no tiene cliente: se crea uno nuevo y aprende su NIF
    v.tabla_envio.selectRow(2)
    import interfaz.dialogos as D

    def asignar_a_bio(self):
        self.elegido = [c for c in self.clientes if c["nombre"] == "BIO SEMILLA SAT"][0]
        assert self.que_aprender(self.elegido) == ("nif", "B04555555")
        self.recordar.setChecked(True)
        return True
    monkeypatch.setattr(D.DialogoAsignar, "exec", asignar_a_bio)
    monkeypatch.setattr(D.DialogoAsignar, "aprendizaje", lambda self: ("nif", "B04555555"))
    v._asignar()
    assert v.filas[2].estado == A.OK and v.filas[2].cliente == "BIO SEMILLA SAT"
    assert [c for c in datos.clientes() if c["nombre"] == "BIO SEMILLA SAT"][0]["nif"] == "B04555555"

    # añadir el email al de teléfono: pasa a Lista
    agrolumen = [c for c in datos.clientes() if c["nombre"] == "AGROLUMEN S.L"][0]

    def poner_email(self):
        self.cliente = {**self.cliente, "email": "pop@agrolumen.es"}
        return True
    monkeypatch.setattr(D.DialogoCliente, "exec", poner_email)
    monkeypatch.setattr(V.DialogoCliente, "exec", poner_email)
    v._editar_cliente(agrolumen["id"])
    assert v.filas[1].estado == A.OK and v.pestanas.tabText(1) == "Por teléfono"

    # enviar todas (la confirmación se acepta sola)
    monkeypatch.setattr(V.DialogoConfirmar, "exec", lambda self: True)
    v._enviar([f for f in v.filas if f.estado == A.OK])
    esperar(app, lambda: v.boton_buscar.isEnabled())
    assert [f.estado for f in v.filas] == [A.ENVIADA] * 3
    assert sorted(tuple(m["para"]) for m in correo_falso.mensajes) == [
        ("admin@fervalia.com",), ("info@biosemilla.es",), ("pop@agrolumen.es",)]
    adjunto = {m["para"][0]: next(m["mensaje"].iter_attachments()).get_filename() for m in correo_falso.mensajes}
    assert adjunto == {"admin@fervalia.com": "26-1077.pdf", "pop@agrolumen.es": "26-1078.pdf",
                       "info@biosemilla.es": "26-1080.pdf"}

    # buscar otra vez: todo sale como ya enviado, y el historial lo recoge
    v._buscar()
    esperar(app, lambda: v.boton_buscar.isEnabled())
    assert {f.estado for f in v.filas} == {A.YA_ENVIADA}
    assert not v.boton_todas.isEnabled()
    v.pestanas.setCurrentIndex(3)
    assert v.tabla_hist.rowCount() == 3
    v.close()


def test_ajustes_guardan(app, datos, sin_ventanitas):
    from interfaz.ventana import VentanaPrincipal
    v = VentanaPrincipal(datos)
    empresa = v.paginas_ajustes[0]
    empresa.nombre.setText("Otra Empresa SL")
    from interfaz.estilo import caja
    v._guardar_ajustes(empresa, caja(""))
    assert datos.empresa()["nombre"] == "Otra Empresa SL"
    assert v.nombre_empresa.text() == "Otra Empresa SL"
    v.close()
