"""Recordatorios y rutinas guardados en disco (en la carpeta temporal de pruebas)."""
import unittest
from unittest import mock
from datetime import datetime, timedelta

import estado
import recordatorios
import rutinas


class TestRecordatorios(unittest.TestCase):
    def setUp(self):
        recordatorios.cancelar("")  # vacío = borra todos

    def test_crear_listar_cancelar(self):
        recordatorios.crear("sacar la ropa", datetime.now() + timedelta(minutes=20))
        recordatorios.crear("llamar a mamá", datetime.now() + timedelta(hours=2))
        self.assertEqual([r["mensaje"] for r in recordatorios.listar()], ["sacar la ropa", "llamar a mamá"])
        self.assertEqual(recordatorios.cancelar("ropa"), 1)
        self.assertEqual(len(recordatorios.listar()), 1)

    def test_vencido_se_anuncia(self):
        recordatorios.crear("ya", datetime.now() - timedelta(seconds=1))
        while not estado.anuncios.empty():
            estado.anuncios.get_nowait()
        with mock.patch("voz.mandar_notificacion"):
            estado.running = True
            recordatorios.iniciar()
            mensaje = estado.anuncios.get(timeout=3)
        self.assertEqual(mensaje, "ya")
        self.assertEqual(recordatorios.listar(), [])


class TestRutinas(unittest.TestCase):
    def test_ejemplo_se_crea_y_se_encuentra(self):
        self.assertIn("trabajo", rutinas.cargar())
        self.assertEqual(rutinas.buscar("modo trabajo"), "trabajo")
        self.assertEqual(rutinas.buscar("hora del descanso"), "descanso")
        self.assertIsNone(rutinas.buscar("abre chrome"))

    def test_rutina_inexistente(self):
        self.assertIn("No tengo", rutinas.ejecutar("fiesta"))


if __name__ == "__main__":
    unittest.main()
