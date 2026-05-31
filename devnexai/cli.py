"""DevNexAI CLI — interfaz de línea de comandos estilo Claude Code.

Uso:
    devnexai                     # REPL interactivo en el directorio actual
    devnexai "tu petición"       # ejecuta una tarea y termina
    devnexai config add <prov>   # registra una API key
    devnexai config list         # muestra proveedores configurados
    devnexai config use <prov>   # cambia el proveedor activo
    devnexai config local        # asistente para LLM local (Ollama / LM Studio)
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

from . import config, memory
from .agent import Agent
from .providers import (LOCAL_PRESETS, OPENAI_COMPAT_PRESETS, PROVIDERS,
                        ProviderError, build_provider)
from .ui import UI

ALL_PROVIDERS = list(PROVIDERS) + list(OPENAI_COMPAT_PRESETS)
ui = UI()


def _make_event_handler():
    state = {"status": None}

    def handler(kind: str, data):
        if kind == "thinking_start":
            state["status"] = ui.thinking()
            state["status"].__enter__()
        elif kind == "thinking_stop":
            if state["status"] is not None:
                state["status"].__exit__(None, None, None)
                state["status"] = None
        elif kind == "assistant":
            ui.assistant(data)
        elif kind == "tool_call":
            ui.tool_call(data["name"], data["input"])
        elif kind == "tool_result":
            ui.tool_result(data["name"], data["output"], path=data.get("path"))
        elif kind == "plan":
            ui.plan(data)
        elif kind == "remember":
            ui.remembered(data)

    return handler


def _confirm(command: str, reason: str) -> bool:
    # Pausar el spinner si estuviera activo lo maneja el flujo (no corre en paralelo).
    return ui.confirm_danger(command, reason)


def cmd_config(argv: list[str]) -> int:
    if not argv:
        argv = ["list"]
    sub = argv[0]

    if sub == "list":
        provs = config.list_providers()
        active = config.load().get("active")
        if not provs:
            ui.warn("No hay proveedores configurados.")
            ui.info("Agrega uno con: devnexai config add <proveedor>")
            ui.info(f"Proveedores: {', '.join(ALL_PROVIDERS)}")
            ui.info("Para un modelo local sin internet: devnexai config local")
            return 0
        ui.providers_table(provs, active, config._mask)
        return 0

    if sub == "add":
        if len(argv) < 2:
            ui.error(f"Indica el proveedor: devnexai config add <{'/'.join(ALL_PROVIDERS)}>")
            return 1
        kind = argv[1].lower()
        if kind not in ALL_PROVIDERS:
            ui.error(f"Proveedor desconocido. Opciones: {', '.join(ALL_PROVIDERS)}")
            return 1
        ui.info(f"Configurando {kind}")
        local = kind in LOCAL_PRESETS
        if local:
            ui.info("Modelo local: la API key suele ser irrelevante (deja vacío o pon 'local').")
            key = input("  API key (enter = 'local'): ").strip() or "local"
        else:
            key = getpass.getpass("  API key (oculta): ").strip()
        if not key:
            ui.error("API key vacía, cancelado.")
            return 1
        model = input("  Modelo (enter = por defecto): ").strip() or None
        base = None
        if kind in OPENAI_COMPAT_PRESETS:
            default_base = OPENAI_COMPAT_PRESETS[kind]
            base = input(f"  Base URL (enter = {default_base}): ").strip() or None
        config.set_provider(kind, key, model, base)
        ui.ok(f"{kind} guardado y activado.")
        return 0

    if sub == "local":
        return _setup_local()

    if sub == "use":
        if len(argv) < 2 or not config.set_active(argv[1].lower()):
            ui.error("No se pudo activar. ¿Está configurado?")
            return 1
        ui.ok(f"Proveedor activo: {argv[1].lower()}")
        return 0

    if sub == "forget":
        memory.clear(Path.cwd())
        ui.ok("Memoria de este proyecto borrada.")
        return 0

    ui.error(f"Subcomando desconocido: {sub}")
    return 1


def _setup_local() -> int:
    ui.info("Asistente de modelo LOCAL (sin internet)")
    ui.info("Opciones: 1) Ollama   2) LM Studio")
    choice = input("  Elige [1/2]: ").strip()
    kind = "ollama" if choice == "1" else "lmstudio" if choice == "2" else None
    if kind is None:
        ui.error("Opción inválida.")
        return 1
    default_base = LOCAL_PRESETS[kind]
    ui.info(f"{kind} corre normalmente en {default_base}")
    base = input(f"  Base URL (enter = {default_base}): ").strip() or default_base
    model = input("  Nombre del modelo (ej. llama3, qwen2.5-coder): ").strip()
    if not model:
        ui.error("Debes indicar el nombre del modelo cargado localmente.")
        return 1
    config.set_provider(kind, "local", model, base)
    ui.ok(f"{kind} configurado con modelo '{model}'.")
    ui.info("Asegúrate de tener el servidor local corriendo antes de usarlo.")
    return 0


def _get_agent() -> Agent | None:
    active = config.get_active()
    if active is None:
        ui.error("No hay proveedor configurado.")
        ui.info("Ejecuta: devnexai config add <proveedor>")
        return None
    kind, entry = active
    try:
        provider = build_provider(kind, entry["api_key"], entry.get("model"), entry.get("base_url"))
    except ProviderError as e:
        ui.error(str(e))
        return None
    return Agent(provider, Path.cwd(), on_event=_make_event_handler(),
                 confirm=_confirm, use_memory=True)


def repl() -> int:
    active = config.get_active()
    kind = active[0] if active else "—"
    model = "(sin configurar)"
    if active:
        try:
            model = build_provider(kind, active[1]["api_key"],
                                   active[1].get("model"), active[1].get("base_url")).model
        except ProviderError:
            pass
    ui.banner(kind, model, Path.cwd())

    # Avisar si hay memoria previa
    mem = memory.load(Path.cwd())
    if mem.get("history"):
        ui.info(f"Memoria: {len(mem['history'])} turnos recordados de este proyecto. "
                f"(/olvidar para borrar)")

    agent = _get_agent()
    if agent is None:
        ui.warn("Configura un proveedor para empezar:")
        ui.info("  py -m devnexai config add anthropic")
        ui.info("  py -m devnexai config local   (para modelos sin internet)")
        return 1
    while True:
        try:
            line = ui.prompt().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/salir", "/exit", "/quit"):
            break
        if line == "/limpiar":
            agent.messages = agent.messages[:1]
            agent.plan = []
            ui.info("Contexto reiniciado.")
            continue
        if line == "/olvidar":
            memory.clear(Path.cwd())
            ui.info("Memoria del proyecto borrada.")
            continue
        if line == "/plan":
            if agent.plan:
                ui.plan(agent.plan)
            else:
                ui.info("No hay plan activo.")
            continue
        if line == "/modelo":
            ui.info(f"{agent.provider.name} · {agent.provider.model}")
            continue
        try:
            agent.run(line)
        except ProviderError as e:
            ui.error(f"Error del proveedor: {e}")
        except KeyboardInterrupt:
            ui.warn("Interrumpido.")
        print()
    ui.info("Hasta luego.")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "config":
        return cmd_config(argv[1:])
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv:
        agent = _get_agent()
        if agent is None:
            return 1
        agent.run(" ".join(argv))
        return 0
    return repl()


if __name__ == "__main__":
    sys.exit(main())
