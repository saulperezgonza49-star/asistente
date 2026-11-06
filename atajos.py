"""Tecla para hablar (push-to-talk) global.

Se revisa el estado del teclado cada 20 ms con GetAsyncKeyState: no
necesita permisos de administrador ni librerías extra (bueno para el .exe),
y no le quita la tecla a la app que estés usando. Si cambias la tecla en
Ajustes, se aplica sola sin reiniciar.
"""
import ctypes
import threading
import time

import estado
from config import CONFIG, logger

_TECLAS = {
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "mayus": 0x10, "win": 0x5B,
    "space": 0x20, "espacio": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
    "insert": 0x2D, "pausa": 0x13, "pause": 0x13, "bloqdespl": 0x91, "scrolllock": 0x91,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
    **{chr(c): c for c in range(ord("A"), ord("Z") + 1)},
    **{str(d): 0x30 + d for d in range(10)},
}


def parsear_combinacion(texto: str):
    """'ctrl+alt+space' -> [0x11, 0x12, 0x20]. Lanza ValueError si hay una tecla desconocida."""
    codigos = []
    for parte in texto.lower().replace(" ", "").split("+"):
        codigo = _TECLAS.get(parte) or _TECLAS.get(parte.upper())
        if codigo is None:
            raise ValueError(f"Tecla desconocida: '{parte}'")
        codigos.append(codigo)
    return codigos


def _hilo_teclado():
    leer = ctypes.windll.user32.GetAsyncKeyState
    combinacion, codigos, anterior = None, [], False
    while estado.running:
        actual = CONFIG.get("tecla_hablar", "") or ""
        if actual != combinacion:  # cambió en Ajustes (o es la primera vez)
            combinacion = actual
            try:
                codigos = parsear_combinacion(actual) if actual else []
                logger.info(f"Tecla para hablar: {actual or 'desactivada'}")
            except ValueError as e:
                logger.error(f"tecla_hablar inválida: {e}")
                codigos = []
        presionada = bool(codigos) and all(leer(c) & 0x8000 for c in codigos)
        if presionada and not anterior:
            estado.tecla_evento.set()
            estado.interrumpir_voz.set()  # si estaba hablando, que se calle y te escuche
        estado.tecla_presionada = presionada
        anterior = presionada
        time.sleep(0.02)


def iniciar_tecla_hablar():
    threading.Thread(target=_hilo_teclado, daemon=True, name="teclado").start()
