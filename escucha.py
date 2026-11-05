"""
Entrada de audio: micrófono, detección de voz (VAD), palabra clave local y
reconocimiento de la orden.

Flujo:
  micrófono -> bloques de 30 ms (16 kHz, int16) -> cola
  reposo:  Vosk revisa la cola buscando "solo vino" (sin internet)
  atento:  el VAD decide cuándo empiezas y terminas de hablar -> Google
"""
import json
import queue
import time
from collections import deque

import numpy as np
import sounddevice as sd
import speech_recognition as sr

import estado
from config import CONFIG, PALABRAS_CLAVE, logger
from rutas import buscar_recurso

TASA = 16000                  # Hz: lo que esperan Vosk, webrtcvad y Google
MUESTRAS_BLOQUE = 480         # 30 ms
CARPETA_MODELO_VOSK = "vosk-model-small-es-0.42"


# ---------------------------------------------------------
# 🎙️ MICRÓFONO
# ---------------------------------------------------------
class Microfono:
    """Abre el micrófono y deja bloques de 30 ms en una cola. Si el micro no
    acepta 16 kHz, graba a su tasa nativa y convierte."""

    def __init__(self):
        info = sd.query_devices(kind="input")
        self.nombre = info["name"]
        try:
            sd.check_input_settings(samplerate=TASA, channels=1, dtype="float32")
            self.tasa_entrada = TASA
        except Exception:
            self.tasa_entrada = int(info["default_samplerate"])
        self.cola = queue.Queue(maxsize=2000)  # ~60 s de audio como máximo
        self._resto = np.zeros(0, dtype=np.int16)
        self._stream = sd.InputStream(samplerate=self.tasa_entrada, channels=1, dtype="float32",
                                      blocksize=int(self.tasa_entrada * 0.03), callback=self._callback)
        logger.info(f"Micro: {self.nombre} @ {self.tasa_entrada} Hz")

    def __enter__(self):
        self._stream.start()
        return self

    def __exit__(self, *_):
        self._stream.stop()
        self._stream.close()

    def _callback(self, indata, frames, time_info, status):
        if estado.ia_hablando:  # no grabarse a sí mismo
            return
        x = indata[:, 0]
        if self.tasa_entrada != TASA:
            n = int(len(x) * TASA / self.tasa_entrada)
            x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
        ganancia = CONFIG.get("factor_ganancia", 1.0)
        pcm = (np.clip(x * ganancia, -1.0, 1.0) * 32767).astype(np.int16)
        datos = np.concatenate((self._resto, pcm))
        completos = len(datos) // MUESTRAS_BLOQUE
        for i in range(completos):
            bloque = datos[i * MUESTRAS_BLOQUE:(i + 1) * MUESTRAS_BLOQUE].tobytes()
            try:
                self.cola.put_nowait(bloque)
            except queue.Full:  # nadie está leyendo: tira lo más viejo
                try:
                    self.cola.get_nowait()
                    self.cola.put_nowait(bloque)
                except queue.Empty:
                    pass
        self._resto = datos[completos * MUESTRAS_BLOQUE:]

    def leer(self, timeout=0.1):
        try:
            return self.cola.get(timeout=timeout)
        except queue.Empty:
            return None

    def vaciar(self):
        while True:
            try:
                self.cola.get_nowait()
            except queue.Empty:
                return


# ---------------------------------------------------------
# 🗣️ DETECCIÓN DE VOZ (VAD)
# ---------------------------------------------------------
class DetectorVoz:
    """Distingue voz humana de ruido (ventilador, tele, teclado). Antes se
    usaba solo el volumen, y cualquier ruido fuerte contaba como voz."""

    def __init__(self):
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(int(CONFIG.get("sensibilidad_vad", 2)))
        except Exception as e:
            logger.error(f"webrtcvad no disponible, uso volumen: {e}")
            self._vad = None

    def es_voz(self, bloque: bytes) -> bool:
        # Bloques casi en silencio nunca son voz (evita falsos positivos del VAD).
        energia = np.sqrt(np.mean(np.frombuffer(bloque, dtype=np.int16).astype(np.float32) ** 2))
        if energia < 200:
            return False
        if self._vad is None:
            return energia > 900
        return self._vad.is_speech(bloque, TASA)


_vad = None


def detector_voz() -> DetectorVoz:
    global _vad
    if _vad is None:
        _vad = DetectorVoz()
    return _vad


