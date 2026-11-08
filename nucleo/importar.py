# -*- coding: utf-8 -*-
"""
importar.py — Carga la lista de clientes desde lo que la empresa ya tenga:
un Excel (.xlsx), un CSV o una tabla dentro de un Word (.docx).

Las columnas se reconocen por su título ("Cliente", "Razón social", "Correo",
"E-mail", "Móvil", "CIF"…), da igual el orden. Si no hay títulos, se adivina
por el contenido: la columna con "@" es el email, etc.
"""

import csv
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from nucleo.emparejar import sin_acentos

TITULOS = {
    "nombre": ("cliente", "nombre", "razon social", "empresa", "denominacion", "titular", "nombre cliente"),
    "email": ("email", "e-mail", "correo", "mail", "correo electronico", "e mail"),
    "telefono": ("telefono", "tel", "movil", "tlf", "telf", "celular", "whatsapp", "phone"),
    "nif": ("nif", "cif", "dni", "nif/cif", "cif/nif", "nie", "vat"),
    "nota": ("nota", "notas", "observaciones", "comentario", "nota_sin_email"),
}


def _clave_titulo(texto: str) -> str | None:
    t = re.sub(r"[^a-z/ -]", "", sin_acentos(str(texto)).lower()).strip()
    for campo, opciones in TITULOS.items():
        if t in opciones or any(t.startswith(o) for o in opciones if len(o) > 3):
            return campo
    return None


def _desde_tabla(filas: list[list[str]]) -> list[dict]:
    filas = [[(c or "").strip() for c in f] for f in filas if any((c or "").strip() for c in f)]
    if not filas:
        return []
    columnas = {}
    for i, titulo in enumerate(filas[0]):
        campo = _clave_titulo(titulo)
        if campo and campo not in columnas.values():
            columnas[i] = campo
    if "nombre" in columnas.values():
        datos = filas[1:]
    else:  # sin títulos: se adivina por el contenido
        datos, columnas = filas, _adivinar_columnas(filas)
    clientes = []
    for f in datos:
        c = {campo: (f[i] if i < len(f) else "") for i, campo in columnas.items()}
        if c.get("nombre"):
            c["telefono"] = re.sub(r"\.0$", "", c.get("telefono", ""))  # Excel guarda 667042506 como 667042506.0
            clientes.append({k: c.get(k, "") for k in TITULOS})
    return clientes


def _adivinar_columnas(filas) -> dict:
    ancho = max(len(f) for f in filas)
    columnas = {}
    for i in range(ancho):
        valores = [f[i] for f in filas if i < len(f) and f[i]]
        if not valores:
            continue
        if sum("@" in v for v in valores) > len(valores) / 2:
            columnas[i] = "email"
        elif sum(bool(re.fullmatch(r"[+\d\s().-]{9,}", v)) for v in valores) > len(valores) / 2:
            columnas[i] = "telefono"
    libres = [i for i in range(ancho) if i not in columnas]
    if libres:
        columnas[libres[0]] = "nombre"
    return columnas


def leer_xlsx(ruta) -> list[dict]:
    from openpyxl import load_workbook
    libro = load_workbook(ruta, read_only=True, data_only=True)
    mejor = []
    for hoja in libro.worksheets:  # la hoja que más clientes dé
        filas = [["" if v is None else str(v) for v in fila] for fila in hoja.iter_rows(values_only=True)]
        clientes = _desde_tabla(filas)
        if len(clientes) > len(mejor):
            mejor = clientes
    libro.close()
    return mejor


def leer_csv(ruta) -> list[dict]:
    crudo = Path(ruta).read_bytes()
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = crudo.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    separador = ";" if texto.count(";") > texto.count(",") else ","
    return _desde_tabla(list(csv.reader(texto.splitlines(), delimiter=separador)))


def leer_docx(ruta) -> list[dict]:
    """Tablas de un Word, sin depender de python-docx: un .docx es un zip con XML."""
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(ruta) as z:
        raiz = ElementTree.fromstring(z.read("word/document.xml"))
    clientes = []
    for tabla in raiz.iter(f"{w}tbl"):
        filas = []
        for tr in tabla.iter(f"{w}tr"):
            celdas = []
            for tc in tr.findall(f"{w}tc"):
                parrafos = ["".join(t.text or "" for t in p.iter(f"{w}t")) for p in tc.iter(f"{w}p")]
                celdas.append(" ".join(p for p in parrafos if p.strip()))
            filas.append(celdas)
        clientes += _desde_tabla(filas)
    return clientes


def leer_clientes(ruta) -> list[dict]:
    extension = Path(ruta).suffix.lower()
    if extension in (".xlsx", ".xlsm"):
        return leer_xlsx(ruta)
    if extension in (".csv", ".txt"):
        return leer_csv(ruta)
    if extension == ".docx":
        return leer_docx(ruta)
    raise ValueError("Formato no admitido. Usa un Excel (.xlsx), un CSV o un Word (.docx).")


def exportar_xlsx(clientes: list[dict], ruta) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Clientes"
    hoja.append(["Cliente", "Email", "Teléfono", "NIF", "Nota"])
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    for c in clientes:
        hoja.append([c["nombre"], c["email"], c["telefono"], c["nif"], c["nota"]])
    for col, ancho in zip("ABCDE", (40, 36, 16, 14, 30)):
        hoja.column_dimensions[col].width = ancho
    libro.save(ruta)
