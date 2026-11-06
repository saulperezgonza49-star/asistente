"""Ventana de ajustes (se abre desde el ícono de la bandeja).

Corre en su propio hilo con tkinter (viene con Python, no agrega nada al
.exe). Tkinter no es seguro entre hilos: todo lo que tarda (probar la API
key, la voz, conectar Spotify) corre en un hilo aparte y el resultado se
regresa por una cola que la ventana revisa con after().
"""
import os
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

import autoarranque
import estado
from config import CONFIG, VERSION, guardar_clave, guardar_config, logger
from rutas import DIR_DATOS

PREDETERMINADO = "Predeterminado de Windows"
DETECCION = {"local": "En tu computadora (sin internet)", "google": "Con Google (necesita internet)"}

_abierta = threading.Lock()
al_reiniciar = None  # main.py pone aquí la función para reiniciar Solovino


def abrir(pestana: str = "general"):
    """Abre la ventana (si ya está abierta no hace nada)."""
    if not _abierta.acquire(blocking=False):
        return
    threading.Thread(target=_correr, args=(pestana,), daemon=True, name="ajustes").start()


def _correr(pestana):
    try:
        VentanaAjustes(pestana).root.mainloop()
    except Exception as e:
        logger.exception(f"Error en la ventana de ajustes: {e}")
    finally:
        _abierta.release()


