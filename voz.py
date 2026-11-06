"""
Salida de voz y avisos: voz neural (edge-tts) con respaldo de la voz de
Windows (SAPI), pitido de "te escucho" y notificaciones.
"""
import asyncio
import ctypes
import hashlib
import os
import re
import threading
import time
import uuid
import winsound
from concurrent.futures import ThreadPoolExecutor

import estado
from config import CONFIG, logger
from rutas import ruta_datos

DIR_CACHE = ruta_datos("cache_voz")
os.makedirs(DIR_CACHE, exist_ok=True)


def _debe_callarse() -> bool:
    return estado.interrumpir_voz.is_set() or not estado.running


# ---------------------------------------------------------
# 🎧 VOZ NEURAL (edge-tts) — se reproduce con MCI de Windows, sin librerías extra
# ---------------------------------------------------------
def _dividir_en_frases(texto: str):
    """Parte el texto en frases de ~40+ caracteres: la primera se genera
    rápido y las demás se van generando mientras suena la anterior."""
    partes = [p for p in re.split(r'(?<=[.!?;:])\s+', texto.strip()) if p]
    frases, actual = [], ""
    for p in partes:
        actual = f"{actual} {p}".strip()
        if len(actual) >= 40:
            frases.append(actual)
            actual = ""
    if actual:
        frases.append(actual)
    return frases or [texto]


def _generar_audio(texto: str, voz: str = None, velocidad: str = None):
    """Genera el mp3 de una frase. Las frases cortas se guardan en caché
    ("Listo.", "Siguiente."...) para que suenen al instante la próxima vez."""
    import edge_tts
    voz = voz or CONFIG["voz_neural"]
    velocidad = velocidad or CONFIG["velocidad_voz"]
    cachear = len(texto) <= 60
    if cachear:
        clave = hashlib.md5(f"{voz}|{velocidad}|{texto}".encode("utf-8")).hexdigest()
        ruta = os.path.join(DIR_CACHE, f"{clave}.mp3")
        if os.path.exists(ruta):
            return ruta, False
    else:
        ruta = os.path.join(DIR_CACHE, f"tmp_{uuid.uuid4().hex}.mp3")

    async def _guardar():
        await asyncio.wait_for(edge_tts.Communicate(texto, voz, rate=velocidad).save(ruta), timeout=10)

    # El servicio de Microsoft a veces responde "No audio was received" sin
    # razón (≈1 de cada 3 veces en pruebas): se reintenta antes de rendirse.
    for intento in range(3):
        try:
            asyncio.run(_guardar())
            return ruta, not cachear  # (ruta, hay_que_borrarlo_después)
        except Exception as e:
            error = e
            if "NoAudioReceived" not in type(e).__name__ and "No audio" not in str(e):
                break  # otro error (sin internet, etc.): no tiene caso reintentar
    logger.error(f"edge-tts falló: {error}")
    try:
        os.remove(ruta)
    except OSError:
        pass
    return None, False


def _mci(comando: str) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    error = ctypes.windll.winmm.mciSendStringW(comando, buffer, 255, 0)
    if error:
        raise RuntimeError(f"MCI error {error} en: {comando}")
    return buffer.value


def _reproducir_mp3(ruta: str):
    alias = f"solovino_{uuid.uuid4().hex[:8]}"
    _mci(f'open "{ruta}" type mpegvideo alias {alias}')
    try:
        _mci(f"play {alias}")
        while _mci(f"status {alias} mode") == "playing":
            if _debe_callarse():
                _mci(f"stop {alias}")
                break
            time.sleep(0.05)
    finally:
        _mci(f"close {alias}")


def _hablar_neural(texto: str):
    """Regresa la lista de frases que NO se pudieron decir (para la voz de respaldo)."""
    frases = _dividir_en_frases(texto)
    with ThreadPoolExecutor(max_workers=1) as hilo:
        siguiente = hilo.submit(_generar_audio, frases[0])
        for i in range(len(frases)):
            ruta, borrar = siguiente.result()
            if i + 1 < len(frases):
                siguiente = hilo.submit(_generar_audio, frases[i + 1])
            if ruta is None:
                return frases[i:]
            try:
                _reproducir_mp3(ruta)
            except Exception as e:
                logger.error(f"No pude reproducir el audio: {e}")
                return frases[i:]
            finally:
                if borrar:
                    try:
                        os.remove(ruta)
                    except OSError:
                        pass
            if _debe_callarse():
                return []
    return []


# ---------------------------------------------------------
# 🗣️ VOZ DE WINDOWS (SAPI) — respaldo sin internet
# ---------------------------------------------------------
_local = threading.local()  # una voz SAPI por hilo (COM no se comparte entre hilos)


