# -*- mode: python ; coding: utf-8 -*-
# Receta de PyInstaller para Solovino. No la corras directo: usa build.bat.
#
# Genera dist\Solovino\ (modo carpeta, no un solo .exe: arranca más rápido y
# Vosk carga sus DLL sin problemas). build.bat copia ahí la carpeta modelos.
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

CONSOLA = os.environ.get("SOLOVINO_CONSOLA") == "1"  # build.bat consola -> ventana negra para depurar

datas = [
    *collect_data_files("speech_recognition"),   # flac-win32.exe: Google lo necesita para recibir el audio
    ("recursos/solovino.ico", "recursos"),
]
binaries = collect_dynamic_libs("vosk")          # libvosk.dll y sus dependencias

hiddenimports = [
    "pystray._win32",                       # pystray elige su backend al vuelo
    "plyer.platforms.win.notification",     # respaldo de notificaciones
    "win32timezone",                        # lo pide pywin32 en algunas llamadas COM
    "comtypes.stream",
    "webrtcvad",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["hooks_pyinstaller"],        # reglas propias (tienen prioridad sobre las de PyInstaller)
    excludes=["pyttsx3", "scipy", "matplotlib", "IPython", "pytest", "tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Solovino",
    icon="recursos/solovino.ico",
    console=CONSOLA,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Solovino")

# El modelo de voz va junto al .exe (no dentro): PyInstaller borra la carpeta
# en cada build, así que se copia aquí y no se puede olvidar.
import shutil
shutil.copytree("modelos", os.path.join(DISTPATH, "Solovino", "modelos"), dirs_exist_ok=True)
