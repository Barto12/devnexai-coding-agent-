"""Herramientas que el agente puede invocar sobre el sistema de archivos
y la shell. Diseñadas para trabajar dentro de un directorio de proyecto.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

ToolFn = Callable[[dict, Path], str]


def _safe(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        raise ValueError(f"Ruta fuera del proyecto: {rel}")
    return p


def read_file(args: dict, root: Path) -> str:
    p = _safe(root, args["path"])
    if not p.exists():
        return f"ERROR: no existe {args['path']}"
    text = p.read_text(errors="replace")
    lines = text.splitlines()
    return "\n".join(f"{i+1}\t{l}" for i, l in enumerate(lines))


def write_file(args: dict, root: Path) -> str:
    p = _safe(root, args["path"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(args["content"])
    return f"OK: escrito {args['path']} ({len(args['content'])} bytes)"


def edit_file(args: dict, root: Path) -> str:
    p = _safe(root, args["path"])
    if not p.exists():
        return f"ERROR: no existe {args['path']}"
    text = p.read_text()
    old, new = args["old_str"], args["new_str"]
    if text.count(old) != 1:
        return f"ERROR: 'old_str' aparece {text.count(old)} veces (debe ser 1)"
    p.write_text(text.replace(old, new))
    return f"OK: editado {args['path']}"


def list_dir(args: dict, root: Path) -> str:
    p = _safe(root, args.get("path", "."))
    if not p.exists():
        return f"ERROR: no existe {args.get('path', '.')}"
    out = []
    for item in sorted(p.iterdir()):
        if item.name.startswith("."):
            continue
        out.append(item.name + ("/" if item.is_dir() else ""))
    return "\n".join(out) or "(vacío)"


def run_bash(args: dict, root: Path) -> str:
    try:
        r = subprocess.run(
            args["command"], shell=True, cwd=root,
            capture_output=True, text=True, timeout=args.get("timeout", 60),
        )
        out = (r.stdout or "") + (r.stderr or "")
        return f"[exit {r.returncode}]\n{out[:8000]}"
    except subprocess.TimeoutExpired:
        return "ERROR: timeout"


REGISTRY: dict[str, ToolFn] = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_dir": list_dir,
    "run_bash": run_bash,
}

SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Lee un archivo del proyecto y devuelve su contenido numerado por líneas.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Ruta relativa al proyecto"}},
            "required": ["path"]},
    },
    {
        "name": "write_file",
        "description": "Crea o sobrescribe un archivo con el contenido dado.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"]},
    },
    {
        "name": "edit_file",
        "description": "Reemplaza una única ocurrencia de old_str por new_str en un archivo.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"}},
            "required": ["path", "old_str", "new_str"]},
    },
    {
        "name": "list_dir",
        "description": "Lista archivos y carpetas de un directorio del proyecto.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Ruta relativa (por defecto raíz)"}},
            "required": []},
    },
    {
        "name": "run_bash",
        "description": "Ejecuta un comando de shell dentro del proyecto. Úsalo para tests, git, instalar deps, etc.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}, "timeout": {"type": "integer"}},
            "required": ["command"]},
    },
]
