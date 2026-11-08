# -*- coding: utf-8 -*-
"""Pruebas del núcleo: reconocer al cliente, no repetir envíos, importar y enviar de verdad (a un servidor falso)."""

import zipfile
from datetime import date
from pathlib import Path

import pytest

from nucleo import analisis as A
from nucleo.emparejar import identificar, leer_texto_pdf, nifs_en_texto, normalizar, tokens
from nucleo.envio import enviar_filas, marcar_avisada
from utiles import factura_ejidosoft, factura_otro_programa

DIRECTORIO_REAL = Path(__file__).parent / "reales" / "directorio_clientes.xlsx"


def cargar(datos, clientes):
    for c in clientes:
        datos.guardar_cliente({"nif": "", "email": "", "telefono": "", "nota": "", **c})
    return datos.clientes()


# ------------------------------------------------------------ nombres
def test_formas_juridicas_se_quitan_como_palabras():
    assert tokens("Hortofrutícola Costa de Málaga, S.A.T.") == ["hortofruticola", "costa", "malaga"]
    assert normalizar("AGRO-MARTILOR S.L") == "agro martilor"
    assert normalizar("Bio Naturaleza Agro, S.L.U") == "bio naturaleza agro"
    # la versión antigua convertía "casa" en "ca" al quitar "sa"
    assert normalizar("Casa Isla SA") == "casa isla"


def test_nif_en_varios_formatos():
    assert nifs_en_texto("CIF: B-04.123456 y ES B04999999, DNI 12345678Z, NIE X1234567L") == \
        {"B04123456", "B04999999", "12345678Z", "X1234567L"}


# ------------------------------------------------------------ reconocer
def test_formato_ejidosoft_por_ancla_y_por_nombre(datos, tmp_path):
    clientes = cargar(datos, [{"nombre": "AGRICOLA FERVALIA S.L", "email": "admin@fervalia.com"},
                              {"nombre": "BIO SEMILLA, S.A.T.", "email": "info@biosemilla.es"}])
    texto = leer_texto_pdf(factura_ejidosoft(tmp_path / "a.pdf", "AGRICOLA FERVALIA, S.L."))
    con_ancla = identificar(texto, clientes, datos.empresa(), ancla="E-MAIL:")
    sin_ancla = identificar(texto, clientes, datos.empresa())
    for r in (con_ancla, sin_ancla):
        assert clientes[0]["id"] == r.cliente_id and not r.dudosa
    assert con_ancla.nombre_leido == "AGRICOLA FERVALIA, S.L."


def test_otro_programa_sin_ancla(datos, tmp_path):
    clientes = cargar(datos, [{"nombre": "Talleres Brisa S.L.", "email": "t@brisa.es"},
                              {"nombre": "Hortofrutícola Costa de Málaga", "email": "h@costa.es"}])
    texto = leer_texto_pdf(factura_otro_programa(tmp_path / "b.pdf", "HORTOFRUTICOLA COSTA DE MALAGA SAT"))
    r = identificar(texto, clientes, {"nombre": "Asesoría Mirasol", "nif": "B04999999"})
    assert r.cliente_id == clientes[0]["id"] or clientes[1]["id"] == r.cliente_id
    assert [c for c in clientes if c["id"] == r.cliente_id][0]["nombre"].startswith("Hortofrut")


def test_nif_manda_aunque_el_nombre_este_cambiado(datos, tmp_path):
    clientes = cargar(datos, [{"nombre": "Juan Pérez García", "nif": "12345678Z", "email": "j@p.es"},
                              {"nombre": "Otro Cliente", "email": "o@c.es"}])
    texto = leer_texto_pdf(factura_otro_programa(tmp_path / "c.pdf", "J. PEREZ (TALLER)", nif_cliente="12345678-Z"))
    r = identificar(texto, clientes, {"nombre": "Asesoría", "nif": "B04999999"})
    assert (r.cliente_id, r.metodo) == (clientes[0]["id"], "nif")


def test_el_nif_y_el_nombre_de_mi_empresa_no_cuentan(datos, tmp_path):
    # un "cliente" con el NIF y el nombre de la propia empresa no debe salir nunca
    clientes = cargar(datos, [{"nombre": "Suministros La Vega", "nif": "B04123456", "email": "x@x.es"}])
    texto = leer_texto_pdf(factura_ejidosoft(tmp_path / "d.pdf", "CLIENTE DESCONOCIDO SL"))
    assert identificar(texto, clientes, datos.empresa()).cliente_id is None


def test_errata_en_el_nombre(datos, tmp_path):
    clientes = cargar(datos, [{"nombre": "Hortofrutícola Costa de Málaga", "email": "h@c.es"}])
    texto = leer_texto_pdf(factura_ejidosoft(tmp_path / "e.pdf", "HORTOFRUTICULA COSTA MALAGA"))
    assert identificar(texto, clientes, datos.empresa()).cliente_id == clientes[0]["id"]


