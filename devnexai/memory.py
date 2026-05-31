"""Memoria entre sesiones.

Guarda un resumen y los hechos relevantes de cada proyecto en
~/.devnexai/memory/<hash-del-proyecto>.json, de modo que al reabrir
DevNexAI en la misma carpeta recuerde el contexto previo.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .config import CONFIG_DIR

MEMORY_DIR = CONFIG_DIR / "memory"


def _key(root: Path) -> str:
    h = hashlib.sha1(str(root.resolve()).encode("utf-8")).hexdigest()[:16]
    return h


def _file(root: Path) -> Path:
    return MEMORY_DIR / f"{_key(root)}.json"


def load(root: Path) -> dict[str, Any]:
    f = _file(root)
    if not f.exists():
        return {"project": str(root.resolve()), "notes": [], "history": []}
    try:
        return json.loads(f.read_text())
    except (json.JSONDecodeError, OSError):
        return {"project": str(root.resolve()), "notes": [], "history": []}


def save(root: Path, data: dict[str, Any]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _file(root).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def add_turn(root: Path, user: str, summary: str) -> None:
    """Registra un turno (petición + resumen del resultado)."""
    data = load(root)
    data["history"].append({
        "t": time.strftime("%Y-%m-%d %H:%M"),
        "user": user[:500],
        "summary": summary[:1000],
    })
    # Conservamos solo los últimos 30 turnos para no crecer sin límite.
    data["history"] = data["history"][-30:]
    save(root, data)


def add_note(root: Path, note: str) -> None:
    data = load(root)
    if note not in data["notes"]:
        data["notes"].append(note)
        data["notes"] = data["notes"][-50:]
        save(root, data)


def context_block(root: Path, max_turns: int = 6) -> str:
    """Texto inyectable al system prompt con lo recordado del proyecto."""
    data = load(root)
    if not data["history"] and not data["notes"]:
        return ""
    lines = ["CONTEXTO RECORDADO DE SESIONES ANTERIORES EN ESTE PROYECTO:"]
    if data["notes"]:
        lines.append("Notas persistentes:")
        lines += [f"  - {n}" for n in data["notes"][-15:]]
    if data["history"]:
        lines.append("Turnos recientes:")
        for h in data["history"][-max_turns:]:
            lines.append(f"  [{h['t']}] Pidió: {h['user'][:120]}")
            lines.append(f"            Resultado: {h['summary'][:160]}")
    return "\n".join(lines)


def clear(root: Path) -> None:
    f = _file(root)
    if f.exists():
        f.unlink()
