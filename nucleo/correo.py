# -*- coding: utf-8 -*-
"""
correo.py — Envío por SMTP con cualquier proveedor.

La contraseña no se guarda en la base de datos: va al llavero del sistema
(Llavero de macOS / Administrador de credenciales de Windows). Solo si el
llavero no está disponible se guarda en la base de datos, y se avisa.
"""

import base64
import mimetypes
import smtplib
import socket
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape
from pathlib import Path

from nucleo.config import NOMBRE_APP
from nucleo.emparejar import emails_de


@dataclass(frozen=True)
class Proveedor:
    nombre: str
    servidor: str
    puerto: int
    seguridad: str              # "starttls", "ssl" o "ninguna"
    ayuda: str
    enlace: str = ""            # dónde se crea la contraseña de aplicación
    dominios: tuple = ()


PROVEEDORES = [
    Proveedor("Gmail", "smtp.gmail.com", 587, "starttls",
              "Gmail no deja usar tu contraseña normal. Necesitas una «contraseña de aplicación»: "
              "activa la verificación en dos pasos en tu cuenta de Google y luego crea la contraseña "
              "en el enlace (ponle de nombre «Facturas»). Son 16 letras; pégalas aquí.",
              "https://myaccount.google.com/apppasswords", ("gmail.com", "googlemail.com")),
    Proveedor("Google Workspace (correo de empresa en Google)", "smtp.gmail.com", 587, "starttls",
              "Igual que Gmail: hace falta verificación en dos pasos y una contraseña de aplicación. "
              "Si no te deja crearla, el administrador de tu dominio tiene que permitirlo.",
              "https://myaccount.google.com/apppasswords"),
    Proveedor("Outlook / Hotmail", "smtp-mail.outlook.com", 587, "starttls",
              "Microsoft está retirando el acceso con contraseña para programas externos. Prueba con una "
              "contraseña de aplicación (requiere verificación en dos pasos). Si la prueba falla, usa "
              "Gmail o el correo de tu dominio.",
              "https://account.live.com/proofs/AppPassword", ("outlook.com", "outlook.es", "hotmail.com",
                                                              "hotmail.es", "live.com", "msn.com")),
    Proveedor("Microsoft 365 (correo de empresa en Microsoft)", "smtp.office365.com", 587, "starttls",
              "El administrador de Microsoft 365 tiene que activar «SMTP autenticado» para este buzón. "
              "Si la prueba falla con un error de autenticación, es por eso."),
    Proveedor("IONOS (1&1)", "smtp.ionos.es", 587, "starttls",
              "Usa el email completo y la contraseña del buzón."),
    Proveedor("Hostinger", "smtp.hostinger.com", 465, "ssl",
              "Usa el email completo y la contraseña del buzón."),
    Proveedor("Zoho Mail", "smtp.zoho.eu", 465, "ssl",
              "Si tienes la verificación en dos pasos, crea una contraseña específica de aplicación en Zoho.",
              "https://accounts.zoho.eu/home#security/app_password", ("zoho.com", "zoho.eu", "zohomail.eu")),
    Proveedor("iCloud", "smtp.mail.me.com", 587, "starttls",
              "Crea una «contraseña específica para apps» en tu cuenta de Apple y pégala aquí.",
              "https://account.apple.com", ("icloud.com", "me.com", "mac.com")),
    Proveedor("Yahoo", "smtp.mail.yahoo.com", 465, "ssl",
              "Yahoo pide una contraseña de aplicación: Seguridad de la cuenta → Generar contraseña de aplicación.",
              "https://login.yahoo.com/account/security", ("yahoo.com", "yahoo.es")),
    Proveedor("Otro (lo pongo yo)", "", 587, "starttls",
              "Los datos del servidor de salida (SMTP) te los da quien te lleva el correo o la web. "
              "Casi siempre es puerto 587 con STARTTLS, o 465 con SSL."),
]
OTRO = PROVEEDORES[-1]


def proveedor_por_nombre(nombre: str) -> Proveedor:
    return next((p for p in PROVEEDORES if p.nombre == nombre), OTRO)


