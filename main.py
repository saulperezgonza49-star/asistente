"""Punto de entrada de Solovino.

Hilos:
- principal: solo espera; así Ctrl+C siempre funciona.
- asistente: el bucle de voz (reposo -> atento -> orden -> respuesta).
- teclado: la tecla para hablar (atajos.py).
- recordatorios: revisa cada segundo si toca avisar algo.
- bandeja: el ícono con su menú.

Formas de activarlo:
- Decir "Solovino" (detectado sin internet con Vosk).
- Tecla para hablar (ctrl+alt+space por defecto):
    mantener presionada = graba mientras la sostienes;
    un toque = escucha hasta que te calles;
    presionarla mientras habla = lo calla y te escucha.
"""
import ctypes
import logging
import os
import signal
import threading
import time

# Coordenadas reales de pantalla aunque haya escalado (125 %, 150 %...).
# Debe ir antes de crear cualquier ventana.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import estado
from config import CONFIG, NOMBRE, logger
from utils import contiene
import atajos
import dictado
import ia
import recordatorios
from escucha import (Microfono, capturar, reconocer, escuchar, separar_orden,
                     crear_detector_palabra_clave)
from voz import hablar, pitido, mandar_notificacion, limpiar_cache_voz
from volumen import bajar_volumen, restaurar_volumen
from multimedia import pausar_video_para_escuchar, reanudar_video
from comandos import ejecutar_comando_local
from tray import iniciar_icono_bandeja

PALABRAS_SALIR = ("salir", "adiós", "adios", "apágate", "apagate", "ciérrate", "cierrate")


def apagar(motivo: str):
    """Apaga todo de forma ordenada. Se puede llamar desde cualquier hilo."""
    if estado.running:
        logger.info(f"Apagando: {motivo}")
    estado.running = False
    estado.interrumpir_voz.set()
    if estado.icono_bandeja:
        try:
            estado.icono_bandeja.stop()
        except Exception:
            pass


def _tecla_o_anuncio() -> bool:
    return estado.tecla_evento.is_set() or not estado.anuncios.empty()


# ---------------------------------------------------------
# 💤 Reposo
# ---------------------------------------------------------
def esperar_activacion(mic, detector):
    """Espera a que digas la palabra clave, presiones la tecla o venza un
    recordatorio. Regresa (tipo, dato):
      ("voz", "")        dijo "Solovino" (Vosk)
      ("voz", "orden")   dijo "Solovino, orden" (modo Google)
      ("tecla", None)    presionó la tecla para hablar
      ("anuncio", texto) venció un recordatorio
    """
    estado.cambiar(estado.DORMIDO)
    if detector:
        detector.reiniciar()
    while estado.running:
        if estado.tecla_evento.is_set():
            return "tecla", None
        if not estado.anuncios.empty():
            return "anuncio", estado.anuncios.get_nowait()
        if detector:
            bloque = mic.leer(0.1)
            if bloque and detector.procesar(bloque):
                return "voz", ""
        else:
            texto = escuchar(mic, espera_inicio=1.0, silencio_fin=0.6, max_total=8, abortar=_tecla_o_anuncio)
            orden = separar_orden(texto) if texto else None
            if orden is not None:
                return "voz", orden
    return "salir", None


# ---------------------------------------------------------
# 🎙️ Atento
# ---------------------------------------------------------
def escuchar_orden(mic, via: str) -> str:
    """Pausa el video, baja el volumen, avisa y graba la orden."""
    estado.cambiar(estado.ESCUCHANDO)
    video_pausado = pausar_video_para_escuchar()
    nivel_previo = bajar_volumen()
    try:
        if CONFIG.get("saludo_al_despertar"):
            hablar(f"¿Qué onda {NOMBRE}? Dime.")
        else:
            pitido()
        espera, silencio = CONFIG["segundos_espera_orden"], CONFIG["segundos_silencio_orden"]
        if via == "tecla":
            estado.tecla_evento.clear()
            inicio = time.time()
            while estado.tecla_presionada and time.time() - inicio < 0.4:
                time.sleep(0.02)
            if estado.tecla_presionada:  # la mantiene: graba hasta que la suelte
                audio = capturar(mic, mientras=lambda: estado.tecla_presionada, max_total=60)
            else:                        # fue un toque: escucha hasta que te calles
                audio = capturar(mic, espera_inicio=espera, silencio_fin=silencio)
        else:
            audio = capturar(mic, espera_inicio=espera, silencio_fin=silencio)
    finally:
        # Siempre regresa volumen y video, aunque algo falle al escuchar.
        restaurar_volumen(nivel_previo)
        reanudar_video(video_pausado)
    estado.cambiar(estado.PENSANDO)
    return reconocer(audio)


