"""
Configuración del asistente: logging a archivo (necesario cuando corre sin
consola), config.json editable sin recompilar, variables del .env y las
listas de palabras clave que usa el resto del programa.

Todo vive en %APPDATA%\\Solovino (ver rutas.py).
"""
import os
import sys
import json
import logging
import logging.handlers

from dotenv import load_dotenv

from rutas import ruta_datos, buscar_recurso, migrar_archivo_viejo

# Los print usan emojis; si la salida no es una consola UTF-8 (redirigida a
# archivo, tarea programada, etc.) Python truena con UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------
# 🔑 .env (junto al .exe/main.py, o en %APPDATA%\Solovino)
# ---------------------------------------------------------
VERSION = "3.1"

_env = buscar_recurso(".env")
if _env:
    load_dotenv(_env)


def guardar_clave(nombre: str, valor: str):
    """Guarda una API key en el .env que se cargó (o en %APPDATA%\\Solovino\\.env
    si no hay uno o no se puede escribir, p. ej. el .exe en Archivos de programa)
    y la aplica de inmediato."""
    from dotenv import set_key
    valor = valor.strip()
    for ruta in (buscar_recurso(".env"), ruta_datos(".env")):
        if not ruta:
            continue
        try:
            if not os.path.exists(ruta):
                open(ruta, "a", encoding="utf-8").close()
            set_key(ruta, nombre, valor, quote_mode="never")
            break
        except OSError:
            continue
    os.environ[nombre] = valor

# ---------------------------------------------------------
# 📝 LOGGING A ARCHIVO
# ---------------------------------------------------------
LOG_PATH = ruta_datos("solovino.log")

logger = logging.getLogger("solovino")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(threadName)s - %(message)s"))
    logger.addHandler(_handler)


# ---------------------------------------------------------
# ⚙️ CONFIGURACIÓN EXTERNA (config.json) — editable sin recompilar
# ---------------------------------------------------------
CONFIG_PATH = ruta_datos("config.json")
migrar_archivo_viejo("solovino_config.json", "config.json")

CONFIG_DEFAULT = {
    "nombre_usuario": "Saúl",

    # --- Activación ---
    "palabra_clave": "solovino",
    "variantes_palabra_clave": ["solo vino", "solo bino", "solobino", "sol vino"],
    "deteccion_palabra_clave": "local",  # "local" = Vosk, sin internet; "google" = como antes
    "tecla_hablar": "ctrl+alt+space",    # mantener = hablar mientras la presionas; toque = escucha hasta que te calles

    # --- Escucha ---
    "dispositivo_entrada": "",           # "" = el micrófono predeterminado de Windows (sigue al que cambies)
    "sensibilidad_vad": 2,               # 0 a 3: qué tan estricto es para decidir que algo es voz (3 = ignora más ruido)
    "factor_ganancia": 1.0,
    "nivel_volumen_escucha": 0.15,
    "segundos_espera_orden": 6,          # cuánto te espera a que EMPIECES a dar la orden
    "segundos_silencio_orden": 1.2,      # silencio que significa "ya terminé"
    "segundos_seguimiento": 5,           # tras una respuesta, escucha sin palabra clave (0 = desactivado)
    "saludo_al_despertar": False,        # False = pitido; True = dice "¿Qué onda? Dime."

    # --- Voz ---
    "usar_voz_neural": True,             # voz natural de Microsoft (necesita internet; si falla usa la de Windows)
    "voz_neural": "es-MX-JorgeNeural",   # otras: es-MX-DaliaNeural, es-ES-AlvaroNeural
    "velocidad_voz": "+10%",

    # --- IA ---
    "modelo_ia": "gemini-2.5-flash",
    "minutos_memoria_chat": 15,          # tras este tiempo sin hablar, olvida la conversación

    # --- Seguridad ---
    "confirmar_acciones": True,          # pregunta antes de cerrar apps, apagar o suspender

    # --- Spotify ---
    "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
}


def cargar_config():
    data = {}
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception as e:
        logger.error(f"Error leyendo config.json, uso valores por defecto: {e}")
        return CONFIG_DEFAULT.copy()

    faltantes = {k: v for k, v in CONFIG_DEFAULT.items() if k not in data}
    if faltantes:
        # Escribe las opciones nuevas en el archivo para que puedas verlas y editarlas.
        data.update(faltantes)
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"No pude actualizar config.json: {e}")
    return data


CONFIG = cargar_config()


def guardar_config(cambios: dict):
    """Actualiza CONFIG en su lugar (todos los módulos ven el cambio al
    instante) y lo escribe en config.json."""
    CONFIG.update(cambios)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, indent=4, ensure_ascii=False)
    logger.info(f"Configuración guardada: {cambios}")
NOMBRE = CONFIG["nombre_usuario"]
PALABRA_CLAVE = CONFIG["palabra_clave"].lower().strip()  # el texto reconocido siempre llega en minúsculas
# Las más largas primero, para que "solo vino" gane sobre "sol vino" al recortar la orden.
PALABRAS_CLAVE = sorted({PALABRA_CLAVE, *(v.lower().strip() for v in CONFIG["variantes_palabra_clave"])},
                        key=len, reverse=True)

# ---------------------------------------------------------
# 🗣️ VOCABULARIO — agrega sinónimos aquí, sin tocar la lógica de comandos.py
# ---------------------------------------------------------
# Si la orden trae alguna de estas, no se ejecuta como comando rápido: se
# manda a Gemini, que entiende mejor la intención y tiene herramientas.
PALABRAS_TAREA = [
    "resume", "resumir", "resúmeme", "resumeme",
    "copia", "copiar", "cópiame", "copiame",
    "pega", "pegar", "portapapeles",
    "explica esto", "explícame esto", "explicame esto",
    "traduce esto", "traduce lo que"
]

PALABRAS_PREGUNTA = [
    "busca información", "búscame información", "investiga",
    "qué es", "quién es", "cuánto", "cuándo", "explícame",
    "cómo se hace", "cómo funciona", "dime sobre", "cuál es"
]

PALABRAS_SI = ["sí", "si", "dale", "claro", "ándale", "andale", "órale", "orale", "va", "sale",
               "simón", "simon", "confirmo", "hazlo", "correcto", "por favor", "ok", "okay", "adelante"]
PALABRAS_NO = ["no", "nel", "cancela", "déjalo", "dejalo", "mejor no", "espera", "para"]
