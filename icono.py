"""Ícono de Solovino (un perrito), dibujado con código: lo usan la bandeja
(con un punto del color del estado), la ventana de ajustes y el .exe.

    python icono.py      -> genera recursos/solovino.ico
"""
import os

from PIL import Image, ImageDraw

_BASE = 256  # se dibuja grande y se reduce: queda suave en cualquier tamaño


def dibujar(tamano: int = 64, color_estado=None) -> Image.Image:
    img = Image.new("RGBA", (_BASE, _BASE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cafe, cafe_oscuro, hocico = (196, 140, 82), (120, 78, 42), (240, 214, 174)

    # Orejas caídas
    d.ellipse((18, 50, 92, 190), fill=cafe_oscuro)
    d.ellipse((164, 50, 238, 190), fill=cafe_oscuro)
    # Cabeza
    d.ellipse((48, 34, 208, 214), fill=cafe)
    # Hocico
    d.ellipse((82, 122, 174, 210), fill=hocico)
    # Ojos con brillo
    for x in (90, 146):
        d.ellipse((x, 92, x + 22, 116), fill=(35, 25, 20))
        d.ellipse((x + 12, 96, x + 18, 102), fill=(255, 255, 255))
    # Nariz y boca
    d.ellipse((110, 136, 146, 162), fill=(40, 28, 24))
    d.line((128, 162, 128, 180), fill=(40, 28, 24), width=5)
    d.arc((104, 162, 128, 192), 20, 160, fill=(40, 28, 24), width=5)
    d.arc((128, 162, 152, 192), 20, 160, fill=(40, 28, 24), width=5)

    if color_estado is not None:  # punto de estado abajo a la derecha
        d.ellipse((160, 160, 252, 252), fill=(255, 255, 255))
        d.ellipse((172, 172, 240, 240), fill=color_estado)

    return img.resize((tamano, tamano), Image.LANCZOS)


def guardar_ico(ruta: str):
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    dibujar(256).save(ruta, format="ICO", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])


if __name__ == "__main__":
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos", "solovino.ico")
    guardar_ico(destino)
    print(f"Ícono guardado en {destino}")
