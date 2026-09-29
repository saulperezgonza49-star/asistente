"""Punto de entrada de Solovino: bucle de voz (reposo/atento), supervisor
con auto-reinicio, e inicio del ícono en la bandeja del sistema."""
import time
import threading
import speech_recognition as sr
import sounddevice as sd

import estado
from config import CONFIG, PALABRA_CLAVE, logger
from voz import hablar, mandar_notificacion, callback_audio, escuchar_segmento
from volumen import bajar_volumen, restaurar_volumen
from multimedia import pausar_video_para_escuchar, reanudar_video
from comandos import ejecutar_comando_local
from tray import iniciar_icono_bandeja
import ia


def chat_por_voz():
    recognizer = sr.Recognizer()
    chat_busqueda, chat_tareas = ia.crear_chats()

    device_info = sd.query_devices(kind='input')
    samplerate_nativo = device_info['default_samplerate']
    print(f"🎙️ Micro detectado: {device_info['name']}")
    logger.info(f"Micro detectado: {device_info['name']} @ {samplerate_nativo}Hz")

    mandar_notificacion("Solovino Online", "💤 En guardia. Di 'Solovino'...")
    print("💤 Solovino listo de fondo.")

    with sd.InputStream(samplerate=samplerate_nativo, channels=1, callback=callback_audio):
        while estado.running:
            try:
                user_input = escuchar_segmento(recognizer, samplerate_nativo,
                                                segundos_max=CONFIG["segundos_espera_reposo"])

                if PALABRA_CLAVE in user_input or "solo vino" in user_input:
                    video_pausado = pausar_video_para_escuchar()   # 🎬 pausa lo que se esté viendo
                    nivel_previo = bajar_volumen()                  # 🔉 y además baja el volumen
                    mandar_notificacion("🐕 Solovino Atento", "Te escucho Saúl...")
                    hablar("¿Qué onda Saúl? Dime.")

                    print("🎙️ [Atento] Escuchando orden...")
                    orden = escuchar_segmento(recognizer, samplerate_nativo,
                                               segundos_max=CONFIG["segundos_espera_orden"])

                    restaurar_volumen(nivel_previo)
                    reanudar_video(video_pausado)

                    if not orden:
                        mandar_notificacion("💤 Solovino Dormido", "Volviendo a reposo.")
                        hablar("Ya no me dijiste nada. Me regreso a dormir.")
                        continue

                    print(f"📥 Orden recibida en Modo Atento: '{orden}'")
                    logger.info(f"Orden: {orden}")

                    if "salir" in orden or "adiós" in orden:
                        hablar("Sobres, ahí nos vemos.")
                        estado.running = False
                        if estado.icono_bandeja:
                            estado.icono_bandeja.stop()
                        break

                    if ejecutar_comando_local(orden):
                        mandar_notificacion("💤 Solovino Dormido", "Volviendo a reposo.")
                        time.sleep(1.5)
                        continue

                    respuesta = ia.responder(orden, chat_busqueda, chat_tareas)
                    if respuesta:
                        hablar(respuesta)

                    mandar_notificacion("💤 Solovino Dormido", "Volviendo a reposo.")

            except KeyboardInterrupt:
                print("\n👋 Saliendo del asistente...")
                estado.running = False
                break
            except Exception as e:
                logger.error(f"Excepción en el bucle principal: {e}")
                print(f"⚠️ Alerta en bucle: {e}")
                time.sleep(1)


def hilo_supervisor():
    """Si el hilo de voz truena por algo inesperado, lo reinicia solo en vez de morirse en silencio."""
    while estado.running:
        try:
            chat_por_voz()
            break  # salida limpia (comando 'salir' o botón del tray)
        except Exception as e:
            logger.error(f"El asistente se cayó, reiniciando en 3s: {e}")
            time.sleep(3)


if __name__ == "__main__":
    try:
        logger.info("=== Solovino iniciando ===")
        hilo_asistente = threading.Thread(target=hilo_supervisor, daemon=True)
        hilo_asistente.start()
        try:
            iniciar_icono_bandeja()  # bloquea el hilo principal — así vive el ícono en la bandeja
        except KeyboardInterrupt:
            estado.running = False
            if estado.icono_bandeja:
                estado.icono_bandeja.stop()
    except KeyboardInterrupt:
        estado.running = False
        print("\n👋 Programa detenido.")
    logger.info("=== Solovino detenido ===")