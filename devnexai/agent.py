"""Loop agéntico de DevNexAI con planificación, confirmación de comandos
peligrosos y memoria entre sesiones.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import memory
from .providers import BaseProvider, LLMResponse
from .safety import assess_command, is_write_tool
from .tools import REGISTRY, SCHEMAS

SYSTEM_PROMPT = """Eres DevNexAI, un agente de codificación autónomo que opera \
en la terminal del usuario, similar a Claude Code. Trabajas dentro del directorio \
del proyecto actual.

Capacidades:
- Lees y escribes archivos, editas con precisión y ejecutas comandos de shell.
- Mantienes un plan de subtareas con la herramienta update_plan.
- Guardas hechos importantes del proyecto con la herramienta remember.

Flujo de trabajo:
1. Para tareas no triviales, primero llama a update_plan con la lista de pasos.
2. Ejecuta los pasos uno a uno usando las herramientas; marca el avance del plan.
3. Verifica tu trabajo (corre tests, lints) antes de declarar algo terminado.
4. Si descubres algo que conviene recordar a futuro (estructura del proyecto,
   comandos de build, convenciones), guárdalo con remember.

Reglas:
- Usa rutas relativas al proyecto.
- Antes de editar un archivo, léelo. Antes de afirmar que funciona, verifícalo.
- Sé conciso; el trabajo real lo haces con herramientas.
- Al terminar, responde con un resumen breve sin más llamadas a herramientas.
"""

MAX_STEPS = 50

# Herramientas internas del agente (no tocan el filesystem directamente).
PLANNING_SCHEMAS = [
    {
        "name": "update_plan",
        "description": "Crea o actualiza el plan de subtareas. Envía la lista completa "
                       "de pasos con su estado cada vez.",
        "parameters": {"type": "object", "properties": {
            "steps": {"type": "array", "items": {"type": "object", "properties": {
                "task": {"type": "string"},
                "status": {"type": "string", "enum": ["pendiente", "en_progreso", "hecho"]},
            }, "required": ["task", "status"]}}},
            "required": ["steps"]},
    },
    {
        "name": "remember",
        "description": "Guarda un hecho importante del proyecto para recordarlo en "
                       "sesiones futuras (estructura, comandos de build, convenciones).",
        "parameters": {"type": "object", "properties": {
            "note": {"type": "string"}}, "required": ["note"]},
    },
]


class Agent:
    def __init__(self, provider: BaseProvider, root: Path, on_event=None,
                 confirm=None, use_memory=True):
        self.provider = provider
        self.root = root
        self.on_event = on_event or (lambda *a, **k: None)
        # confirm(command, reason) -> bool. Si None, todo se permite.
        self.confirm = confirm or (lambda *a, **k: True)
        self.use_memory = use_memory
        self.plan: list[dict] = []

        system = SYSTEM_PROMPT
        if use_memory:
            ctx = memory.context_block(root)
            if ctx:
                system += "\n\n" + ctx
        self.messages: list[dict] = [{"role": "system", "content": system}]

    def _emit(self, kind: str, data):
        self.on_event(kind, data)

    @property
    def _all_schemas(self):
        return SCHEMAS + PLANNING_SCHEMAS

    # ---------- ejecución de herramientas ----------
    def _exec_one(self, name: str, args: dict) -> str:
        # Herramientas internas
        if name == "update_plan":
            self.plan = args.get("steps", [])
            self._emit("plan", self.plan)
            return "Plan actualizado."
        if name == "remember":
            if self.use_memory:
                memory.add_note(self.root, args["note"])
            self._emit("remember", args["note"])
            return "Nota guardada."

        # Confirmación de comandos peligrosos
        if name == "run_bash":
            reason = assess_command(args.get("command", ""))
            if reason and not self.confirm(args["command"], reason):
                return f"CANCELADO POR EL USUARIO: el comando se consideró peligroso ({reason})."
        if is_write_tool(name):
            # Escrituras se permiten pero se notifican; podría pedirse confirmación
            # si se desea ser más estricto (no por defecto).
            pass

        fn = REGISTRY.get(name)
        if fn is None:
            return f"ERROR: herramienta desconocida {name}"
        try:
            return fn(args, self.root)
        except Exception as e:  # noqa: BLE001
            return f"ERROR: {e}"

    def _run_tools(self, calls: list[dict]) -> None:
        results = []
        for call in calls:
            name, args = call["name"], call["input"]
            self._emit("tool_call", {"name": name, "input": args})
            out = self._exec_one(name, args)
            self._emit("tool_result", {"name": name, "output": out, "path": args.get("path")})
            results.append((call, out))

        if self.provider.name == "anthropic":
            self.messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": c["id"], "content": o}
                for c, o in results
            ]})
        else:
            joined = "\n\n".join(f"[{c['name']}] →\n{o}" for c, o in results)
            self.messages.append({"role": "user", "content": "Resultados de herramientas:\n" + joined})

    def _append_assistant(self, resp: LLMResponse) -> None:
        if self.provider.name == "anthropic" and resp.raw:
            self.messages.append({"role": "assistant", "content": resp.raw["content"]})
        else:
            content = resp.text
            if resp.tool_calls:
                content += "\n" + json.dumps(
                    [{"name": c["name"], "input": c["input"]} for c in resp.tool_calls],
                    ensure_ascii=False)
            self.messages.append({"role": "assistant", "content": content or "..."})

    def run(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})
        final = ""
        for _ in range(MAX_STEPS):
            self._emit("thinking_start", None)
            try:
                resp = self.provider.chat(self.messages, tools=self._all_schemas)
            finally:
                self._emit("thinking_stop", None)
            if resp.text:
                self._emit("assistant", resp.text)
                final = resp.text
            self._append_assistant(resp)
            if not resp.tool_calls:
                break
            self._run_tools(resp.tool_calls)

        if self.use_memory and final:
            memory.add_turn(self.root, user_input, final)
        return final
