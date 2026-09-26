import os
import subprocess
import ctypes
import glob
import re
import json
import logging
import logging.handlers
import pyautogui
import time
import numpy as np
import threading
import winspeech
import webbrowser
import urllib.parse
import pyperclip
from dotenv import load_dotenv
from google import genai
import speech_recognition as sr
import sounddevice as sd
from plyer import notification
from google.genai import types
import pystray
from PIL import Image, ImageDraw

# Imports para la gestión nativa de pantallas y ventanas en Windows
import win32gui
import win32con
from screeninfo import get_monitors

# Control de volumen nativo y medidor de audio (pycaw)
import comtypes
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IAudioMeterInformation

# ---------------------------------------------------------
# 📝 LOGGING A ARCHIVO (necesario para cuando corra sin consola)
# ---------------------------------------------------------
USER_PROFILE = os.environ.get("USERPROFILE", "C:\\Users\\saul")
LOG_PATH = os.path.join(USER_PROFILE, "solovino.log")

logger = logging.getLogger("solovino")
logger.setLevel(logging.INFO)
_handler = logging.handlers.RotatingFileHandler(
    LOG_PATH, maxBytes=2_000_000, backupCount=2, encoding="utf-8"
)
_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(_handler)


# ---------------------------------------------------------
# ⚙️ CONFIGURACIÓN EXTERNA (config.json) — editable sin recompilar
# ---------------------------------------------------------
CONFIG_PATH = os.path.join(USER_PROFILE, "solovino_config.json")

CONFIG_DEFAULT = {
    "palabra_clave": "solovino",
    "umbral_voz": 0.02,
    "factor_ganancia": 1.0,
    "nivel_volumen_escucha": 0.15,
    "segundos_espera_reposo": 3,
    "segundos_espera_orden": 5,
    "segundos_silencio_corte": 0.8
}

def cargar_config():
    if not os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(CONFIG_DEFAULT, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"No pude crear config.json, uso valores por defecto: {e}")
        return CONFIG_DEFAULT.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in CONFIG_DEFAULT.items():
            data.setdefault(k, v)
        return data
    except Exception as e:
        logger.error(f"Error leyendo config.json, uso valores por defecto: {e}")
        return CONFIG_DEFAULT.copy()

CONFIG = cargar_config()


# ---------------------------------------------------------
# 🔐 API KEY DESDE .env
# ---------------------------------------------------------
load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    logger.error("No encontré GEMINI_API_KEY. Crea un archivo .env junto al programa con GEMINI_API_KEY=tu_key")
client = genai.Client(api_key=API_KEY)


# ---------------------------------------------------------
# CONSTANTES Y FUNCIONES MULTIMEDIA (ctypes)
# ---------------------------------------------------------
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1

def enviar_tecla_multimedia(codigo_vk):
    """Envía una tecla multimedia directo al sistema (más confiable que pyautogui)"""
    ctypes.windll.user32.keybd_event(codigo_vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(codigo_vk, 0, 2, 0)


# ---------------------------------------------------------
# CONTROL DE VOLUMEN Y DETECCIÓN DE AUDIO (pycaw)
# ---------------------------------------------------------
def extraer_numero(texto: str):
    match = re.search(r'\d+', texto)
    return int(match.group()) if match else None

def _control_volumen():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))

def bajar_volumen(nivel=None):
    nivel = CONFIG["nivel_volumen_escucha"] if nivel is None else nivel
    try:
        comtypes.CoInitialize()
        vol = _control_volumen()
        nivel_anterior = vol.GetMasterVolumeLevelScalar()
        vol.SetMasterVolumeLevelScalar(nivel, None)
        return nivel_anterior
    except Exception as e:
        logger.error(f"Error al bajar volumen: {e}")
        return None
    finally:
        comtypes.CoUninitialize()

def restaurar_volumen(nivel_anterior):
    if nivel_anterior is None:
        return
    try:
        comtypes.CoInitialize()
        vol = _control_volumen()
        vol.SetMasterVolumeLevelScalar(nivel_anterior, None)
    except Exception as e:
        logger.error(f"Error al restaurar volumen: {e}")
    finally:
        comtypes.CoUninitialize()

