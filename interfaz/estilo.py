# -*- coding: utf-8 -*-
"""estilo.py — Colores y hoja de estilos de la interfaz."""

from nucleo import analisis as A
from nucleo.config import ruta_recurso

# Qt solo entiende rutas con barras normales, también en Windows
MARCA = ruta_recurso("marca.svg").as_posix()

AZUL = "#24577F"
AZUL_OSCURO = "#1B4565"
AZUL_SUAVE = "#E4EEF6"
FONDO = "#F4F6F8"
BORDE = "#D8DEE4"
TEXTO = "#1D2329"
TEXTO_SUAVE = "#66717C"
ROJO = "#A23B2C"
VERDE = "#1F6F4A"

# (fondo, texto) de cada estado en la tabla, los mismos colores que la versión anterior
COLOR_ESTADO = {
    A.OK: ("#E3F4EA", "#1F6F4A"),
    A.ENVIADA: ("#D6ECFF", "#1B4F80"),
    A.SIN_EMAIL: ("#FFF3CD", "#7A5A00"),
    A.DUDOSA: ("#FFE2C4", "#8A4300"),
    A.SIN_COINCIDENCIA: ("#FBE1DE", "#A23B2C"),
    A.ERROR_LECTURA: ("#FBE1DE", "#A23B2C"),
    A.ERROR_ENVIO: ("#FBE1DE", "#A23B2C"),
    A.YA_ENVIADA: ("#D6ECFF", "#1B4F80"),
    A.YA_AVISADA: ("#E8DEF8", "#5B3D8F"),
    A.AVISADA: ("#E8DEF8", "#5B3D8F"),
}

LEYENDA = [
    (A.OK, "lista para enviar"),
    (A.SIN_EMAIL, "avisar por teléfono"),
    (A.DUDOSA, "encajan varios clientes: elige"),
    (A.SIN_COINCIDENCIA, "no se sabe de quién es: asígnala"),
    (A.YA_ENVIADA, "ya se envió, no se repite"),
    (A.YA_AVISADA, "ya se avisó por teléfono"),
]

HOJA_ESTILOS = f"""
QWidget {{ color: {TEXTO}; font-size: 13px; }}
QMainWindow, #fondo, QDialog {{ background: {FONDO}; }}
#cabecera {{ background: white; border-bottom: 1px solid {BORDE}; }}
#panel {{ background: white; border: 1px solid {BORDE}; border-radius: 10px; }}
#nombreEmpresa {{ font-size: 17px; font-weight: 600; }}
#tituloPaso {{ font-size: 20px; font-weight: 600; }}
#tituloPanel {{ font-size: 15px; font-weight: 600; }}
#suave {{ color: {TEXTO_SUAVE}; font-size: 12px; }}
#ayuda {{ background: {AZUL_SUAVE}; border: 1px solid #C5D9EA; border-radius: 8px; padding: 9px; color: #1D3D57; }}
#aviso {{ background: #FFF8EA; border: 1px solid #F2DDB0; border-radius: 8px; padding: 9px; color: #6B4A00; }}
#bien {{ background: #E3F4EA; border: 1px solid #BFE3CC; border-radius: 8px; padding: 9px; color: {VERDE}; }}
#mal {{ background: #FBE9E7; border: 1px solid #F0C4BD; border-radius: 8px; padding: 9px; color: {ROJO}; }}
#pasos {{ background: white; border-right: 1px solid {BORDE}; }}
#paso {{ color: {TEXTO_SUAVE}; padding: 7px 10px; border-radius: 6px; }}
#pasoActual {{ color: {AZUL}; background: {AZUL_SUAVE}; padding: 7px 10px; border-radius: 6px; font-weight: 600; }}
#pasoHecho {{ color: {TEXTO}; padding: 7px 10px; }}
#leyenda {{ border-radius: 4px; padding: 2px 7px; font-size: 11px; }}

QPushButton {{ background: white; border: 1px solid {BORDE}; border-radius: 7px; padding: 7px 14px; }}
QPushButton:hover {{ background: #EEF2F5; }}
QPushButton:disabled {{ color: #A9B0B6; }}
QPushButton#principal {{ background: {AZUL}; color: white; border: none; font-weight: 600; }}
QPushButton#principal:hover {{ background: {AZUL_OSCURO}; }}
QPushButton#principal:disabled {{ background: #9FB6CA; }}
QPushButton#peligro {{ color: {ROJO}; }}
QPushButton#plano {{ border: none; background: transparent; color: {AZUL}; padding: 4px 6px; }}
QPushButton#plano:hover {{ text-decoration: underline; }}

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QDoubleSpinBox {{
    background: white; border: 1px solid {BORDE}; border-radius: 6px; padding: 5px 7px;
    selection-background-color: {AZUL};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border: 1px solid {AZUL}; }}
QLineEdit[error="true"] {{ border: 1px solid #C0503F; background: #FFF6F5; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 9px 16px; color: {TEXTO_SUAVE}; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {AZUL}; border-bottom: 2px solid {AZUL}; font-weight: 600; }}

QTableView, QListWidget {{
    background: white; border: 1px solid {BORDE}; border-radius: 8px; gridline-color: #EEF1F3;
    selection-background-color: #CFE0EE; selection-color: {TEXTO};
}}
QHeaderView::section {{
    background: white; border: none; border-bottom: 1px solid {BORDE};
    padding: 6px; font-weight: 600; color: {TEXTO_SUAVE};
}}
QProgressBar {{ border: none; background: #E3E8EC; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {AZUL}; border-radius: 3px; }}
QScrollArea {{ border: none; background: transparent; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid #A9B4BE; border-radius: 4px; background: white; }}
QCheckBox::indicator:hover {{ border-color: {AZUL}; }}
QCheckBox::indicator:checked {{ background: {AZUL}; border-color: {AZUL}; image: url({MARCA}); }}
QCheckBox::indicator:disabled {{ background: #EEF1F3; border-color: {BORDE}; }}
QRadioButton {{ spacing: 8px; }}
QRadioButton::indicator {{ width: 14px; height: 14px; border: 1px solid #A9B4BE; border-radius: 8px; background: white; }}
QRadioButton::indicator:hover {{ border-color: {AZUL}; }}
QRadioButton::indicator:checked {{ border: 5px solid {AZUL}; width: 6px; height: 6px; background: white; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
"""


def caja(texto: str, tipo: str = "ayuda"):
    """Un recuadro de texto de color: ayuda, aviso, bien o mal."""
    from PySide6.QtWidgets import QLabel
    etiqueta = QLabel(texto)
    etiqueta.setObjectName(tipo)
    etiqueta.setWordWrap(True)
    etiqueta.setOpenExternalLinks(True)
    etiqueta.setTextInteractionFlags(etiqueta.textInteractionFlags() | etiqueta.textInteractionFlags().TextSelectableByMouse)
    return etiqueta


def poner_tipo(etiqueta, tipo: str, texto: str) -> None:
    etiqueta.setObjectName(tipo)
    etiqueta.setText(texto)
    etiqueta.style().unpolish(etiqueta)
    etiqueta.style().polish(etiqueta)
    etiqueta.setVisible(bool(texto))