def test_dos_clientes_casi_iguales_es_dudosa(datos, tmp_path):
    clientes = cargar(datos, [{"nombre": "Agrícola Navarro", "email": "a@n.es"},
                              {"nombre": "Navarro Agrícola", "email": "b@n.es"}])
    texto = leer_texto_pdf(factura_ejidosoft(tmp_path / "f.pdf", "AGRICOLA NAVARRO"))
    r = identificar(texto, clientes, datos.empresa())
    # "Agrícola Navarro" sale seguido (100 %), "Navarro Agrícola" solo con las palabras sueltas (85 %): no es duda
    assert r.cliente_id == clientes[0]["id"] and not r.dudosa
    clientes = cargar(datos, [{"nombre": "Agricola Navarro SL", "email": "c@n.es"}])
    r = identificar(texto, clientes, datos.empresa())
    assert r.dudosa  # ahora hay dos con el mismo nombre


def test_el_nombre_mas_largo_gana(datos, tmp_path):
    clientes = cargar(datos, [{"nombre": "Agro Sur", "email": "a@s.es"},
                              {"nombre": "Agro Sur Export", "email": "e@s.es"}])
    texto = leer_texto_pdf(factura_ejidosoft(tmp_path / "g.pdf", "AGRO SUR EXPORT S.L."))
    r = identificar(texto, clientes, datos.empresa())
    assert r.cliente_id == clientes[1]["id"] and not r.dudosa


def test_no_confunde_con_palabras_sueltas(datos, tmp_path):
    # "Costa" y "Almería" salen en la dirección: no basta con eso para elegir a "Costa Almería Frutas"
    clientes = cargar(datos, [{"nombre": "Frutas Costa Almería Export", "email": "f@c.es"}])
    texto = leer_texto_pdf(factura_ejidosoft(tmp_path / "h.pdf", "BIO SEMILLA SAT"))
    assert identificar(texto + "\nCosta de Malaga", clientes, datos.empresa()).cliente_id is None


# ------------------------------------------------------------ carpeta del mes
def test_carpeta_del_mes():
    base = "/srv/Facturas"
    assert A.carpeta_del_mes(base, "FACTURAS {MES} {AA}", date(2026, 9, 3)) == "/srv/Facturas/FACTURAS SEPTIEMBRE 26"
    assert A.carpeta_del_mes(base, "{AAAA}/{MM} {Mes}", date(2026, 1, 9)) == "/srv/Facturas/2026/01 Enero"
    assert A.carpeta_del_mes(base, "", date(2026, 1, 9)) == base
    assert A.mes_pasado(date(2026, 1, 15)) == date(2025, 12, 1)


# ------------------------------------------------------------ análisis + envío
@pytest.fixture
def carpeta_mes(datos, tmp_path):
    cargar(datos, [{"nombre": "AGRICOLA FERVALIA S.L", "email": "admin@fervalia.com"},
                   {"nombre": "AGROLUMEN S.L", "telefono": "667 042 506"},
                   {"nombre": "BIO SEMILLA, S.A.T.", "email": "info@biosemilla.es; conta@biosemilla.es"}])
    carpeta = tmp_path / "FACTURAS SEPTIEMBRE 26"
    carpeta.mkdir()
    factura_ejidosoft(carpeta / "26-1077.pdf", "AGRICOLA FERVALIA S.L.")
    factura_ejidosoft(carpeta / "26-1078.pdf", "AGROLUMEN, S.L.")
    factura_ejidosoft(carpeta / "26-1079.pdf", "BIO SEMILLA SAT")
    factura_ejidosoft(carpeta / "26-1080.pdf", "CLIENTE NUEVO SIN DAR DE ALTA")
    (carpeta / "26-1081.pdf").write_bytes(b"esto no es un pdf")
    (carpeta / "notas.txt").write_text("no es pdf")
    return carpeta


def test_analizar_carpeta(datos, carpeta_mes):
    filas = {f.archivo: f for f in A.analizar_carpeta(str(carpeta_mes), datos)}
    assert len(filas) == 5
    assert filas["26-1077.pdf"].estado == A.OK
    assert filas["26-1078.pdf"].estado == A.SIN_EMAIL and filas["26-1078.pdf"].telefono == "667 042 506"
    assert filas["26-1079.pdf"].estado == A.OK
    assert filas["26-1080.pdf"].estado == A.SIN_COINCIDENCIA
    assert filas["26-1081.pdf"].estado == A.ERROR_LECTURA


