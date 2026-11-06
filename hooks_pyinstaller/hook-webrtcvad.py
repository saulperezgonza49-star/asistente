# La regla que trae PyInstaller busca el paquete "webrtcvad", pero el que
# existe para Python 3.14 se llama "webrtcvad-wheels" (mismo módulo).
from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata("webrtcvad-wheels")
