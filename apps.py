"""Buscar, abrir y cerrar aplicaciones instaladas en Windows."""
import os
import glob
import functools
import subprocess
import webbrowser
import urllib.parse

import psutil

from config import NOMBRE, logger
from rutas import ESCRITORIO
from voz import hablar

_PERFIL = os.environ.get("USERPROFILE", os.path.expanduser("~"))

# Apps de Windows que no tienen acceso directo con su nombre en español.
APPS_WINDOWS = {
    "calculadora": "calc", "bloc de notas": "notepad", "notas": "notepad", "paint": "mspaint",
    "explorador": "explorer", "explorador de archivos": "explorer", "archivos": "explorer",
    "administrador de tareas": "taskmgr", "terminal": "wt", "símbolo del sistema": "cmd",
    "recortes": "snippingtool", "herramienta de recortes": "snippingtool",
}
URIS = {
    "configuracion": "ms-settings:", "configuración": "ms-settings:", "ajustes": "ms-settings:",
    "spotify": "spotify:", "discord": "discord://", "tienda": "ms-windows-store:",
    "whatsapp": "whatsapp:", "wasap": "whatsapp:", "uatsap": "whatsapp:",
    "correo": "outlookmail:", "calendario": "outlookcal:",
}

# Procesos que nunca se deben matar aunque el nombre coincida por accidente.
PROCESOS_PROTEGIDOS = {"system", "svchost.exe", "csrss.exe", "winlogon.exe", "wininit.exe",
                       "lsass.exe", "services.exe", "smss.exe", "explorer.exe", "dwm.exe"}


@functools.lru_cache(maxsize=64)
def buscar_ejecutable_automatico(nombre_app: str) -> str:
    """Busca un .lnk o .exe que coincida. El resultado se cachea porque la
    búsqueda recursiva en Program Files tarda varios segundos."""
    nombre_app = glob.escape(nombre_app.lower().strip())

    rutas_busqueda = [
        os.path.join(_PERFIL, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        ESCRITORIO,
        os.path.join(_PERFIL, "AppData", "Local", "Programs"),
        r"C:\Program Files",
        r"C:\Program Files (x86)",
    ]

    patrones_lnk = [f"{nombre_app}.lnk", f"*{nombre_app}*.lnk"]
    for ruta in rutas_busqueda:
        if not os.path.exists(ruta):
            continue
        for patron in patrones_lnk:
            try:
                busqueda = glob.glob(f"{ruta}\\{patron}") or glob.glob(f"{ruta}\\**\\{patron}", recursive=True)
                if busqueda:
                    print(f"🎯 Buscador Universal: ¡Acceso directo encontrado! -> {busqueda[0]}")
                    return busqueda[0]
            except Exception:
                continue

    posibles_nombres_exe = [f"{nombre_app}.exe", f"*{nombre_app}*.exe", f"{nombre_app}launcher.exe"]
    for ruta in rutas_busqueda:
        if not os.path.exists(ruta):
            continue
        for patron in posibles_nombres_exe:
            try:
                busqueda = glob.glob(f"{ruta}\\{patron}") or glob.glob(f"{ruta}\\**\\{patron}", recursive=True)
                if busqueda:
                    for resultado in busqueda:
                        if "update" not in resultado.lower() and "setup" not in resultado.lower() and "uninst" not in resultado.lower():
                            print(f"🎯 Buscador Universal: Ejecutable encontrado -> {resultado}")
                            return resultado
                    return busqueda[0]
            except Exception:
                continue
    return ""


def abrir_aplicacion(nombre_app: str, avisar_voz: bool = True) -> bool:
    """Abre una app: primero las de Windows y las que tienen URI propia
    (WhatsApp, Spotify, Configuración...), luego busca .lnk/.exe en disco.

    avisar_voz=False se usa desde ventanas.py, rutinas y Gemini, que dan su
    propio aviso. Con avisar_voz=True, si no la encuentra la busca en Google.
    """
    nombre_app = nombre_app.lower().strip()
    decir = hablar if avisar_voz else (lambda _texto: None)

    if nombre_app == "panel de control":
        decir("Abriendo el panel de control.")
        subprocess.Popen(["control"])
        return True
    if nombre_app in APPS_WINDOWS:
        decir(f"Abriendo {nombre_app}.")
        subprocess.Popen([APPS_WINDOWS[nombre_app]])
        return True
    if nombre_app in URIS:
        decir(f"Abriendo {nombre_app}, {NOMBRE}.")
        os.startfile(URIS[nombre_app])
        return True

    ruta_encontrada = buscar_ejecutable_automatico(nombre_app)
    if ruta_encontrada:
        nombre_limpio = os.path.basename(ruta_encontrada).split(".")[0].capitalize()
        decir(f"Abriendo {nombre_limpio}, carnal.")
        if ruta_encontrada.endswith(".lnk"):
            os.startfile(ruta_encontrada)
        else:
            subprocess.Popen([ruta_encontrada], cwd=os.path.dirname(ruta_encontrada))
        return True

    if avisar_voz:
        hablar("No encontré la aplicación, pero te lo busco en Google.")
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(nombre_app)}")
        return True
    return False


def cerrar_aplicacion(target_app: str) -> int:
    """Cierra los procesos cuyo nombre contenga target_app y las ventanas
    cuyo título empiece así. Regresa cuántos procesos se cerraron.

    Antes usaba `taskkill /IM *app*` con shell=True: el texto reconocido
    iba directo a la consola y el comodín inicial no siempre funciona.
    """
    target_app = target_app.lower().strip()
    if target_app in ["wasap", "uatsap"]:
        target_app = "whatsapp"
    if target_app == "minecraft":
        target_app = "javaw"

    mi_pid = os.getpid()
    cerrados = 0
    for proc in psutil.process_iter(["pid", "name"]):
        nombre = (proc.info["name"] or "").lower()
        if (target_app in nombre and proc.info["pid"] != mi_pid
                and nombre not in PROCESOS_PROTEGIDOS):
            try:
                proc.kill()
                cerrados += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.error(f"No pude cerrar {nombre}: {e}")

    subprocess.run(["taskkill", "/F", "/FI", f"WINDOWTITLE eq {target_app}*"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    logger.info(f"cerrar_aplicacion('{target_app}'): {cerrados} procesos")
    return cerrados
