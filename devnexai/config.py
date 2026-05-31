"""Configuración persistente y manejo seguro de API keys.

Las keys se guardan en ~/.devnexai/config.json con permisos 0600.
También se leen desde variables de entorno como respaldo.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.path.expanduser("~")) / ".devnexai"
CONFIG_FILE = CONFIG_DIR / "config.json"

ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "together": "TOGETHER_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "xai": "XAI_API_KEY",
}


def _default() -> dict[str, Any]:
    return {"active": None, "providers": {}}


def load() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return _default()
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return _default()


def save(cfg: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    try:
        CONFIG_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass


def set_provider(kind: str, api_key: str, model: str | None = None,
                 base_url: str | None = None, make_active: bool = True) -> None:
    cfg = load()
    cfg["providers"][kind] = {"api_key": api_key, "model": model, "base_url": base_url}
    if make_active or cfg.get("active") is None:
        cfg["active"] = kind
    save(cfg)


def get_active() -> tuple[str, dict[str, Any]] | None:
    cfg = load()
    active = cfg.get("active")
    if active and active in cfg["providers"]:
        entry = dict(cfg["providers"][active])
        if not entry.get("api_key"):
            entry["api_key"] = os.environ.get(ENV_KEYS.get(active, ""), "")
        return active, entry
    # respaldo: variable de entorno
    for kind, env in ENV_KEYS.items():
        if os.environ.get(env):
            return kind, {"api_key": os.environ[env], "model": None, "base_url": None}
    return None


def set_active(kind: str) -> bool:
    cfg = load()
    if kind in cfg["providers"]:
        cfg["active"] = kind
        save(cfg)
        return True
    return False


def list_providers() -> dict[str, Any]:
    return load()["providers"]


def _mask(key: str) -> str:
    if not key:
        return "(vacía)"
    return key[:4] + "…" + key[-4:] if len(key) > 8 else "****"
