# -*- coding: utf-8 -*-
"""
envio.py — Manda una tanda de facturas y lo apunta todo en el historial.

Antes de enviar cada PDF se vuelve a comprobar que no se haya enviado ya
(por si dos personas pulsan "Enviar" a la vez desde dos ordenadores que
comparten los datos).
"""

import smtplib

from nucleo import analisis as A
from nucleo.correo import AJUSTES_CORREO, AJUSTES_MENSAJE, Conexion, crear_mensaje, explicar_error, leer_clave, valores_para
from nucleo.datos import AVISADO, ENVIADO, ERROR, Datos


def ajustes_correo(datos: Datos) -> dict:
    return {**AJUSTES_CORREO, **(datos.ajuste("correo", {}) or {})}


def ajustes_mensaje(datos: Datos) -> dict:
    return {**AJUSTES_MENSAJE, **(datos.ajuste("mensaje", {}) or {})}


def enviar_filas(filas: list, datos: Datos, avance=None, parar=lambda: False) -> tuple[int, int]:
    """
    Envía las filas en estado Lista. Cambia el estado de cada una a Enviada,
    Ya enviada o Error al enviar. Devuelve (enviadas, fallidas).
    Si no se puede ni conectar, todas quedan con error y el motivo en .detalle.
    """
    pendientes = [f for f in filas if f.estado == A.OK]
    if not pendientes:
        return 0, 0
    correo, mensaje, empresa = ajustes_correo(datos), ajustes_mensaje(datos), datos.empresa()
    enviadas = fallidas = 0
    try:
        with Conexion(correo, leer_clave(datos, correo)) as conexion:
            for n, fila in enumerate(pendientes, 1):
                if parar():
                    break
                if avance:
                    avance(n - 1, len(pendientes), fila.archivo)
                if datos.resuelto(fila.archivo, fila.huella):
                    fila.estado, fila.detalle = A.YA_ENVIADA, "Ya estaba enviada"
                    continue
                try:
                    msg = crear_mensaje(correo, mensaje, empresa, fila.email,
                                        valores_para(fila.cliente, fila.archivo, empresa), fila.ruta)
                    conexion.enviar(msg)
                except (smtplib.SMTPServerDisconnected, ConnectionError) as e:
                    _fallo(datos, fila, e, correo)
                    fallidas += 1
                    raise  # la conexión se ha caído: no tiene sentido seguir con esta
                except Exception as e:  # noqa: BLE001 — un cliente con email malo no para la tanda
                    _fallo(datos, fila, e, correo)
                    fallidas += 1
                    continue
                datos.registrar(fila.archivo, fila.huella, fila.cliente, fila.email, ENVIADO)
                fila.estado, fila.detalle = A.ENVIADA, ""
                enviadas += 1
    except Exception as e:  # noqa: BLE001 — no se pudo conectar, o se cayó a mitad
        motivo = explicar_error(e, correo)
        for fila in pendientes:
            if fila.estado == A.OK:
                fila.estado, fila.detalle = A.ERROR_ENVIO, motivo
                fallidas += 1
    if avance:
        avance(len(pendientes), len(pendientes), "")
    return enviadas, fallidas


def _fallo(datos: Datos, fila, e: Exception, correo: dict) -> None:
    motivo = explicar_error(e, correo)
    datos.registrar(fila.archivo, fila.huella, fila.cliente, fila.email, ERROR, motivo)
    fila.estado, fila.detalle = A.ERROR_ENVIO, motivo


def marcar_avisada(fila, datos: Datos) -> None:
    datos.registrar(fila.archivo, fila.huella, fila.cliente, "", AVISADO, fila.telefono)
    fila.estado, fila.detalle = A.AVISADA, f"Avisado por teléfono ({fila.telefono})" if fila.telefono else "Avisado"


def enviar_prueba(datos: Datos, para: str) -> None:
    """Un correo de prueba, sin adjunto, para ver cómo le llega al cliente. Lanza la excepción si falla."""
    correo, mensaje, empresa = ajustes_correo(datos), ajustes_mensaje(datos), datos.empresa()
    valores = valores_para("Cliente de Ejemplo, S.L.", "26-0001.pdf", empresa)
    msg = crear_mensaje(correo, mensaje, empresa, para, valores, None)
    msg.replace_header("Subject", "[PRUEBA] " + msg["Subject"])
    with Conexion(correo, leer_clave(datos, correo)) as conexion:
        conexion.enviar(msg)
