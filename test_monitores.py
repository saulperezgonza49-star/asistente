import re
from screeninfo import get_monitors

print("Comparando con la numeración de Windows (Configuración > Sistema > Pantalla):\n")
for m in get_monitors():
    match = re.search(r'DISPLAY(\d+)', m.name)
    numero = match.group(1) if match else "?"
    print(f"Windows la llama Pantalla {numero}  ->  x={m.x}, y={m.y} | tamaño {m.width}x{m.height} | primaria={m.is_primary}")