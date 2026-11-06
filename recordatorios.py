"""Recordatorios y temporizadores. Se guardan en %APPDATA%\\Solovino\\recordatorios.json,
así que sobreviven si cierras Solovino o reinicias la computadora."""
import json
import re
import threading
import time
import uuid
from datetime import datetime, timedelta

import estado
from config import logger
from rutas import ruta_datos
from utils import NUMEROS_EN_PALABRAS

ARCHIVO = ruta_datos("recordatorios.json")
_lock = threading.Lock()

_UNIDADES = {"segundo": 1, "minuto": 60, "hora": 3600}


def _cargar():
    try:
        with open(ARCHIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _guardar(lista):
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(lista, f, indent=2, ensure_ascii=False)


def crear(mensaje: str, cuando: datetime) -> dict:
    recordatorio = {"id": uuid.uuid4().hex[:6], "mensaje": mensaje.strip() or "tu temporizador",
                    "cuando": cuando.isoformat(timespec="seconds")}
    with _lock:
        lista = _cargar()
        lista.append(recordatorio)
        _guardar(lista)
    logger.info(f"Recordatorio creado: {recordatorio}")
    return recordatorio


def listar():
    with _lock:
        return sorted(_cargar(), key=lambda r: r["cuando"])


def cancelar(texto_o_id: str = "") -> int:
    """Cancela los que coincidan con el id o con parte del mensaje. Vacío = todos.
    Regresa cuántos se cancelaron."""
    texto_o_id = texto_o_id.lower().strip()
    with _lock:
        lista = _cargar()
        quedan = [r for r in lista if texto_o_id and texto_o_id not in r["mensaje"].lower()
                  and texto_o_id != r["id"]]
        _guardar(quedan)
    return len(lista) - len(quedan)


def parsear_duracion(texto: str):
    """'20 minutos' -> 1200 s, 'una hora y media' -> 5400, 'media hora' -> 1800.
    Regresa los segundos o None si no encuentra una duración."""
    texto = texto.lower()
    total = 0
    if "media hora" in texto:
        total += 1800
    patron = r'(\d+(?:[.,]\d+)?|un|una|' + "|".join(NUMEROS_EN_PALABRAS) + r')\s+(segundo|minuto|hora)s?'
    for cantidad, unidad in re.findall(patron, texto):
        if cantidad in ("un", "una"):
            valor = 1.0
        elif cantidad in NUMEROS_EN_PALABRAS:
            valor = float(NUMEROS_EN_PALABRAS[cantidad])
        else:
            valor = float(cantidad.replace(",", "."))
        total += valor * _UNIDADES[unidad]
        if unidad == "hora" and re.search(r'hora[s]?\s+y\s+media', texto):
            total += 1800
    return int(total) if total else None


def describir_tiempo(segundos: int) -> str:
    if segundos < 60:
        return f"{segundos} segundos"
    minutos = round(segundos / 60)
    if minutos < 60:
        return f"{minutos} minuto{'s' if minutos != 1 else ''}"
    horas, minutos = divmod(minutos, 60)
    texto = f"{horas} hora{'s' if horas != 1 else ''}"
    return texto + (f" y {minutos} minutos" if minutos else "")


def describir_fecha(cuando: datetime) -> str:
    hoy = datetime.now().date()
    dia = "hoy" if cuando.date() == hoy else "mañana" if cuando.date() == hoy + timedelta(days=1) \
        else cuando.strftime("el %d/%m")
    return f"{dia} a las {cuando.strftime('%H:%M')}"


def _hilo_revisor():
    """Cada segundo revisa si ya toca algún recordatorio; si sí, lo deja en
    estado.anuncios para que el hilo de voz lo diga cuando esté libre."""
    from voz import mandar_notificacion
    while estado.running:
        ahora = datetime.now()
        with _lock:
            lista = _cargar()
            vencidos = [r for r in lista if datetime.fromisoformat(r["cuando"]) <= ahora]
            if vencidos:
                _guardar([r for r in lista if r not in vencidos])
        for r in vencidos:
            logger.info(f"Recordatorio vencido: {r}")
            mandar_notificacion("⏰ Recordatorio", r["mensaje"])
            estado.anuncios.put(r["mensaje"])
        time.sleep(1)


def iniciar():
    threading.Thread(target=_hilo_revisor, daemon=True, name="recordatorios").start()