def ajustar_volumen(nivel: float):
    try:
        comtypes.CoInitialize()
        vol = _control_volumen()
        nivel = max(0.0, min(1.0, nivel))
        vol.SetMasterVolumeLevelScalar(nivel, None)
    except Exception as e:
        logger.error(f"Error ajustando volumen: {e}")
    finally:
        comtypes.CoUninitialize()

def hay_audio_reproduciendose(umbral: float = 0.01) -> bool:
    """Mide el pico de audio que sale por las bocinas AHORITA MISMO.
    Si hay sonido de verdad saliendo (musica, video, etc.), regresa True."""
    try:
        comtypes.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
        medidor = cast(interface, POINTER(IAudioMeterInformation))
        pico = medidor.GetPeakValue()
        return pico > umbral
    except Exception as e:
        logger.error(f"Error detectando audio: {e}")
        return False
    finally:
        comtypes.CoUninitialize()

def pausar_video_para_escuchar() -> bool:
    """Si hay algo sonando ahorita, lo pausa con la tecla multimedia.
    Regresa True SOLO si de verdad pauso algo, para saber si hay que
    reanudarlo despues (y no reanudar algo que ya estaba pausado)."""
    if hay_audio_reproduciendose():
        enviar_tecla_multimedia(VK_MEDIA_PLAY_PAUSE)
        time.sleep(0.15)  # le da un instante al sistema para procesar la pausa
        return True
    return False

def reanudar_video(estaba_reproduciendo: bool):
    """Solo reanuda si pausar_video_para_escuchar() de verdad pauso algo"""
    if estaba_reproduciendo:
        enviar_tecla_multimedia(VK_MEDIA_PLAY_PAUSE)  # vuelve a togglear -> reproduce otra vez


# ---------------------------------------------------------
# 🧩 HERRAMIENTAS PARA GEMINI (FUNCTION CALLING) — CHAT DE TAREAS
# ---------------------------------------------------------
def leer_portapapeles() -> str:
    """Lee el texto que el usuario tiene copiado actualmente en el portapapeles de Windows."""
    try:
        contenido = pyperclip.paste()
        return contenido if contenido else "El portapapeles está vacío."
    except Exception as e:
        return f"No pude leer el portapapeles: {e}"

def escribir_portapapeles(texto: str) -> str:
    """Escribe un texto en el portapapeles de Windows para que el usuario lo pegue con Ctrl+V."""
    try:
        pyperclip.copy(texto)
        return "Listo, ya está en tu portapapeles."
    except Exception as e:
        return f"No pude escribir en el portapapeles: {e}"


# ---------------------------------------------------------
# VARIABLES GLOBALES
# ---------------------------------------------------------
PALABRA_CLAVE = CONFIG["palabra_clave"]
PALABRAS_TAREA = [
    "resume", "resumir", "resúmeme", "resumeme",
    "copia", "copiar", "cópiame", "copiame",
    "pega", "pegar", "portapapeles",
    "explica esto", "explícame esto", "explicame esto",
    "traduce esto", "traduce lo que"
]

audio_buffer = []
running = True
ia_hablando = False  # 🛡️ ESCUDO ANTI-ECO
lock = threading.Lock()

def hablar(texto: str):
    global ia_hablando, audio_buffer
    ia_hablando = True
    logger.info(f"solovino dijo: {texto}")
    print(f"solovino: {texto}")
    try:
        winspeech.say(texto)
        time.sleep(1.5)
    except:
        os.system(f'PowerShell -Command "Add-Type –AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{texto}\')"')

    with lock:
        audio_buffer = []
    ia_hablando = False

def mandar_notificacion(titulo: str, mensaje: str):
    try:
        notification.notify(title=titulo, message=mensaje, app_name="Solovino Bot", timeout=2)
    except:
        pass

def callback_audio(indata, frames, time_info, status):
    global audio_buffer, ia_hablando
    if not ia_hablando:
        with lock:
            audio_buffer.append(indata.copy())

