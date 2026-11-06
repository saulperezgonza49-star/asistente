"""Escucha de punta a punta sin micrófono: se genera voz con la voz de
Windows (Sabina, español) y se pasa por el VAD y por Vosk."""
import os
import queue
import tempfile
import unittest
import wave

import numpy as np

import escucha
from rutas import buscar_recurso


def sintetizar(texto: str) -> bytes:
    """PCM 16 kHz mono int16 de `texto` con SAPI."""
    import win32com.client
    ruta = os.path.join(tempfile.mkdtemp(), "voz.wav")
    formato = win32com.client.Dispatch("SAPI.SpAudioFormat")
    formato.Type = 18  # SAFT16kHz16BitMono
    archivo = win32com.client.Dispatch("SAPI.SpFileStream")
    archivo.Format = formato
    archivo.Open(ruta, 3)
    voz = win32com.client.Dispatch("SAPI.SpVoice")
    for v in voz.GetVoices():
        if "spanish" in v.GetDescription().lower():
            voz.Voice = v
    voz.AudioOutputStream = archivo
    voz.Speak(texto)
    archivo.Close()
    with wave.open(ruta) as w:
        return w.readframes(w.getnframes())


class MicFalso:
    """Imita a escucha.Microfono con audio ya grabado."""

    def __init__(self, pcm: bytes):
        self.cola = queue.Queue()
        tam = escucha.MUESTRAS_BLOQUE * 2
        for i in range(0, len(pcm) - tam + 1, tam):
            self.cola.put(pcm[i:i + tam])

    def leer(self, timeout=0.1):
        try:
            return self.cola.get_nowait()
        except queue.Empty:
            return None


def silencio(segundos: float) -> bytes:
    ruido = (np.random.randn(int(escucha.TASA * segundos)) * 30).astype(np.int16)  # ruido de fondo leve
    return ruido.tobytes()


class TestCaptura(unittest.TestCase):
    def test_corta_al_callar(self):
        voz = sintetizar("mueve esto a la otra pantalla")
        mic = MicFalso(silencio(0.5) + voz + silencio(3))
        audio = escucha.capturar(mic, espera_inicio=2, silencio_fin=1.0)
        self.assertIsNotNone(audio)
        duracion = len(audio) / 2 / escucha.TASA
        duracion_voz = len(voz) / 2 / escucha.TASA
        # Incluye la frase completa y no espera los 3 s de silencio.
        self.assertGreater(duracion, duracion_voz * 0.8)
        self.assertLess(duracion, duracion_voz + 1.8)

    def test_solo_silencio_no_regresa_nada(self):
        mic = MicFalso(silencio(2))
        self.assertIsNone(escucha.capturar(mic, espera_inicio=1, silencio_fin=0.5))


@unittest.skipUnless(buscar_recurso("modelos", escucha.CARPETA_MODELO_VOSK), "falta el modelo de Vosk")
class TestPalabraClave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = escucha.DetectorPalabraClave(escucha.modelo_vosk())

    def detecta(self, texto: str) -> bool:
        self.detector.reiniciar()
        mic = MicFalso(silencio(0.3) + sintetizar(texto) + silencio(0.5))
        while (bloque := mic.leer()) is not None:
            if self.detector.procesar(bloque):
                return True
        return False

    def test_detecta_solovino(self):
        self.assertTrue(self.detecta("Solovino"))
        self.assertTrue(self.detecta("oye solovino, pon pausa"))

    def test_ignora_otras_frases(self):
        self.assertFalse(self.detecta("mañana voy a comprar pan y leche"))
        self.assertFalse(self.detecta("el vino tinto está muy bueno"))


if __name__ == "__main__":
    unittest.main()
