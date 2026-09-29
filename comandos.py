"""Router de comandos locales: decide qué hacer con la orden reconocida
antes de mandarla a Gemini. Cada bloque revisa palabras clave y ejecuta
la acción correspondiente."""
import webbrowser
import urllib.parse
import pyautogui

from config import PALABRAS_TAREA, PALABRAS_PREGUNTA
from utils import extraer_numero, limpiar_texto
from voz import hablar
import volumen
import multimedia
import ventanas
import apps
import archivos


def ejecutar_comando_local(texto_usuario: str) -> bool:
    accion = texto_usuario.lower().strip()

    if any(w in accion for w in PALABRAS_PREGUNTA) or any(w in accion for w in PALABRAS_TAREA):
        print("🧠 Detectada intención de pregunta/tarea — sin ejecutar acción local")
        return False

    # ---------------------------------------------------------
    # 🖥️ MONITORES POR NUMERACIÓN DE WINDOWS ("abre X en la pantalla 2")
    # ---------------------------------------------------------
    if any(w in accion for w in ["pantalla", "monitor"]) and extraer_numero(accion) is not None:
        numero_monitor = extraer_numero(accion)

        if any(w in accion for w in ["abre", "inicia", "pon", "ejecuta"]):
            nombre_app = limpiar_texto(accion, ["abre", "inicia", "pon", "ejecuta", "en", "la", "el",
                                                  "pantalla", "monitor", str(numero_monitor)])
            if nombre_app:
                hablar(f"Abriendo {nombre_app} en la pantalla {numero_monitor}.")
                ventanas.abrir_app_en_monitor(nombre_app, numero_monitor)
                return True

        if any(w in accion for w in ["mueve", "manda", "pasalo", "pásalo"]):
            nombre_app = limpiar_texto(accion, ["mueve", "manda", "pasalo", "pásalo", "a", "la", "el",
                                                  "pantalla", "monitor", str(numero_monitor)])
            if nombre_app:
                if ventanas.mover_app_a_monitor(nombre_app, numero_monitor):
                    hablar(f"Listo, {nombre_app} ya está en la pantalla {numero_monitor}.")
                else:
                    hablar(f"No encontré una ventana abierta de {nombre_app}.")
                return True

    # ---------------------------------------------------------
    # 🔊 VOLUMEN
    # ---------------------------------------------------------
    if any(w in accion for w in ["volumen", "sonido"]) and not any(w in accion for w in ["pausa", "reproduce"]):
        numero = extraer_numero(accion)
        if any(w in accion for w in ["baja", "bájale", "bajale", "disminuye", "reduce"]):
            nivel = (numero / 100) if numero is not None else 0.15
            volumen.ajustar_volumen(nivel)
            hablar(f"Volumen al {int(nivel * 100)} por ciento.")
            return True
        if any(w in accion for w in ["sube", "súbele", "subele", "aumenta"]):
            nivel = (numero / 100) if numero is not None else 0.7
            volumen.ajustar_volumen(nivel)
            hablar(f"Volumen al {int(nivel * 100)} por ciento.")
            return True
        if any(w in accion for w in ["silencio", "mute", "quita el sonido"]):
            volumen.ajustar_volumen(0.0)
            hablar("Silenciado.")
            return True

    # ---------------------------------------------------------
    # 🎵 MULTIMEDIA
    # ---------------------------------------------------------
    if any(palabra in accion for palabra in ["pausa", "reproduce", "reproducción", "play", "siguiente",
                                               "anterior", "quita pausa", "avanza", "cambia"]):
        if any(w in accion for w in ["pausa", "ponle play", "reproduce", "reproducción", "quita pausa"]):
            hablar("Hecho.")
            multimedia.enviar_tecla_multimedia(multimedia.VK_MEDIA_PLAY_PAUSE)
            return True
        if any(w in accion for w in ["siguiente", "cambia", "siguiente canción", "siguiente video", "avanza"]):
            hablar("Siguiente.")
            multimedia.enviar_tecla_multimedia(multimedia.VK_MEDIA_NEXT_TRACK)
            return True
        if any(w in accion for w in ["anterior", "regresa", "atrás"]):
            hablar("Regresando.")
            multimedia.enviar_tecla_multimedia(multimedia.VK_MEDIA_PREV_TRACK)
            return True

    # ---------------------------------------------------------
    # 🖥️ PANTALLA ACTIVA (mover al otro monitor, maximizar, minimizar)
    # ---------------------------------------------------------
    if any(palabra in accion for palabra in ["pantalla", "monitor", "pásalo", "pasalo", "mueve"]):
        if any(w in accion for w in ["mueve a la otra", "pásalo a la otra", "cambia de pantalla",
                                       "pasa al otro monitor", "mueve al otro"]):
            hablar("Ventana movida, Saúl.")
            pyautogui.hotkey('win', 'shift', 'right')
            return True
        if "maximiza" in accion or "agranda" in accion:
            hablar("Maximizando ventana.")
            pyautogui.hotkey('win', 'up')
            return True
        if "minimiza" in accion or "esconde" in accion:
            hablar("Ventana minimizada.")
            pyautogui.hotkey('win', 'down')
            return True

    # ---------------------------------------------------------
    # 📂 CARPETAS
    # ---------------------------------------------------------
    if any(palabra in accion for palabra in ["crea una carpeta", "crea la carpeta", "haz una carpeta"]):
        nombre_carpeta = limpiar_texto(
            accion, ["crea", "haz", "una", "la", "carpeta", "llamada", "que se llame"]
        ).capitalize()
        if nombre_carpeta:
            ok, ya_existia = archivos.crear_carpeta_en_escritorio(nombre_carpeta)
            if not ok:
                hablar("No pude crear la carpeta por un tema de permisos.")
            elif ya_existia:
                hablar("Esa carpeta ya existe en el escritorio, Saúl.")
            else:
                hablar(f"Ya creé la carpeta {nombre_carpeta} en el escritorio, carnal.")
            return True

    # ---------------------------------------------------------
    # ❌ CERRAR APLICACIONES / PESTAÑAS
    # ---------------------------------------------------------
    if any(palabra in accion for palabra in ["cierra", "quita", "apaga", "elimina"]):
        if any(w in accion for w in ["pestaña", "pagina", "página", "eso", "ventana"]):
            hablar("Cerrando pestaña, listo Saúl.")
            pyautogui.hotkey('ctrl', 'w')
            return True

        target_app = limpiar_texto(accion, ["cierra", "el", "la", "quita", "apaga", "elimina", "app", "programa"])
        if target_app:
            hablar(f"Cerrando {target_app}, listo carnal.")
            apps.cerrar_aplicacion(target_app)
            return True

    # ---------------------------------------------------------
    # 🌐 ABRIR APLICACIONES / PÁGINAS WEB
    # ---------------------------------------------------------
    if any(palabra in accion for palabra in ["abre", "inicia", "pon", "ejecuta", "abrir"]):
        if any(w in accion for w in ["página", "pagina", "pestaña", "de la página", "de la pestaña"]):
            sitio_busqueda = limpiar_texto(accion, ["abre", "el", "la", "pon", "inicia", "por", "fa", "favor",
                                                      "página", "pagina", "pestaña", "de"])
            if sitio_busqueda:
                if " " not in sitio_busqueda:
                    url_final = (f"https://www.{sitio_busqueda}.com"
                                 if not any(ext in sitio_busqueda for ext in [".com", ".org", ".net", ".mx"])
                                 else f"https://www.{sitio_busqueda}")
                    hablar(f"Abriendo {sitio_busqueda} en el navegador.")
                else:
                    texto_formateado = urllib.parse.quote(sitio_busqueda)
                    url_final = f"https://www.google.com/search?q={texto_formateado}"
                    hablar(f"Buscando {sitio_busqueda} en Google, Saúl.")
                webbrowser.open(url_final)
                return True

        nombre_app = limpiar_texto(accion, ["abre", "el", "la", "inicia", "pon", "por", "fa", "favor",
                                              "ejecuta", "abrir"])
        if "pan de" in nombre_app:
            nombre_app = "panel de control"
        if "minecraft" in accion:
            nombre_app = "minecraftlauncher" if any(o in accion for o in ["oficial", "original"]) else "prism"

        if nombre_app:
            apps.abrir_aplicacion(nombre_app)
            return True

    return False