def escuchar_segmento(recognizer, samplerate, segundos_max=5, silencio_para_cortar=None) -> str:
    """ Escucha el micrófono y corta automáticamente tras detectar silencio tras la voz """
    global audio_buffer, ia_hablando, running
    silencio_para_cortar = CONFIG["segundos_silencio_corte"] if silencio_para_cortar is None else silencio_para_cortar
    umbral_voz = CONFIG["umbral_voz"]

    inicio = time.time()
    ultimo_sonido = None

    while time.time() - inicio < segundos_max:
        if not running:              # corta de inmediato si ya pidieron cerrar
            return ""
        time.sleep(0.1)
        if ia_hablando:
            return ""
        with lock:
            if audio_buffer:
                ultimo_chunk = audio_buffer[-1]
                if np.max(np.abs(ultimo_chunk)) > umbral_voz:
                    ultimo_sonido = time.time()

        if ultimo_sonido and (time.time() - ultimo_sonido) > silencio_para_cortar:
            break

    if not running:
        return ""

    try:
        with lock:
            if len(audio_buffer) == 0:
                return ""
            datos_crudos = np.concatenate(audio_buffer, axis=0)
            audio_buffer = []

        factor_ganancia = CONFIG.get("factor_ganancia", 1.0)
        if factor_ganancia != 1.0:
            datos_crudos = np.clip(datos_crudos * factor_ganancia, -1.0, 1.0)

        if np.max(np.abs(datos_crudos)) > 0:
            datos_crudos = datos_crudos / np.max(np.abs(datos_crudos)) * 0.9

        audio_int16 = (datos_crudos * 32767).astype(np.int16)
        audio_data = sr.AudioData(audio_int16.tobytes(), int(samplerate), 2)

        texto = recognizer.recognize_google(audio_data, language="es-MX")
        texto_limpio = texto.lower().strip()

        if texto_limpio:
            print(f"🎙️ [Escuchado]: '{texto_limpio}'")
        return texto_limpio
    except Exception:
        return ""


# ==========================================
# 🔍 BUSCADOR AUTOMÁTICO DE EJECUTABLES
# ==========================================
def buscar_ejecutable_automatico(nombre_app: str) -> str:
    nombre_app = nombre_app.lower().strip()
    user_profile = USER_PROFILE

    rutas_busqueda = [
        f"{user_profile}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs",
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        f"{user_profile}\\Desktop",
        f"{user_profile}\\AppData\\Local\\Programs",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
    ]

    patrones_lnk = [f"{nombre_app}.lnk", f"*{nombre_app}*.lnk"]
    for ruta in rutas_busqueda:
        if not os.path.exists(ruta): continue
        for patron in patrones_lnk:
            try:
                busqueda = glob.glob(f"{ruta}\\{patron}") or glob.glob(f"{ruta}\\**\\{patron}", recursive=True)
                if busqueda:
                    print(f"🎯 Buscador Universal: ¡Acceso directo encontrado! -> {busqueda[0]}")
                    return busqueda[0]
            except: continue

    posibles_nombres_exe = [f"{nombre_app}.exe", f"*{nombre_app}*.exe", f"{nombre_app}launcher.exe"]
    for ruta in rutas_busqueda:
        if not os.path.exists(ruta): continue
        for patron in posibles_nombres_exe:
            try:
                busqueda = glob.glob(f"{ruta}\\{patron}") or glob.glob(f"{ruta}\\**\\{patron}", recursive=True)
                if busqueda:
                    for resultado in busqueda:
                        if "update" not in resultado.lower() and "setup" not in resultado.lower() and "uninst" not in resultado.lower():
                            print(f"🎯 Buscador Universal: Ejecutable encontrado -> {resultado}")
                            return resultado
                    return busqueda[0]
            except: continue
    return ""


# ==========================================
# 🖥️ FUNCIONES AVANZADAS DE PANTALLAS Y MONITORES
# ==========================================
def obtener_monitores_por_numero():
    """Devuelve {numero: monitor} usando el MISMO número que Windows muestra
    en Configuración > Sistema > Pantalla."""
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
    monitores = obtener_monitores_por_numero()
    monitor = monitores.get(numero_monitor)
    if not monitor:
        return False
    hwnd = encontrar_hwnd_por_titulo(nombre_app)
    if not hwnd:
        return False
    return mover_hwnd_a_monitor(hwnd, monitor)

def _abrir_app_silencioso(nombre_app: str) -> bool:
    """Abre aplicaciones sin voz adicional para no duplicar audios."""
    nombre_app = nombre_app.lower().strip()
    if nombre_app in ["whatsapp", "wasap", "uatsap"]:
        subprocess.Popen("explorer.exe shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App", shell=True)
        return True
    if nombre_app in ["spotify", "discord"]:
        webbrowser.open(f"{nombre_app}://")
        return True
    ruta = buscar_ejecutable_automatico(nombre_app)
    if ruta:
        os.startfile(ruta) if ruta.endswith(".lnk") else subprocess.Popen(f'"{ruta}"', shell=True)
        return True
    return False