def adivinar_proveedor(email: str) -> Proveedor | None:
    dominio = email.rsplit("@", 1)[-1].lower().strip() if "@" in email else ""
    return next((p for p in PROVEEDORES if dominio in p.dominios), None)


AJUSTES_CORREO = {
    "proveedor": "Gmail",
    "email": "",
    "servidor": "smtp.gmail.com",
    "puerto": 587,
    "seguridad": "starttls",
    "usuario": "",               # vacío = el propio email
    "nombre_remitente": "",
    "responder_a": "",
    "copia_oculta": "",          # p. ej. tu propio correo, para tener copia de todo
}

AJUSTES_MENSAJE = {
    "asunto": "Factura {factura} - {empresa}",
    "cuerpo": ("Buenos días,\n\n"
               "Le adjuntamos su factura {factura}.\n\n"
               "Para cualquier duda, quedamos a su disposición.\n\n"
               "Un saludo,\n{empresa}"),
    "firma_logo": True,
}

HUECOS = {
    "{cliente}": "nombre del cliente",
    "{factura}": "número de factura (nombre del PDF)",
    "{empresa}": "nombre de tu empresa",
    "{mes}": "mes actual",
    "{año}": "año actual",
}


# ---------------------------------------------------------------- contraseña
def _usuario_llavero(ajustes: dict) -> str:
    return (ajustes.get("usuario") or ajustes.get("email") or "").strip().lower()


def guardar_clave(datos, ajustes: dict, clave: str) -> bool:
    """Devuelve True si quedó en el llavero del sistema, False si tuvo que ir a la base de datos."""
    usuario = _usuario_llavero(ajustes)
    try:
        import keyring
        keyring.set_password(NOMBRE_APP, usuario, clave)
        datos.guardar_ajuste("clave_local", None)
        return True
    except Exception:  # noqa: BLE001 — sin llavero (algunos Linux, sesiones raras)
        datos.guardar_ajuste("clave_local", {usuario: base64.b64encode(clave.encode()).decode()})
        return False


def leer_clave(datos, ajustes: dict) -> str:
    usuario = _usuario_llavero(ajustes)
    try:
        import keyring
        clave = keyring.get_password(NOMBRE_APP, usuario)
        if clave:
            return clave
    except Exception:  # noqa: BLE001
        pass
    local = datos.ajuste("clave_local") or {}
    return base64.b64decode(local[usuario]).decode() if usuario in local else ""


# ---------------------------------------------------------------- mensaje
def rellenar(plantilla: str, valores: dict) -> str:
    texto = plantilla
    for hueco, valor in valores.items():
        texto = texto.replace("{" + hueco + "}", str(valor))
    return texto


def valores_para(cliente: str, archivo: str, empresa: dict) -> dict:
    from datetime import date
    from nucleo.analisis import MESES
    hoy = date.today()
    return {"cliente": cliente, "factura": Path(archivo).stem, "empresa": empresa.get("nombre", ""),
            "mes": MESES[hoy.month - 1], "año": str(hoy.year)}