def capturar(mic: Microfono, espera_inicio=6.0, silencio_fin=1.2, max_total=20.0,
             mientras=None, abortar=None):
    """Graba una frase y regresa el audio (bytes PCM) o None si no hablaste.

    - Modo normal: espera hasta `espera_inicio` s a que empieces a hablar y
      corta tras `silencio_fin` s de silencio.
    - Modo tecla (`mientras` es una función): graba mientras regrese True.
    - `abortar`: función que, si regresa True, cancela la espera.
    """
    vad = detector_voz()
    ultimos = deque(maxlen=6)     # para decidir que empezaste a hablar (evita clics sueltos)
    previo = deque(maxlen=10)     # 300 ms antes de la voz, para no comerse la primera sílaba
    audio, hablando, bloques_voz = [], False, 0
    inicio_voz = ultima_voz = None
    # El "reloj" es la cantidad de audio recibido (30 ms por bloque), no la
    # hora: así los cortes son exactos aunque el audio llegue a tirones.
    ahora = 0.0
    ultimo_bloque_real = time.time()

    while estado.running:
        if abortar and abortar():
            return None
        if mientras is not None and not mientras():
            break
        bloque = mic.leer(0.1)
        if bloque is None:
            # Sin audio por más de 2 s (micro desconectado): no esperar para siempre.
            if time.time() - ultimo_bloque_real > 2.0:
                if not hablando and mientras is None:
                    return None
                break
            continue
        ultimo_bloque_real = time.time()
        ahora += MUESTRAS_BLOQUE / TASA
        inicio = 0.0

        voz = vad.es_voz(bloque)
        bloques_voz += voz

        if mientras is not None:  # modo tecla: graba todo
            audio.append(bloque)
            if ahora - inicio > max_total:
                break
            continue

        if not hablando:
            previo.append(bloque)
            ultimos.append(voz)
            if sum(ultimos) >= 3:
                hablando, audio = True, list(previo)
                inicio_voz = ultima_voz = ahora
            elif ahora - inicio > espera_inicio:
                return None
            continue

        audio.append(bloque)
        if voz:
            ultima_voz = ahora
        if ahora - ultima_voz > silencio_fin or ahora - inicio_voz > max_total:
            break

    if not estado.running or bloques_voz < 5:  # menos de 150 ms de voz: era ruido
        return None
    return b"".join(audio)


_reconocedor = sr.Recognizer()


def reconocer(audio: bytes) -> str:
    """Manda el audio a Google y regresa el texto en minúsculas ("" si no se entendió)."""
    if not audio:
        return ""
    muestras = np.frombuffer(audio, dtype=np.int16).astype(np.float32)
    pico = np.max(np.abs(muestras))
    if pico > 0:  # normaliza el volumen: Google entiende mejor
        muestras = muestras / pico * 0.9 * 32767
    datos = sr.AudioData(muestras.astype(np.int16).tobytes(), TASA, 2)
    try:
        texto = _reconocedor.recognize_google(datos, language="es-MX").lower().strip()
        if texto:
            print(f"🎙️ [Escuchado]: '{texto}'")
        return texto
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        logger.error(f"Error de conexión con el reconocimiento de voz: {e}")
        return ""
    except Exception as e:
        logger.error(f"Error reconociendo audio: {e}")
        return ""


def escuchar(mic: Microfono, **kwargs) -> str:
    """capturar() + reconocer() en un paso."""
    return reconocer(capturar(mic, **kwargs))


# ---------------------------------------------------------
# 🐕 PALABRA CLAVE SIN INTERNET (Vosk)
# ---------------------------------------------------------
class DetectorPalabraClave:
    """Escucha continuamente con un modelo local restringido a la palabra
    clave. Así no se manda audio a Google hasta que dices "Solovino"."""

    def __init__(self, ruta_modelo: str):
        import vosk
        vosk.SetLogLevel(-1)
        modelo = vosk.Model(ruta_modelo)
        # Vosk solo puede buscar frases cuyas palabras estén en su vocabulario
        # ("solovino" no está, "solo vino" sí).
        self.frases = [f for f in PALABRAS_CLAVE
                       if all(modelo.vosk_model_find_word(p) != -1 for p in f.split())]
        if not self.frases:
            raise RuntimeError(f"Ninguna variante de la palabra clave está en el vocabulario: {PALABRAS_CLAVE}")
        self._rec = vosk.KaldiRecognizer(modelo, TASA, json.dumps(self.frases + ["[unk]"]))
        logger.info(f"Palabra clave local activa: {self.frases}")

    def procesar(self, bloque: bytes) -> bool:
        if self._rec.AcceptWaveform(bloque):
            texto = json.loads(self._rec.Result()).get("text", "")
        else:
            texto = json.loads(self._rec.PartialResult()).get("partial", "")
        if any(f in texto for f in self.frases):
            self._rec.Reset()
            return True
        return False

    def reiniciar(self):
        self._rec.Reset()


def crear_detector_palabra_clave():
    """Regresa el detector local, o None para usar Google (sin modelo o desactivado)."""
    if CONFIG.get("deteccion_palabra_clave", "local") != "local":
        return None
    ruta = buscar_recurso("modelos", CARPETA_MODELO_VOSK)
    if not ruta:
        logger.error(f"No encontré modelos/{CARPETA_MODELO_VOSK}; detecto la palabra clave con Google.")
        return None
    try:
        return DetectorPalabraClave(ruta)
    except Exception as e:
        logger.exception(f"No pude cargar Vosk, uso Google: {e}")
        return None


def separar_orden(texto: str):
    """Si el texto trae la palabra clave regresa lo que viene DESPUÉS
    ("" si solo dijiste "Solovino"); si no la trae, regresa None."""
    for palabra in PALABRAS_CLAVE:
        if palabra in texto:
            return texto.split(palabra, 1)[1].strip(" ,.")
    return None
