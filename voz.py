"""
Entrada/salida de voz: decir texto por las bocinas, mandar notificaciones,
y escuchar el micrófono con corte automático por silencio.
"""
import os
import time
import numpy as np
import winspeech
import speech_recognition as sr
from plyer import notification

import estado
from config import CONFIG, logger


def hablar(texto: str):
    """Dice el texto por los altavoces desactivando el micro temporalmente."""
    estado.ia_hablando = True
    logger.info(f"solovino dijo: {texto}")
    print(f"solovino: {texto}")
    try:
        winspeech.say(texto)
        time.sleep(1.5)
    except Exception:
        os.system(
            'PowerShell -Command "Add-Type –AssemblyName System.Speech; '
            f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{texto}')\""
        )

    with estado.lock:
        estado.audio_buffer = []  # borra el eco que se haya colado mientras hablaba
    estado.ia_hablando = False


def mandar_notificacion(titulo: str, mensaje: str):
    try:
        notification.notify(title=titulo, message=mensaje, app_name="Solovino Bot", timeout=2)
    except Exception:
        pass


def callback_audio(indata, frames, time_info, status):
    """Captura los bloques de audio del micrófono en vivo si la IA no está hablando."""
    if not estado.ia_hablando:
        with estado.lock:
            estado.audio_buffer.append(indata.copy())


def escuchar_segmento(recognizer, samplerate, segundos_max=5, silencio_para_cortar=None) -> str:
    """Escucha el micrófono y corta automáticamente tras detectar silencio tras la voz."""
    silencio_para_cortar = CONFIG["segundos_silencio_corte"] if silencio_para_cortar is None else silencio_para_cortar
    umbral_voz = CONFIG["umbral_voz"]

    inicio = time.time()
    ultimo_sonido = None

    while time.time() - inicio < segundos_max:
        if not estado.running:  # corta de inmediato si ya pidieron cerrar el programa
            return ""
        time.sleep(0.1)
        if estado.ia_hablando:
            return ""
        with estado.lock:
            if estado.audio_buffer:
                ultimo_chunk = estado.audio_buffer[-1]
                if np.max(np.abs(ultimo_chunk)) > umbral_voz:
                    ultimo_sonido = time.time()

        if ultimo_sonido and (time.time() - ultimo_sonido) > silencio_para_cortar:
            break

    if not estado.running:
        return ""

    try:
        with estado.lock:
            if len(estado.audio_buffer) == 0:
                return ""
            datos_crudos = np.concatenate(estado.audio_buffer, axis=0)
            estado.audio_buffer = []

        factor_ganancia = CONFIG.get("factor_ganancia", 1.0)
        if factor_ganancia != 1.0:
            datos_crudos = np.clip(datos_crudos * factor_ganancia, -1.0, 1.0)

        if np.max(np.abs(datos_crudos)) > 0:
            datos_crudos = datos_crudos / np.max(np.abs(datos_crudos)) * 0.9

        audio_int16 = (datos_crudos * 32767).astype(np.int16)
        audio_data = sr.AudioData(audio_int16.tobytes(), int(samplerate), 2)

        texto = recognizer.recognize_google(audio_data, language="es-MX")
        texto_limpio = texto.lower().strip()

        if texto_limpio:
            print(f"🎙️ [Escuchado]: '{texto_limpio}'")
        return texto_limpio
    except Exception:
        return ""