"""DevNexAI GUI — interfaz de escritorio moderna (CustomTkinter).

Estética tipo app de chat (ChatGPT/Claude): barra lateral, burbujas de
mensaje, modo oscuro, acento naranja. Reutiliza el motor agéntico.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

from . import config, memory
from .agent import Agent
from .providers import (LOCAL_PRESETS, OPENAI_COMPAT_PRESETS, PROVIDERS,
                        ProviderError, build_provider)

# Paleta
ORANGE = "#e07b39"
ORANGE_HOVER = "#c96a2e"
BG = "#0f0f11"
SIDEBAR = "#17171a"
CARD = "#1d1d21"
USER_BUBBLE = "#2a2a30"
BOT_BUBBLE = "#1a1a1e"
TOOL_FG = "#7a7a85"
GREEN = "#4caf7d"
BLUE = "#5b9bd5"
TEXT = "#ececec"
MUTED = "#9a9aa5"

ALL_PROVIDERS = list(PROVIDERS) + list(OPENAI_COMPAT_PRESETS)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class DevNexGUI:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("DevNexAI")
        self.root.geometry("1040x720")
        self.root.minsize(820, 560)
        self.root.configure(fg_color=BG)

        self.project_dir = Path.cwd()
        self.agent: Agent | None = None
        self.event_q: queue.Queue = queue.Queue()
        self.confirm_result: queue.Queue = queue.Queue()
        self.busy = False
        self._streaming_label = None  # burbuja "pensando"

        self._build_ui()
        self._refresh_status()
        self.root.after(60, self._drain_events)

    # ---------------- layout ----------------
    def _build_ui(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ---- Sidebar ----
        sidebar = ctk.CTkFrame(self.root, width=230, fg_color=SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        logo = ctk.CTkLabel(sidebar, text="DevNexAI", font=("Segoe UI", 24, "bold"),
                            text_color=ORANGE)
        logo.pack(anchor="w", padx=22, pady=(24, 2))
        ctk.CTkLabel(sidebar, text="agente multi-LLM", font=("Segoe UI", 11),
                     text_color=MUTED).pack(anchor="w", padx=22, pady=(0, 24))

        self._side_btn(sidebar, "＋   Nueva conversación", self.clear_chat).pack(
            fill="x", padx=14, pady=4)
        self._side_btn(sidebar, "⚙   Proveedores", self.open_config).pack(
            fill="x", padx=14, pady=4)
        self._side_btn(sidebar, "📁   Carpeta del proyecto", self.choose_folder).pack(
            fill="x", padx=14, pady=4)

        # estado del proveedor (abajo)
        self.status_card = ctk.CTkFrame(sidebar, fg_color=CARD, corner_radius=10)
        self.status_card.pack(side="bottom", fill="x", padx=14, pady=16)
        self.status_label = ctk.CTkLabel(self.status_card, text="", font=("Segoe UI", 11),
                                         text_color=MUTED, justify="left", anchor="w",
                                         wraplength=180)
        self.status_label.pack(fill="x", padx=12, pady=10)

        # ---- Panel principal ----
        main = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # Área scrollable de mensajes
        self.chat = ctk.CTkScrollableFrame(main, fg_color=BG)
        self.chat.grid(row=0, column=0, sticky="nsew", padx=20, pady=(18, 8))
        self.chat.grid_columnconfigure(0, weight=1)
        self._row = 0

        # Barra de entrada
        inbar = ctk.CTkFrame(main, fg_color=CARD, corner_radius=16)
        inbar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 18))
        inbar.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkTextbox(inbar, height=52, fg_color="transparent",
                                    font=("Segoe UI", 13), text_color=TEXT,
                                    border_width=0, wrap="word")
        self.entry.grid(row=0, column=0, sticky="ew", padx=(16, 8), pady=8)
        self.entry.bind("<Return>", self._on_return)

        self.send_btn = ctk.CTkButton(inbar, text="➤", width=46, height=46,
                                      corner_radius=12, fg_color=ORANGE,
                                      hover_color=ORANGE_HOVER, text_color="#1a1a1a",
                                      font=("Segoe UI", 18, "bold"), command=self.send)
        self.send_btn.grid(row=0, column=1, padx=(0, 8), pady=8)

        self._welcome()

    def _side_btn(self, parent, text, cmd):
        return ctk.CTkButton(parent, text=text, command=cmd, anchor="w",
                             fg_color="transparent", hover_color=CARD,
                             text_color=TEXT, font=("Segoe UI", 13), height=38,
                             corner_radius=8)

    # ---------------- burbujas ----------------
    def _bubble(self, text: str, who: str):
        """who: 'user' | 'bot' | 'tool' | 'plan' | 'note' | 'error'"""
        wrap = ctk.CTkFrame(self.chat, fg_color="transparent")
        wrap.grid(row=self._row, column=0, sticky="ew", pady=5)
        wrap.grid_columnconfigure(0, weight=1)
        self._row += 1

        if who == "user":
            b = ctk.CTkFrame(wrap, fg_color=USER_BUBBLE, corner_radius=14)
            b.grid(row=0, column=0, sticky="e", padx=(80, 0))
            ctk.CTkLabel(b, text=text, font=("Segoe UI", 13), text_color=TEXT,
                         justify="left", wraplength=560).pack(padx=14, pady=10)
        elif who == "bot":
            b = ctk.CTkFrame(wrap, fg_color=BOT_BUBBLE, corner_radius=14)
            b.grid(row=0, column=0, sticky="w", padx=(0, 80))
            ctk.CTkLabel(b, text="DevNexAI", font=("Segoe UI", 11, "bold"),
                         text_color=ORANGE, anchor="w").pack(fill="x", padx=14, pady=(8, 0))
            lbl = ctk.CTkLabel(b, text=text, font=("Segoe UI", 13), text_color=TEXT,
                               justify="left", wraplength=600, anchor="w")
            lbl.pack(fill="x", padx=14, pady=(2, 10))
            return lbl  # devolver para poder actualizar (spinner)
        elif who in ("tool", "plan", "note"):
            color = TOOL_FG if who == "tool" else (BLUE if who == "plan" else GREEN)
            ctk.CTkLabel(wrap, text=text, font=("Consolas", 11), text_color=color,
                         justify="left", anchor="w", wraplength=620).grid(
                row=0, column=0, sticky="w", padx=8)
        elif who == "error":
            b = ctk.CTkFrame(wrap, fg_color="#3a1f1f", corner_radius=10)
            b.grid(row=0, column=0, sticky="w", padx=(0, 80))
            ctk.CTkLabel(b, text=text, font=("Segoe UI", 12), text_color="#ff6b6b",
                         justify="left", wraplength=560).pack(padx=14, pady=8)

        self.root.after(20, self._scroll_bottom)

    def _scroll_bottom(self):
        try:
            self.chat._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _welcome(self):
        self._bubble("¡Hola! Soy DevNexAI, tu agente de codificación. Conecta un "
                     "proveedor en ⚙ Proveedores y elige la carpeta de tu proyecto "
                     "para empezar.", "bot")

    def _refresh_status(self):
        import os
        folder = "mi-proyecto" if os.environ.get("DEVNEXAI_DEMO") else self.project_dir.name
        active = config.get_active()
        if active:
            kind, entry = active
            try:
                model = build_provider(kind, entry["api_key"], entry.get("model"),
                                       entry.get("base_url")).model
            except ProviderError:
                model = "?"
            self.status_label.configure(
                text=f"● {kind}\n{model}\n\n📁 {folder}")
        else:
            self.status_label.configure(text=f"○ sin proveedor\n\n📁 {folder}")

    # ---------------- acciones ----------------
    def choose_folder(self):
        d = filedialog.askdirectory(initialdir=str(self.project_dir),
                                    title="Elige la carpeta del proyecto")
        if d:
            self.project_dir = Path(d)
            self.agent = None
            self._refresh_status()
            import os
            shown = "mi-proyecto" if os.environ.get("DEVNEXAI_DEMO") else d
            self._bubble(f"Carpeta de trabajo: {shown}", "note")

    def clear_chat(self):
        for w in self.chat.winfo_children():
            w.destroy()
        self._row = 0
        if self.agent:
            self.agent.messages = self.agent.messages[:1]
            self.agent.plan = []
        self._welcome()

    def open_config(self):
        ConfigWindow(self.root, on_save=self._refresh_status)

    # ---------------- envío ----------------
    def _on_return(self, event):
        if event.state & 0x0001:  # Shift+Enter = salto de línea
            return
        self.send()
        return "break"

    def send(self):
        if self.busy:
            return
        text = self.entry.get("1.0", "end").strip()
        if not text:
            return
        active = config.get_active()
        if active is None:
            messagebox.showwarning("DevNexAI", "Configura un proveedor primero (⚙ Proveedores).")
            return

        self.entry.delete("1.0", "end")
        self._bubble(text, "user")

        if self.agent is None:
            kind, entry = active
            try:
                provider = build_provider(kind, entry["api_key"], entry.get("model"),
                                          entry.get("base_url"))
            except ProviderError as e:
                messagebox.showerror("DevNexAI", str(e))
                return
            self.agent = Agent(provider, self.project_dir,
                               on_event=lambda k, d: self.event_q.put((k, d)),
                               confirm=self._confirm_from_thread, use_memory=True)

        self.busy = True
        self.send_btn.configure(state="disabled", text="…")
        self._streaming_label = self._bubble("pensando…", "bot")
        threading.Thread(target=self._run_agent, args=(text,), daemon=True).start()

    def _run_agent(self, text: str):
        try:
            self.agent.run(text)
        except ProviderError as e:
            self.event_q.put(("error", str(e)))
        except Exception as e:  # noqa: BLE001
            self.event_q.put(("error", f"{type(e).__name__}: {e}"))
        finally:
            self.event_q.put(("done", None))

    def _confirm_from_thread(self, command: str, reason: str) -> bool:
        self.event_q.put(("confirm", (command, reason)))
        return self.confirm_result.get()

    # ---------------- eventos ----------------
    def _drain_events(self):
        try:
            while True:
                kind, data = self.event_q.get_nowait()
                self._handle_event(kind, data)
        except queue.Empty:
            pass
        self.root.after(60, self._drain_events)

    def _handle_event(self, kind: str, data):
        if kind == "assistant":
            if self._streaming_label is not None:
                self._streaming_label.configure(text=data)
                self._streaming_label = None
            else:
                self._bubble(data, "bot")
        elif kind == "tool_call":
            preview = data["input"].get("command") or data["input"].get("path") or ""
            self._bubble(f"⚙ {data['name']}({preview})", "tool")
        elif kind == "tool_result":
            head = (data["output"].strip().splitlines() or [""])[0]
            self._bubble(f"    ↳ {head[:110]}", "tool")
        elif kind == "plan":
            icons = {"pendiente": "○", "en_progreso": "◐", "hecho": "●"}
            txt = "Plan:\n" + "\n".join(
                f"  {icons.get(s.get('status'), '○')} {s.get('task','')}" for s in data)
            self._bubble(txt, "plan")
        elif kind == "remember":
            self._bubble(f"💾 recordado: {data}", "note")
        elif kind == "error":
            if self._streaming_label is not None:
                self._streaming_label = None
            self._bubble(f"⚠ {data}", "error")
        elif kind == "confirm":
            command, reason = data
            ok = messagebox.askyesno(
                "⚠ Comando peligroso",
                f"DevNexAI quiere ejecutar un comando potencialmente peligroso.\n\n"
                f"Motivo: {reason}\n\nComando:\n{command}\n\n¿Permitir?")
            self.confirm_result.put(ok)
        elif kind == "done":
            self.busy = False
            self.send_btn.configure(state="normal", text="➤")
            if self._streaming_label is not None:
                self._streaming_label.configure(text="(sin respuesta)")
                self._streaming_label = None


class ConfigWindow:
    def __init__(self, parent, on_save=None):
        self.on_save = on_save or (lambda: None)
        self.win = ctk.CTkToplevel(parent)
        self.win.title("Proveedores")
        self.win.geometry("520x600")
        self.win.configure(fg_color=BG)
        self.win.transient(parent)
        self.win.after(120, self.win.grab_set)

        ctk.CTkLabel(self.win, text="Conectar proveedor", font=("Segoe UI", 20, "bold"),
                     text_color=ORANGE).pack(pady=(22, 16))

        form = ctk.CTkFrame(self.win, fg_color=CARD, corner_radius=14)
        form.pack(fill="x", padx=24)

        ctk.CTkLabel(form, text="Proveedor", font=("Segoe UI", 12),
                     text_color=MUTED, anchor="w").pack(fill="x", padx=18, pady=(16, 2))
        self.prov_var = ctk.StringVar(value="anthropic")
        self.combo = ctk.CTkComboBox(form, values=ALL_PROVIDERS, variable=self.prov_var,
                                     command=self._on_change, state="readonly",
                                     fg_color=BG, button_color=ORANGE,
                                     button_hover_color=ORANGE_HOVER, dropdown_fg_color=CARD)
        self.combo.pack(fill="x", padx=18, pady=(0, 10))

        ctk.CTkLabel(form, text="API key", font=("Segoe UI", 12),
                     text_color=MUTED, anchor="w").pack(fill="x", padx=18, pady=(6, 2))
        self.key_entry = ctk.CTkEntry(form, show="•", fg_color=BG, border_width=0)
        self.key_entry.pack(fill="x", padx=18, pady=(0, 10))

        ctk.CTkLabel(form, text="Modelo (opcional)", font=("Segoe UI", 12),
                     text_color=MUTED, anchor="w").pack(fill="x", padx=18, pady=(6, 2))
        self.model_entry = ctk.CTkEntry(form, fg_color=BG, border_width=0)
        self.model_entry.pack(fill="x", padx=18, pady=(0, 10))

        ctk.CTkLabel(form, text="Base URL (opcional)", font=("Segoe UI", 12),
                     text_color=MUTED, anchor="w").pack(fill="x", padx=18, pady=(6, 2))
        self.base_entry = ctk.CTkEntry(form, fg_color=BG, border_width=0)
        self.base_entry.pack(fill="x", padx=18, pady=(0, 14))

        self.hint = ctk.CTkLabel(self.win, text="", font=("Segoe UI", 11, "italic"),
                                 text_color=MUTED, wraplength=460, justify="left")
        self.hint.pack(fill="x", padx=26, pady=(6, 0))

        ctk.CTkButton(self.win, text="Guardar y activar", command=self.save,
                      fg_color=ORANGE, hover_color=ORANGE_HOVER, text_color="#1a1a1a",
                      font=("Segoe UI", 13, "bold"), height=42).pack(pady=16, padx=24, fill="x")

        ctk.CTkLabel(self.win, text="Configurados", font=("Segoe UI", 13, "bold"),
                     text_color=TEXT, anchor="w").pack(fill="x", padx=26)
        self.list_frame = ctk.CTkScrollableFrame(self.win, fg_color=BG, height=120)
        self.list_frame.pack(fill="both", expand=True, padx=24, pady=8)

        self._on_change()
        self._refresh_list()

    def _on_change(self, *_):
        kind = self.prov_var.get()
        if kind in LOCAL_PRESETS:
            self.hint.configure(text=f"Local sin internet. Base URL: {LOCAL_PRESETS[kind]}. "
                                     f"API key puede ser 'local'. Indica el modelo (ej. llama3).")
            self.base_entry.delete(0, "end"); self.base_entry.insert(0, LOCAL_PRESETS[kind])
            self.key_entry.delete(0, "end"); self.key_entry.insert(0, "local")
        elif kind in OPENAI_COMPAT_PRESETS:
            self.hint.configure(text=f"OpenAI-compatible. Base URL por defecto: {OPENAI_COMPAT_PRESETS[kind]}")
            self.base_entry.delete(0, "end")
        else:
            self.hint.configure(text="Proveedor oficial. Solo necesitas la API key.")
            self.base_entry.delete(0, "end")

    def save(self):
        kind = self.prov_var.get()
        key = self.key_entry.get().strip()
        if not key:
            messagebox.showwarning("DevNexAI", "La API key no puede estar vacía.")
            return
        config.set_provider(kind, key, self.model_entry.get().strip() or None,
                            self.base_entry.get().strip() or None)
        self.on_save()
        self._refresh_list()
        messagebox.showinfo("DevNexAI", f"{kind} guardado y activado.")

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        provs = config.list_providers()
        active = config.load().get("active")
        if not provs:
            ctk.CTkLabel(self.list_frame, text="(ninguno)", text_color=MUTED).pack(anchor="w")
            return
        for kind, e in provs.items():
            row = ctk.CTkFrame(self.list_frame, fg_color=CARD, corner_radius=8)
            row.pack(fill="x", pady=3)
            mark = "●" if kind == active else "○"
            color = GREEN if kind == active else MUTED
            ctk.CTkLabel(row, text=f"{mark} {kind}", text_color=color,
                         font=("Segoe UI", 12, "bold")).pack(side="left", padx=12, pady=6)
            ctk.CTkLabel(row, text=config._mask(e.get("api_key", "")), text_color=MUTED,
                         font=("Consolas", 10)).pack(side="left", padx=8)
            ctk.CTkButton(row, text="usar", width=50, height=26, fg_color=BG,
                          hover_color=ORANGE, command=lambda k=kind: self._use(k)).pack(
                side="right", padx=8)

    def _use(self, kind):
        config.set_active(kind)
        self.on_save()
        self._refresh_list()


def main():
    root = ctk.CTk()
    DevNexGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
