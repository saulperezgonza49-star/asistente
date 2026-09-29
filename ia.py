"""Conexión con Gemini: dos chats separados —uno con búsqueda de Google en
vivo, otro con function calling sobre el portapapeles— y la función que
decide cuál usar según la orden."""
import os
from dotenv import load_dotenv, find_dotenv
from google import genai
from google.genai import types

from config import logger, PALABRAS_TAREA
from archivos import leer_portapapeles, escribir_portapapeles

load_dotenv(find_dotenv())
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    logger.error("No encontré GEMINI_API_KEY. Crea un archivo .env con GEMINI_API_KEY=tu_key")

client = genai.Client(api_key=API_KEY)


def crear_chats():
    """Crea los dos chats: uno con búsqueda de Google, otro con function calling."""
    config_busqueda = types.GenerateContentConfig(tools=[{"google_search": {}}])
    chat_busqueda = client.chats.create(model="gemini-2.5-flash", config=config_busqueda)

    config_tareas = types.GenerateContentConfig(tools=[leer_portapapeles, escribir_portapapeles])
    chat_tareas = client.chats.create(model="gemini-2.5-flash", config=config_tareas)

    return chat_busqueda, chat_tareas


def responder(orden: str, chat_busqueda, chat_tareas) -> str:
    """Decide si la orden es una tarea (portapapeles, resumir, etc.) o una
    pregunta de búsqueda, y regresa el texto de respuesta de Gemini."""
    if any(w in orden for w in PALABRAS_TAREA):
        print("🧩 Enviando a chat de TAREAS (function calling)")
        response = chat_tareas.send_message(orden)
    else:
        print("🌐 Enviando a chat de BÚSQUEDA (google_search)")
        response = chat_busqueda.send_message(orden)
    return response.text