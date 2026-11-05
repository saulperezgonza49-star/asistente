"""Helpers genéricos usados por varios módulos de comandos."""
import re


# Google a veces escribe "pantalla dos" en vez de "pantalla 2".
NUMEROS_EN_PALABRAS = {
    "uno": 1, "primera": 1, "primer": 1, "primero": 1,
    "dos": 2, "segunda": 2, "segundo": 2,
    "tres": 3, "tercera": 3, "tercer": 3, "tercero": 3,
    "cuatro": 4, "cuarta": 4, "cuarto": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50,
    "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100,
}


def extraer_numero(texto: str):
    """Regresa el primer número del texto (en dígitos o en palabra), o None."""
    match = re.search(r'\d+', texto)
    if match:
        return int(match.group())
    for palabra in re.findall(r'\w+', texto):
        if palabra in NUMEROS_EN_PALABRAS:
            return NUMEROS_EN_PALABRAS[palabra]
    return None


def contiene(texto: str, palabras) -> bool:
    """True si alguna palabra/frase de la lista aparece en el texto al INICIO
    de una palabra.

    Antes se usaba `w in texto`, que también encuentra coincidencias a media
    palabra ("pon" dentro de "japón", "en" dentro de "abrenos"). Con el
    límite de palabra al inicio se siguen aceptando derivados ("pausa" ->
    "pausar", "cuánto" -> "cuántos") pero no coincidencias accidentales.
    """
    return any(re.search(r'(?<!\w)' + re.escape(p), texto) for p in palabras)


def limpiar_texto(texto: str, palabras_quitar) -> str:
    """Quita del texto cada palabra/frase de la lista, SOLO como palabra
    completa, y normaliza espacios.

    Antes usaba str.replace, que borraba letras dentro de otras palabras:
    "mueve whatsapp a la pantalla 2" quedaba como "whtspp  l pntll" y
    "abre la calculadora" como "calcudora".
    """
    # Frases largas primero para que "que se llame" se quite antes que "se".
    for palabra in sorted(palabras_quitar, key=len, reverse=True):
        texto = re.sub(r'(?<!\w)' + re.escape(palabra) + r'(?!\w)', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()
