"""Helpers genéricos usados por varios módulos de comandos."""
import re


def extraer_numero(texto: str):
    """Regresa el primer número que aparezca en el texto, o None si no hay."""
    match = re.search(r'\d+', texto)
    return int(match.group()) if match else None


def limpiar_texto(texto: str, palabras_quitar: list) -> str:
    """Quita cada palabra de la lista del texto y recorta espacios sobrantes.

    Reemplaza el patrón que antes estaba copiado en cada sección de
    ejecutar_comando_local:
        for palabra in lista:
            texto = texto.replace(palabra, "")
        texto = texto.strip()
    """
    resultado = texto
    for palabra in palabras_quitar:
        resultado = resultado.replace(palabra, "")
    return resultado.strip()