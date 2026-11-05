"""Router de comandos rápidos: órdenes comunes y sin ambigüedad que se
resuelven al instante, sin internet. Si la orden no encaja aquí (regresa
False), main.py se la pasa a Gemini, que tiene las mismas acciones como
herramientas y entiende frases más libres."""
import re
import webbrowser
import urllib.parse
from datetime import datetime, timedelta

import pyautogui

from config import NOMBRE, PALABRAS_TAREA, PALABRAS_PREGUNTA
from dialogo import confirmar
from utils import extraer_numero, limpiar_texto, contiene
from voz import hablar
import apps
import archivos
import dictado
import multimedia
import pantalla
import recordatorios
import rutinas
import sistema
import spotify
import ventanas
import volumen


# ---------------------------------------------------------
# Vocabulario
# ---------------------------------------------------------
VERBOS_MOVER = ["mueve", "muévelo", "muevelo", "muévela", "muevela", "pasa", "pásalo", "pasalo",
                "pásala", "pasala", "manda", "mándalo", "mandalo", "mándala", "mandala",
                "lleva", "llévalo", "llevalo", "llévala", "llevala", "llévate", "llevate", "pásate", "pasate",
                "mándate", "mandate", "cambia", "cámbialo", "cambialo", "cámbiala", "cambiala"]
VERBOS_ABRIR = ["abre", "ábreme", "abreme", "inicia", "pon", "ponme", "ejecuta", "abrir"]
# Palabras que sobran al sacar el nombre de la app de la orden.
RELLENO_PANTALLA = ["a", "al", "la", "el", "en", "de", "del", "mi", "por", "fa", "favor", "número",
                    "pantalla", "monitor", "otra", "otro", "siguiente", "lado", "ventana", "app",
                    "esto", "eso", "esta", "este", "esa", "ese", "lo", "acá", "allá",
                    "uno", "dos", "tres", "cuatro", "primera", "primer", "segunda", "tercera", "cuarta"]

_COMPU = ["computadora", "compu", "pc", "laptop", "máquina", "maquina", "equipo"]
_VER_PANTALLA = ["qué ves", "que ves", "qué hay en mi pantalla", "lee mi pantalla", "lee la pantalla",
                 "mira mi pantalla", "mira la pantalla", "ve mi pantalla", "lo que estoy viendo",
                 "lo que tengo en pantalla", "lo que tengo en la pantalla", "este error", "esta pantalla",
                 "en mi pantalla", "qué dice aquí", "que dice aqui", "qué dice esto", "que dice esto"]
_VERBOS_MUSICA = ["pon", "ponme", "pónme", "reproduce", "toca", "tócame", "quiero escuchar"]
_PISTAS_MUSICA = ["spotify", "la canción", "una canción", "la rola", "una rola", "música de", "musica de",
                  "canciones de", "la playlist", "una playlist", "el álbum", "el album", "el disco"]
_RELLENO_MUSICA = ["pon", "ponme", "pónme", "reproduce", "toca", "tócame", "quiero", "escuchar", "en", "spotify",
                   "la", "el", "una", "un", "canción", "cancion", "canciones", "rola", "música", "musica", "de",
                   "del", "playlist", "lista", "álbum", "album", "disco", "artista", "algo", "por", "favor"]
# "escribe un correo para..." no es texto literal: eso lo redacta Gemini.
_NO_ES_LITERAL = ["un correo", "un mensaje", "un texto", "una carta", "un párrafo", "un resumen", "algo", "redacta"]


# ---------------------------------------------------------
# 🖥️ Pantallas
# ---------------------------------------------------------
def _es_orden_de_pantalla(accion: str) -> bool:
    """¿Es algo como "mueve esto a la otra pantalla", "manda chrome a la
    pantalla 2" o "abre spotify en el monitor dos"?"""
    menciona_pantalla = contiene(accion, ["pantalla", "monitor", "la otra", "el otro", "al lado"])
    if not menciona_pantalla or contiene(accion, ["maximiza", "minimiza", "pantalla completa"]):
        return False
    return contiene(accion, VERBOS_MOVER) or (
        contiene(accion, VERBOS_ABRIR) and extraer_numero(accion) is not None)


