"""Herramientas que Gemini puede usar (function calling).

Gemini lee el nombre, los parámetros y el docstring de cada función para
decidir cuándo llamarla, así que los docstrings están escritos para él.
Cada herramienta regresa un texto con el resultado; Gemini lo usa para
contestarte. Las acciones delicadas piden confirmación por voz.
"""
import functools
import webbrowser
import urllib.parse
from datetime import datetime, timedelta

import pyautogui

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
from config import logger
from dialogo import confirmar


def _segura(funcion):
    """Si una herramienta truena, Gemini recibe el error como texto en vez
    de que se caiga toda la respuesta."""
    @functools.wraps(funcion)
    def envoltura(*args, **kwargs):
        logger.info(f"Herramienta {funcion.__name__}({args}, {kwargs})")
        try:
            return funcion(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Herramienta {funcion.__name__} falló: {e}")
            return f"Error: {e}"
    return envoltura


# ---------------------------------------------------------
# 🌐 Información
# ---------------------------------------------------------
@_segura
def buscar_en_internet(pregunta: str) -> str:
    """Busca en Google información actual: noticias, clima, precios, deportes,
    horarios, datos que cambian o cualquier cosa que no sepas con certeza.

    Args:
        pregunta: lo que hay que buscar, redactado como pregunta completa.
    """
    import ia
    return ia.buscar_en_internet(pregunta)


@_segura
def ver_pantalla(pregunta: str) -> str:
    """Toma una captura del monitor donde está trabajando el usuario y la
    analiza. Úsala cuando pida ver, leer, explicar o ayudar con algo que
    tiene en pantalla ("¿qué dice este error?", "resume esta página").

    Args:
        pregunta: qué quiere saber el usuario sobre su pantalla.
    """
    return pantalla.preguntar_sobre_pantalla(pregunta)


@_segura
def estado_bateria() -> str:
    """Porcentaje de batería y si está cargando."""
    return sistema.bateria()


# ---------------------------------------------------------
# 📋 Portapapeles y texto
# ---------------------------------------------------------
leer_portapapeles = _segura(archivos.leer_portapapeles)
escribir_portapapeles = _segura(archivos.escribir_portapapeles)


@_segura
def escribir_texto(texto: str) -> str:
    """Escribe (pega) un texto en la ventana donde está el cursor del usuario,
    por ejemplo en un chat, un documento o el buscador.

    Args:
        texto: el texto exacto a escribir.
    """
    dictado.escribir(texto)
    return "Texto escrito."


# ---------------------------------------------------------
# 🔊 Audio y música
# ---------------------------------------------------------
@_segura
def ajustar_volumen(porcentaje: int) -> str:
    """Pone el volumen general de la computadora.

    Args:
        porcentaje: de 0 (silencio) a 100.
    """
    porcentaje = max(0, min(100, int(porcentaje)))
    volumen.ajustar_volumen(porcentaje / 100)
    return f"Volumen en {porcentaje} %."


@_segura
def control_multimedia(accion: str) -> str:
    """Controla lo que se esté reproduciendo (YouTube, Spotify, etc.).

    Args:
        accion: "pausa" (pausa o reanuda), "siguiente" o "anterior".
    """
    teclas = {"pausa": multimedia.VK_MEDIA_PLAY_PAUSE, "play": multimedia.VK_MEDIA_PLAY_PAUSE,
              "siguiente": multimedia.VK_MEDIA_NEXT_TRACK, "anterior": multimedia.VK_MEDIA_PREV_TRACK}
    if accion not in teclas:
        return "Acción inválida: usa pausa, siguiente o anterior."
    multimedia.enviar_tecla_multimedia(teclas[accion])
    return "Hecho."


@_segura
def reproducir_en_spotify(busqueda: str, tipo: str = "track") -> str:
    """Pone música en Spotify.

    Args:
        busqueda: canción, artista, álbum o playlist a buscar (ej. "Bohemian Rhapsody Queen").
        tipo: "track" (canción, por defecto), "artist", "album" o "playlist".
    """
    return spotify.reproducir(busqueda, tipo)


# ---------------------------------------------------------
# 🪟 Aplicaciones y ventanas
# ---------------------------------------------------------
@_segura
def abrir_aplicacion(nombre: str) -> str:
    """Abre un programa instalado (chrome, spotify, whatsapp, discord, code,
    calculadora, configuración, panel de control, etc.).

    Args:
        nombre: nombre del programa en minúsculas.
    """
    if apps.abrir_aplicacion(nombre, avisar_voz=False):
        return f"Abrí {nombre}."
    return f"No encontré la aplicación {nombre} instalada."


@_segura
def cerrar_aplicacion(nombre: str) -> str:
    """Cierra por completo un programa (pide confirmación al usuario).

    Args:
        nombre: nombre del programa en minúsculas (ej. "chrome", "discord").
    """
    if not confirmar(f"¿Cierro {nombre}?"):
        return "El usuario canceló; no se cerró nada."
    cerrados = apps.cerrar_aplicacion(nombre)
    return f"Cerré {nombre}." if cerrados else f"{nombre} no estaba abierto."


@_segura
def cerrar_pestana() -> str:
    """Cierra la pestaña o documento activo (Ctrl+W)."""
    pyautogui.hotkey("ctrl", "w")
    return "Pestaña cerrada."


@_segura
def mover_ventana(aplicacion: str = "", pantalla: int = 0) -> str:
    """Mueve una ventana a otro monitor.

    Args:
        aplicacion: programa a mover; vacío = la ventana en la que está el usuario.
        pantalla: número de pantalla (1, 2...); 0 = la siguiente pantalla.
    """
    hwnd = ventanas.encontrar_ventana(aplicacion) if aplicacion else ventanas.ventana_activa()
    resultado = ventanas.mover_ventana(hwnd, pantalla or None)
    return {"ok": "Ventana movida.", "sin_ventana": "No encontré esa ventana abierta.",
            "sin_monitor": f"No existe la pantalla {pantalla}.",
            "un_monitor": "Solo hay una pantalla conectada."}.get(resultado, "No pude mover la ventana.")


@_segura
def abrir_en_pantalla(aplicacion: str, pantalla: int) -> str:
    """Abre un programa (o lo mueve si ya está abierto) en un monitor específico.

    Args:
        aplicacion: programa a abrir.
        pantalla: número de pantalla (1, 2...).
    """
    ventanas.abrir_app_en_monitor(aplicacion, int(pantalla))
    return f"{aplicacion} en la pantalla {pantalla}."


@_segura
def maximizar_o_minimizar(accion: str) -> str:
    """Maximiza o minimiza la ventana activa.

    Args:
        accion: "maximizar" o "minimizar".
    """
    ok = ventanas.maximizar_activa() if accion.startswith("max") else ventanas.minimizar_activa()
    return "Hecho." if ok else "No hay ventana activa."


@_segura
def abrir_pagina_web(sitio_o_busqueda: str) -> str:
    """Abre un sitio en el navegador ("youtube.com", "mercadolibre") o, si es
    una frase, la busca en Google.

    Args:
        sitio_o_busqueda: dominio o texto a buscar.
    """
    texto = sitio_o_busqueda.strip()
    if " " not in texto:
        webbrowser.open(texto if "://" in texto else f"https://{texto if '.' in texto else f'www.{texto}.com'}")
    else:
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(texto)}")
    return "Abierto en el navegador."


