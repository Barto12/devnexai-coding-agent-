"""Evaluación de riesgo de comandos de shell.

Clasifica un comando antes de ejecutarlo para que el agente pueda pedir
confirmación al usuario en operaciones potencialmente destructivas.
"""

from __future__ import annotations

import re

# Patrones considerados peligrosos. Cada entrada: (regex, motivo).
_DANGEROUS = [
    (r"\brm\s+-rf?\b", "borrado recursivo de archivos"),
    (r"\brm\s+.*-[a-z]*f", "borrado forzado"),
    (r"\brmdir\b", "eliminación de directorios"),
    (r"\bdel\s+/[sq]", "borrado masivo (Windows)"),
    (r"\bformat\b", "formateo de disco"),
    (r"\bmkfs\b", "creación de sistema de archivos"),
    (r"\bdd\s+if=", "escritura de disco a bajo nivel"),
    (r">\s*/dev/sd", "escritura directa a disco"),
    (r":\(\)\s*\{.*\}\s*;", "fork bomb"),
    (r"\bchmod\s+-R\b", "cambio recursivo de permisos"),
    (r"\bchown\s+-R\b", "cambio recursivo de propietario"),
    (r"\bgit\s+push\b.*--force", "push forzado a git"),
    (r"\bgit\s+reset\s+--hard", "reset destructivo de git"),
    (r"\bgit\s+clean\b", "limpieza de archivos no rastreados"),
    (r"\bsudo\b", "ejecución con privilegios de superusuario"),
    (r"\bcurl\b.*\|\s*(ba)?sh", "descarga y ejecución de script remoto"),
    (r"\bwget\b.*\|\s*(ba)?sh", "descarga y ejecución de script remoto"),
    (r"\bshutdown\b", "apagado del sistema"),
    (r"\breboot\b", "reinicio del sistema"),
    (r"\bkillall\b", "terminación masiva de procesos"),
    (r"\b>\s*/etc/", "modificación de configuración del sistema"),
    (r"\bpip\s+uninstall\b", "desinstalación de paquetes"),
    (r"\bnpm\s+publish\b", "publicación de paquete npm"),
    (r"\btruncate\b", "truncado de archivos"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), reason) for p, reason in _DANGEROUS]


def assess_command(command: str) -> str | None:
    """Devuelve el motivo de riesgo si el comando es peligroso, o None."""
    for rx, reason in _COMPILED:
        if rx.search(command):
            return reason
    return None


def is_write_tool(name: str) -> bool:
    return name in ("write_file", "edit_file")
