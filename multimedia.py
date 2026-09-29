"""Teclas multimedia nativas y pausa/reanudación de video mientras se escucha."""
import ctypes
import time

from volumen import hay_audio_reproduciendose

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1


def enviar_tecla_multimedia(codigo_vk):
    """Envía una tecla multimedia directo al sistema (más confiable que pyautogui)."""
    ctypes.windll.user32.keybd_event(codigo_vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(codigo_vk, 0, 2, 0)


def pausar_video_para_escuchar() -> bool:
    """Si hay algo sonando ahorita, lo pausa con la tecla multimedia.
    Regresa True SOLO si de verdad pausó algo, para saber si hay que
    reanudarlo después (y no reanudar algo que ya estaba pausado)."""
    if hay_audio_reproduciendose():
        enviar_tecla_multimedia(VK_MEDIA_PLAY_PAUSE)
        time.sleep(0.15)  # le da un instante al sistema para procesar la pausa
        return True
    return False


def reanudar_video(estaba_reproduciendo: bool):
    """Solo reanuda si pausar_video_para_escuchar() de verdad pausó algo."""
    if estaba_reproduciendo:
        enviar_tecla_multimedia(VK_MEDIA_PLAY_PAUSE)  # togglea de vuelta a reproducir