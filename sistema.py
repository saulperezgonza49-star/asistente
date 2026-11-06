"""Acciones del sistema: bloquear, suspender, apagar/reiniciar (con cuenta
regresiva cancelable), batería, hora y fecha, captura de pantalla."""
import ctypes
import subprocess
from datetime import datetime

import psutil
import pyautogui

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _shutdown(*argumentos):
    subprocess.run(["shutdown", *argumentos], creationflags=subprocess.CREATE_NO_WINDOW,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def bloquear():
    ctypes.windll.user32.LockWorkStation()


def suspender():
    # SetSuspendState(hibernar=False, forzar=True, desactivar_eventos_despertar=False)
    ctypes.windll.powrprof.SetSuspendState(False, True, False)


def apagar(segundos=60):
    """Programa el apagado con cuenta regresiva para que se pueda cancelar."""
    _shutdown("/s", "/t", str(segundos))


def reiniciar(segundos=60):
    _shutdown("/r", "/t", str(segundos))


def cancelar_apagado():
    _shutdown("/a")


def bateria() -> str:
    b = psutil.sensors_battery()
    if b is None:
        return "Esta computadora no tiene batería."
    texto = f"Tienes {round(b.percent)} por ciento de batería"
    if b.power_plugged:
        return texto + " y está conectada."
    if b.secsleft not in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN):
        horas, resto = divmod(b.secsleft // 60, 60)
        return texto + f", te queda como {f'{horas} horas y ' if horas else ''}{resto} minutos."
    return texto + "."


def hora() -> str:
    ahora = datetime.now()
    h = ahora.hour % 12 or 12
    momento = "de la mañana" if ahora.hour < 12 else "de la tarde" if ahora.hour < 19 else "de la noche"
    return f"Son las {h}:{ahora.minute:02d} {momento}."


def fecha() -> str:
    hoy = datetime.now()
    return f"Hoy es {DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}."


def fecha_hora_contexto() -> str:
    """Para Gemini: fecha y hora exactas (ISO) más el día de la semana."""
    ahora = datetime.now()
    return f"{DIAS[ahora.weekday()]} {ahora.isoformat(timespec='minutes')}"


def captura_de_pantalla():
    """Win+ImprPant: Windows la guarda en Imágenes\\Capturas de pantalla."""
    pyautogui.hotkey("win", "printscreen")