class VentanaAjustes:
    def __init__(self, pestana):
        self.root = tk.Tk()
        self.root.title(f"Solovino {VERSION} — Ajustes")
        self.root.resizable(False, False)
        self._resultados = queue.Queue()
        self._icono()

        cuaderno = ttk.Notebook(self.root)
        cuaderno.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        paginas = {
            "general": self._pagina_general(cuaderno),
            "voz": self._pagina_voz(cuaderno),
            "microfono": self._pagina_microfono(cuaderno),
            "claves": self._pagina_claves(cuaderno),
        }
        cuaderno.select(paginas.get(pestana, paginas["general"]))

        botones = ttk.Frame(self.root)
        botones.pack(fill="x", padx=10, pady=10)
        ttk.Button(botones, text="Abrir carpeta de datos", command=lambda: os.startfile(DIR_DATOS)).pack(side="left")
        ttk.Button(botones, text="Guardar", command=self._guardar).pack(side="right")
        ttk.Button(botones, text="Cancelar", command=self.root.destroy).pack(side="right", padx=6)

        self.root.after(80, self._revisar_resultados)
        self.root.after(80, self._actualizar_medidor)
        # Aparece al frente aunque la abras desde la bandeja.
        self.root.attributes("-topmost", True)
        self.root.after(400, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    # ---------------------------------------------------------
    # Utilidades
    # ---------------------------------------------------------
    def _icono(self):
        try:
            from PIL import ImageTk
            import icono
            self._foto = ImageTk.PhotoImage(icono.dibujar(64), master=self.root)
            self.root.iconphoto(True, self._foto)
        except Exception:
            pass

    def _en_hilo(self, funcion, al_terminar):
        """Corre `funcion` en otro hilo y llama `al_terminar(resultado)` en el de la ventana."""
        def tarea():
            try:
                resultado = funcion()
            except Exception as e:
                resultado = f"Error: {e}"
            self._resultados.put((al_terminar, resultado))
        threading.Thread(target=tarea, daemon=True).start()

    def _revisar_resultados(self):
        while not self._resultados.empty():
            al_terminar, resultado = self._resultados.get_nowait()
            al_terminar(resultado)
        self.root.after(80, self._revisar_resultados)

    @staticmethod
    def _fila(padre, fila, texto, widget, ayuda=None):
        ttk.Label(padre, text=texto).grid(row=fila, column=0, sticky="w", pady=4, padx=(0, 10))
        widget.grid(row=fila, column=1, sticky="we", pady=4)
        if ayuda:
            ttk.Label(padre, text=ayuda, foreground="#777").grid(row=fila + 1, column=1, sticky="w")

    @staticmethod
    def _pagina(cuaderno, titulo):
        marco = ttk.Frame(cuaderno, padding=14)
        marco.columnconfigure(1, weight=1)
        cuaderno.add(marco, text=titulo)
        return marco

    # ---------------------------------------------------------
    # Páginas
    # ---------------------------------------------------------
    def _pagina_general(self, cuaderno):
        p = self._pagina(cuaderno, "General")
        self.v_nombre = tk.StringVar(value=CONFIG["nombre_usuario"])
        self.v_tecla = tk.StringVar(value=CONFIG.get("tecla_hablar", ""))
        self.v_deteccion = tk.StringVar(value=DETECCION.get(CONFIG.get("deteccion_palabra_clave", "local")))
        self.v_seguimiento = tk.IntVar(value=int(CONFIG.get("segundos_seguimiento", 5)))
        self.v_saludo = tk.BooleanVar(value=bool(CONFIG.get("saludo_al_despertar")))
        self.v_confirmar = tk.BooleanVar(value=bool(CONFIG.get("confirmar_acciones", True)))
        self.v_inicio = tk.BooleanVar(value=autoarranque.activo())
        self.v_modelo = tk.StringVar(value=CONFIG["modelo_ia"])

        self._fila(p, 0, "Tu nombre", ttk.Entry(p, textvariable=self.v_nombre, width=34))
        self._fila(p, 1, "Tecla para hablar", ttk.Entry(p, textvariable=self.v_tecla),
                   "Ej.: ctrl+alt+space, f9, ctrl+shift+h. Vacío = desactivada.")
        self._fila(p, 3, "Detectar 'Solovino'",
                   ttk.Combobox(p, textvariable=self.v_deteccion, values=list(DETECCION.values()), state="readonly"))
        self._fila(p, 4, "Seguir escuchando (s)", ttk.Spinbox(p, from_=0, to=15, textvariable=self.v_seguimiento, width=6),
                   "Tras una respuesta, te escucha sin decir 'Solovino'. 0 = no.")
        ttk.Checkbutton(p, text="Saludar con voz al despertar (si no, un pitido)",
                        variable=self.v_saludo).grid(row=6, column=0, columnspan=2, sticky="w", pady=(10, 2))
        ttk.Checkbutton(p, text="Preguntar antes de cerrar apps, suspender o apagar",
                        variable=self.v_confirmar).grid(row=7, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Checkbutton(p, text="Iniciar con Windows",
                        variable=self.v_inicio).grid(row=8, column=0, columnspan=2, sticky="w", pady=2)
        self._fila(p, 9, "Modelo de Gemini", ttk.Entry(p, textvariable=self.v_modelo))
        return p

    def _pagina_voz(self, cuaderno):
        import voz
        p = self._pagina(cuaderno, "Voz")
        self.v_neural = tk.BooleanVar(value=bool(CONFIG.get("usar_voz_neural", True)))
        self.v_voz = tk.StringVar(value=CONFIG["voz_neural"])
        self.v_velocidad = tk.StringVar(value=CONFIG["velocidad_voz"])

        ttk.Checkbutton(p, text="Voz natural (necesita internet; sin internet usa la de Windows)",
                        variable=self.v_neural).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._fila(p, 1, "Voz", ttk.Combobox(p, textvariable=self.v_voz, values=voz.VOCES_NEURALES))
        self._fila(p, 2, "Velocidad", ttk.Combobox(p, textvariable=self.v_velocidad, width=8,
                                                   values=["-10%", "+0%", "+10%", "+20%", "+30%"]))
        self.l_voz = ttk.Label(p, text="")
        ttk.Button(p, text="▶ Probar voz", command=self._probar_voz).grid(row=3, column=1, sticky="w", pady=10)
        self.l_voz.grid(row=4, column=1, sticky="w")
        return p

    def _pagina_microfono(self, cuaderno):
        from escucha import listar_microfonos
        p = self._pagina(cuaderno, "Micrófono")
        self.v_micro = tk.StringVar(value=CONFIG.get("dispositivo_entrada") or PREDETERMINADO)
        self.v_vad = tk.IntVar(value=int(CONFIG.get("sensibilidad_vad", 2)))
        self.v_ganancia = tk.DoubleVar(value=float(CONFIG.get("factor_ganancia", 1.0)))

        self.c_micro = ttk.Combobox(p, textvariable=self.v_micro, state="readonly", width=40,
                                    values=[PREDETERMINADO] + listar_microfonos())
        self._fila(p, 0, "Micrófono", self.c_micro)
        ttk.Button(p, text="Actualizar lista", command=lambda: self.c_micro.configure(
            values=[PREDETERMINADO] + listar_microfonos())).grid(row=1, column=1, sticky="w")

        l_vad = ttk.Label(p, text="")
        def _texto_vad(*_):
            l_vad.configure(text=["0 · capta todo", "1", "2 · recomendado", "3 · ignora más ruido"][self.v_vad.get()])
        escala = ttk.Scale(p, from_=0, to=3, variable=self.v_vad,
                           command=lambda v: (self.v_vad.set(round(float(v))), _texto_vad()))
        self._fila(p, 2, "Filtro de ruido", escala)
        l_vad.grid(row=3, column=1, sticky="w")
        _texto_vad()

        l_ganancia = ttk.Label(p, text=f"{self.v_ganancia.get():.1f}×")
        self._fila(p, 4, "Ganancia", ttk.Scale(p, from_=0.5, to=3.0, variable=self.v_ganancia,
                                               command=lambda v: l_ganancia.configure(text=f"{float(v):.1f}×")))
        l_ganancia.grid(row=5, column=1, sticky="w")

        ttk.Label(p, text="Habla para probar (micrófono que está usando ahora):").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(14, 4))
        self.medidor = tk.Canvas(p, height=22, width=420, bg="#e6e6e6", highlightthickness=0)
        self.medidor.grid(row=7, column=0, columnspan=2, sticky="we")
        self.l_medidor = ttk.Label(p, text="")
        self.l_medidor.grid(row=8, column=0, columnspan=2, sticky="w", pady=4)
        return p

    def _pagina_claves(self, cuaderno):
        p = self._pagina(cuaderno, "Claves")
        self.v_gemini = tk.StringVar(value=os.environ.get("GEMINI_API_KEY", ""))
        self.v_spotify = tk.StringVar(value=os.environ.get("SPOTIFY_CLIENT_ID", ""))
        self.v_mostrar = tk.BooleanVar(value=False)

        e_gemini = ttk.Entry(p, textvariable=self.v_gemini, show="•", width=40)
        self._fila(p, 0, "Gemini API key", e_gemini)
        fila = ttk.Frame(p)
        fila.grid(row=1, column=1, sticky="w")
        ttk.Checkbutton(fila, text="Mostrar", variable=self.v_mostrar,
                        command=lambda: e_gemini.configure(show="" if self.v_mostrar.get() else "•")).pack(side="left")
        ttk.Button(fila, text="Probar", command=self._probar_gemini).pack(side="left", padx=8)
        self.l_gemini = ttk.Label(fila, text="")
        self.l_gemini.pack(side="left")
        enlace = ttk.Label(p, text="Consíguela gratis en aistudio.google.com/apikey", foreground="#1a6fd6",
                           cursor="hand2")
        enlace.grid(row=2, column=1, sticky="w", pady=(0, 14))
        enlace.bind("<Button-1>", lambda _e: webbrowser.open("https://aistudio.google.com/apikey"))

        self._fila(p, 3, "Spotify Client ID", ttk.Entry(p, textvariable=self.v_spotify))
        fila = ttk.Frame(p)
        fila.grid(row=4, column=1, sticky="w")
        ttk.Button(fila, text="Conectar", command=self._conectar_spotify).pack(side="left")
        self.l_spotify = ttk.Label(fila, text="")
        self.l_spotify.pack(side="left", padx=8)
        ttk.Label(p, text="Redirect URI de tu app: " + CONFIG["spotify_redirect_uri"],
                  foreground="#777").grid(row=5, column=1, sticky="w")
        return p

    # ---------------------------------------------------------
    # Acciones
    # ---------------------------------------------------------
    def _actualizar_medidor(self):
        mic = estado.microfono
        self.medidor.delete("all")
        if mic is None:
            self.l_medidor.configure(text="El micrófono no está activo.")
        else:
            ancho = int(self.medidor.winfo_width() * min(1.0, mic.nivel * 1.5))
            color = "#18b56b" if mic.hay_voz else "#9a9a9a"
            self.medidor.create_rectangle(0, 0, ancho, 22, fill=color, width=0)
            if estado.ia_hablando:
                self.l_medidor.configure(text="(Solovino está hablando)")
            else:
                self.l_medidor.configure(text="✓ Detecto voz" if mic.hay_voz else "Silencio o ruido")
        self.root.after(80, self._actualizar_medidor)

    def _probar_voz(self):
        import voz
        self.l_voz.configure(text="Generando…")
        neural, nombre, velocidad = self.v_neural.get(), self.v_voz.get(), self.v_velocidad.get()
        self._en_hilo(lambda: voz.probar_voz(nombre, velocidad, neural),
                      lambda error: self.l_voz.configure(text=error or "✓"))

    def _probar_gemini(self):
        clave, modelo = self.v_gemini.get().strip(), self.v_modelo.get().strip()
        self.l_gemini.configure(text="Probando…")

        def probar():
            from google import genai
            if not clave:
                return "✗ Pega primero la key"
            # El cliente se guarda en una variable: si se usa directo
            # (genai.Client(...).models.get) Python lo descarta antes de que
            # llegue la respuesta y truena con "client has been closed".
            cliente = genai.Client(api_key=clave)
            try:
                cliente.models.get(model=modelo)
            except Exception as e:
                texto = str(e)
                if "API_KEY_INVALID" in texto or "API key not valid" in texto:
                    return "✗ La key no es válida"
                if "NOT_FOUND" in texto or "404" in texto:
                    return f"✗ La key sirve, pero no existe el modelo '{modelo}'"
                if "PERMISSION_DENIED" in texto or "403" in texto:
                    return "✗ La key no tiene permiso para Gemini"
                return f"✗ {type(e).__name__}: {texto[:80]}"
            return "✓ Funciona"
        self._en_hilo(probar, lambda r: self.l_gemini.configure(text=r))

    def _conectar_spotify(self):
        import spotify
        nuevo = self.v_spotify.get().strip()
        if nuevo != os.environ.get("SPOTIFY_CLIENT_ID", ""):
            guardar_clave("SPOTIFY_CLIENT_ID", nuevo)
            spotify._cliente_cache = None
        self.l_spotify.configure(text="Revisa tu navegador…")
        self._en_hilo(spotify.conectar, lambda r: self.l_spotify.configure(text=r))

    def _guardar(self):
        import atajos
        import ia
        import spotify

        tecla = self.v_tecla.get().strip().lower()
        if tecla:
            try:
                atajos.parsear_combinacion(tecla)
            except ValueError as e:
                messagebox.showerror("Tecla inválida", str(e), parent=self.root)
                return

        deteccion = next(k for k, v in DETECCION.items() if v == self.v_deteccion.get())
        microfono = "" if self.v_micro.get() == PREDETERMINADO else self.v_micro.get()
        cambios = {
            "nombre_usuario": self.v_nombre.get().strip() or CONFIG["nombre_usuario"],
            "tecla_hablar": tecla,
            "deteccion_palabra_clave": deteccion,
            "segundos_seguimiento": max(0, min(15, int(self.v_seguimiento.get()))),
            "saludo_al_despertar": self.v_saludo.get(),
            "confirmar_acciones": self.v_confirmar.get(),
            "modelo_ia": self.v_modelo.get().strip() or CONFIG["modelo_ia"],
            "usar_voz_neural": self.v_neural.get(),
            "voz_neural": self.v_voz.get().strip() or CONFIG["voz_neural"],
            "velocidad_voz": self.v_velocidad.get().strip() or "+0%",
            "dispositivo_entrada": microfono,
            "sensibilidad_vad": int(self.v_vad.get()),
            "factor_ganancia": round(float(self.v_ganancia.get()), 2),
        }
        reiniciar_escucha = any(cambios[k] != CONFIG.get(k) for k in
                                ("dispositivo_entrada", "sensibilidad_vad", "deteccion_palabra_clave"))
        cambio_nombre = cambios["nombre_usuario"] != CONFIG["nombre_usuario"]
        if cambios["modelo_ia"] != CONFIG["modelo_ia"]:
            ia.olvidar()
        try:
            guardar_config(cambios)
        except OSError as e:
            messagebox.showerror("No se pudo guardar", str(e), parent=self.root)
            return

        if self.v_gemini.get().strip() != os.environ.get("GEMINI_API_KEY", ""):
            guardar_clave("GEMINI_API_KEY", self.v_gemini.get())
            ia._client = None
            ia.olvidar()
        if self.v_spotify.get().strip() != os.environ.get("SPOTIFY_CLIENT_ID", ""):
            guardar_clave("SPOTIFY_CLIENT_ID", self.v_spotify.get())
            spotify._cliente_cache = None
        if self.v_inicio.get() != autoarranque.activo():
            autoarranque.alternar()
        if reiniciar_escucha:
            estado.reiniciar_escucha.set()

        if cambio_nombre and al_reiniciar and messagebox.askyesno(
                "Reiniciar", "El nombre se aplica al reiniciar Solovino. ¿Reiniciar ahora?", parent=self.root):
            self.root.destroy()
            al_reiniciar()
            return
        self.root.destroy()