@_segura
def crear_carpeta_en_escritorio(nombre: str) -> str:
    """Crea una carpeta nueva en el escritorio.

    Args:
        nombre: nombre de la carpeta.
    """
    ok, ya_existia = archivos.crear_carpeta_en_escritorio(nombre)
    if not ok:
        return "No pude crear la carpeta."
    return "Esa carpeta ya existía." if ya_existia else f"Carpeta {nombre} creada en el escritorio."


# ---------------------------------------------------------
# ⏰ Recordatorios y rutinas
# ---------------------------------------------------------
@_segura
def crear_recordatorio(mensaje: str, minutos_desde_ahora: float = 0, fecha_hora: str = "") -> str:
    """Crea un recordatorio, alarma o temporizador. Usa UNO de los dos tiempos.

    Args:
        mensaje: qué hay que recordarle (ej. "sacar la ropa"); "temporizador" si no dijo qué.
        minutos_desde_ahora: para "en 20 minutos", "en 2 horas" (en minutos).
        fecha_hora: para horas exactas, formato ISO "2026-11-05T17:30" (usa la fecha actual del mensaje).
    """
    if fecha_hora:
        cuando = datetime.fromisoformat(fecha_hora)
    elif minutos_desde_ahora > 0:
        cuando = datetime.now() + timedelta(minutes=minutos_desde_ahora)
    else:
        return "Falta cuándo: dame minutos_desde_ahora o fecha_hora."
    if cuando <= datetime.now():
        return "Esa hora ya pasó."
    recordatorios.crear(mensaje, cuando)
    return f"Recordatorio para {recordatorios.describir_fecha(cuando)}: {mensaje}."


