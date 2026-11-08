# -*- coding: utf-8 -*-
"""
emparejar.py — Averigua a qué cliente del directorio va cada PDF.

No depende del programa de facturación: busca en el texto del PDF, de más
seguro a menos,

  1. el NIF de un cliente (sin contar el de tu empresa),
  2. el email de un cliente,
  3. el nombre que hay tras un "texto ancla" (opcional; p. ej. EjidoSoft pone
     el cliente justo debajo de la línea "E-MAIL:"),
  4. el nombre del cliente o un alias aprendido, escrito en cualquier parte.

Si dos clientes distintos encajan casi igual, no se elige ninguno ("dudosa"):
mandar una factura a quien no es resulta peor que no mandarla.
"""

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

SUFIJOS_LEGALES = {
    "sl", "sa", "slu", "sau", "sat", "scp", "sca", "scl", "cb", "sll", "slne", "sc", "scoop", "coop",
    "sociedad", "limitada", "anonima", "unipersonal", "laboral", "civil", "agraria", "transformacion",
}
PALABRAS_VACIAS = {"de", "del", "la", "las", "el", "los", "y", "e", "en", "cia", "hnos"}

DUDA_MARGEN = 0.08  # si el segundo cliente se queda a menos de esto del primero, es dudosa

_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_RE_CIF = re.compile(r"\b(?:ES)?[\s-]?([ABCDEFGHJNPQRSUVW])[\s.-]?(\d{7})[\s.-]?([0-9A-J])\b")
_RE_DNI = re.compile(r"(?<![A-Z0-9-])(\d{8})[\s-]?([A-Z])\b")
_RE_NIE = re.compile(r"\b([XYZ])[\s-]?(\d{7})[\s-]?([A-Z])\b")


# ---------------------------------------------------------------- texto
def sin_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")


def tokens(texto: str) -> list[str]:
    """'Hortofrutícola Costa de Málaga, S.A.T.' -> ['hortofruticola', 'costa', 'malaga']"""
    t = sin_acentos(texto).lower()
    t = re.sub(r"\b([a-z])\.", r"\1", t)            # s.a.t. -> sat
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\b([a-z]) (?=[a-z]\b)", r"\1", t)   # s l -> sl
    return [p for p in t.split()
            if p not in SUFIJOS_LEGALES and p not in PALABRAS_VACIAS and not p.isdigit() and len(p) > 1]


def normalizar(texto: str) -> str:
    return " ".join(tokens(texto))


def normalizar_nif(nif: str) -> str:
    nif = re.sub(r"[^A-Z0-9]", "", sin_acentos(nif).upper())
    return nif[2:] if nif.startswith("ES") and len(nif) == 11 else nif


def nifs_en_texto(texto: str) -> set[str]:
    t = re.sub(r"(?<=\d)\.(?=\d)", "", sin_acentos(texto).upper())  # B-04.123.456 -> B-04123456
    encontrados = {"".join(m.groups()) for m in _RE_CIF.finditer(t)}
    encontrados |= {"".join(m.groups()) for m in _RE_DNI.finditer(t)}
    encontrados |= {"".join(m.groups()) for m in _RE_NIE.finditer(t)}
    return encontrados


def emails_en_texto(texto: str) -> set[str]:
    return {e.lower().rstrip(".") for e in _RE_EMAIL.findall(texto)}


def emails_de(campo: str) -> list[str]:
    """Un cliente puede tener varios emails: 'a@x.es; b@x.es'."""
    return [e.strip() for e in re.split(r"[;,\s]+", campo or "") if "@" in e]


def leer_texto_pdf(ruta, paginas: int = 2) -> str:
    import pdfplumber
    with pdfplumber.open(ruta) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages[:paginas])


def texto_tras_ancla(texto: str, ancla: str) -> str:
    """La primera línea no vacía después de la que contiene el ancla (sin distinguir mayúsculas)."""
    if not ancla:
        return ""
    lineas = [l.strip() for l in texto.splitlines()]
    for i, linea in enumerate(lineas):
        if ancla.lower() in linea.lower():
            for siguiente in lineas[i + 1:]:
                if siguiente:
                    return siguiente
            return ""
    return ""


