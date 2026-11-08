# -*- coding: utf-8 -*-
"""Ayudas para las pruebas: PDF de factura de mentira y un servidor de correo falso."""

import socketserver
import threading
from email import message_from_bytes, policy

import pymupdf


def crear_pdf(ruta, lineas: list[str]) -> str:
    doc = pymupdf.open()
    pagina = doc.new_page()
    y = 60
    for linea in lineas:
        pagina.insert_text((50, y), linea, fontsize=10)
        y += 16
    doc.save(ruta)
    doc.close()
    return str(ruta)


def factura_ejidosoft(ruta, cliente: str, numero: str = "26-1077", nif_cliente: str = "") -> str:
    """Membrete como el de Suministros La Vega: el cliente va justo bajo 'E-MAIL:'."""
    return crear_pdf(ruta, [
        "SUMINISTROS LA VEGA, S.L.", "C/ Ejemplo 12 - 04700 El Ejido (Almeria)", "CIF: B04123456",
        "TELF: 950 000 000  E-MAIL: info@suministroslavega.es",
        cliente, "Ctra. de Almerimar, km 3", f"NIF: {nif_cliente}" if nif_cliente else "",
        f"FACTURA N. {numero}   FECHA 30/09/2026", "Abono 15-15-15  25 sacos   312,50",
        "BASE 312,50  IVA 10% 31,25  TOTAL 343,75 EUR",
    ])


def factura_otro_programa(ruta, cliente: str, nif_cliente: str = "") -> str:
    """Otro formato: el cliente a la derecha, con la palabra 'Cliente:' delante y sin ancla."""
    return crear_pdf(ruta, [
        "ASESORIA MIRASOL", "NIF B04999999", "",
        "Factura 2026/0412                       Cliente: " + cliente,
        "Fecha: 01/10/2026                       " + (f"CIF {nif_cliente}" if nif_cliente else ""),
        "Honorarios asesoria fiscal tercer trimestre     120,00",
        "IVA 21%  25,20     TOTAL 145,20",
    ])


class ServidorCorreoFalso:
    """
    SMTP mínimo en 127.0.0.1 sin cifrado ni contraseña: guarda lo que recibe en
    .mensajes para comprobarlo. Con rechazar=True contesta 550 a los destinatarios.
    """

    def __init__(self, rechazar: bool = False):
        self.mensajes: list[dict] = []
        self.rechazar = rechazar
        self.sesiones = 0
        fuera = self

        class Manejador(socketserver.StreamRequestHandler):
            def handle(self):
                self.escribir("220 falso ESMTP")
                destinos, origen = [], ""
                while True:
                    linea = self.rfile.readline()
                    if not linea:
                        return
                    orden = linea.decode("utf-8", "replace").strip()
                    mayus = orden.upper()
                    if mayus.startswith(("EHLO", "HELO")):
                        self.escribir("250-falso\r\n250-AUTH PLAIN LOGIN\r\n250 8BITMIME")
                    elif mayus.startswith("AUTH"):
                        fuera.sesiones += 1
                        self.escribir("235 Dentro")
                    elif mayus.startswith("MAIL FROM"):
                        origen, destinos = orden[10:], []
                        self.escribir("250 OK")
                    elif mayus.startswith("RCPT TO"):
                        if fuera.rechazar:
                            self.escribir("550 No existe ese buzon")
                        else:
                            destinos.append(orden[8:].strip("<> "))
                            self.escribir("250 OK")
                    elif mayus == "DATA":
                        self.escribir("354 Adelante")
                        datos = b""
                        while True:
                            l = self.rfile.readline()
                            if l in (b".\r\n", b".\n", b""):
                                break
                            datos += l[1:] if l.startswith(b"..") else l
                        fuera.mensajes.append({"de": origen, "para": destinos,
                                               "mensaje": message_from_bytes(datos, policy=policy.default)})
                        self.escribir("250 Recibido")
                    elif mayus == "QUIT":
                        self.escribir("221 Adios")
                        return
                    else:
                        self.escribir("250 OK")

            def escribir(self, texto):
                self.wfile.write((texto + "\r\n").encode())

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.servidor = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Manejador)
        self.puerto = self.servidor.server_address[1]
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def ajustes(self) -> dict:
        return {"proveedor": "Otro (lo pongo yo)", "email": "yo@miempresa.es", "servidor": "127.0.0.1",
                "puerto": self.puerto, "seguridad": "ninguna", "usuario": "", "nombre_remitente": "",
                "responder_a": "", "copia_oculta": ""}

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()