@_segura
def listar_recordatorios() -> str:
    """Dice qué recordatorios y temporizadores hay pendientes."""
    lista = recordatorios.listar()
    if not lista:
        return "No hay recordatorios pendientes."
    return "; ".join(f"{recordatorios.describir_fecha(datetime.fromisoformat(r['cuando']))}: {r['mensaje']}"
                     for r in lista)


@_segura
def cancelar_recordatorio(texto: str = "") -> str:
    """Cancela recordatorios.

    Args:
        texto: parte del mensaje del recordatorio a cancelar; vacío = todos.
    """
    n = recordatorios.cancelar(texto)
    return f"Cancelé {n} recordatorio{'s' if n != 1 else ''}." if n else "No encontré ese recordatorio."


@_segura
def ejecutar_rutina(nombre: str) -> str:
    """Ejecuta una rutina guardada (varias acciones juntas, ej. "trabajo").

    Args:
        nombre: nombre de la rutina; usa listar_rutinas si no sabes cuáles hay.
    """
    return rutinas.ejecutar(nombre)


@_segura
def listar_rutinas() -> str:
    """Nombres de las rutinas disponibles."""
    nombres = list(rutinas.cargar())
    return ", ".join(nombres) if nombres else "No hay rutinas."


# ---------------------------------------------------------
# 💻 Sistema
# ---------------------------------------------------------
@_segura
def bloquear_computadora() -> str:
    """Bloquea la sesión de Windows."""
    sistema.bloquear()
    return "Computadora bloqueada."


@_segura
def suspender_computadora() -> str:
    """Pone la computadora en suspensión (pide confirmación)."""
    if not confirmar("¿Suspendo la computadora?"):
        return "Cancelado por el usuario."
    sistema.suspender()
    return "Suspendiendo."


@_segura
def apagar_computadora(reiniciar: bool = False) -> str:
    """Apaga o reinicia la computadora en 60 segundos (pide confirmación; se
    puede cancelar con cancelar_apagado).

    Args:
        reiniciar: True para reiniciar en vez de apagar.
    """
    accion = "reinicio" if reiniciar else "apago"
    if not confirmar(f"¿Seguro que {accion} la computadora?"):
        return "Cancelado por el usuario."
    sistema.reiniciar() if reiniciar else sistema.apagar()
    return f"La computadora se {'reinicia' if reiniciar else 'apaga'} en un minuto. Di 'cancela el apagado' para detenerlo."


@_segura
def cancelar_apagado() -> str:
    """Cancela un apagado o reinicio programado."""
    sistema.cancelar_apagado()
    return "Apagado cancelado."


TODAS = [
    buscar_en_internet, ver_pantalla, estado_bateria,
    leer_portapapeles, escribir_portapapeles, escribir_texto,
    ajustar_volumen, control_multimedia, reproducir_en_spotify,
    abrir_aplicacion, cerrar_aplicacion, cerrar_pestana, mover_ventana, abrir_en_pantalla,
    maximizar_o_minimizar, abrir_pagina_web, crear_carpeta_en_escritorio,
    crear_recordatorio, listar_recordatorios, cancelar_recordatorio, ejecutar_rutina, listar_rutinas,
    bloquear_computadora, suspender_computadora, apagar_computadora, cancelar_apagado,
]
