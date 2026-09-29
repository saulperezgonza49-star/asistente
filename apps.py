"""Buscar, abrir y cerrar aplicaciones instaladas en Windows."""
import os
import glob
import subprocess
import webbrowser
import urllib.parse

from config import USER_PROFILE
from voz import hablar


def buscar_ejecutable_automatico(nombre_app: str) -> str:
    nombre_app = nombre_app.lower().strip()

    rutas_busqueda = [
        f"{USER_PROFILE}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs",
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        f"{USER_PROFILE}\\Desktop",
        f"{USER_PROFILE}\\AppData\\Local\\Programs",
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
    """Abre WhatsApp/Spotify/Discord/Configuración/Panel de control, o cualquier
    .exe/.lnk encontrado en disco.

    avisar_voz=False es lo que usa ventanas.py para abrir en silencio y
    reposicionar en un monitor sin duplicar el aviso de voz (antes esto
    era una función aparte, _abrir_app_silencioso, con la misma lógica
    copiada dos veces — ahora es una sola).
    """
    nombre_app = nombre_app.lower().strip()

    if nombre_app in ["whatsapp", "wasap", "uatsap"]:
        if avisar_voz:
            hablar("Abriendo WhatsApp, carnal.")
        subprocess.Popen("explorer.exe shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App", shell=True)
        return True

    if nombre_app in ["spotify", "discord"]:
        if avisar_voz:
            hablar(f"Abriendo {nombre_app}, Saúl.")
        webbrowser.open(f"{nombre_app}://")
        return True

    if avisar_voz:
        if nombre_app in ["configuracion", "configuración", "ajustes"]:
            hablar("Abriendo la configuración.")
            webbrowser.open("ms-settings:")
            return True
        if nombre_app == "panel de control":
            hablar("Abriendo el panel de control.")
            subprocess.Popen("control", shell=True)
            return True

    ruta_encontrada = buscar_ejecutable_automatico(nombre_app)
    if ruta_encontrada:
        nombre_limpio = os.path.basename(ruta_encontrada).split(".")[0].capitalize()
        if avisar_voz:
            hablar(f"Abriendo {nombre_limpio}, carnal.")
        if ruta_encontrada.endswith(".lnk"):
            os.startfile(ruta_encontrada)
        else:
            subprocess.Popen(f'"{ruta_encontrada}"', shell=True)
        return True

    if avisar_voz:
        texto_formateado = urllib.parse.quote(nombre_app)
        hablar("No encontré la aplicación, pero te lo busco en Google.")
        webbrowser.open(f'https://www.google.com/search?q={texto_formateado}')
        return True

    return False


def cerrar_aplicacion(target_app: str) -> str:
    """Mata cualquier proceso o ventana relacionada con target_app.
    Regresa el nombre ya normalizado (ej. minecraft -> javaw)."""
    if target_app in ["wasap", "uatsap"]:
        target_app = "whatsapp"
    if target_app == "minecraft":
        target_app = "javaw"

    subprocess.run(f"taskkill /F /IM *{target_app}*", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(f'taskkill /F /FI "WINDOWTITLE eq {target_app}*"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return target_app