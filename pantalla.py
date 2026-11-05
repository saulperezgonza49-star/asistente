"""Ver la pantalla: toma una captura del monitor donde estás trabajando y se
la manda a Gemini junto con tu pregunta ("¿qué dice este error?")."""
import io

import win32api
import win32con
import win32gui
from PIL import ImageGrab

from config import logger

LADO_MAXIMO = 1600  # px: suficiente para leer texto y no manda imágenes enormes


def capturar_monitor_activo() -> bytes:
    """PNG del monitor donde está la ventana activa (no de todos)."""
    hwnd = win32gui.GetForegroundWindow()
    monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
    izq, arr, der, aba = win32api.GetMonitorInfo(monitor)["Monitor"]
    imagen = ImageGrab.grab(bbox=(izq, arr, der, aba), all_screens=True)
    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def preguntar_sobre_pantalla(pregunta: str) -> str:
    import ia
    try:
        png = capturar_monitor_activo()
    except Exception as e:
        logger.error(f"No pude capturar la pantalla: {e}")
        return "No pude tomar la captura de pantalla."
    return ia.analizar_imagen(png, pregunta or "¿Qué hay en mi pantalla? Descríbelo brevemente.")
