"""Control de volumen del sistema y detección de audio reproduciéndose (pycaw)."""
import comtypes
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IAudioMeterInformation

from config import CONFIG, logger


def _control_volumen():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def bajar_volumen(nivel=None):
    nivel = CONFIG["nivel_volumen_escucha"] if nivel is None else nivel
    try:
        comtypes.CoInitialize()
        vol = _control_volumen()
        nivel_anterior = vol.GetMasterVolumeLevelScalar()
        vol.SetMasterVolumeLevelScalar(nivel, None)
        return nivel_anterior
    except Exception as e:
        logger.error(f"Error al bajar volumen: {e}")
        return None
    finally:
        comtypes.CoUninitialize()


def restaurar_volumen(nivel_anterior):
    if nivel_anterior is None:
        return
    try:
        comtypes.CoInitialize()
        vol = _control_volumen()
        vol.SetMasterVolumeLevelScalar(nivel_anterior, None)
    except Exception as e:
        logger.error(f"Error al restaurar volumen: {e}")
    finally:
        comtypes.CoUninitialize()


def ajustar_volumen(nivel: float):
    try:
        comtypes.CoInitialize()
        vol = _control_volumen()
        nivel = max(0.0, min(1.0, nivel))
        vol.SetMasterVolumeLevelScalar(nivel, None)
    except Exception as e:
        logger.error(f"Error ajustando volumen: {e}")
    finally:
        comtypes.CoUninitialize()


def hay_audio_reproduciendose(umbral: float = 0.01) -> bool:
    """Mide el pico de audio que sale por las bocinas ahorita mismo.
    Si hay sonido de verdad saliendo (música, video, etc.), regresa True."""
    try:
        comtypes.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
        medidor = cast(interface, POINTER(IAudioMeterInformation))
        return medidor.GetPeakValue() > umbral
    except Exception as e:
        logger.error(f"Error detectando audio: {e}")
        return False
    finally:
        comtypes.CoUninitialize()