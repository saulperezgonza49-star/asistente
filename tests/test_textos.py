"""Funciones de texto puras: limpieza, números, dictado, duraciones, teclas."""
import unittest

import atajos
import dictado
import ia
import recordatorios
from escucha import separar_orden
from utils import contiene, extraer_numero, limpiar_texto


class TestUtils(unittest.TestCase):
    def test_limpiar_texto_no_rompe_palabras(self):
        quitar = ["mueve", "a", "la", "el", "pantalla", "2"]
        self.assertEqual(limpiar_texto("mueve whatsapp a la pantalla 2", quitar), "whatsapp")
        self.assertEqual(limpiar_texto("abre la calculadora", ["abre", "la"]), "calculadora")
        self.assertEqual(limpiar_texto("cierra telegram", ["cierra", "el"]), "telegram")

    def test_limpiar_texto_frases_largas_primero(self):
        self.assertEqual(limpiar_texto("crea una carpeta que se llame planes",
                                       ["crea", "una", "carpeta", "se", "que se llame"]), "planes")

    def test_contiene_solo_al_inicio_de_palabra(self):
        self.assertFalse(contiene("qué es japón", ["pon"]))
        self.assertTrue(contiene("ponle pausa", ["pon"]))
        self.assertTrue(contiene("cuántos años tiene", ["cuánto"]))

    def test_extraer_numero(self):
        self.assertEqual(extraer_numero("pantalla 2"), 2)
        self.assertEqual(extraer_numero("la pantalla dos"), 2)
        self.assertEqual(extraer_numero("la segunda pantalla"), 2)
        self.assertEqual(extraer_numero("volumen en cuarenta"), 40)
        self.assertIsNone(extraer_numero("abre chrome"))


class TestPalabraClave(unittest.TestCase):
    def test_separar_orden(self):
        self.assertEqual(separar_orden("solovino pon pausa"), "pon pausa")
        self.assertEqual(separar_orden("oye solo vino, mueve esto"), "mueve esto")
        self.assertEqual(separar_orden("solovino"), "")
        self.assertIsNone(separar_orden("hola qué tal"))


class TestDictado(unittest.TestCase):
    def test_puntuacion(self):
        self.assertEqual(dictado.formatear("hola coma cómo estás signo de interrogación"), "Hola, cómo estás?")
        self.assertEqual(dictado.formatear("abre signo de interrogación vienes cierra signo de interrogación"),
                         "¿Vienes?")
        self.assertEqual(dictado.formatear("listo punto nos vemos"), "Listo. Nos vemos")
        self.assertEqual(dictado.formatear("uno nueva línea dos"), "Uno\nDos")

    def test_no_confunde_palabras(self):
        # "puntos" y "comal" no son signos.
        self.assertEqual(dictado.formatear("tengo tres puntos en el comal"), "Tengo tres puntos en el comal")


class TestDuraciones(unittest.TestCase):
    def test_parsear(self):
        self.assertEqual(recordatorios.parsear_duracion("en 20 minutos"), 1200)
        self.assertEqual(recordatorios.parsear_duracion("en cinco minutos"), 300)
        self.assertEqual(recordatorios.parsear_duracion("en una hora y media"), 5400)
        self.assertEqual(recordatorios.parsear_duracion("en media hora"), 1800)
        self.assertEqual(recordatorios.parsear_duracion("de 30 segundos"), 30)
        self.assertIsNone(recordatorios.parsear_duracion("a las cinco"))

    def test_describir(self):
        self.assertEqual(recordatorios.describir_tiempo(300), "5 minutos")
        self.assertEqual(recordatorios.describir_tiempo(5400), "1 hora y 30 minutos")


class TestAtajos(unittest.TestCase):
    def test_parsear(self):
        self.assertEqual(atajos.parsear_combinacion("ctrl+alt+space"), [0x11, 0x12, 0x20])
        self.assertEqual(atajos.parsear_combinacion("F9"), [0x78])
        with self.assertRaises(ValueError):
            atajos.parsear_combinacion("ctrl+tecla_rara")


class TestVozIA(unittest.TestCase):
    def test_limpiar_para_voz(self):
        self.assertEqual(ia.limpiar_para_voz("[jueves 2026-11-05T10:29] **Hola**, mira [esto](http://x.com)"),
                         "Hola, mira esto")


if __name__ == "__main__":
    unittest.main()