# ---------------------------------------------------------------- puntuar
def similitud(a: str, b: str) -> float:
    a, b = normalizar(a), normalizar(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if f" {a} " in f" {b} " or f" {b} " in f" {a} ":
        return 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


class TextoFactura:
    """El texto del PDF ya troceado, para buscar muchos nombres sin repetir trabajo."""

    def __init__(self, texto: str, quitar: list[str] = ()):
        norm = " " + normalizar(texto) + " "
        for frase in quitar:  # el nombre de tu empresa sale en todas tus facturas: fuera
            f = normalizar(frase)
            if f:
                norm = norm.replace(f" {f} ", " ")
        self.norm = norm
        self.palabras = set(norm.split())
        self._parecidas: dict[str, bool] = {}

    def contiene_palabra(self, palabra: str) -> bool:
        if palabra in self.palabras:
            return True
        if len(palabra) < 5:
            return False
        if palabra not in self._parecidas:  # admite una errata: "Hortofruticola" / "Hortofrutícula"
            self._parecidas[palabra] = bool(difflib.get_close_matches(palabra, self.palabras, n=1, cutoff=0.88))
        return self._parecidas[palabra]

    def puntuar_nombre(self, nombre: str) -> float:
        partes = tokens(nombre)
        if not partes:
            return 0.0
        frase = " ".join(partes)
        if f" {frase} " in self.norm:
            # un nombre de una sola palabra corta ("Agro") es poco fiable aunque aparezca
            return 0.75 if len(partes) == 1 and len(frase) <= 4 else 1.0
        halladas = sum(self.contiene_palabra(p) for p in partes)
        if halladas == len(partes):
            return 0.85 if len(partes) > 1 else 0.7
        return max(0.0, 0.85 * halladas / len(partes) - 0.1)


@dataclass
class Identificacion:
    cliente_id: int | None = None
    puntuacion: float = 0.0
    metodo: str = ""                 # nif, email, ancla, nombre, alias, manual
    nombre_leido: str = ""           # lo que hay tras el ancla, si se configuró
    dudosa: bool = False
    candidatos: list[tuple[int, float, str]] = field(default_factory=list)  # (id, puntuación, método)
    nifs: set[str] = field(default_factory=set)       # NIF del PDF que no son de tu empresa


def identificar(texto: str, clientes: list[dict], empresa: dict | None = None,
                ancla: str = "", umbral: float = 0.7, ignorar_nifs: set[str] = frozenset()) -> Identificacion:
    empresa = empresa or {}
    nif_propio = normalizar_nif(empresa.get("nif", ""))
    emails_propios = {e.lower() for e in emails_de(empresa.get("email", ""))}

    nifs = nifs_en_texto(texto) - {nif_propio} - set(ignorar_nifs)
    emails = emails_en_texto(texto) - emails_propios
    leido = texto_tras_ancla(texto, ancla)
    tf = TextoFactura(texto, quitar=[empresa.get("nombre", "")])

    mejor: dict[int, tuple[float, str]] = {}

    def anotar(id_cliente: int, puntos: float, metodo: str):
        if puntos > mejor.get(id_cliente, (0.0, ""))[0]:
            mejor[id_cliente] = (puntos, metodo)

    for c in clientes:
        if c.get("nif") and normalizar_nif(c["nif"]) in nifs:
            anotar(c["id"], 1.0, "nif")
        if any(e.lower() in emails for e in emails_de(c.get("email", ""))):
            anotar(c["id"], 1.0, "email")
        if leido:
            anotar(c["id"], max([similitud(leido, c["nombre"])] + [similitud(leido, a) for a in c.get("alias", [])]),
                   "ancla")
        anotar(c["id"], tf.puntuar_nombre(c["nombre"]), "nombre")
        for alias in c.get("alias", []):
            anotar(c["id"], tf.puntuar_nombre(alias), "alias")

    candidatos = sorted(((i, p, m) for i, (p, m) in mejor.items() if p > 0), key=lambda x: -x[1])
    candidatos = _quitar_contenidos(candidatos, {c["id"]: c for c in clientes})
    resultado = Identificacion(nombre_leido=leido, candidatos=candidatos[:5], nifs=nifs)
    if not candidatos or candidatos[0][1] < umbral:
        return resultado
    primero = candidatos[0]
    resultado.cliente_id, resultado.puntuacion, resultado.metodo = primero
    if len(candidatos) > 1 and candidatos[1][1] >= umbral and primero[1] - candidatos[1][1] < DUDA_MARGEN:
        resultado.dudosa = True
    return resultado


def _quitar_contenidos(candidatos, por_id):
    """
    Si salen "Agro Sur" y "Agro Sur Export" y el PDF dice "Agro Sur Export",
    el bueno es el más largo: el corto solo aparece porque está dentro.
    """
    nombres = {i: normalizar(por_id[i]["nombre"]) for i, _, _ in candidatos}
    fuera = set()
    for i, p, m in candidatos:
        for j, q, n in candidatos:
            if i != j and m == n == "nombre" and p == q and nombres[i] and nombres[i] != nombres[j] \
                    and f" {nombres[i]} " in f" {nombres[j]} ":
                fuera.add(i)
    return [c for c in candidatos if c[0] not in fuera]
