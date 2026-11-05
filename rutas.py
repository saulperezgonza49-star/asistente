"""Rutas del programa, pensadas para que funcione igual como script y como .exe.

- DIR_APP: carpeta de main.py, o del .exe cuando está empaquetado. Ahí se
  busca primero el .env y la carpeta 'modelos'.
- DIR_RECURSOS: donde PyInstaller descomprime lo que metas con --add-data
  (sys._MEIPASS). Como script es lo mismo que DIR_APP.
- DIR_DATOS: %APPDATA%\\Solovino. Configuración, log, recordatorios, rutinas,
  token de Spotify y caché de voz. No se borra al actualizar el .exe.
"""
import os
import shutil
import sys

CONGELADO = getattr(sys, "frozen", False)  # True cuando corre como .exe de PyInstaller

DIR_APP = os.path.dirname(sys.executable) if CONGELADO else os.path.dirname(os.path.abspath(__file__))
DIR_RECURSOS = getattr(sys, "_MEIPASS", DIR_APP)
DIR_DATOS = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Solovino")
os.makedirs(DIR_DATOS, exist_ok=True)


def ruta_datos(*partes) -> str:
    return os.path.join(DIR_DATOS, *partes)


def buscar_recurso(*partes):
    """Busca un archivo/carpeta junto al .exe, luego en los recursos
    empaquetados y luego en %APPDATA%\\Solovino. Regresa None si no está."""
    for base in (DIR_APP, DIR_RECURSOS, DIR_DATOS):
        ruta = os.path.join(base, *partes)
        if os.path.exists(ruta):
            return ruta
    return None


def _carpeta_shell(csidl, respaldo):
    """Carpetas reales de Windows (respeta OneDrive: tu escritorio está en
    OneDrive\\Desktop, no en C:\\Users\\saul\\Desktop)."""
    try:
        from win32com.shell import shell
        return shell.SHGetFolderPath(0, csidl, None, 0)
    except Exception:
        return respaldo


_PERFIL = os.environ.get("USERPROFILE", os.path.expanduser("~"))
ESCRITORIO = _carpeta_shell(0x0010, os.path.join(_PERFIL, "Desktop"))   # CSIDL_DESKTOPDIRECTORY
INICIO_WINDOWS = _carpeta_shell(0x0007, os.path.join(                    # CSIDL_STARTUP
    os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"))


def migrar_archivo_viejo(nombre_viejo: str, nombre_nuevo: str):
    """Las versiones anteriores guardaban todo en C:\\Users\\saul. Si existe
    un archivo viejo y todavía no hay uno nuevo, lo copia (no lo borra)."""
    viejo = os.path.join(_PERFIL, nombre_viejo)
    nuevo = ruta_datos(nombre_nuevo)
    if os.path.exists(viejo) and not os.path.exists(nuevo):
        try:
            shutil.copy2(viejo, nuevo)
        except OSError:
            pass