def _voz_sapi():
    if getattr(_local, "voz", None) is None:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        voz = win32com.client.Dispatch("SAPI.SpVoice")
        try:  # prefiere una voz en español si Windows tiene alguna
            for v in voz.GetVoices():
                desc = v.GetDescription().lower()
                if "spanish" in desc or "español" in desc:
                    voz.Voice = v
                    break
        except Exception:
            pass
        _local.voz = voz
    return _local.voz


def _hablar_sapi(texto: str):
    voz = _voz_sapi()
    voz.Speak(texto, 1)  # 1 = asíncrono, para poder cortarlo...
    while not voz.WaitUntilDone(100):  # ...mientras esperamos aquí
        if _debe_callarse():
            voz.Speak("", 3)  # 3 = purgar lo que estaba diciendo
            break


# ---------------------------------------------------------
# API pública
# ---------------------------------------------------------
def hablar(texto: str):
    """Dice el texto y ESPERA a que termine (el micrófono no graba mientras
    tanto). Se calla si presionas la tecla para hablar o cierras el programa."""
    if not texto:
        return
    logger.info(f"solovino dijo: {texto}")
    print(f"🐕 solovino: {texto}")
    estado_previo = estado.actual
    estado.cambiar(estado.HABLANDO)
    estado.interrumpir_voz.clear()
    estado.ia_hablando = True
    try:
        pendiente = [texto]
        if CONFIG.get("usar_voz_neural", True) and not estado.sin_internet:
            pendiente = _hablar_neural(texto)
        if pendiente and not _debe_callarse():
            _hablar_sapi(" ".join(pendiente))
    except Exception as e:
        logger.error(f"No pude hablar: {e}")
    finally:
        time.sleep(0.25)  # deja que se apague el eco del cuarto
        if estado.microfono:
            estado.microfono.vaciar()
        estado.ia_hablando = False
        estado.cambiar(estado_previo if estado_previo != estado.HABLANDO else estado.DORMIDO)


VOCES_NEURALES = ["es-MX-JorgeNeural", "es-MX-DaliaNeural", "es-US-AlonsoNeural", "es-US-PalomaNeural",
                  "es-ES-AlvaroNeural", "es-ES-ElviraNeural", "es-AR-TomasNeural", "es-CO-GonzaloNeural"]


def probar_voz(voz: str, velocidad: str, usar_neural: bool = True) -> str:
    """Para la ventana de ajustes: dice una frase con la voz elegida (sin
    guardar nada). Regresa "" si salió bien o el error."""
    texto = f"Hola {CONFIG['nombre_usuario']}, así sueno yo."
    estado.ia_hablando = True
    try:
        if usar_neural:
            ruta, borrar = _generar_audio(texto, voz, velocidad)
            if ruta is None:
                return "No pude generar la voz neural (¿hay internet?)."
            _reproducir_mp3(ruta)
            if borrar:
                os.remove(ruta)
        else:
            _hablar_sapi(texto)
        return ""
    except Exception as e:
        return str(e)
    finally:
        estado.ia_hablando = False


def pitido(frecuencia=880, duracion_ms=120):
    """Aviso cortito de 'te escucho'. No descarta el audio que ya se grabó:
    si sigues hablando después de "Solovino", no se pierde nada."""
    try:
        winsound.Beep(frecuencia, duracion_ms)
    except Exception:
        pass


def mandar_notificacion(titulo: str, mensaje: str):
    """Notificación de Windows usando el ícono de la bandeja (no necesita
    librerías extra en el .exe). Si no hay ícono, usa plyer."""
    icono = estado.icono_bandeja
    try:
        if icono is not None and getattr(icono, "HAS_NOTIFICATION", False):
            icono.notify(mensaje, titulo)
            return
    except Exception:
        pass
    try:
        from plyer import notification
        notification.notify(title=titulo, message=mensaje, app_name="Solovino", timeout=3)
    except Exception:
        pass


def limpiar_cache_voz(maximo=400):
    """Borra mp3 temporales que hayan quedado y recorta la caché si creció mucho."""
    try:
        archivos = [os.path.join(DIR_CACHE, f) for f in os.listdir(DIR_CACHE) if f.endswith(".mp3")]
        for f in archivos:
            if os.path.basename(f).startswith("tmp_"):
                os.remove(f)
        cache = sorted((f for f in archivos if os.path.exists(f)), key=os.path.getmtime)
        for f in cache[:-maximo]:
            os.remove(f)
    except OSError:
        pass