def _mover_o_abrir_en_pantalla(accion: str) -> bool:
    numero = extraer_numero(accion)
    nombre_app = limpiar_texto(accion, VERBOS_MOVER + VERBOS_ABRIR + RELLENO_PANTALLA
                               + ([str(numero)] if numero is not None else []))
    destino = f"la pantalla {numero}" if numero is not None else "la otra pantalla"

    if contiene(accion, VERBOS_ABRIR) and not contiene(accion, VERBOS_MOVER) and nombre_app:
        hablar(f"Abriendo {nombre_app} en {destino}.")
        ventanas.abrir_app_en_monitor(nombre_app, numero)
        return True

    # Sin nombre ("mueve esto a la otra pantalla") -> la ventana en la que estás.
    hwnd = ventanas.encontrar_ventana(nombre_app) if nombre_app else ventanas.ventana_activa()
    resultado = ventanas.mover_ventana(hwnd, numero)
    que = nombre_app or "la ventana"
    hablar({
        "ok": f"Listo, {que} ya está en {destino}.",
        "sin_ventana": f"No encontré una ventana abierta de {nombre_app}." if nombre_app
                       else "No hay ninguna ventana activa para mover.",
        "sin_monitor": f"No tengo pantalla {numero}. Tienes {len(ventanas.listar_monitores())}.",
        "un_monitor": "Solo detecto una pantalla conectada.",
    }.get(resultado, f"No pude mover {que}. Puede que esté abierta como administrador."))
    return True


# ---------------------------------------------------------
# 🎧 Música, ⏰ temporizadores, 💻 sistema
# ---------------------------------------------------------
def _orden_de_musica(accion: str):
    """("busqueda", "tipo") si es "pon X en spotify" / "pon la canción X"; si no, None."""
    if not (contiene(accion, _VERBOS_MUSICA) and contiene(accion, _PISTAS_MUSICA)):
        return None
    if contiene(accion, ["playlist", "lista"]):
        tipo = "playlist"
    elif contiene(accion, ["álbum", "album", "disco"]):
        tipo = "album"
    elif contiene(accion, ["música de", "musica de", "canciones de", "artista"]):
        tipo = "artist"
    else:
        tipo = "track"
    return limpiar_texto(accion, _RELLENO_MUSICA), tipo


def _orden_de_temporizador(accion: str):
    """(mensaje, segundos) para "pon un temporizador de 5 minutos" o
    "recuérdame en 20 minutos sacar la ropa". Las horas exactas ("a las 5")
    las resuelve Gemini."""
    if not contiene(accion, ["temporizador", "timer", "alarma", "recuérdame", "recuerdame", "avísame", "avisame"]):
        return None
    segundos = recordatorios.parsear_duracion(accion)
    if not segundos or contiene(accion, ["a las", "mañana", "pasado"]):
        return None
    sin_tiempo = re.sub(r'(dentro de |en )?(\S+ )(segundos?|minutos?|horas?)( y media)?|media hora', ' ', accion)
    mensaje = limpiar_texto(sin_tiempo, ["recuérdame", "recuerdame", "avísame", "avisame", "pon", "ponme", "un",
                                         "una", "temporizador", "timer", "alarma", "de", "en", "que", "dentro", "para"])
    return mensaje or "se acabó el tiempo", segundos


def _comando_sistema(accion: str) -> bool:
    if contiene(accion, ["qué hora es", "que hora es", "qué horas son", "que horas son", "dime la hora"]):
        hablar(sistema.hora())
        return True
    if contiene(accion, ["qué día es", "que dia es", "qué fecha es", "que fecha es", "a qué estamos", "fecha de hoy"]):
        hablar(sistema.fecha())
        return True
    if contiene(accion, ["batería", "bateria", "pila"]) and not contiene(accion, ["ahorro"]):
        hablar(sistema.bateria())
        return True
    if contiene(accion, ["cancela el apagado", "cancela el reinicio", "no apagues", "no reinicies", "cancela apagado"]):
        sistema.cancelar_apagado()
        hablar("Apagado cancelado.")
        return True
    if contiene(accion, ["bloquea"]) and contiene(accion, _COMPU + ["sesión", "sesion", "pantalla"]):
        hablar("Bloqueando.")
        sistema.bloquear()
        return True
    if contiene(accion, ["suspende", "suspender"]) and contiene(accion, _COMPU):
        if confirmar("¿Suspendo la computadora?"):
            hablar("Suspendiendo.")
            sistema.suspender()
        else:
            hablar("Va, no la suspendo.")
        return True
    if contiene(accion, ["apaga", "reinicia"]) and contiene(accion, _COMPU):
        reiniciar = contiene(accion, ["reinicia"])
        if confirmar(f"¿Seguro que {'reinicio' if reiniciar else 'apago'} la computadora?"):
            sistema.reiniciar() if reiniciar else sistema.apagar()
            hablar(f"Se {'reinicia' if reiniciar else 'apaga'} en un minuto. Di cancela el apagado si te arrepientes.")
        else:
            hablar("Sale, no hago nada.")
        return True
    if contiene(accion, ["toma una captura", "toma captura", "haz una captura", "captura de pantalla", "screenshot"]):
        sistema.captura_de_pantalla()
        hablar("Captura guardada en Imágenes.")
        return True
    return False


