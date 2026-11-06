@echo off
rem ============================================================
rem  Genera dist\Solovino\Solovino.exe
rem    build.bat           = version normal (sin ventana negra)
rem    build.bat consola   = con consola, para ver errores
rem  (sin el signo de mayor que en comentarios: cmd lo toma como "guardar en archivo")
rem ============================================================
setlocal
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe

if not exist "%PY%" (
    echo No encontre el entorno virtual .venv
    exit /b 1
)
if not exist "modelos\vosk-model-small-es-0.42" (
    echo Falta modelos\vosk-model-small-es-0.42
    echo Descargalo de https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
    exit /b 1
)

echo.
echo == 1/4 Pruebas ==
"%PY%" -m unittest || (echo. & echo Las pruebas fallaron, no genero el .exe. & exit /b 1)

echo.
echo == 2/4 Icono ==
"%PY%" icono.py || exit /b 1

echo.
echo == 3/4 PyInstaller (tambien copia la carpeta modelos) ==
if /i "%1"=="consola" (set SOLOVINO_CONSOLA=1) else (set SOLOVINO_CONSOLA=0)
"%PY%" -m PyInstaller --noconfirm --clean solovino.spec || exit /b 1

echo.
echo == 4/4 Diagnostico del .exe ==
"dist\Solovino\Solovino.exe" --diagnostico --silencioso
type "%APPDATA%\Solovino\diagnostico.txt"

rem Las claves NO van dentro del .exe. En esta computadora se copian una sola
rem vez a %APPDATA%\Solovino\.env para que el .exe las encuentre.
if exist ".env" if not exist "%APPDATA%\Solovino\.env" (
    if not exist "%APPDATA%\Solovino" mkdir "%APPDATA%\Solovino"
    copy ".env" "%APPDATA%\Solovino\.env" >nul
    echo Copie tus claves a %APPDATA%\Solovino\.env
)

echo.
echo Listo: dist\Solovino\Solovino.exe
echo Para moverlo de lugar, copia la carpeta dist\Solovino completa.
endlocal
