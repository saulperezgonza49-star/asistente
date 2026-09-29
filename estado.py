"""
Estado compartido en tiempo de ejecución.

Varios módulos leen y modifican estos valores (el ícono de la bandeja apaga
`running`, el bucle de voz lo revisa todo el tiempo, etc.). Por eso viven
aquí en vez de duplicarse: cualquier módulo que los necesite hace
`import estado` y usa `estado.running`, `estado.audio_buffer`, etc.
directamente — nunca una copia local, porque entonces cada módulo tendría
su propia variable y no se enterarían entre sí de los cambios.
"""
import threading

running = True
ia_hablando = False   # 🛡️ Escudo anti-eco: si es True, el micrófono ignora el audio
audio_buffer = []
lock = threading.Lock()
icono_bandeja = None   # se asigna en tray.py cuando se crea el ícono de la bandeja