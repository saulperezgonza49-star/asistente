"""Revisión rápida de que todo funciona (útil sobre todo en el .exe).

    Solovino.exe --diagnostico         -> revisa y abre el reporte en el Bloc de notas
    python main.py --diagnostico

El reporte queda en %APPDATA%\\Solovino\\diagnostico.txt.
"""
import os
import time

import numpy as np

from config import CONFIG, VERSION, logger
from rutas import CONGELADO, DIR_APP, ruta_datos


def _revisar(nombre, prueba, resultados):
    inicio = time.time()
    try:
        detalle = prueba() or ""
        resultados.append(f"✓ {nombre}: {detalle} ({time.time() - inicio:.1f} s)")
    except Exception as e:
        resultados.append(f"✗ {nombre}: {type(e).__name__}: {e}")


def _microfono():
    import escucha
    with escucha.Microfono() as mic:
        time.sleep(1.0)
        bloques = 0
        while mic.leer(0) is not None:
            bloques += 1
    if bloques < 20:
        raise RuntimeError(f"solo llegaron {bloques} bloques de audio en 1 s")
    return f"{mic.nombre}, {bloques} bloques en 1 s"


def _vosk():
    import escucha
    detector = escucha.crear_detector_palabra_clave()
    if detector is None:
        raise RuntimeError("no se cargó (¿falta la carpeta modelos junto al .exe?)")
    return f"palabra clave: {detector.frases}"


def _vad():
    import webrtcvad
    webrtcvad.Vad(2).is_speech(np.zeros(480, np.int16).tobytes(), 16000)
    return "webrtcvad funcionando"


def _google():
    import speech_recognition as sr
    silencio = sr.AudioData(np.zeros(16000, np.int16).tobytes(), 16000, 2)
    try:
        sr.Recognizer().recognize_google(silencio, language="es-MX")
    except sr.UnknownValueError:
        pass  # contestó "no entendí": hay conexión y el audio (flac) se mandó bien
    return "responde"


def _voz_neural():
    import voz
    ruta, borrar = voz._generar_audio("Prueba de diagnóstico número " + str(int(time.time())))
    if ruta is None:
        raise RuntimeError("edge-tts no generó audio")
    tamano = os.path.getsize(ruta)
    if borrar:
        os.remove(ruta)
    return f"{CONFIG['voz_neural']}, {tamano} bytes"


def _gemini():
    import ia
    respuesta = ia._obtener_cliente().models.generate_content(
        model=CONFIG["modelo_ia"], contents="Responde solo: ok")
    return f"{CONFIG['modelo_ia']} respondió '{(respuesta.text or '').strip()[:20]}'"


def _spotify():
    if not os.environ.get("SPOTIFY_CLIENT_ID"):
        return "sin configurar (opcional)"
    conectado = os.path.exists(ruta_datos("spotify_token.json"))
    return "Client ID listo, " + ("conectado" if conectado else "falta 'Conectar Spotify'")


def correr(abrir_reporte: bool = True) -> str:
    resultados = [f"Diagnóstico de Solovino {VERSION} — {time.strftime('%Y-%m-%d %H:%M')}",
                  f"{'.exe' if CONGELADO else 'script'} en {DIR_APP}", ""]
    for nombre, prueba in [("Micrófono", _microfono), ("Palabra clave (Vosk)", _vosk),
                           ("Detector de voz", _vad), ("Reconocimiento de Google", _google),
                           ("Voz natural (edge-tts)", _voz_neural), ("Gemini", _gemini),
                           ("Spotify", _spotify)]:
        _revisar(nombre, prueba, resultados)
    reporte = "\n".join(resultados)
    ruta = ruta_datos("diagnostico.txt")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(reporte + "\n")
    logger.info("Diagnóstico:\n" + reporte)
    print(reporte)
    if abrir_reporte:
        os.startfile(ruta)
    return reporte
