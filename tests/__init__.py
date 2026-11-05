"""Pruebas de Solovino. Correr con:  .venv\\Scripts\\python.exe -m unittest -v

Usan una carpeta temporal como %APPDATA% para no tocar tu configuración,
recordatorios ni rutinas reales.
"""
import os
import sys
import tempfile

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="solovino_pruebas_")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
