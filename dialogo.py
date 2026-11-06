"""Preguntas de sí/no por voz, para confirmar acciones delicadas."""
import estado
from config import CONFIG, PALABRAS_SI, PALABRAS_NO
from utils import contiene
from voz import hablar, pitido


def confirmar(pregunta: str, por_defecto: bool = False) -> bool:
    """Pregunta en voz alta y espera un "sí" o "no". Si no contestas o no se
    entiende, regresa `por_defecto` (False: en la duda, no hace nada).
    Si las confirmaciones están desactivadas en config.json, regresa True."""
    if not CONFIG.get("confirmar_acciones", True):
        return True
    mic = estado.microfono
    if mic is None:
        return por_defecto

    from escucha import escuchar  # import aquí: escucha abre dependencias de audio
    hablar(pregunta)
    pitido(1000, 80)
    respuesta = escuchar(mic, espera_inicio=4, silencio_fin=0.8, max_total=5)
    if not respuesta:
        hablar("No te escuché, mejor no lo hago.")
        return por_defecto
    if contiene(respuesta, PALABRAS_NO):  # "no" gana: "sí, no, mejor no" = no
        return False
    return contiene(respuesta, PALABRAS_SI)