def abrir_app_en_monitor(nombre_app: str, numero_monitor: int):
    """Abre y reposiciona una aplicación en un monitor específico manteniendo el foco."""
    hwnd_foco_previo = win32gui.GetForegroundWindow()
    if not _abrir_app_silencioso(nombre_app):
        return False

    hwnd_nuevo = None
    for _ in range(20):  # hasta 4 segundos esperando que la ventana aparezca
        time.sleep(0.2)
        hwnd_nuevo = encontrar_hwnd_por_titulo(nombre_app)
        if hwnd_nuevo:
            break

    if hwnd_nuevo:
        monitores = obtener_monitores_por_numero()
        monitor = monitores.get(numero_monitor)
        if monitor:
            mover_hwnd_a_monitor(hwnd_nuevo, monitor)

    try:
        win32gui.SetForegroundWindow(hwnd_foco_previo)
    except Exception:
        pass
    return True


# ==========================================
# 🎮 MANEJADOR DE COMANDOS LOCALES
# ==========================================
def ejecutar_comando_local(texto_usuario: str) -> bool:
    accion = texto_usuario.lower().strip()
    user_profile = USER_PROFILE

    palabras_pregunta = [
        "busca información", "búscame información", "investiga",
        "qué es", "quién es", "cuánto", "cuándo", "explícame",
        "cómo se hace", "cómo funciona", "dime sobre", "cuál es"
    ]
    if any(w in accion for w in palabras_pregunta) or any(w in accion for w in PALABRAS_TAREA):
        print("🧠 Detectada intención de pregunta/tarea — sin ejecutar acción local")
        return False

    # ---------------------------------------------------------
    # 🖥️ COMANDOS AVANZADOS DE MONITORES POR NUMERACIÓN DE WINDOWS
    # ---------------------------------------------------------
    if any(w in accion for w in ["pantalla", "monitor"]) and extraer_numero(accion) is not None:
        numero_monitor = extraer_numero(accion)

        if any(w in accion for w in ["abre", "inicia", "pon", "ejecuta"]):
            palabras_quitar = ["abre", "inicia", "pon", "ejecuta", "en", "la", "el",
                                "pantalla", "monitor", str(numero_monitor)]
            nombre_app = accion
            for palabra in palabras_quitar:
                nombre_app = nombre_app.replace(palabra, "")
            nombre_app = nombre_app.strip()

            if nombre_app:
                hablar(f"Abriendo {nombre_app} en la pantalla {numero_monitor}.")
                abrir_app_en_monitor(nombre_app, numero_monitor)
                return True

        if any(w in accion for w in ["mueve", "manda", "pasalo", "pásalo"]):
            palabras_quitar = ["mueve", "manda", "pasalo", "pásalo", "a", "la", "el",
                                "pantalla", "monitor", str(numero_monitor)]
            nombre_app = accion
            for palabra in palabras_quitar:
                nombre_app = nombre_app.replace(palabra, "")
            nombre_app = nombre_app.strip()

            if nombre_app:
                if mover_app_a_monitor(nombre_app, numero_monitor):
                    hablar(f"Listo, {nombre_app} ya está en la pantalla {numero_monitor}.")
                else:
                    hablar(f"No encontré una ventana abierta de {nombre_app}.")
                return True

    # ---------------------------------------------------------
    # OTROS COMANDOS LOCALES
    # ---------------------------------------------------------
    if any(w in accion for w in ["volumen", "sonido"]) and not any(w in accion for w in ["pausa", "reproduce"]):
        numero = extraer_numero(accion)
        if any(w in accion for w in ["baja", "bájale", "bajale", "disminuye", "reduce"]):
            nivel = (numero / 100) if numero is not None else 0.15
            ajustar_volumen(nivel)
            hablar(f"Volumen al {int(nivel * 100)} por ciento.")
            return True
        if any(w in accion for w in ["sube", "súbele", "subele", "aumenta"]):
            nivel = (numero / 100) if numero is not None else 0.7
            ajustar_volumen(nivel)
            hablar(f"Volumen al {int(nivel * 100)} por ciento.")
            return True
        if any(w in accion for w in ["silencio", "mute", "quita el sonido"]):
            ajustar_volumen(0.0)
            hablar("Silenciado.")
            return True

    if any(palabra in accion for palabra in ["pausa", "reproduce", "reproducción", "play", "siguiente", "anterior", "quita pausa", "avanza"]):
        if any(w in accion for w in ["pausa", "ponle play", "reproduce", "reproducción", "quita pausa"]):
            print("🎵 Multimedia: Pausar/Reproducir")
            hablar("Hecho.")
            enviar_tecla_multimedia(VK_MEDIA_PLAY_PAUSE)
            return True
        if any(w in accion for w in ["siguiente", "cambia", "siguiente canción", "siguiente video", "avanza"]):
            print("🎵 Multimedia: Siguiente pista")
            hablar("Siguiente.")
            enviar_tecla_multimedia(VK_MEDIA_NEXT_TRACK)
            return True
        if any(w in accion for w in ["anterior", "regresa", "atrás"]):
            print("🎵 Multimedia: Pista anterior")
            hablar("Regresando.")
            enviar_tecla_multimedia(VK_MEDIA_PREV_TRACK)
            return True

    if any(palabra in accion for palabra in ["pantalla", "monitor", "pásalo", "pasalo", "mueve"]):
        if any(w in accion for w in ["mueve a la otra", "pásalo a la otra", "cambia de pantalla", "pasa al otro monitor", "mueve al otro"]):
            print("🖥️ Doble Monitor: Moviendo ventana activa...")
            hablar("Ventana movida, Saúl.")
            pyautogui.hotkey('win', 'shift', 'right')
            return True
        if "maximiza" in accion or "agranda" in accion:
            hablar("Maximizando ventana.")
            pyautogui.hotkey('win', 'up')
            return True
        if "minimiza" in accion or "esconde" in accion:
            hablar("Ventana minimizada.")
            pyautogui.hotkey('win', 'down')
            return True

    if any(palabra in accion for palabra in ["crea una carpeta", "crea la carpeta", "haz una carpeta"]):
        print(f"📁 Procesando comando de archivos para: '{accion}'")
        palabras_carpeta = ["crea", "haz", "una", "la", "carpeta", "llamada", "que se llame"]
        nombre_carpeta = accion
        for palabra in palabras_carpeta:
            nombre_carpeta = nombre_carpeta.replace(palabra, "")
        nombre_carpeta = nombre_carpeta.strip().capitalize()

        if nombre_carpeta:
            ruta_carpeta = os.path.join(user_profile, "Desktop", nombre_carpeta)
            try:
                if not os.path.exists(ruta_carpeta):
                    os.makedirs(ruta_carpeta)
                    print(f"🎯 Carpeta creada con éxito en: {ruta_carpeta}")
                    hablar(f"Ya creé la carpeta {nombre_carpeta} en el escritorio, carnal.")
                else:
                    hablar(f"Esa carpeta ya existe en el escritorio, Saúl.")
                return True
            except Exception as e:
                logger.error(f"Error al crear carpeta: {e}")
                hablar("No pude crear la carpeta por un tema de permisos.")
                return True

    if any(palabra in accion for palabra in ["cierra", "quita", "apaga", "elimina"]):
        print(f"⚙️ Procesando comando de cierre para: '{accion}'")
        if any(w in accion for w in ["pestaña", "pagina", "página", "eso", "ventana"]):
            print("⌨️ Emulando comando de teclado para cerrar pestaña/ventana...")
            hablar("Cerrando pestaña, listo Saúl.")
            pyautogui.hotkey('ctrl', 'w')
            return True

        palabras_cierre = ["cierra", "el", "la", "quita", "apaga", "elimina", "app", "programa"]
        target_app = accion
        for palabra in palabras_cierre:
            target_app = target_app.replace(palabra, "")
        target_app = target_app.strip()

        if target_app:
            if target_app in ["wasap", "uatsap"]: target_app = "whatsapp"
            if target_app == "minecraft": target_app = "javaw"

            print(f"💀 Intentando matar cualquier proceso relacionado con: '{target_app}'")
            hablar(f"Cerrando {target_app}, listo carnal.")

            subprocess.run(f"taskkill /F /IM *{target_app}*", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(f'taskkill /F /FI "WINDOWTITLE eq {target_app}*"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True

    if any(palabra in accion for palabra in ["abre", "inicia", "pon", "ejecuta", "abrir"]):
        print(f"⚙️ Procesando comando local para: '{accion}'")
        if any(w in accion for w in ["página", "pagina", "pestaña", "de la página", "de la pestaña"]):
            palabras_web = ["abre", "el", "la", "pon", "inicia", "por", "fa", "favor", "página", "pagina", "pestaña", "de"]
            sitio_busqueda = accion
            for palabra in palabras_web:
                sitio_busqueda = sitio_busqueda.replace(palabra, "")
            sitio_busqueda = sitio_busqueda.strip()

            if sitio_busqueda:
                if " " not in sitio_busqueda:
                    url_final = f"https://www.{sitio_busqueda}.com" if not any(ext in sitio_busqueda for ext in [".com", ".org", ".net", ".mx"]) else f"https://www.{sitio_busqueda}"
                    hablar(f"Abriendo {sitio_busqueda} en el navegador.")
                else:
                    texto_formateado = urllib.parse.quote(sitio_busqueda)
                    url_final = f"https://www.google.com/search?q={texto_formateado}"
                    hablar(f"Buscando {sitio_busqueda} en Google, Saúl.")
                webbrowser.open(url_final)
                return True

        palabras_a_quitar = ["abre", "el", "la", "inicia", "pon", "por", "fa", "favor", "ejecuta", "abrir"]
        nombre_app = accion
        for palabra in palabras_a_quitar:
            nombre_app = nombre_app.replace(palabra, "")
        nombre_app = nombre_app.strip()

        if "pan de" in nombre_app: nombre_app = "panel de control"
        if "minecraft" in accion:
            nombre_app = "minecraftlauncher" if any(o in accion for o in ["oficial", "original"]) else "prism"

        if nombre_app in ["whatsapp", "wasap", "uatsap"]:
            print("💬 Invocando WhatsApp mediante comando shell ejecutable...")
            hablar("Abriendo WhatsApp, carnal.")
            subprocess.Popen("explorer.exe shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App", shell=True)
            return True

        if nombre_app in ["spotify", "discord"]:
            try:
                print(f"📡 Invocando protocolo del sistema para: '{nombre_app}://'")
                hablar(f"Abriendo {nombre_app}, Saúl.")
                webbrowser.open(f"{nombre_app}://")
                return True
            except: pass

        if nombre_app in ["configuracion", "configuración", "ajustes"]:
            hablar("Abriendo la configuración.")
            webbrowser.open("ms-settings:")
            return True
        elif nombre_app == "panel de control":
            hablar("Abriendo el panel de control.")
            subprocess.Popen("control", shell=True)
            return True

        print(f"🔍 Rastreando ruta en disco duro para '{nombre_app}'...")
        ruta_encontrada = buscar_ejecutable_automatico(nombre_app)

        if ruta_encontrada:
            nombre_limpio = os.path.basename(ruta_encontrada).split(".")[0].capitalize()
            hablar(f"Abriendo {nombre_limpio}, carnal.")
            if ruta_encontrada.endswith(".lnk"):
                os.startfile(ruta_encontrada)
            else:
                subprocess.Popen(f'"{ruta_encontrada}"', shell=True)
            return True
        else:
            texto_formateado = urllib.parse.quote(nombre_app)
            print(f"❌ No se encontró localmente. Buscando en Google: {nombre_app}")
            hablar(f"No encontré la aplicación, pero te lo busco en Google.")
            webbrowser.open(f'https://www.google.com/search?q={texto_formateado}')
            return True

    return False


# ==========================================
# 🖥️ ÍCONO EN LA BANDEJA DEL SISTEMA
# ==========================================
def _crear_imagen_icono():
    imagen = Image.new("RGB", (64, 64), color=(20, 20, 20))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.ellipse((8, 8, 56, 56), fill=(0, 200, 120))
    return imagen

_icono_bandeja = None

def _salir_desde_tray(icon, item):
    global running
    running = False
    logger.info("Cierre solicitado desde el ícono de la bandeja.")
    icon.stop()

def iniciar_icono_bandeja():
    global _icono_bandeja
    _icono_bandeja = pystray.Icon(
        "solovino",
        _crear_imagen_icono(),
        "Solovino Bot",
        menu=pystray.Menu(
            pystray.MenuItem("Solovino está activo 🐕", None, enabled=False),
            pystray.MenuItem("Salir", _salir_desde_tray)
        )
    )
    _icono_bandeja.run()


# ==========================================
# 🧠 BUCLE PRINCIPAL (MODO REPOSO Y ATENTO)
# ==========================================
def chat_por_voz():
    global running
    recognizer = sr.Recognizer()

    config_busqueda = types.GenerateContentConfig(tools=[{"google_search": {}}])
    chat_busqueda = client.chats.create(model="gemini-2.5-flash", config=config_busqueda)

    config_tareas = types.GenerateContentConfig(tools=[leer_portapapeles, escribir_portapapeles])
    chat_tareas = client.chats.create(model="gemini-2.5-flash", config=config_tareas)

    device_info = sd.query_devices(kind='input')
    samplerate_nativo = device_info['default_samplerate']
    print(f"🎙️ Micro detectado: {device_info['name']}")
    logger.info(f"Micro detectado: {device_info['name']} @ {samplerate_nativo}Hz")

    mandar_notificacion("Solovino Online", "💤 En guardia. Di 'Solovino'...")
    print("💤 Solovino listo de fondo.")

    with sd.InputStream(samplerate=samplerate_nativo, channels=1, callback=callback_audio):
        while running:
            try:
                user_input = escuchar_segmento(recognizer, samplerate_nativo, segundos_max=CONFIG["segundos_espera_reposo"])

                if PALABRA_CLAVE in user_input or "solo vino" in user_input:
                    video_pausado = pausar_video_para_escuchar()   # 🎬 pausa lo que se este viendo
                    nivel_previo = bajar_volumen()                  # 🔉 y ademas baja el volumen por si acaso
                    mandar_notificacion("🐕 Solovino Atento", "Te escucho Saúl...")
                    hablar("¿Qué onda Saúl? Dime.")

                    print("🎙️ [Atento] Escuchando orden...")
                    orden = escuchar_segmento(recognizer, samplerate_nativo, segundos_max=CONFIG["segundos_espera_orden"])

                    restaurar_volumen(nivel_previo)
                    reanudar_video(video_pausado)                   # ▶️ solo reanuda si de verdad pauso algo

                    if not orden:
                        mandar_notificacion("💤 Solovino Dormido", "Volviendo a reposo.")
                        hablar("Ya no me dijiste nada. Me regreso a dormir.")
                        continue

                    print(f"📥 Orden recibida en Modo Atento: '{orden}'")
                    logger.info(f"Orden: {orden}")

                    if "salir" in orden or "adiós" in orden:
                        hablar("Sobres, ahí nos vemos.")
                        running = False
                        if _icono_bandeja:
                            _icono_bandeja.stop()
                        break

                    if ejecutar_comando_local(orden):
                        mandar_notificacion("💤 Solovino Dormido", "Volviendo a reposo.")
                        time.sleep(1.5)
                        continue

                    if any(w in orden for w in PALABRAS_TAREA):
                        print("🧩 Enviando a chat de TAREAS (function calling)")
                        response = chat_tareas.send_message(orden)
                    else:
                        print("🌐 Enviando a chat de BÚSQUEDA (google_search)")
                        response = chat_busqueda.send_message(orden)

                    if response.text:
                        hablar(response.text)

                    mandar_notificacion("💤 Solovino Dormido", "Volviendo a reposo.")

            except KeyboardInterrupt:
                print("\n👋 Saliendo del asistente...")
                running = False
                break
            except Exception as e:
                logger.error(f"Excepción en el bucle principal: {e}")
                print(f"⚠️ Alerta en bucle: {e}")
                time.sleep(1)


def hilo_supervisor():
    """Si el hilo de voz truena por algo inesperado, lo reinicia solo en vez de morirse en silencio."""
    while running:
        try:
            chat_por_voz()
            break
        except Exception as e:
            logger.error(f"El asistente se cayó, reiniciando en 3s: {e}")
            time.sleep(3)


if __name__ == "__main__":
    try:
        logger.info("=== Solovino iniciando ===")
        hilo_asistente = threading.Thread(target=hilo_supervisor, daemon=True)
        hilo_asistente.start()
        try:
            iniciar_icono_bandeja()
        except KeyboardInterrupt:
            running = False
            if _icono_bandeja:
                _icono_bandeja.stop()
    except KeyboardInterrupt:
        running = False
        print("\n👋 Programa detenido.")
    logger.info("=== Solovino detenido ===")