def crear_mensaje(ajustes_correo: dict, mensaje: dict, empresa: dict, para: str, valores: dict,
                  adjunto: str | None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = rellenar(mensaje["asunto"], valores)
    remitente = ajustes_correo.get("nombre_remitente") or empresa.get("nombre", "")
    msg["From"] = formataddr((remitente, ajustes_correo["email"]))
    msg["To"] = ", ".join(emails_de(para))
    if ajustes_correo.get("responder_a"):
        msg["Reply-To"] = ajustes_correo["responder_a"]
    cuerpo = rellenar(mensaje["cuerpo"], valores)
    msg.set_content(cuerpo)

    logo = empresa.get("logo")
    if mensaje.get("firma_logo") and logo and Path(logo).exists():
        cid = make_msgid(domain="cartero.local")
        html = ("<div style=\"font-family: Arial, sans-serif; font-size: 14px; color: #222;\">"
                + escape(cuerpo).replace("\n", "<br>")
                + f"<br><br><img src=\"cid:{cid[1:-1]}\" alt=\"{escape(empresa.get('nombre', ''))}\" "
                  "style=\"max-height: 70px; max-width: 240px;\"></div>")
        msg.add_alternative(html, subtype="html")
        tipo = (mimetypes.guess_type(logo)[0] or "image/png").split("/")
        msg.get_payload()[1].add_related(Path(logo).read_bytes(), maintype=tipo[0], subtype=tipo[1], cid=cid)

    if adjunto:
        msg.add_attachment(Path(adjunto).read_bytes(), maintype="application", subtype="pdf",
                           filename=Path(adjunto).name)
    return msg


# ---------------------------------------------------------------- conexión
def _contexto_ssl() -> ssl.SSLContext:
    # dentro de la app empaquetada no siempre están los certificados del sistema: se usan los de certifi
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


class Conexion:
    """Una sola conexión para mandar muchos correos seguidos: `with Conexion(...) as c: c.enviar(msg)`."""

    def __init__(self, ajustes: dict, clave: str, espera: float = 30):
        self.ajustes, self.clave, self.espera = ajustes, clave, espera
        self.smtp = None

    def __enter__(self):
        a = self.ajustes
        servidor, puerto = a["servidor"].strip(), int(a["puerto"])
        if a.get("seguridad") == "ssl":
            self.smtp = smtplib.SMTP_SSL(servidor, puerto, timeout=self.espera, context=_contexto_ssl())
        else:
            self.smtp = smtplib.SMTP(servidor, puerto, timeout=self.espera)
            if a.get("seguridad", "starttls") == "starttls":
                self.smtp.starttls(context=_contexto_ssl())
        if self.clave:
            self.smtp.login((a.get("usuario") or a["email"]).strip(), self.clave)
        return self

    def enviar(self, msg: EmailMessage) -> None:
        destinos = emails_de(msg["To"])
        cco = emails_de(self.ajustes.get("copia_oculta", ""))
        self.smtp.send_message(msg, to_addrs=destinos + cco)

    def __exit__(self, *_):
        try:
            self.smtp.quit()
        except Exception:  # noqa: BLE001
            pass


def probar(ajustes: dict, clave: str) -> None:
    """Conecta e inicia sesión sin enviar nada. Lanza la excepción si algo falla."""
    with Conexion(ajustes, clave, espera=20):
        pass


def explicar_error(e: Exception, ajustes: dict | None = None) -> str:
    """Traduce el error técnico a algo que se entienda, y qué hacer."""
    proveedor = proveedor_por_nombre((ajustes or {}).get("proveedor", ""))
    if isinstance(e, smtplib.SMTPAuthenticationError):
        texto = "El servidor no acepta el email o la contraseña."
        if proveedor.enlace:
            texto += " Recuerda que hace falta una contraseña de aplicación, no la normal."
        return texto
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return "El servidor ha rechazado la dirección del cliente. Revisa que el email esté bien escrito."
    if isinstance(e, smtplib.SMTPSenderRefused):
        return "El servidor no deja enviar desde ese remitente. Revisa el email remitente."
    if isinstance(e, socket.gaierror):
        return "No se encuentra el servidor. Revisa el nombre del servidor y que haya Internet."
    if isinstance(e, (socket.timeout, TimeoutError)):
        return "El servidor no responde. Revisa el puerto, o puede que la red de la oficina lo bloquee."
    if isinstance(e, ConnectionRefusedError):
        return "El servidor rechaza la conexión en ese puerto. Prueba 587 con STARTTLS o 465 con SSL."
    if isinstance(e, (ssl.SSLError, smtplib.SMTPServerDisconnected)):
        return ("Falla la conexión segura. Suele ser la combinación de puerto y seguridad: "
                "587 va con STARTTLS y 465 con SSL.")
    if isinstance(e, smtplib.SMTPNotSupportedError):
        return "El servidor no admite ese tipo de seguridad. Prueba con la otra (STARTTLS / SSL)."
    if isinstance(e, smtplib.SMTPDataError) and e.smtp_code in (421, 450, 451, 452, 550, 554):
        return f"El servidor ha frenado el envío (puede ser el límite diario de correos): {e.smtp_error!r}"
    return f"{type(e).__name__}: {e}"
