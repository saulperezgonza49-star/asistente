"""Ícono en la bandeja del sistema — necesario para poder cerrar el programa
limpiamente en cuanto corra como .exe sin ventana de consola."""
import pystray
from PIL import Image, ImageDraw

import estado
from config import logger


def _crear_imagen_icono():
    imagen = Image.new("RGB", (64, 64), color=(20, 20, 20))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.ellipse((8, 8, 56, 56), fill=(0, 200, 120))
    return imagen


def _salir_desde_tray(icon, item):
    estado.running = False
    logger.info("Cierre solicitado desde el ícono de la bandeja.")
    icon.stop()


def iniciar_icono_bandeja():
    estado.icono_bandeja = pystray.Icon(
        "solovino",
        _crear_imagen_icono(),
        "Solovino Bot",
        menu=pystray.Menu(
            pystray.MenuItem("Solovino está activo 🐕", None, enabled=False),
            pystray.MenuItem("Salir", _salir_desde_tray)
        )
    )
    estado.icono_bandeja.run()  # bloquea este hilo, por eso corre en el hilo principal