def test_enviar_y_no_repetir(datos, carpeta_mes, correo_falso):
    datos.guardar_ajuste("correo", correo_falso.ajustes())
    datos.guardar_ajuste("mensaje", {"asunto": "Factura {factura} - {empresa}",
                                     "cuerpo": "Hola {cliente},\nadjunta la factura {factura}.", "firma_logo": False})
    filas = A.analizar_carpeta(str(carpeta_mes), datos)
    enviadas, fallidas = enviar_filas(filas, datos)
    assert (enviadas, fallidas) == (2, 0)
    assert len(correo_falso.mensajes) == 2

    m = {tuple(x["para"]): x["mensaje"] for x in correo_falso.mensajes}
    fervalia = m[("admin@fervalia.com",)]
    assert fervalia["Subject"] == "Factura 26-1077 - Suministros La Vega, S.L."
    assert "Hola AGRICOLA FERVALIA S.L" in fervalia.get_body(("plain",)).get_content()
    adjuntos = list(fervalia.iter_attachments())
    assert [a.get_filename() for a in adjuntos] == ["26-1077.pdf"]
    assert adjuntos[0].get_content() == (carpeta_mes / "26-1077.pdf").read_bytes()  # el PDF de ESE cliente
    assert ("info@biosemilla.es", "conta@biosemilla.es") in m  # varios emails del mismo cliente

    # el aviso por teléfono
    agrolumen = [f for f in filas if f.archivo == "26-1078.pdf"][0]
    marcar_avisada(agrolumen, datos)

    # segunda búsqueda: nada se repite, aunque se cambie el nombre del archivo
    (carpeta_mes / "26-1077.pdf").rename(carpeta_mes / "copia de 26-1077.pdf")
    filas2 = {f.archivo: f.estado for f in A.analizar_carpeta(str(carpeta_mes), datos)}
    assert filas2["copia de 26-1077.pdf"] == A.YA_ENVIADA
    assert filas2["26-1079.pdf"] == A.YA_ENVIADA
    assert filas2["26-1078.pdf"] == A.YA_AVISADA
    assert enviar_filas(A.analizar_carpeta(str(carpeta_mes), datos), datos) == (0, 0)
    assert len(correo_falso.mensajes) == 2


def test_logo_en_la_firma(datos, carpeta_mes, correo_falso, tmp_path):
    from PIL import Image
    logo = tmp_path / "logo.png"
    Image.new("RGB", (120, 40), "green").save(logo)
    datos.guardar_ajuste("empresa", {**datos.empresa(), "logo": str(logo)})
    datos.guardar_ajuste("correo", {**correo_falso.ajustes(), "copia_oculta": "archivo@miempresa.es"})
    filas = [f for f in A.analizar_carpeta(str(carpeta_mes), datos) if f.archivo == "26-1077.pdf"]
    assert enviar_filas(filas, datos) == (1, 0)
    recibido = correo_falso.mensajes[0]
    assert recibido["para"] == ["admin@fervalia.com", "archivo@miempresa.es"]  # copia oculta
    assert "Bcc" not in recibido["mensaje"]                                   # y no se ve
    html = recibido["mensaje"].get_body(("html",)).get_content()
    assert "cid:" in html
    tipos = [p.get_content_type() for p in recibido["mensaje"].walk()]
    assert "image/png" in tipos and "application/pdf" in tipos


def test_servidor_que_rechaza(datos, carpeta_mes):
    from utiles import ServidorCorreoFalso
    s = ServidorCorreoFalso(rechazar=True)
    try:
        datos.guardar_ajuste("correo", s.ajustes())
        filas = A.analizar_carpeta(str(carpeta_mes), datos)
        assert enviar_filas(filas, datos) == (0, 2)
        malas = [f for f in filas if f.estado == A.ERROR_ENVIO]
        assert len(malas) == 2 and "rechazado" in malas[0].detalle
        # un error no cuenta como enviada: la siguiente vez vuelve a salir lista
        assert {f.estado for f in A.analizar_carpeta(str(carpeta_mes), datos) if f.archivo == "26-1077.pdf"} == {A.OK}
    finally:
        s.cerrar()


def test_sin_servidor_no_cuelga(datos, carpeta_mes):
    datos.guardar_ajuste("correo", {"email": "yo@x.es", "servidor": "127.0.0.1", "puerto": 1,
                                    "seguridad": "ninguna"})
    filas = A.analizar_carpeta(str(carpeta_mes), datos)
    assert enviar_filas(filas, datos) == (0, 2)
    assert all("rechaza la conexión" in f.detalle for f in filas if f.estado == A.ERROR_ENVIO)


# ------------------------------------------------------------ importar
@pytest.mark.skipif(not DIRECTORIO_REAL.exists(), reason="directorio real de la distribuidora no disponible")
def test_importar_directorio_real(datos):
    from nucleo.importar import leer_clientes
    clientes = leer_clientes(DIRECTORIO_REAL)
    assert len(clientes) == 78
    assert datos.importar_clientes(clientes) == (78, 0)
    assert datos.importar_clientes(clientes) == (0, 0)  # importar dos veces no duplica


