"""Rutinas: varias acciones con una sola frase ("modo trabajo").

Se definen en %APPDATA%\\Solovino\\rutinas.json. Cada paso es un objeto con
UNA de estas acciones:
  {"abrir": "code", "pantalla": 1}   abre una app (opcional: en qué pantalla)
  {"cerrar": "discord"}              cierra una app (sin preguntar)
  {"volumen": 30}                    pone el volumen en 30 %
  {"web": "youtube.com"}             abre una página
  {"spotify": "lofi hip hop", "tipo": "playlist"}   pone música
  {"multimedia": "pausa"}            pausa | siguiente | anterior
  {"esperar": 2}                     espera 2 segundos
  {"decir": "A darle"}               lo dice en voz alta
"""
import json
import time
import webbrowser

from config import logger
from rutas import ruta_datos
from utils import contiene

ARCHIVO = ruta_datos("rutinas.json")

EJEMPLO = {
    "trabajo": {
        "frases": ["modo trabajo", "a trabajar", "hora de trabajar"],
        "pasos": [
            {"decir": "Arrancando modo trabajo."},
            {"abrir": "code", "pantalla": 1},
            {"abrir": "chrome", "pantalla": 2},
            {"volumen": 25},
        ],
    },
    "descanso": {
        "frases": ["modo descanso", "hora del descanso"],
        "pasos": [
            {"spotify": "lofi hip hop", "tipo": "playlist"},
            {"volumen": 40},
            {"decir": "Tómate un respiro."},
        ],
    },
}


def cargar() -> dict:
    try:
        with open(ARCHIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        try:
            with open(ARCHIVO, "w", encoding="utf-8") as f:
                json.dump(EJEMPLO, f, indent=4, ensure_ascii=False)
        except OSError:
            pass
        return EJEMPLO
    except (OSError, ValueError) as e:
        logger.error(f"rutinas.json tiene un error: {e}")
        return {}


def buscar(texto: str):
    """Regresa el nombre de la rutina que corresponde al texto, o None."""
    for nombre, rutina in cargar().items():
        frases = rutina.get("frases", []) + [f"rutina {nombre}", f"modo {nombre}"]
        if contiene(texto, [f.lower() for f in frases]):
            return nombre
    return None


def ejecutar(nombre: str) -> str:
    """Corre los pasos de la rutina. Regresa un resumen o un error."""
    import apps
    import multimedia
    import spotify
    import ventanas
    import volumen
    from voz import hablar

    rutina = cargar().get(nombre)
    if not rutina:
        return f"No tengo una rutina llamada {nombre}."
    errores = []
    for paso in rutina.get("pasos", []):
        try:
            if "abrir" in paso:
                if paso.get("pantalla"):
                    ventanas.abrir_app_en_monitor(paso["abrir"], int(paso["pantalla"]))
                else:
                    apps.abrir_aplicacion(paso["abrir"], avisar_voz=False)
            elif "cerrar" in paso:
                apps.cerrar_aplicacion(paso["cerrar"])
            elif "volumen" in paso:
                volumen.ajustar_volumen(float(paso["volumen"]) / 100)
            elif "web" in paso:
                sitio = paso["web"]
                webbrowser.open(sitio if "://" in sitio else f"https://{sitio}")
            elif "spotify" in paso:
                spotify.reproducir(paso["spotify"], paso.get("tipo", "track"))
            elif "multimedia" in paso:
                teclas = {"pausa": multimedia.VK_MEDIA_PLAY_PAUSE, "play": multimedia.VK_MEDIA_PLAY_PAUSE,
                          "siguiente": multimedia.VK_MEDIA_NEXT_TRACK, "anterior": multimedia.VK_MEDIA_PREV_TRACK}
                multimedia.enviar_tecla_multimedia(teclas[paso["multimedia"]])
            elif "esperar" in paso:
                time.sleep(float(paso["esperar"]))
            elif "decir" in paso:
                hablar(paso["decir"])
            else:
                errores.append(f"paso desconocido {paso}")
        except Exception as e:
            logger.error(f"Rutina {nombre}, paso {paso}: {e}")
            errores.append(str(paso))
    if errores:
        return f"Rutina {nombre} terminada, pero fallaron {len(errores)} pasos."
    return f"Rutina {nombre} lista."
