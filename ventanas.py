"""Multimonitor: numeración de Windows, mover ventanas (la activa o la de
una app) y abrir apps en un monitor específico sin robar el foco."""
import ctypes
import os
import re
import time

import psutil
import win32api
import win32con
import win32gui
import win32process

from config import logger

# Nombre que dices -> fragmentos del nombre del proceso (.exe). Sirve para
# apps cuyo título de ventana no dice su nombre (Spotify muestra la canción,
# Chrome el título de la página, etc.).
ALIAS_PROCESOS = {
    "chrome": ["chrome"], "google chrome": ["chrome"],
    "navegador": ["chrome", "msedge", "firefox", "brave", "opera"],
    "edge": ["msedge"], "firefox": ["firefox"], "brave": ["brave"], "opera": ["opera"],
    "spotify": ["spotify"], "discord": ["discord"],
    "whatsapp": ["whatsapp"], "wasap": ["whatsapp"], "uatsap": ["whatsapp"],
    "visual studio code": ["code"], "vs code": ["code"], "code": ["code"],
    "explorador": ["explorer"], "carpeta": ["explorer"], "archivos": ["explorer"],
    "terminal": ["windowsterminal", "cmd", "powershell"],
    "word": ["winword"], "excel": ["excel"], "power point": ["powerpnt"], "powerpoint": ["powerpnt"],
    "minecraft": ["javaw", "minecraft"], "steam": ["steam"], "obs": ["obs"],
}

_CLASES_ESCRITORIO = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


# ---------------------------------------------------------
# 🖥️ MONITORES
# ---------------------------------------------------------
def listar_monitores():
    """Monitores ordenados de izquierda a derecha. Cada uno es un dict con
    handle, area (completa), trabajo (sin barra de tareas) y numero de Windows."""
    monitores = []
    for hmon, _, _ in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(hmon)
        match = re.search(r'DISPLAY(\d+)', info.get("Device", ""))
        monitores.append({
            "handle": int(hmon),
            "area": info["Monitor"],
            "trabajo": info["Work"],
            "numero": int(match.group(1)) if match else None,
        })
    monitores.sort(key=lambda m: (m["area"][0], m["area"][1]))
    return monitores


def obtener_monitor(numero: int):
    """El monitor que Windows llama "numero" (Configuración > Pantalla). Si
    no existe (a veces Windows los numera 1 y 3), usa el orden izquierda a
    derecha: pantalla 2 = la segunda desde la izquierda."""
    monitores = listar_monitores()
    for m in monitores:
        if m["numero"] == numero:
            return m
    if 1 <= numero <= len(monitores):
        return monitores[numero - 1]
    return None


def _indice_monitor_de(hwnd, monitores):
    hmon = int(win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST))
    for i, m in enumerate(monitores):
        if m["handle"] == hmon:
            return i
    return 0


# ---------------------------------------------------------
# 🪟 VENTANAS
# ---------------------------------------------------------
def _esta_oculta(hwnd) -> bool:
    """Ventanas 'cloaked' por Windows: existen y dicen ser visibles, pero no
    se ven (apps de la Store suspendidas, otros escritorios virtuales)."""
    cloaked = ctypes.c_int(0)
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    except Exception:
        return False
    return cloaked.value != 0


def _ventanas_normales():
    """Ventanas de nivel superior que de verdad ves en la barra de tareas."""
    ventanas = []

    def _callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd) or not win32gui.GetWindowText(hwnd):
            return True
        if win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOOLWINDOW:
            return True
        if win32gui.GetClassName(hwnd) in _CLASES_ESCRITORIO or _esta_oculta(hwnd):
            return True
        ventanas.append(hwnd)
        return True

    try:
        win32gui.EnumWindows(_callback, None)
    except Exception:
        pass
    return ventanas


def _nombre_proceso(hwnd) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid == os.getpid():
            return ""
        return psutil.Process(pid).name().lower().removesuffix(".exe")
    except Exception:
        return ""


