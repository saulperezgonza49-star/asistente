"""
Estado compartido en tiempo de ejecución.

Varios hilos leen y modifican estos valores (el ícono apaga `running`, el
hilo del teclado marca la tecla de hablar, los recordatorios dejan avisos,
etc.). Siempre se usa `import estado` y `estado.algo`, nunca una copia
local, para que todos vean el mismo valor.
"""
import queue
import threading

running = True
ia_hablando = False          # 🛡️ escudo anti-eco: mientras es True el micrófono descarta audio
lock = threading.Lock()
icono_bandeja = None         # se asigna en tray.py
microfono = None             # escucha.Microfono, se asigna en main.py

# --- Tecla para hablar (la marca atajos.py) ---
tecla_presionada = False             # True mientras la mantienes presionada
tecla_evento = threading.Event()     # se activa cada vez que la presionas
interrumpir_voz = threading.Event()  # pide a hablar() que se calle

# --- Avisos de recordatorios para decir en voz alta (los pone recordatorios.py) ---
anuncios = queue.Queue()

# --- Estado visible (color del ícono de la bandeja) ---
DORMIDO, ESCUCHANDO, PENSANDO, HABLANDO, DICTANDO = "dormido", "escuchando", "pensando", "hablando", "dictando"
actual = DORMIDO
_oyentes = []


def al_cambiar(funcion):
    """Registra una función que se llama con el nuevo estado cada vez que cambia."""
    _oyentes.append(funcion)


def cambiar(nuevo: str):
    global actual
    if nuevo == actual:
        return
    actual = nuevo
    for funcion in list(_oyentes):
        try:
            funcion(nuevo)
        except Exception:
            pass
