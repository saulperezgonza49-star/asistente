"""Creación de carpetas y acceso al portapapeles (esto último se usa también
como herramienta de function calling para Gemini, ver ia.py)."""
import os
import pyperclip

from config import USER_PROFILE, logger


def crear_carpeta_en_escritorio(nombre_carpeta: str):
    """Crea la carpeta en el escritorio del usuario. Regresa (ok, ya_existia)."""
    ruta_carpeta = os.path.join(USER_PROFILE, "Desktop", nombre_carpeta)
    if os.path.exists(ruta_carpeta):
        return True, True
    try:
        os.makedirs(ruta_carpeta)
        return True, False
    except Exception as e:
        logger.error(f"Error al crear carpeta: {e}")
        return False, False


def leer_portapapeles() -> str:
    """Lee el texto que el usuario tiene copiado actualmente en el portapapeles
    de Windows. Úsala cuando el usuario pida resumir, explicar, traducir o
    analizar 'esto' o 'lo que copié'.
    """
    try:
        contenido = pyperclip.paste()
        return contenido if contenido else "El portapapeles está vacío."
    except Exception as e:
        return f"No pude leer el portapapeles: {e}"


def escribir_portapapeles(texto: str) -> str:
    """Escribe un texto en el portapapeles de Windows para que el usuario lo
    pegue con Ctrl+V.

    Args:
        texto: el contenido que se va a copiar al portapapeles.
    """
    try:
        pyperclip.copy(texto)
        return "Listo, ya está en tu portapapeles."
    except Exception as e:
        return f"No pude escribir en el portapapeles: {e}"