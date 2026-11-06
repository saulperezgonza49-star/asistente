"""Evita que corran dos Solovinos a la vez (p. ej. el de "Iniciar con
Windows" y uno que abriste a mano): los dos escucharían y contestarían.

Usa un mutex con nombre de Windows: lo libera el sistema aunque el proceso
truene, así que nunca se queda "trabado".
"""
import ctypes
import os
import subprocess
import sys
import time

from rutas import CONGELADO, DIR_APP

_NOMBRE = "Local\\Solovino_asistente_de_voz"
_ERROR_ALREADY_EXISTS = 183
_handle = None


def adquirir(esperar_segundos: float = 0) -> bool:
    """True si esta es la única instancia. Con `esperar_segundos` reintenta
    (lo usa el reinicio: la instancia vieja tarda un momento en cerrarse)."""
    global _handle
    kernel32 = ctypes.windll.kernel32
    limite = time.time() + esperar_segundos
    while True:
        handle = kernel32.CreateMutexW(None, False, _NOMBRE)
        if handle and kernel32.GetLastError() != _ERROR_ALREADY_EXISTS:
            _handle = handle  # se guarda para que el mutex viva lo mismo que el proceso
            return True
        if handle:
            kernel32.CloseHandle(handle)
        if time.time() >= limite:
            return False
        time.sleep(0.3)


_EVENTO_SALIR = "Local\\Solovino_pedir_salir"
_SYNCHRONIZE_Y_MODIFICAR = 0x00100000 | 0x0002  # SYNCHRONIZE | EVENT_MODIFY_STATE


def escuchar_peticion_de_salir(al_pedir):
    """Hilo que espera a que alguien corra `Solovino.exe --salir` y entonces
    llama `al_pedir()`. Sirve aunque el ícono de la bandeja no responda."""
    import threading
    kernel32 = ctypes.windll.kernel32
    evento = kernel32.CreateEventW(None, True, False, _EVENTO_SALIR)
    if not evento:
        return

    def esperar():
        if kernel32.WaitForSingleObject(evento, 0xFFFFFFFF) == 0:  # INFINITE; 0 = WAIT_OBJECT_0
            al_pedir()
    threading.Thread(target=esperar, daemon=True, name="pedir-salir").start()


def pedir_salir_a_la_instancia_abierta() -> bool:
    """Para `Solovino.exe --salir`: avisa a la instancia abierta que se cierre.
    Regresa False si no había ninguna abierta."""
    kernel32 = ctypes.windll.kernel32
    evento = kernel32.OpenEventW(_SYNCHRONIZE_Y_MODIFICAR, False, _EVENTO_SALIR)
    if not evento:
        return False
    kernel32.SetEvent(evento)
    kernel32.CloseHandle(evento)
    return True


def liberar():
    global _handle
    if _handle:
        ctypes.windll.kernel32.CloseHandle(_handle)
        _handle = None


def lanzar_nueva_instancia():
    """Abre otro Solovino que espera a que este se cierre (para "Reiniciar")."""
    if CONGELADO:
        comando = [sys.executable, "--reinicio"]
    else:
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        ejecutable = sys.executable if sys.stdout is not None else (pythonw if os.path.exists(pythonw) else sys.executable)
        comando = [ejecutable, os.path.join(DIR_APP, "main.py"), "--reinicio"]
    subprocess.Popen(comando, cwd=DIR_APP, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