def test_importar_word_y_csv(tmp_path):
    from nucleo.importar import leer_clientes
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

    def celda(t):
        return f"<w:tc><w:p><w:r><w:t>{t}</w:t></w:r></w:p></w:tc>"

    filas = [("NOMBRE", "CORREO", "TELÉFONO"), ("Agrícola Fervalia S.L", "admin@fervalia.com", ""),
             ("Agrolumen S.L", "", "667 042 506")]
    cuerpo = "".join("<w:tr>" + "".join(celda(c) for c in f) + "</w:tr>" for f in filas)
    docx = tmp_path / "ENVIO_FACTURAS.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", f"<w:document {w}><w:body><w:tbl>{cuerpo}</w:tbl></w:body></w:document>")
    assert leer_clientes(docx) == [
        {"nombre": "Agrícola Fervalia S.L", "email": "admin@fervalia.com", "telefono": "", "nif": "", "nota": ""},
        {"nombre": "Agrolumen S.L", "email": "", "telefono": "667 042 506", "nif": "", "nota": ""}]

    csv = tmp_path / "clientes.csv"
    csv.write_bytes("Razón social;CIF;E-mail\nTalleres Brisa SL;B12345674;t@brisa.es\n".encode("cp1252"))
    assert leer_clientes(csv)[0] == {"nombre": "Talleres Brisa SL", "email": "t@brisa.es", "telefono": "",
                                     "nif": "B12345674", "nota": ""}


def test_importar_log_antiguo(datos, carpeta_mes, tmp_path):
    log = tmp_path / "log_envios.csv"
    log.write_text("fecha,archivo_pdf,nombre_leido_pdf,cliente_directorio,email,resultado,detalle\n"
                   "2026-09-30 10:00:00,26-1077.pdf,X,AGRICOLA FERVALIA S.L,admin@fervalia.com,ENVIADO,\n"
                   "2026-09-30 10:01:00,26-1079.pdf,X,BIO SEMILLA,info@biosemilla.es,ERROR,fallo\n", encoding="utf-8")
    assert datos.importar_log_antiguo(log) == 2
    estados = {f.archivo: f.estado for f in A.analizar_carpeta(str(carpeta_mes), datos)}
    assert estados["26-1077.pdf"] == A.YA_ENVIADA
    assert estados["26-1079.pdf"] == A.OK  # el error no cuenta


def test_contrasena_en_el_llavero(datos, monkeypatch):
    import keyring
    from keyring.backend import KeyringBackend
    from nucleo.correo import guardar_clave, leer_clave

    class Memoria(KeyringBackend):
        priority = 1
        guardado = {}

        def set_password(self, s, u, p): self.guardado[(s, u)] = p
        def get_password(self, s, u): return self.guardado.get((s, u))
        def delete_password(self, s, u): self.guardado.pop((s, u), None)

    keyring.set_keyring(Memoria())
    ajustes = {"email": "Yo@Empresa.es"}
    assert guardar_clave(datos, ajustes, "abcd efgh") is True
    assert leer_clave(datos, ajustes) == "abcd efgh"
    assert datos.ajuste("clave_local") is None  # no queda en la base de datos


def test_inferir_patron():
    assert A.inferir_patron("/srv/Facturas/2026/FACTURAS SEPTIEMBRE 26") == ("/srv/Facturas", "{AAAA}/FACTURAS {MES} {AA}")
    assert A.inferir_patron("/srv/Facturas/2026-09") == ("/srv/Facturas", "{AAAA}-{MM}")
    assert A.inferir_patron("/srv/F/Octubre 2026") == ("/srv/F", "{Mes} {AAAA}")
    assert A.inferir_patron("/srv/F/09 2026") == ("/srv/F", "{MM} {AAAA}")
    assert A.inferir_patron("/srv/F/Emitidas") is None
    base, patron = A.inferir_patron("/srv/Facturas/2026/FACTURAS SEPTIEMBRE 26")
    assert A.carpeta_del_mes(base, patron, date(2027, 1, 5)) == "/srv/Facturas/2027/FACTURAS ENERO 27"


def test_nif_propio_se_detecta_aunque_no_este_en_ajustes(datos, carpeta_mes):
    # la empresa no ha escrito su NIF; el membrete de todas las facturas lleva B04123456
    datos.guardar_ajuste("empresa", {"nombre": "Suministros La Vega, S.L."})
    filas = A.analizar_carpeta(str(carpeta_mes), datos)
    assert all("B04123456" not in f.nifs for f in filas)
    assert datos.empresa()["nif"] == "B04123456"  # y queda apuntado
    sin = [f for f in filas if f.archivo == "26-1080.pdf"][0]
    assert sin.estado == A.SIN_COINCIDENCIA and not sin.nifs  # nada que «aprender» por error
