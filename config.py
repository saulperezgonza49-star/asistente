"""
Configuración del asistente: logging a archivo (necesario para cuando corre
sin consola), config.json editable sin recompilar, y las listas de palabras
clave que usa el resto del programa para reconocer intenciones.
"""
import os
import json
import logging
import logging.handlers

USER_PROFILE = os.environ.get("USERPROFILE", "C:\\Users\\saul")

# ---------------------------------------------------------
# 📝 LOGGING A ARCHIVO
# ---------------------------------------------------------
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
            data.setdefault(k, v)  # por si agregas opciones nuevas después
        return data
    except Exception as e:
        logger.error(f"Error leyendo config.json, uso valores por defecto: {e}")
        return CONFIG_DEFAULT.copy()


CONFIG = cargar_config()
PALABRA_CLAVE = CONFIG["palabra_clave"]

# ---------------------------------------------------------
# 🗣️ VOCABULARIO — agrega sinónimos aquí, sin tocar la lógica de comandos.py
# ---------------------------------------------------------
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