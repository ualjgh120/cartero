# -*- coding: utf-8 -*-
"""
datos.py — Todo lo que la app recuerda, en un único archivo SQLite:

  ajustes   empresa, correo, mensaje, carpetas (clave -> JSON)
  clientes  nombre, NIF, email, teléfono, nota y alias aprendidos
  envios    historial: qué PDF se envió o avisó, a quién y cuándo

Un PDF se reconoce por su huella (SHA-256 del contenido), así que aunque lo
cambies de nombre o de carpeta no se vuelve a enviar. Las entradas importadas
de la versión antigua (log_envios.csv) solo traen el nombre del archivo, y se
comparan por nombre.
"""

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from nucleo.config import carpeta_datos

ENVIADO = "ENVIADO"
AVISADO = "AVISADO_TELEFONO"
ERROR = "ERROR"
RESUELTOS = (ENVIADO, AVISADO)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    nif TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    telefono TEXT NOT NULL DEFAULT '',
    nota TEXT NOT NULL DEFAULT '',
    alias TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS envios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,
    archivo TEXT NOT NULL,
    huella TEXT NOT NULL DEFAULT '',
    cliente TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    resultado TEXT NOT NULL,
    detalle TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS envios_huella ON envios (huella);
"""


def huella_archivo(ruta) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 16), b""):
            h.update(bloque)
    return h.hexdigest()


class Datos:
    def __init__(self, ruta: Path | None = None):
        self.ruta = Path(ruta) if ruta else carpeta_datos() / "cartero.sqlite"
        self.db = sqlite3.connect(self.ruta, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(ESQUEMA)
        self.db.commit()

    # ------------------------------------------------------------ ajustes
    def ajuste(self, clave: str, defecto=None):
        fila = self.db.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
        return json.loads(fila["valor"]) if fila else defecto

    def guardar_ajuste(self, clave: str, valor) -> None:
        self.db.execute("INSERT OR REPLACE INTO ajustes (clave, valor) VALUES (?, ?)",
                        (clave, json.dumps(valor, ensure_ascii=False)))
        self.db.commit()

    def empresa(self) -> dict:
        return self.ajuste("empresa", {}) or {}

    def configurada(self) -> bool:
        """El asistente inicial ya se completó."""
        return bool(self.ajuste("asistente_completado", False))

    # ------------------------------------------------------------ clientes
    def clientes(self) -> list[dict]:
        filas = self.db.execute("SELECT * FROM clientes ORDER BY nombre COLLATE NOCASE").fetchall()
        return [self._cliente(f) for f in filas]

    def cliente(self, id_cliente: int) -> dict | None:
        fila = self.db.execute("SELECT * FROM clientes WHERE id = ?", (id_cliente,)).fetchone()
        return self._cliente(fila) if fila else None

    @staticmethod
    def _cliente(fila) -> dict:
        c = dict(fila)
        c["alias"] = json.loads(c["alias"] or "[]")
        return c

    def guardar_cliente(self, cliente: dict) -> int:
        valores = (cliente.get("nombre", "").strip(), cliente.get("nif", "").strip().upper(),
                   cliente.get("email", "").strip(), cliente.get("telefono", "").strip(),
                   cliente.get("nota", "").strip(), json.dumps(cliente.get("alias", []), ensure_ascii=False))
        if cliente.get("id"):
            self.db.execute("UPDATE clientes SET nombre=?, nif=?, email=?, telefono=?, nota=?, alias=? WHERE id=?",
                            valores + (cliente["id"],))
            id_cliente = cliente["id"]
        else:
            id_cliente = self.db.execute(
                "INSERT INTO clientes (nombre, nif, email, telefono, nota, alias) VALUES (?, ?, ?, ?, ?, ?)",
                valores).lastrowid
        self.db.commit()
        return id_cliente

    def borrar_cliente(self, id_cliente: int) -> None:
        self.db.execute("DELETE FROM clientes WHERE id = ?", (id_cliente,))
        self.db.commit()

    def importar_clientes(self, nuevos: list[dict]) -> tuple[int, int]:
        """Añade los que no existan y completa email/teléfono/NIF vacíos de los que ya están."""
        from nucleo.emparejar import normalizar
        existentes = {normalizar(c["nombre"]): c for c in self.clientes()}
        anadidos = actualizados = 0
        for nuevo in nuevos:
            if not nuevo.get("nombre", "").strip():
                continue
            actual = existentes.get(normalizar(nuevo["nombre"]))
            if actual is None:
                self.guardar_cliente(nuevo)
                anadidos += 1
                continue
            cambiado = False
            for campo in ("email", "telefono", "nif", "nota"):
                if not actual.get(campo) and nuevo.get(campo):
                    actual[campo] = nuevo[campo]
                    cambiado = True
            if cambiado:
                self.guardar_cliente(actual)
                actualizados += 1
        return anadidos, actualizados

    def aprender_alias(self, id_cliente: int, alias: str) -> None:
        cliente = self.cliente(id_cliente)
        alias = alias.strip()
        if cliente and alias and alias not in cliente["alias"]:
            cliente["alias"].append(alias)
            self.guardar_cliente(cliente)

    # ------------------------------------------------------------ envíos
    def registrar(self, archivo: str, huella: str, cliente: str, email: str, resultado: str, detalle: str = "") -> None:
        self.db.execute(
            "INSERT INTO envios (fecha, archivo, huella, cliente, email, resultado, detalle) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), archivo, huella, cliente, email, resultado, detalle))
        self.db.commit()

    def resuelto(self, archivo: str, huella: str) -> dict | None:
        """Último envío o aviso de este PDF, si lo hay (por huella; o por nombre si viene de la versión antigua)."""
        marcas = ",".join("?" * len(RESUELTOS))
        fila = self.db.execute(
            f"SELECT * FROM envios WHERE resultado IN ({marcas}) AND (huella = ? OR (huella = '' AND archivo = ?)) "
            "ORDER BY id DESC LIMIT 1", (*RESUELTOS, huella, archivo)).fetchone()
        return dict(fila) if fila else None

    def historial(self, limite: int = 5000) -> list[dict]:
        return [dict(f) for f in self.db.execute("SELECT * FROM envios ORDER BY id DESC LIMIT ?", (limite,))]

    def importar_log_antiguo(self, ruta_csv) -> int:
        """log_envios.csv de la versión anterior (fecha, archivo_pdf, …, resultado, detalle)."""
        import csv
        n = 0
        with open(ruta_csv, newline="", encoding="utf-8-sig") as f:
            for fila in csv.DictReader(f):
                if not fila.get("archivo_pdf") or not fila.get("resultado"):
                    continue
                self.db.execute(
                    "INSERT INTO envios (fecha, archivo, huella, cliente, email, resultado, detalle) VALUES (?, ?, '', ?, ?, ?, ?)",
                    (fila.get("fecha", ""), fila["archivo_pdf"], fila.get("cliente_directorio", ""),
                     fila.get("email", ""), fila["resultado"], fila.get("detalle", "")))
                n += 1
        self.db.commit()
        return n
