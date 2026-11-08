# -*- coding: utf-8 -*-
"""
analisis.py — Recorre la carpeta de facturas y decide qué hacer con cada PDF:
enviarlo, avisar por teléfono, revisarlo a mano o saltarlo porque ya se hizo.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from nucleo.datos import AVISADO, ENVIADO, Datos, huella_archivo
from nucleo.emparejar import Identificacion, emails_de, identificar, leer_texto_pdf, nifs_en_texto

# Estados de una fila (el color de cada uno está en interfaz/estilo.py)
OK = "Lista"
SIN_EMAIL = "Sin email"
DUDOSA = "Dudosa"
SIN_COINCIDENCIA = "Sin cliente"
YA_ENVIADA = "Ya enviada"
YA_AVISADA = "Ya avisada"
ERROR_LECTURA = "No se lee"
ENVIADA = "Enviada"
ERROR_ENVIO = "Error al enviar"
AVISADA = "Avisada"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

PISTA_MINIMA = 0.4  # por debajo, «lo más parecido» solo confunde

AJUSTES_FACTURAS = {
    "carpeta_base": "",
    "patron_mes": "",          # vacío = las facturas están siempre en la carpeta base
    "ancla": "",
    "umbral": 0.7,
}


@dataclass
class Fila:
    archivo: str
    ruta: str
    huella: str = ""
    estado: str = SIN_COINCIDENCIA
    cliente_id: int | None = None
    cliente: str = ""
    email: str = ""
    telefono: str = ""
    puntuacion: float = 0.0
    metodo: str = ""
    nombre_leido: str = ""
    detalle: str = ""
    candidatos: list = field(default_factory=list)
    nifs: set = field(default_factory=set)

    def asignar(self, cliente: dict | None, metodo: str, puntuacion: float = 1.0) -> None:
        self.cliente_id = cliente["id"] if cliente else None
        self.cliente = cliente["nombre"] if cliente else ""
        self.email = cliente.get("email", "") if cliente else ""
        self.telefono = cliente.get("telefono", "") if cliente else ""
        self.metodo, self.puntuacion = metodo, puntuacion
        if not cliente:
            self.estado = SIN_COINCIDENCIA
        else:
            self.estado = OK if emails_de(self.email) else SIN_EMAIL


def ajustes_facturas(datos: Datos) -> dict:
    return {**AJUSTES_FACTURAS, **(datos.ajuste("facturas", {}) or {})}


def carpeta_del_mes(base: str, patron: str, dia: date | None = None) -> str:
    """
    Patrón con huecos: {MES} SEPTIEMBRE, {Mes} Septiembre, {mes} septiembre,
    {MM} 09, {M} 9, {AAAA} 2026, {AA} 26. Puede llevar subcarpetas:
    "{AAAA}/FACTURAS {MES} {AA}".
    """
    dia = dia or date.today()
    if not patron.strip():
        return base
    mes = MESES[dia.month - 1]
    huecos = {"MES": mes.upper(), "Mes": mes.capitalize(), "mes": mes, "MM": f"{dia.month:02d}",
              "M": str(dia.month), "AAAA": str(dia.year), "AA": str(dia.year)[-2:]}

    class _Seguro(dict):
        def __missing__(self, clave):
            return "{" + clave + "}"

    relativa = patron.format_map(_Seguro(huecos)).replace("\\", "/")
    return str(Path(base).joinpath(*[p for p in relativa.split("/") if p]))


def inferir_patron(carpeta_de_un_mes: str) -> tuple[str, str] | None:
    """
    A partir de la carpeta de un mes cualquiera, saca (carpeta base, patrón):
      .../Facturas/2026/FACTURAS SEPTIEMBRE 26 -> (.../Facturas, "{AAAA}/FACTURAS {MES} {AA}")
      .../Facturas/2026-09                     -> (.../Facturas, "{AAAA}-{MM}")
    None si el nombre no lleva ni mes ni año.
    """
    import re
    ruta = Path(carpeta_de_un_mes)
    nombre = ruta.name
    patron = nombre
    hallado = False
    for mes in MESES:
        for escrito, hueco in ((mes.upper(), "{MES}"), (mes.capitalize(), "{Mes}"), (mes, "{mes}")):
            if re.search(rf"(?<![A-Za-z]){escrito}(?![A-Za-z])", patron):
                patron = re.sub(rf"(?<![A-Za-z]){escrito}(?![A-Za-z])", hueco, patron)
                hallado = True
                break
        if hallado:
            break
    patron, n = re.subn(r"(?<!\d)(19|20)\d\d(?!\d)", "{AAAA}", patron)
    tiene_anio = n > 0
    if not hallado:  # sin nombre de mes: buscar el número junto al año (2026-09, 09.2026)
        patron, m = re.subn(r"(?<=\{AAAA\}[-_. ])(0[1-9]|1[0-2])(?!\d)|(?<!\d)(0[1-9]|1[0-2])(?=[-_. ]\{AAAA\})",
                            "{MM}", patron)
        hallado = m > 0
    elif not tiene_anio:
        patron, n = re.subn(r"(?<!\d)([2-9]\d)(?!\d)", "{AA}", patron)
        tiene_anio = n > 0
    if not hallado and not tiene_anio:
        return None
    base = ruta.parent
    if re.fullmatch(r"(19|20)\d\d", base.name):  # el año va en la carpeta de arriba
        base, patron = base.parent, "{AAAA}/" + patron
    return str(base), patron


def mes_pasado(dia: date | None = None) -> date:
    dia = dia or date.today()
    return date(dia.year - 1, 12, 1) if dia.month == 1 else date(dia.year, dia.month - 1, 1)


def pdfs_de(carpeta: str) -> list[Path]:
    return sorted((p for p in Path(carpeta).iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
                   and not p.name.startswith(".")), key=lambda p: p.name.lower())


def leer_pdf(ruta: Path, datos: Datos) -> tuple[Fila, str | None]:
    """Primera pasada: huella, ¿ya hecho?, y el texto. Si la fila ya está resuelta, el texto es None."""
    fila = Fila(archivo=ruta.name, ruta=str(ruta))
    try:
        fila.huella = huella_archivo(ruta)
    except OSError as e:
        fila.estado, fila.detalle = ERROR_LECTURA, f"No se puede abrir: {e}"
        return fila, None

    hecho = datos.resuelto(fila.archivo, fila.huella)
    if hecho:
        fila.estado = YA_ENVIADA if hecho["resultado"] == ENVIADO else YA_AVISADA
        fila.cliente, fila.email = hecho["cliente"], hecho["email"]
        fila.detalle = f"{'Enviada' if hecho['resultado'] == ENVIADO else 'Avisada'} el {hecho['fecha'][:16]}"
        return fila, None

    try:
        texto = leer_texto_pdf(ruta)
    except Exception as e:  # noqa: BLE001 — un PDF roto no para la búsqueda
        fila.estado, fila.detalle = ERROR_LECTURA, f"PDF dañado o protegido: {e}"
        return fila, None
    if not texto.strip():
        fila.estado, fila.detalle = ERROR_LECTURA, "El PDF no tiene texto (¿es un escaneo?). Asígnalo a mano."
        return fila, None
    return fila, texto


def nifs_propios(textos: list[str]) -> set[str]:
    """
    Un NIF que sale en más de la mitad de las facturas es el de tu empresa (va en
    el membrete). Así no se confunde con el de un cliente aunque no lo hayas
    escrito en Ajustes. Hacen falta al menos 3 facturas para saberlo.
    """
    if len(textos) < 3:
        return set()
    from collections import Counter
    cuenta = Counter(n for t in textos for n in nifs_en_texto(t))
    return {n for n, veces in cuenta.items() if veces > len(textos) / 2}


def identificar_fila(fila: Fila, texto: str, clientes: list[dict], empresa: dict, ajustes: dict,
                     ignorar: set[str] = frozenset()) -> Fila:
    ident: Identificacion = identificar(texto, clientes, empresa, ajustes.get("ancla", ""),
                                        float(ajustes.get("umbral", 0.7)), ignorar_nifs=ignorar)
    fila.nombre_leido, fila.candidatos, fila.nifs = ident.nombre_leido, ident.candidatos, ident.nifs
    por_id = {c["id"]: c for c in clientes}
    if ident.cliente_id is None:
        fila.estado = SIN_COINCIDENCIA
        if ident.candidatos and ident.candidatos[0][1] >= PISTA_MINIMA:
            c = por_id[ident.candidatos[0][0]]
            fila.detalle = f"Lo más parecido: {c['nombre']} ({ident.candidatos[0][1]:.0%}), pero no basta"
        else:
            fila.detalle = "Ningún cliente del directorio aparece en el PDF"
        return fila
    fila.asignar(por_id[ident.cliente_id], ident.metodo, ident.puntuacion)
    if ident.dudosa:
        otros = [por_id[i]["nombre"] for i, p, _ in ident.candidatos[:3]]
        fila.estado = DUDOSA
        fila.detalle = "Encajan varios: " + " / ".join(otros) + ". Elige el bueno."
    return fila


def analizar_pdf(ruta: Path, datos: Datos, clientes: list[dict], ajustes: dict) -> Fila:
    """Un PDF suelto (sin mirar el resto de la carpeta)."""
    fila, texto = leer_pdf(ruta, datos)
    return identificar_fila(fila, texto, clientes, datos.empresa(), ajustes) if texto is not None else fila


def analizar_carpeta(carpeta: str, datos: Datos, avance=None) -> list[Fila]:
    ajustes = ajustes_facturas(datos)
    clientes = datos.clientes()
    rutas = pdfs_de(carpeta)
    leidas = []
    for n, ruta in enumerate(rutas, 1):
        if avance:
            avance(n - 1, len(rutas), ruta.name)
        leidas.append(leer_pdf(ruta, datos))
    textos = [t for _, t in leidas if t is not None]
    propios = nifs_propios(textos)
    empresa = datos.empresa()
    if propios and not empresa.get("nif") and len(propios) == 1:
        empresa = {**empresa, "nif": next(iter(propios))}
        datos.guardar_ajuste("empresa", empresa)  # se apunta para la próxima vez
    filas = [identificar_fila(f, t, clientes, empresa, ajustes, propios) if t is not None else f for f, t in leidas]
    if avance:
        avance(len(rutas), len(rutas), "")
    return filas
