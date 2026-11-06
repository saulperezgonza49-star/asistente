"""Lo que hace que el .exe aguante el uso diario: modo sin internet,
una sola instancia y guardar ajustes."""
import json
import unittest
from unittest import mock

import speech_recognition as sr

import escucha
import estado
import instancia
from config import CONFIG, CONFIG_PATH, guardar_config
from rutas import buscar_recurso
from tests.test_escucha import sintetizar, silencio


@unittest.skipUnless(buscar_recurso("modelos", escucha.CARPETA_MODELO_VOSK), "falta el modelo de Vosk")
class TestSinInternet(unittest.TestCase):
    def tearDown(self):
        estado.sin_internet = False

    def test_vosk_entiende_comandos_basicos(self):
        texto = escucha.reconocer_sin_internet(silencio(0.3) + sintetizar("sube el volumen") + silencio(0.3))
        self.assertIn("volumen", texto)

    def test_si_google_falla_usa_vosk(self):
        audio = silencio(0.2) + sintetizar("pon pausa") + silencio(0.2)
        with mock.patch.object(escucha._reconocedor, "recognize_google",
                               side_effect=sr.RequestError("sin conexión")), \
             mock.patch("voz.mandar_notificacion"):
            texto = escucha.reconocer(audio)
        self.assertTrue(estado.sin_internet, "debe marcar que no hay internet")
        self.assertIn("pausa", texto)

    def test_mientras_no_hay_internet_no_espera_a_google(self):
        estado.sin_internet = True
        escucha._ultimo_intento_google = __import__("time").time()
        with mock.patch.object(escucha._reconocedor, "recognize_google") as google:
            escucha.reconocer(silencio(0.2) + sintetizar("qué hora es"))
        google.assert_not_called()

    def test_gemini_avisa_sin_internet(self):
        import ia
        estado.sin_internet = True
        self.assertIn("internet", ia.responder("qué es un agujero negro"))


class TestUnaSolaInstancia(unittest.TestCase):
    def setUp(self):
        # Nombre propio para la prueba: si tienes Solovino abierto, el mutex
        # real ya está ocupado y la prueba fallaría sin que haya ningún bug.
        parche = mock.patch.object(instancia, "_NOMBRE", "Local\\Solovino_prueba_unittest")
        parche.start()
        self.addCleanup(parche.stop)

    def test_segunda_instancia_se_rechaza(self):
        self.assertTrue(instancia.adquirir())
        try:
            guardado = instancia._handle
            instancia._handle = None  # simula ser otro proceso que intenta abrir
            self.assertFalse(instancia.adquirir())
            instancia._handle = guardado
        finally:
            instancia.liberar()
        self.assertTrue(instancia.adquirir(), "al liberar, otro ya puede abrir")
        instancia.liberar()


class TestAjustes(unittest.TestCase):
    def test_guardar_config_actualiza_en_vivo_y_en_disco(self):
        anterior = CONFIG["segundos_seguimiento"]
        try:
            guardar_config({"segundos_seguimiento": 9})
            self.assertEqual(CONFIG["segundos_seguimiento"], 9)
            with open(CONFIG_PATH, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["segundos_seguimiento"], 9)
        finally:
            guardar_config({"segundos_seguimiento": anterior})

    def test_tecla_invalida_se_detecta(self):
        import atajos
        with self.assertRaises(ValueError):
            atajos.parsear_combinacion("ctrl+nada")


if __name__ == "__main__":
    unittest.main()