# ---------------------------------------------------------
# Router
# ---------------------------------------------------------
def ejecutar_comando_local(texto_usuario: str) -> bool:
    accion = texto_usuario.lower().strip()

    # 💻 SISTEMA (hora, batería, bloquear, apagar...) — antes de "cerrar/apagar apps"
    if _comando_sistema(accion):
        return True

    # 👀 VER LA PANTALLA — antes del filtro de preguntas ("explícame este error")
    if contiene(accion, _VER_PANTALLA):
        hablar("Déjame ver.")
        hablar(pantalla.preguntar_sobre_pantalla(texto_usuario))
        return True

    # ⌨️ ESCRIBIR TEXTO LITERAL ("escribe hola coma cómo estás")
    literal = re.match(r'^(escribe esto|escríbeme|escribeme|escribe|teclea)[:,]?\s+(.+)', accion)
    if literal and not contiene(literal.group(2), _NO_ES_LITERAL):
        dictado.escribir(dictado.formatear(texto_usuario.strip()[len(literal.group(1)):].strip(" :,")))
        return True

    if contiene(accion, PALABRAS_PREGUNTA) or contiene(accion, PALABRAS_TAREA):
        print("🧠 Pregunta o tarea: se la paso a Gemini")
        return False

    # 🔁 RUTINAS ("modo trabajo")
    rutina = rutinas.buscar(accion)
    if rutina:
        resultado = rutinas.ejecutar(rutina)
        if "fallaron" in resultado or "No tengo" in resultado:
            hablar(resultado)
        return True

    # ⏰ TEMPORIZADORES Y RECORDATORIOS RELATIVOS
    temporizador = _orden_de_temporizador(accion)
    if temporizador:
        mensaje, segundos = temporizador
        recordatorios.crear(mensaje, datetime.now() + timedelta(seconds=segundos))
        hablar(f"Listo, te aviso en {recordatorios.describir_tiempo(segundos)}.")
        return True

    # 🖥️ MOVER VENTANAS ENTRE PANTALLAS
    if _es_orden_de_pantalla(accion):
        return _mover_o_abrir_en_pantalla(accion)

    # 🎧 SPOTIFY POR NOMBRE — antes de multimedia: "reproduce X" no es play/pausa
    musica = _orden_de_musica(accion)
    if musica:
        busqueda, tipo = musica
        if not busqueda:
            return False  # "pon música" a secas: que Gemini decida
        hablar(spotify.reproducir(busqueda, tipo))
        return True

    # 🔊 VOLUMEN
    if contiene(accion, ["volumen", "sonido"]) and not contiene(accion, ["pausa", "reproduce"]):
        numero = extraer_numero(accion)
        nivel = None
        if contiene(accion, ["silencio", "silencia", "mute", "quita el sonido"]):
            nivel = 0.0
        elif contiene(accion, ["baja", "bájale", "bajale", "disminuye", "reduce"]):
            nivel = (numero / 100) if numero is not None else 0.15
        elif contiene(accion, ["sube", "súbele", "subele", "aumenta"]):
            nivel = (numero / 100) if numero is not None else 0.7
        elif numero is not None:  # "pon el volumen en 40"
            nivel = numero / 100
        if nivel is not None:
            nivel = max(0.0, min(1.0, nivel))  # que no diga "150 por ciento"
            volumen.ajustar_volumen(nivel)
            hablar("Silenciado." if nivel == 0 else f"Volumen al {round(nivel * 100)} por ciento.")
            return True

    # 🪟 MAXIMIZAR / MINIMIZAR LA VENTANA ACTIVA
    if contiene(accion, ["maximiza", "agranda", "pantalla completa"]):
        ventanas.maximizar_activa()
        hablar("Listo.")
        return True
    if contiene(accion, ["minimiza", "esconde"]):
        ventanas.minimizar_activa()
        hablar("Listo.")
        return True

    # 🎵 MULTIMEDIA
    if contiene(accion, ["pausa", "ponle play", "reproduce", "reproducción", "quita pausa", "play"]):
        hablar("Hecho.")
        multimedia.enviar_tecla_multimedia(multimedia.VK_MEDIA_PLAY_PAUSE)
        return True
    if contiene(accion, ["siguiente", "avanza", "cambia de canción", "cambia la canción",
                         "cambia de video", "cambia el video", "cámbiale"]):
        hablar("Siguiente.")
        multimedia.enviar_tecla_multimedia(multimedia.VK_MEDIA_NEXT_TRACK)
        return True
    if contiene(accion, ["anterior", "regresa la canción", "regresa el video", "atrás"]):
        hablar("Regresando.")
        multimedia.enviar_tecla_multimedia(multimedia.VK_MEDIA_PREV_TRACK)
        return True

    # 📂 CARPETAS
    if contiene(accion, ["crea una carpeta", "crea la carpeta", "haz una carpeta"]):
        nombre_carpeta = limpiar_texto(
            accion, ["crea", "haz", "una", "la", "carpeta", "llamada", "que se llame"]
        ).capitalize()
        if nombre_carpeta:
            ok, ya_existia = archivos.crear_carpeta_en_escritorio(nombre_carpeta)
            if not ok:
                hablar("No pude crear la carpeta por un tema de permisos.")
            elif ya_existia:
                hablar(f"Esa carpeta ya existe en el escritorio, {NOMBRE}.")
            else:
                hablar(f"Ya creé la carpeta {nombre_carpeta} en el escritorio, carnal.")
            return True

    # ❌ CERRAR APLICACIONES / PESTAÑAS
    if contiene(accion, ["cierra", "quita", "apaga", "elimina"]):
        if contiene(accion, ["pestaña", "pagina", "página", "eso", "ventana"]):
            hablar(f"Cerrando pestaña, listo {NOMBRE}.")
            pyautogui.hotkey('ctrl', 'w')
            return True

        target_app = limpiar_texto(accion, ["cierra", "el", "la", "quita", "apaga", "elimina", "app", "programa"])
        if len(target_app) >= 3:  # con nombres muy cortos coincidiría con procesos al azar
            if not confirmar(f"¿Cierro {target_app}?"):
                hablar("Va, lo dejo abierto.")
            elif apps.cerrar_aplicacion(target_app):
                hablar(f"Cerré {target_app}, listo carnal.")
            else:
                hablar(f"No encontré {target_app} abierto.")
            return True

    # 🌐 ABRIR APLICACIONES / PÁGINAS WEB
    if contiene(accion, ["abre", "inicia", "pon", "ejecuta", "abrir"]):
        if contiene(accion, ["página", "pagina", "pestaña", "de la página", "de la pestaña"]):
            sitio_busqueda = limpiar_texto(accion, ["abre", "el", "la", "pon", "inicia", "por", "fa", "favor",
                                                      "página", "pagina", "pestaña", "de"])
            if sitio_busqueda:
                if " " not in sitio_busqueda:
                    url_final = (f"https://www.{sitio_busqueda}.com"
                                 if not any(ext in sitio_busqueda for ext in [".com", ".org", ".net", ".mx"])
                                 else f"https://www.{sitio_busqueda}")
                    hablar(f"Abriendo {sitio_busqueda} en el navegador.")
                else:
                    url_final = f"https://www.google.com/search?q={urllib.parse.quote(sitio_busqueda)}"
                    hablar(f"Buscando {sitio_busqueda} en Google, {NOMBRE}.")
                webbrowser.open(url_final)
                return True

        nombre_app = limpiar_texto(accion, ["abre", "el", "la", "inicia", "pon", "por", "fa", "favor",
                                              "ejecuta", "abrir"])
        if nombre_app in ("música", "musica", "algo de música", "algo"):
            return False  # "pon música": no es una app, que Gemini decida qué poner
        if "pan de" in nombre_app:
            nombre_app = "panel de control"
        if "minecraft" in accion:
            nombre_app = "minecraftlauncher" if contiene(accion, ["oficial", "original"]) else "prism"

        if nombre_app:
            apps.abrir_aplicacion(nombre_app)
            return True

    return False
