"""Conexión con Gemini.

- responder(): un "agente" con herramientas (herramientas.py) que puede
  hacer cosas en la computadora, no solo contestar. Recuerda la
  conversación hasta `minutos_memoria_chat` minutos sin hablarle.
- buscar_en_internet(): consulta aparte con Google Search (Gemini no deja
  mezclar búsqueda de Google y herramientas propias en la misma llamada).
- analizar_imagen(): para las capturas de pantalla.
"""
import os
import re
import time

from google import genai
from google.genai import types

from config import CONFIG, NOMBRE, logger

INSTRUCCION_SISTEMA = f"""Eres Solovino, el asistente de voz de {NOMBRE} en su computadora con Windows.
Hablas español de México, relajado y amigable, como un compa.
Tus respuestas se leen en voz alta: contesta en 1 a 3 oraciones, sin markdown, sin viñetas, sin emojis y sin URLs.
Tienes herramientas para controlar la computadora: cuando te pidan una acción, HAZLA con la herramienta en vez de explicar cómo hacerla.
Para cualquier dato actual o que pueda haber cambiado (noticias, clima, precios, resultados, horarios) usa buscar_en_internet.
Si te piden ver, leer o explicar algo de la pantalla, usa ver_pantalla.
Cada mensaje empieza con [fecha y hora actual] solo como contexto: NUNCA la repitas en tu respuesta. Úsala para recordatorios: "a las 5" es hoy a las 17:00 si aún no pasa, si no mañana.
Nunca digas que hiciste algo si la herramienta respondió que falló o que el usuario canceló.
Si la orden es ambigua, haz una pregunta corta."""

INSTRUCCION_VOZ = ("Responde en español de México en 1 a 3 oraciones, para leerse en voz alta: "
                   "sin markdown, viñetas, emojis ni URLs.")

_client = None
_chat = None
_ultimo_uso = 0.0


def _obtener_cliente():
    """Crea el cliente la primera vez que se necesita, para que una API key
    faltante no tumbe el programa al arrancar."""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("No encontré GEMINI_API_KEY. Ponla en el archivo .env.")
        _client = genai.Client(api_key=api_key)
    return _client


def disponible() -> bool:
    try:
        _obtener_cliente()
        return True
    except Exception as e:
        logger.error(f"IA desactivada: {e}")
        return False


def _nuevo_chat():
    import herramientas
    config = types.GenerateContentConfig(
        system_instruction=INSTRUCCION_SISTEMA,
        tools=herramientas.TODAS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=8),
    )
    return _obtener_cliente().chats.create(model=CONFIG["modelo_ia"], config=config)


def olvidar():
    global _chat
    _chat = None


def limpiar_para_voz(texto: str) -> str:
    """Quita restos de markdown que el sintetizador leería literalmente."""
    texto = re.sub(r'^\s*\[[^\]]*\d{4}-\d{2}-\d{2}[^\]]*\]\s*', '', texto)  # la fecha de contexto, si la repite
    texto = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', texto)  # [texto](url) -> texto
    texto = re.sub(r'https?://\S+', '', texto)
    texto = re.sub(r'[*_#`>]+', '', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def _con_reintento(funcion):
    """Gemini a veces responde 503 (saturado): reintenta una vez."""
    try:
        return funcion()
    except Exception as e:
        if any(c in str(e) for c in ("503", "UNAVAILABLE", "overloaded", "500")):
            time.sleep(1.5)
            return funcion()
        raise


def responder(orden: str) -> str:
    """Manda la orden al agente y regresa lo que hay que decir."""
    global _chat, _ultimo_uso
    import estado
    from sistema import fecha_hora_contexto
    if estado.sin_internet:
        return "Ahorita no tengo internet, así que solo puedo hacer comandos básicos."
    try:
        if _chat is None or time.time() - _ultimo_uso > CONFIG["minutos_memoria_chat"] * 60:
            _chat = _nuevo_chat()
        _ultimo_uso = time.time()
        mensaje = f"[{fecha_hora_contexto()}] {orden}"
        respuesta = _con_reintento(lambda: _chat.send_message(mensaje))
        return limpiar_para_voz(respuesta.text or "") or "Listo."
    except RuntimeError as e:  # sin API key
        return str(e)
    except Exception as e:
        logger.exception(f"Error consultando a Gemini: {e}")
        olvidar()  # una conversación a medias puede quedar inválida
        return "Uy, no pude conectarme con Gemini. Intenta de nuevo en un ratito."


def buscar_en_internet(pregunta: str) -> str:
    config = types.GenerateContentConfig(system_instruction=INSTRUCCION_VOZ,
                                         tools=[types.Tool(google_search=types.GoogleSearch())])
    respuesta = _con_reintento(lambda: _obtener_cliente().models.generate_content(
        model=CONFIG["modelo_ia"], contents=pregunta, config=config))
    return limpiar_para_voz(respuesta.text or "") or "No encontré nada."


def analizar_imagen(png: bytes, pregunta: str) -> str:
    try:
        config = types.GenerateContentConfig(system_instruction=INSTRUCCION_VOZ)
        respuesta = _con_reintento(lambda: _obtener_cliente().models.generate_content(
            model=CONFIG["modelo_ia"],
            contents=[types.Part.from_bytes(data=png, mime_type="image/png"), pregunta],
            config=config))
        return limpiar_para_voz(respuesta.text or "") or "No pude ver nada claro."
    except Exception as e:
        logger.exception(f"Error analizando la pantalla: {e}")
        return "No pude analizar la pantalla."
