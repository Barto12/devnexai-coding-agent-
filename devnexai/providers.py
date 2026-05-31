"""Capa de proveedores LLM para DevNexAI.

Cada proveedor implementa la misma interfaz `chat(messages, tools)` y normaliza
la respuesta a un formato común para que el agente sea agnóstico al LLM.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] | None = None


class ProviderError(Exception):
    pass


def _post(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        raise ProviderError(f"HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise ProviderError(f"Error de red: {e.reason}") from e


class BaseProvider:
    name = "base"

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        raise NotImplementedError


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    DEFAULT_MODEL = "claude-opus-4-8"

    def chat(self, messages, tools=None):
        url = (self.base_url or "https://api.anthropic.com") + "/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        system = ""
        conv = []
        for m in messages:
            if m["role"] == "system":
                system += m["content"] + "\n"
            else:
                conv.append(m)
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": conv,
        }
        if system:
            payload["system"] = system.strip()
        if tools:
            payload["tools"] = [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["parameters"],
                }
                for t in tools
            ]
        data = _post(url, headers, payload)
        text, calls = "", []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]
            elif block.get("type") == "tool_use":
                calls.append({"id": block["id"], "name": block["name"], "input": block["input"]})
        return LLMResponse(text=text, tool_calls=calls, raw=data)


class OpenAIProvider(BaseProvider):
    """Compatible con OpenAI y cualquier endpoint OpenAI-compatible
    (Groq, Together, OpenRouter, Ollama, LM Studio, DeepSeek, etc.)."""

    name = "openai"
    DEFAULT_MODEL = "gpt-4o"

    def chat(self, messages, tools=None):
        url = (self.base_url or "https://api.openai.com/v1") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = [
                {"type": "function", "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                }}
                for t in tools
            ]
        data = _post(url, headers, payload)
        msg = data["choices"][0]["message"]
        calls = []
        for tc in msg.get("tool_calls") or []:
            calls.append({
                "id": tc["id"],
                "name": tc["function"]["name"],
                "input": json.loads(tc["function"]["arguments"] or "{}"),
            })
        return LLMResponse(text=msg.get("content") or "", tool_calls=calls, raw=data)


class GeminiProvider(BaseProvider):
    name = "gemini"
    DEFAULT_MODEL = "gemini-2.0-flash"

    def chat(self, messages, tools=None):
        base = self.base_url or "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base}/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        contents, system = [], ""
        for m in messages:
            if m["role"] == "system":
                system += m["content"] + "\n"
                continue
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        payload: dict[str, Any] = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system.strip()}]}
        if tools:
            payload["tools"] = [{"functionDeclarations": [
                {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
                for t in tools
            ]}]
        data = _post(url, headers, payload)
        text, calls = "", []
        cand = (data.get("candidates") or [{}])[0]
        for part in cand.get("content", {}).get("parts", []):
            if "text" in part:
                text += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                calls.append({"id": fc["name"], "name": fc["name"], "input": fc.get("args", {})})
        return LLMResponse(text=text, tool_calls=calls, raw=data)


# Presets de endpoints OpenAI-compatibles populares (remotos, requieren internet)
OPENAI_COMPAT_PRESETS = {
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com",
    "together": "https://api.together.xyz/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "mistral": "https://api.mistral.ai/v1",
    "xai": "https://api.x.ai/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
}

# Subconjunto que corre localmente, SIN conexión a internet.
LOCAL_PRESETS = {
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
}

PROVIDERS: dict[str, type[BaseProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}


def build_provider(kind: str, api_key: str, model: str | None, base_url: str | None) -> BaseProvider:
    kind = kind.lower()
    if kind in OPENAI_COMPAT_PRESETS:
        base_url = base_url or OPENAI_COMPAT_PRESETS[kind]
        cls = OpenAIProvider
    elif kind in PROVIDERS:
        cls = PROVIDERS[kind]
    else:
        raise ProviderError(
            f"Proveedor desconocido: {kind}. "
            f"Opciones: {', '.join(list(PROVIDERS) + list(OPENAI_COMPAT_PRESETS))}"
        )
    model = model or cls.DEFAULT_MODEL
    return cls(api_key=api_key, model=model, base_url=base_url)
