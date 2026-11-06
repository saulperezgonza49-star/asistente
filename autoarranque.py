"""Iniciar Solovino con Windows: un acceso directo en la carpeta Inicio."""
import os
import sys

from config import logger
from rutas import CONGELADO, DIR_APP, INICIO_WINDOWS

ACCESO_DIRECTO = os.path.join(INICIO_WINDOWS, "Solovino.lnk")


def activo() -> bool:
    return os.path.exists(ACCESO_DIRECTO)


def activar() -> bool:
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        acceso = win32com.client.Dispatch("WScript.Shell").CreateShortCut(ACCESO_DIRECTO)
        if CONGELADO:
            acceso.TargetPath = sys.executable
            acceso.Arguments = ""
        else:
            # pythonw = sin ventana de consola
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            acceso.TargetPath = pythonw if os.path.exists(pythonw) else sys.executable
            acceso.Arguments = f'"{os.path.join(DIR_APP, "main.py")}"'
        acceso.WorkingDirectory = DIR_APP
        acceso.Description = "Solovino, asistente de voz"
        acceso.save()
        logger.info(f"Inicio con Windows activado: {ACCESO_DIRECTO}")
        return True
    except Exception as e:
        logger.error(f"No pude activar el inicio con Windows: {e}")
        return False


def desactivar() -> bool:
    try:
        if activo():
            os.remove(ACCESO_DIRECTO)
        logger.info("Inicio con Windows desactivado")
        return True
    except OSError as e:
        logger.error(f"No pude desactivar el inicio con Windows: {e}")
        return False


def alternar():
    return desactivar() if activo() else activar()