def modo_dictado(mic):
    """Escribe todo lo que digas en la ventana activa hasta que digas
    "termina dictado" o presiones la tecla para hablar."""
    estado.cambiar(estado.DICTANDO)
    hablar("Modo dictado. Di termina dictado para salir.")
    estado.tecla_evento.clear()
    inicio_de_oracion = True
    while estado.running and not estado.tecla_evento.is_set():
        texto = escuchar(mic, espera_inicio=120, silencio_fin=1.0, max_total=30,
                         abortar=lambda: estado.tecla_evento.is_set())
        if not texto:
            continue
        if contiene(texto, dictado.FRASES_FIN):
            break
        escrito = dictado.formatear(texto)
        if not inicio_de_oracion and escrito:  # sigue la misma oración: sin mayúscula
            escrito = escrito[0].lower() + escrito[1:]
        dictado.escribir(escrito + ("" if escrito.endswith("\n") else " "))
        inicio_de_oracion = escrito.rstrip().endswith((".", "?", "!", "\n"))
    estado.tecla_evento.clear()
    hablar("Dictado terminado.")


def procesar_orden(mic, orden: str) -> bool:
    """Ejecuta la orden. Regresa True si respondió Gemini (para seguir
    escuchando sin palabra clave por si quieres preguntar algo más)."""
    print(f"📥 Orden: '{orden}'")
    logger.info(f"Orden: {orden}")

    if orden.strip(" .!") in PALABRAS_SALIR:
        hablar("Sobres, ahí nos vemos.")
        apagar("comando de voz")
        return False
    if contiene(orden, dictado.FRASES_INICIO):
        modo_dictado(mic)
        return False
    if ejecutar_comando_local(orden):
        return False

    estado.cambiar(estado.PENSANDO)
    hablar(ia.responder(orden))
    return True


def anunciar(mensaje: str):
    for _ in range(2):
        pitido(1200, 150)
    hablar(f"{NOMBRE}, te recuerdo: {mensaje}.")


def chat_por_voz():
    detector = crear_detector_palabra_clave()
    ia.disponible()  # deja en el log si falta la API key

    with Microfono() as mic:
        estado.microfono = mic
        print(f"🎙️ Micro: {mic.nombre}")
        tecla = CONFIG.get("tecla_hablar") or "sin tecla"
        modo = "local (sin internet)" if detector else "con Google"
        print(f"💤 Solovino listo. Di 'Solovino' [{modo}] o usa {tecla}. Ctrl+C para salir.")
        mandar_notificacion("Solovino listo", f"Di 'Solovino' o usa {tecla}.")

        while estado.running:
            try:
                tipo, dato = esperar_activacion(mic, detector)
                if tipo == "salir":
                    break
                if tipo == "anuncio":
                    anunciar(dato)
                    continue

                orden = dato or escuchar_orden(mic, tipo)
                resto = separar_orden(orden)  # "Solovino, ..." repetido por costumbre
                if resto:
                    orden = resto
                if not estado.running:
                    break
                if not orden:
                    print("💤 No escuché ninguna orden, vuelvo a reposo.")
                    continue

                seguir = procesar_orden(mic, orden)
                segundos = CONFIG.get("segundos_seguimiento", 0)
                while seguir and segundos and estado.running:
                    estado.cambiar(estado.ESCUCHANDO)
                    texto = escuchar(mic, espera_inicio=segundos, silencio_fin=CONFIG["segundos_silencio_orden"],
                                     abortar=_tecla_o_anuncio)
                    if not texto:
                        break
                    seguir = procesar_orden(mic, separar_orden(texto) or texto)
            except Exception as e:
                logger.exception(f"Excepción en el bucle principal: {e}")
                print(f"⚠️ Alerta en bucle: {e}")
                time.sleep(1)
    estado.microfono = None


def hilo_supervisor():
    """Si el hilo de voz truena por algo inesperado (p. ej. desconectaste el
    micrófono), lo reinicia solo en vez de morirse en silencio."""
    while estado.running:
        try:
            chat_por_voz()
        except Exception as e:
            logger.exception(f"El asistente se cayó, reiniciando en 3s: {e}")
            print(f"⚠️ El asistente se cayó ({e}), reiniciando en 3s...")
            time.sleep(3)


def main():
    logger.info("=== Solovino iniciando ===")
    limpiar_cache_voz()
    iniciar_icono_bandeja(on_salir=lambda: apagar("ícono de la bandeja"))
    atajos.iniciar_tecla_hablar()
    recordatorios.iniciar()
    threading.Thread(target=hilo_supervisor, daemon=True, name="asistente").start()

    # Cierre desde la consola (Ctrl+C / Ctrl+Break / cerrar la ventana).
    signal.signal(signal.SIGINT, lambda *_: apagar("Ctrl+C"))
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, lambda *_: apagar("Ctrl+Break"))

    try:
        while estado.running:
            time.sleep(0.2)  # pasitos cortos: Ctrl+C se procesa al instante
    except KeyboardInterrupt:
        apagar("Ctrl+C")

    print("\n👋 Solovino detenido.")
    logger.info("=== Solovino detenido ===")
    logging.shutdown()
    # Salida inmediata: no esperamos a que termine una consulta a Google o
    # Gemini que se haya quedado colgada en el hilo de voz.
    os._exit(0)


if __name__ == "__main__":
    main()
