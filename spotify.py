
"""Spotify por nombre ("pon Bohemian Rhapsody", "pon la playlist lofi").

Usa la API oficial con PKCE: solo necesitas SPOTIFY_CLIENT_ID en el .env
(sin client secret). La primera vez se abre el navegador para que autorices;
después el token se guarda en %APPDATA%\\Solovino\\spotify_token.json.
Controlar la reproducción requiere Spotify Premium.

Cómo sacar el Client ID:
  1. https://developer.spotify.com/dashboard -> Create app
  2. Redirect URI: http://127.0.0.1:8888/callback   (Web API)
  3. Copia el Client ID al .env:  SPOTIFY_CLIENT_ID=xxxxxxxx
"""
import os
import time
import urllib.parse
import webbrowser

from config import CONFIG, logger
from rutas import ruta_datos

ALCANCES = "user-modify-playback-state user-read-playback-state"
TIPOS = {"track", "playlist", "album", "artist"}

_cliente_cache = None


def _cliente():
    global _cliente_cache
    if _cliente_cache is not None:
        return _cliente_cache
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    if not client_id:
        return None
    import spotipy
    from spotipy.cache_handler import CacheFileHandler
    from spotipy.oauth2 import SpotifyPKCE
    auth = SpotifyPKCE(client_id=client_id, redirect_uri=CONFIG["spotify_redirect_uri"], scope=ALCANCES,
                       cache_handler=CacheFileHandler(cache_path=ruta_datos("spotify_token.json")),
                       open_browser=True)
    _cliente_cache = spotipy.Spotify(auth_manager=auth, requests_timeout=10)
    return _cliente_cache


def conectar() -> str:
    """Hace la autorización inicial (abre el navegador si hace falta)."""
    sp = _cliente()
    if sp is None:
        return "Falta SPOTIFY_CLIENT_ID en el archivo .env."
    try:
        usuario = sp.current_user()
        return f"Spotify conectado como {usuario.get('display_name') or usuario.get('id')}."
    except Exception as e:
        logger.error(f"No pude conectar Spotify: {e}")
        return "No pude conectar Spotify. Revisa el Client ID y la Redirect URI."


def _dispositivo(sp):
    """El dispositivo donde poner la música. Si Spotify no está abierto, lo abre y espera."""
    def _elegir():
        dispositivos = sp.devices().get("devices", [])
        for d in dispositivos:
            if d.get("is_active"):
                return d["id"]
        for d in dispositivos:
            if d.get("type") == "Computer":
                return d["id"]
        return dispositivos[0]["id"] if dispositivos else None

    dispositivo = _elegir()
    if dispositivo:
        return dispositivo
    os.startfile("spotify:")
    for _ in range(15):
        time.sleep(1)
        dispositivo = _elegir()
        if dispositivo:
            return dispositivo
    return None


def reproducir(busqueda: str, tipo: str = "track") -> str:
    """Busca y reproduce. tipo: track (canción), playlist, album o artist."""
    busqueda = busqueda.strip()
    tipo = tipo if tipo in TIPOS else "track"
    sp = _cliente()
    if sp is None:
        webbrowser.open(f"spotify:search:{urllib.parse.quote(busqueda)}")
        return "Te abrí la búsqueda en Spotify. Para ponerla directo agrega SPOTIFY_CLIENT_ID al .env."

    from spotipy.exceptions import SpotifyException
    try:
        resultados = sp.search(q=busqueda, type=tipo, limit=3)
        elementos = [e for e in resultados[f"{tipo}s"]["items"] if e]
        if not elementos:
            return f"No encontré {busqueda} en Spotify."
        elemento = elementos[0]
        dispositivo = _dispositivo(sp)
        if not dispositivo:
            return "No encontré Spotify abierto en ningún dispositivo."
        if tipo == "track":
            sp.start_playback(device_id=dispositivo, uris=[elemento["uri"]])
            return f"Poniendo {elemento['name']} de {elemento['artists'][0]['name']}."
        sp.start_playback(device_id=dispositivo, context_uri=elemento["uri"])
        return f"Poniendo {elemento['name']}."
    except SpotifyException as e:
        logger.error(f"Spotify: {e}")
        if e.http_status == 403:
            return "Spotify no me deja controlar la música. Se necesita cuenta Premium."
        return "Spotify me dio un error, intenta de nuevo."
    except Exception as e:
        logger.error(f"Spotify: {e}")
        return "No pude conectarme con Spotify."