def encontrar_ventana(nombre_app: str):
    """Busca la ventana de una app por título o por nombre de proceso."""
    nombre_app = nombre_app.lower().strip()
    alias = ALIAS_PROCESOS.get(nombre_app, [nombre_app.replace(" ", "")])
    por_proceso = None
    for hwnd in _ventanas_normales():  # EnumWindows va de la más reciente a la más vieja
        if nombre_app in win32gui.GetWindowText(hwnd).lower():
            return hwnd
        if por_proceso is None and any(a in _nombre_proceso(hwnd) for a in alias):
            por_proceso = hwnd
    return por_proceso


def ventana_activa():
    """La ventana en la que estás trabajando (o None si es el escritorio)."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd or win32gui.GetClassName(hwnd) in _CLASES_ESCRITORIO:
        return None
    return hwnd


def mover_hwnd_a_monitor(hwnd, monitor, activar=False) -> bool:
    """Mueve la ventana al monitor conservando su tamaño (centrada), y si
    estaba maximizada la vuelve a maximizar allá.

    Antes se usaba SetWindowPos directo, que NO funciona con ventanas
    maximizadas o minimizadas: Windows ignora el movimiento.
    """
    if not hwnd or not monitor:
        return False
    try:
        estaba_max = win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED
        if estaba_max or win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        izq, arr, der, aba = win32gui.GetWindowRect(hwnd)
        t_izq, t_arr, t_der, t_aba = monitor["trabajo"]
        ancho = min(der - izq, t_der - t_izq)
        alto = min(aba - arr, t_aba - t_arr)
        x = t_izq + (t_der - t_izq - ancho) // 2
        y = t_arr + (t_aba - t_arr - alto) // 2

        flags = win32con.SWP_NOZORDER | (0 if activar else win32con.SWP_NOACTIVATE)
        win32gui.SetWindowPos(hwnd, 0, x, y, ancho, alto, flags)
        if estaba_max:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        return True
    except Exception as e:
        # Típico: la ventana es de un programa abierto como administrador.
        logger.error(f"No pude mover la ventana {hwnd}: {e}")
        return False


def mover_ventana(hwnd, numero_monitor=None) -> str:
    """Mueve la ventana a la pantalla indicada, o a la siguiente si no se
    dice número. Regresa "ok", "sin_ventana", "sin_monitor", "un_monitor" o "error"."""
    if not hwnd:
        return "sin_ventana"
    monitores = listar_monitores()
    if numero_monitor is None:
        if len(monitores) < 2:
            return "un_monitor"
        destino = monitores[(_indice_monitor_de(hwnd, monitores) + 1) % len(monitores)]
    else:
        destino = obtener_monitor(numero_monitor)
        if not destino:
            return "sin_monitor"
    return "ok" if mover_hwnd_a_monitor(hwnd, destino) else "error"


def maximizar_activa() -> bool:
    hwnd = ventana_activa()
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    return bool(hwnd)


def minimizar_activa() -> bool:
    hwnd = ventana_activa()
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    return bool(hwnd)


def abrir_app_en_monitor(nombre_app: str, numero_monitor: int) -> bool:
    """Abre (o, si ya está abierta, solo mueve) una app al monitor indicado,
    devolviendo el foco a donde estabas trabajando."""
    from apps import abrir_aplicacion  # import aquí para evitar import circular

    hwnd_foco_previo = win32gui.GetForegroundWindow()
    hwnd = encontrar_ventana(nombre_app)
    if not hwnd:
        if not abrir_aplicacion(nombre_app, avisar_voz=False):
            return False
        for _ in range(40):  # hasta 8 s: Spotify/Discord tardan en mostrar ventana
            time.sleep(0.2)
            hwnd = encontrar_ventana(nombre_app)
            if hwnd:
                time.sleep(0.5)  # algunas apps se reacomodan solas al terminar de abrir
                break

    if hwnd:
        mover_hwnd_a_monitor(hwnd, obtener_monitor(numero_monitor))
    try:
        win32gui.SetForegroundWindow(hwnd_foco_previo)
    except Exception:
        pass
    return True
