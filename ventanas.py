"""Multimonitor: numeración real de Windows, mover ventanas y abrir apps
en un monitor específico sin robar el foco de donde estás trabajando."""
import re
import time
import win32gui
import win32con
from screeninfo import get_monitors

from apps import abrir_aplicacion


def obtener_monitores_por_numero():
    """Devuelve {numero: monitor} usando el MISMO número que Windows muestra
    en Configuración > Sistema > Pantalla (lee el nombre del dispositivo,
    ej. '\\\\.\\DISPLAY1' -> 1)."""
    monitores = {}
    for m in get_monitors():
        match = re.search(r'DISPLAY(\d+)', m.name)
        if match:
            monitores[int(match.group(1))] = m
    return monitores


def encontrar_hwnd_por_titulo(fragmento_titulo: str):
    fragmento_titulo = fragmento_titulo.lower()
    resultado = {"hwnd": None}

    def _callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            if fragmento_titulo in win32gui.GetWindowText(hwnd).lower():
                resultado["hwnd"] = hwnd
                return False
        return True

    try:
        win32gui.EnumWindows(_callback, None)
    except Exception:
        pass
    return resultado["hwnd"]


def mover_hwnd_a_monitor(hwnd, monitor, activar=False):
    """Mueve la ventana al monitor especificado sin quitar el foco activo."""
    if not hwnd:
        return False
    flags = win32con.SWP_NOZORDER
    if not activar:
        flags |= win32con.SWP_NOACTIVATE
    win32gui.SetWindowPos(hwnd, 0, monitor.x + 40, monitor.y + 40,
                           monitor.width - 80, monitor.height - 80, flags)
    return True


def mover_app_a_monitor(nombre_app: str, numero_monitor: int) -> bool:
    """Para ventanas YA abiertas: 'mueve whatsapp a la pantalla 2'."""
    monitor = obtener_monitores_por_numero().get(numero_monitor)
    if not monitor:
        return False
    hwnd = encontrar_hwnd_por_titulo(nombre_app)
    if not hwnd:
        return False
    return mover_hwnd_a_monitor(hwnd, monitor)


def abrir_app_en_monitor(nombre_app: str, numero_monitor: int):
    """Abre y reposiciona una aplicación en un monitor específico
    manteniendo el foco donde estabas trabajando."""
    hwnd_foco_previo = win32gui.GetForegroundWindow()
    if not abrir_aplicacion(nombre_app, avisar_voz=False):
        return False

    hwnd_nuevo = None
    for _ in range(20):  # hasta 4 segundos esperando que la ventana aparezca
        time.sleep(0.2)
        hwnd_nuevo = encontrar_hwnd_por_titulo(nombre_app)
        if hwnd_nuevo:
            break

    if hwnd_nuevo:
        monitor = obtener_monitores_por_numero().get(numero_monitor)
        if monitor:
            mover_hwnd_a_monitor(hwnd_nuevo, monitor)

    try:
        win32gui.SetForegroundWindow(hwnd_foco_previo)
    except Exception:
        pass
    return True