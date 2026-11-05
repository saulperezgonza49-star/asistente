"""Ícono en la bandeja del sistema: muestra el estado con colores y tiene el
menú para salir, iniciar con Windows, conectar Spotify y abrir la configuración."""
import os
import threading

import pystray
from PIL import Image, ImageDraw

import autoarranque
import estado
from config import CONFIG, logger
from rutas import DIR_DATOS

COLORES = {
    estado.DORMIDO: (110, 110, 110),     # gris: esperando la palabra clave
    estado.ESCUCHANDO: (0, 200, 120),    # verde: te está escuchando
    estado.PENSANDO: (60, 140, 255),     # azul: consultando a Gemini
    estado.HABLANDO: (255, 170, 0),      # naranja: está hablando
    estado.DICTANDO: (200, 80, 255),     # morado: modo dictado
}
TEXTOS = {
    estado.DORMIDO: "Esperando 'Solovino'",
    estado.ESCUCHANDO: "Escuchando...",
    estado.PENSANDO: "Pensando...",
    estado.HABLANDO: "Hablando...",
    estado.DICTANDO: "Dictando",
}


def _imagen(color):
    imagen = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.ellipse((4, 4, 60, 60), fill=(25, 25, 25))
    dibujo.ellipse((12, 12, 52, 52), fill=color)
    return imagen


_IMAGENES = {nombre: _imagen(color) for nombre, color in COLORES.items()}


def _al_cambiar_estado(nuevo):
    icono = estado.icono_bandeja
    if icono is not None:
        icono.icon = _IMAGENES.get(nuevo, _IMAGENES[estado.DORMIDO])
        icono.title = f"Solovino — {TEXTOS.get(nuevo, nuevo)}"


def _conectar_spotify(icon, item):
    def _tarea():
        import spotify
        icon.notify(spotify.conectar(), "Spotify")
    threading.Thread(target=_tarea, daemon=True).start()


def iniciar_icono_bandeja(on_salir):
    """Muestra el ícono en su propio hilo y regresa de inmediato, para que el
    hilo principal quede libre y Ctrl+C funcione."""
    def _salir(icon, item):
        logger.info("Cierre solicitado desde el ícono de la bandeja.")
        on_salir()

    tecla = CONFIG.get("tecla_hablar") or "sin tecla"
    try:
        estado.icono_bandeja = pystray.Icon(
            "solovino",
            _IMAGENES[estado.DORMIDO],
            "Solovino",
            menu=pystray.Menu(
                pystray.MenuItem(lambda item: f"🐕 {TEXTOS.get(estado.actual, estado.actual)}", None, enabled=False),
                pystray.MenuItem(f"Tecla para hablar: {tecla}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Iniciar con Windows", lambda icon, item: autoarranque.alternar(),
                                 checked=lambda item: autoarranque.activo()),
                pystray.MenuItem("Conectar Spotify", _conectar_spotify),
                pystray.MenuItem("Abrir configuración", lambda icon, item: os.startfile(DIR_DATOS)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir", _salir),
            ),
        )
        estado.al_cambiar(_al_cambiar_estado)
        estado.icono_bandeja.run_detached()
    except Exception as e:
        # Sin ícono el asistente sigue sirviendo; se cierra con Ctrl+C o "salir".
        logger.error(f"No pude crear el ícono de la bandeja: {e}")
        estado.icono_bandeja = None
