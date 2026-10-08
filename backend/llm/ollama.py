"""Ollama runtime client (PRD 10.11, 17).

* low temperature by default
* strips <think>...</think> from reasoning models (DeepSeek R1)
* optional JSON format for structured output
* graceful error object so the orchestrator can degrade instead of crashing
"""
from __future__ import annotations

import json
import re

import requests

from config import config

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_OPEN_THINK_RE = re.compile(r"<think>.*$", re.DOTALL | re.IGNORECASE)


def strip_think(text: str) -> str:
    if not text:
        return ""
    t = _THINK_RE.sub("", text)
    t = _OPEN_THINK_RE.sub("", t)  # unclosed <think>
    return t.strip()


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: int = 120):
        self.base_url = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            return [m.get("name", "") for m in r.json().get("models", [])]
        except requests.RequestException:
            return []

    def generate(self, model: str, prompt: str, system: str | None = None,
                 temperature: float | None = None, json_mode: bool = False,
                 num_ctx: int = 4096) -> dict:
        """Return {ok, text, raw, error}."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": config.LLM_TEMPERATURE if temperature is None else temperature,
                "num_ctx": num_ctx,
            },
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        try:
            r = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            r.raise_for_status()
            raw = r.json().get("response", "")
        except requests.RequestException as e:
            return {"ok": False, "text": "", "raw": "", "error": f"ollama error: {type(e).__name__}: {e}"}

        text = strip_think(raw)
        return {"ok": True, "text": text, "raw": raw, "error": None}

    def generate_json(self, model: str, prompt: str, system: str | None = None,
                      temperature: float | None = None, num_ctx: int = 4096) -> dict:
        """Generate and parse JSON. Return {ok, data, text, error}."""
        res = self.generate(model, prompt, system=system, temperature=temperature,
                             json_mode=True, num_ctx=num_ctx)
        if not res["ok"]:
            return {"ok": False, "data": None, "text": "", "error": res["error"]}
        text = res["text"]
        data = _extract_json(text)
        if data is None:
            return {"ok": False, "data": None, "text": text, "error": "gagal parse JSON dari model"}
        return {"ok": True, "data": data, "text": text, "error": None}


def _extract_json(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    # find first {...} or [...] block
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            snippet = text[start:end + 1]
            try:
                return json.loads(snippet)
            except (ValueError, TypeError):
                continue
    return None
