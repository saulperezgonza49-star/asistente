"""Router de comandos: qué acción dispara cada frase. Todas las acciones
reales (volumen, ventanas, apagar...) están simuladas: no se ejecuta nada."""
import unittest
from unittest import mock

import comandos


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.llamadas = []
        self.dicho = []
        self.respuesta_confirmar = True

        def registrar(nombre, valor=True):
            return lambda *a, **k: self.llamadas.append((nombre,) + a) or valor

        parches = [
            mock.patch.object(comandos, "hablar", lambda t: self.dicho.append(t)),
            mock.patch.object(comandos, "confirmar", lambda p: self.respuesta_confirmar),
            mock.patch.object(comandos.ventanas, "mover_ventana", registrar("mover", "ok")),
            mock.patch.object(comandos.ventanas, "encontrar_ventana", lambda n: f"<{n}>"),
            mock.patch.object(comandos.ventanas, "ventana_activa", lambda: "<activa>"),
            mock.patch.object(comandos.ventanas, "abrir_app_en_monitor", registrar("abrir_en")),
            mock.patch.object(comandos.ventanas, "maximizar_activa", registrar("maximizar")),
            mock.patch.object(comandos.multimedia, "enviar_tecla_multimedia", registrar("tecla")),
            mock.patch.object(comandos.volumen, "ajustar_volumen", registrar("volumen")),
            mock.patch.object(comandos.apps, "cerrar_aplicacion", registrar("cerrar", 1)),
            mock.patch.object(comandos.apps, "abrir_aplicacion", registrar("abrir")),
            mock.patch.object(comandos.spotify, "reproducir", registrar("spotify", "ok")),
            mock.patch.object(comandos.sistema, "apagar", registrar("apagar")),
            mock.patch.object(comandos.sistema, "bloquear", registrar("bloquear")),
            mock.patch.object(comandos.pantalla, "preguntar_sobre_pantalla", registrar("ver_pantalla", "veo algo")),
            mock.patch.object(comandos.dictado, "escribir", registrar("escribir")),
            mock.patch.object(comandos.recordatorios, "crear", registrar("recordatorio")),
            mock.patch.object(comandos.rutinas, "ejecutar", registrar("rutina", "ok")),
            mock.patch.object(comandos.webbrowser, "open", registrar("web")),
        ]
        for p in parches:
            p.start()
            self.addCleanup(p.stop)

    def orden(self, texto):
        self.llamadas.clear()
        self.dicho.clear()
        return comandos.ejecutar_comando_local(texto)

    def assertAccion(self, texto, *esperado):
        self.assertTrue(self.orden(texto), f"'{texto}' debería ser un comando rápido")
        self.assertIn(esperado, self.llamadas, f"'{texto}' -> {self.llamadas}")

    # --- Pantallas ---
    def test_mover_ventana_activa(self):
        for frase in ["mueve esto a la otra pantalla", "pásalo a la otra pantalla", "cambia de pantalla"]:
            self.assertAccion(frase, "mover", "<activa>", None)

    def test_mover_app_a_pantalla(self):
        self.assertAccion("manda chrome a la pantalla dos", "mover", "<chrome>", 2)
        self.assertAccion("llévate whatsapp a la segunda pantalla", "mover", "<whatsapp>", 2)
        self.assertAccion("mueve spotify al otro monitor", "mover", "<spotify>", None)

    def test_abrir_en_pantalla(self):
        self.assertAccion("abre spotify en la pantalla 2", "abrir_en", "spotify", 2)

    # --- Audio ---
    def test_volumen(self):
        self.assertAccion("sube el volumen a 150", "volumen", 1.0)
        self.assertAccion("pon el volumen en cuarenta", "volumen", 0.4)
        self.assertAccion("silencia el volumen", "volumen", 0.0)

    def test_multimedia(self):
        self.assertAccion("pon pausa", "tecla", comandos.multimedia.VK_MEDIA_PLAY_PAUSE)
        self.assertAccion("siguiente canción", "tecla", comandos.multimedia.VK_MEDIA_NEXT_TRACK)

    def test_spotify(self):
        self.assertAccion("pon bohemian rhapsody en spotify", "spotify", "bohemian rhapsody", "track")
        self.assertAccion("ponme música de queen", "spotify", "queen", "artist")
        self.assertAccion("pon la playlist lofi", "spotify", "lofi", "playlist")

    # --- Apps ---
    def test_cerrar_con_confirmacion(self):
        self.assertAccion("cierra telegram", "cerrar", "telegram")
        self.respuesta_confirmar = False
        self.assertTrue(self.orden("cierra discord"))
        self.assertEqual(self.llamadas, [], "si dices que no, no cierra nada")

    def test_abrir(self):
        self.assertAccion("abre la calculadora", "abrir", "calculadora")
        self.assertAccion("abre la página de youtube", "web", "https://www.youtube.com")

    # --- Sistema ---
    def test_apagar_pide_confirmacion(self):
        self.respuesta_confirmar = False
        self.assertTrue(self.orden("apaga la computadora"))
        self.assertNotIn(("apagar",), self.llamadas)
        self.respuesta_confirmar = True
        self.assertAccion("apaga la computadora", "apagar")

    def test_apagar_app_no_es_apagar_pc(self):
        self.assertAccion("apaga spotify", "cerrar", "spotify")

    def test_bloquear(self):
        self.assertAccion("bloquea la computadora", "bloquear")

    def test_hora_sin_internet(self):
        self.assertTrue(self.orden("qué hora es"))
        self.assertTrue(self.dicho and self.dicho[0].startswith("Son las"))

    # --- Funciones nuevas ---
    def test_ver_pantalla(self):
        self.assertAccion("explícame este error", "ver_pantalla", "explícame este error")

    def test_escribir_literal(self):
        self.assertAccion("escribe hola coma cómo estás", "escribir", "Hola, cómo estás")

    def test_escribir_redactado_va_a_gemini(self):
        self.assertFalse(self.orden("escribe un correo para mi jefe pidiendo vacaciones"))

    def test_temporizador(self):
        self.assertTrue(self.orden("pon un temporizador de 5 minutos"))
        self.assertEqual(self.llamadas[0][0], "recordatorio")
        self.assertEqual(self.llamadas[0][1], "se acabó el tiempo")

    def test_recordatorio_con_mensaje(self):
        self.assertTrue(self.orden("recuérdame en 20 minutos sacar la ropa"))
        self.assertEqual(self.llamadas[0][1], "sacar la ropa")

    def test_hora_exacta_va_a_gemini(self):
        self.assertFalse(self.orden("recuérdame a las 5 llamar a mi mamá"))

    def test_rutina(self):
        self.assertAccion("modo trabajo", "rutina", "trabajo")

    # --- Lo que debe ir a Gemini ---
    def test_preguntas_van_a_gemini(self):
        for frase in ["qué es japón", "resume esto", "cuál es la capital de francia", "pon música"]:
            self.assertFalse(self.orden(frase), frase)
            self.assertEqual(self.llamadas, [], frase)


if __name__ == "__main__":
    unittest.main()
