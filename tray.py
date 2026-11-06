"""Ícono en la bandeja del sistema: el perrito con un punto del color del
estado, y el menú (Ajustes, Spotify, inicio con Windows, reiniciar, salir).
Doble clic en el ícono abre Ajustes."""
import threading

import pystray

import ajustes
import autoarranque
import estado
import icono
from config import CONFIG, VERSION, logger

COLORES = {
    estado.DORMIDO: (130, 130, 130),     # gris: esperando la palabra clave
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

_IMAGENES = {nombre: icono.dibujar(64, color) for nombre, color in COLORES.items()}


def _texto_estado(nuevo):
    texto = TEXTOS.get(nuevo, nuevo)
    return f"{texto} (sin internet)" if estado.sin_internet else texto


def _al_cambiar_estado(nuevo):
    icono_bandeja = estado.icono_bandeja
    if icono_bandeja is not None:
        icono_bandeja.icon = _IMAGENES.get(nuevo, _IMAGENES[estado.DORMIDO])
        icono_bandeja.title = f"Solovino — {_texto_estado(nuevo)}"


def _conectar_spotify(icon, item):
    def _tarea():
        import spotify
        icon.notify(spotify.conectar(), "Spotify")
    threading.Thread(target=_tarea, daemon=True).start()


def iniciar_icono_bandeja(on_salir, on_reiniciar):
    """Muestra el ícono en su propio hilo y regresa de inmediato, para que el
    hilo principal quede libre y Ctrl+C funcione."""
    def _salir(icon, item):
        logger.info("Cierre solicitado desde el ícono de la bandeja.")
        on_salir()

    try:
        estado.icono_bandeja = pystray.Icon(
            "solovino",
            _IMAGENES[estado.DORMIDO],
            "Solovino",
            menu=pystray.Menu(
                pystray.MenuItem(lambda item: f"🐕 Solovino {VERSION} · {_texto_estado(estado.actual)}",
                                 None, enabled=False),
                pystray.MenuItem(lambda item: f"Tecla para hablar: {CONFIG.get('tecla_hablar') or 'ninguna'}",
                                 None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Ajustes…", lambda icon, item: ajustes.abrir(), default=True),
                pystray.MenuItem("Conectar Spotify", _conectar_spotify),
                pystray.MenuItem("Iniciar con Windows", lambda icon, item: autoarranque.alternar(),
                                 checked=lambda item: autoarranque.activo()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Reiniciar", lambda icon, item: on_reiniciar()),
                pystray.MenuItem("Salir", _salir),
            ),
        )
        estado.al_cambiar(_al_cambiar_estado)
        estado.icono_bandeja.run_detached()
    except Exception as e:
        # Sin ícono el asistente sigue sirviendo; se cierra con Ctrl+C o "salir".
        logger.error(f"No pude crear el ícono de la bandeja: {e}")
        estado.icono_bandeja = None
