# -*- coding: utf-8 -*-
"""
autoprueba.py — Comprueba, sin abrir ventanas, que la app ya empaquetada
(.app / .exe) lleva todo lo que necesita: leer PDF, reconocer al cliente,
certificados SSL, llavero y montar y enviar un correo con adjunto (a un
servidor falso en el propio ordenador: no sale nada a Internet).

    Cartero --autoprueba factura.pdf [--salida resultado.txt]
"""

import json
import os
import socketserver
import tempfile
import threading
from pathlib import Path


class _ServidorMinimo:
    def __init__(self):
        self.recibido = b""
        fuera = self

        class M(socketserver.StreamRequestHandler):
            def handle(self):
                w = lambda t: self.wfile.write((t + "\r\n").encode())  # noqa: E731
                w("220 ok")
                while (l := self.rfile.readline()):
                    o = l.strip().upper()
                    if o == b"DATA":
                        w("354 ok")
                        while (d := self.rfile.readline()) not in (b".\r\n", b""):
                            fuera.recibido += d
                        w("250 ok")
                    elif o == b"QUIT":
                        w("221 ok")
                        return
                    else:
                        w("250 ok")

        self.s = socketserver.ThreadingTCPServer(("127.0.0.1", 0), M)
        self.puerto = self.s.server_address[1]
        threading.Thread(target=self.s.serve_forever, daemon=True).start()

    def cerrar(self):
        self.s.shutdown()
        self.s.server_close()


def ejecutar(rutas: list[str], escribir) -> int:
    fallos = 0
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CARTERO_DATOS"] = tmp
        from nucleo.correo import Conexion, _contexto_ssl, crear_mensaje
        from nucleo.emparejar import identificar, leer_texto_pdf
        cliente = {"id": 1, "nombre": "AGRICOLA FERVALIA", "email": "a@b.es", "nif": "", "alias": []}
        for ruta in rutas:
            try:
                texto = leer_texto_pdf(ruta)
                r = identificar(texto, [cliente])
                escribir(json.dumps({"archivo": Path(ruta).name, "caracteres": len(texto), "cliente": r.cliente_id,
                                     "metodo": r.metodo}, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001
                fallos += 1
                escribir(f"ERROR {ruta}: {type(e).__name__}: {e}")
        try:
            _contexto_ssl()
            import keyring
            escribir(f"llavero: {type(keyring.get_keyring()).__module__}")
            s = _ServidorMinimo()
            ajustes = {"email": "yo@x.es", "servidor": "127.0.0.1", "puerto": s.puerto, "seguridad": "ninguna"}
            msg = crear_mensaje(ajustes, {"asunto": "Prueba", "cuerpo": "Hola", "firma_logo": False}, {},
                                "c@d.es", {}, rutas[0] if rutas else None)
            with Conexion(ajustes, "") as c:
                c.enviar(msg)
            s.cerrar()
            escribir(f"correo: enviado al servidor falso ({len(s.recibido)} bytes)")
        except Exception as e:  # noqa: BLE001
            fallos += 1
            escribir(f"ERROR correo: {type(e).__name__}: {e}")
    return 1 if fallos else 0
