"""Dictado: escribe lo que dices en la ventana donde estás.

Se pega con el portapapeles (Ctrl+V) en lugar de teclear letra por letra:
es instantáneo y no falla con acentos ni con la ñ. Lo que tenías copiado se
restaura al terminar.
"""
import re
import time

import pyautogui
import pyperclip

# Orden importante: frases largas antes ("punto y coma" antes que "punto").
PUNTUACION = [
    ("punto y aparte", ".\n"), ("nuevo párrafo", "\n\n"), ("nueva línea", "\n"), ("salto de línea", "\n"),
    ("punto y coma", ";"), ("dos puntos", ":"), ("puntos suspensivos", "..."),
    ("abre signo de interrogación", "¿"), ("cierra signo de interrogación", "?"),
    ("signo de interrogación", "?"), ("abre interrogación", "¿"), ("cierra interrogación", "?"),
    ("abre signo de exclamación", "¡"), ("cierra signo de exclamación", "!"),
    ("signo de exclamación", "!"), ("abre paréntesis", "("), ("cierra paréntesis", ")"),
    ("abre comillas", "«"), ("cierra comillas", "»"), ("guion", "-"),
    ("punto", "."), ("coma", ","),
]
_APERTURA = "¿¡(«"

FRASES_FIN = ["termina dictado", "terminar dictado", "fin del dictado", "para de dictar", "deja de dictar",
              "termina el dictado", "sal del dictado", "salir del dictado", "ya terminé de dictar"]
FRASES_INICIO = ["modo dictado", "empieza a dictar", "voy a dictar", "dictado", "activa el dictado"]


def formatear(texto: str) -> str:
    """'hola coma cómo estás signo de interrogación' -> 'Hola, cómo estás?'"""
    for palabras, simbolo in PUNTUACION:
        texto = re.sub(r'\s*(?<!\w)' + re.escape(palabras) + r'(?!\w)\s*',
                       lambda m, s=simbolo: (" " + s) if s in _APERTURA else s + ("" if s.endswith("\n") else " "),
                       texto, flags=re.IGNORECASE)
    texto = re.sub(r'([¿¡(«])\s+', r'\1', texto)          # sin espacio después de signos de apertura
    texto = re.sub(r'\s+([,.;:?!)»])', r'\1', texto)       # sin espacio antes de signos de cierre
    texto = texto.replace("«", "\"").replace("»", "\"")
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r' *\n *', '\n', texto).strip(" ")
    # Mayúscula al inicio y después de punto / salto de línea.
    texto = re.sub(r'(^|[.!?]\s+|\n\s*|[¿¡])([a-záéíóúñ])', lambda m: m.group(1) + m.group(2).upper(), texto)
    return texto


def escribir(texto: str):
    """Pega el texto en la ventana activa sin perder lo que tenías copiado."""
    if not texto:
        return
    try:
        anterior = pyperclip.paste()
    except Exception:
        anterior = None
    pyperclip.copy(texto)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)  # deja que la app termine de pegar antes de restaurar
    if anterior is not None:
        try:
            pyperclip.copy(anterior)
        except Exception:
            pass
