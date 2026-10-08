"""Glossary helper (PRD 10.10)."""
from __future__ import annotations

import json
from functools import lru_cache

from config import GLOSSARY_PATH


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"terms": {}, "banned_metric_terms": []}


def terms() -> dict:
    return _load().get("terms", {})


def banned_terms() -> list[str]:
    return _load().get("banned_metric_terms", [])


def prompt_block(limit: int = 14) -> str:
    t = terms()
    items = list(t.items())[:limit]
    lines = [f"- {en} = {idn}" for en, idn in items]
    return "Glosarium istilah baku (gunakan istilah Indonesia ini):\n" + "\n".join(lines)


def find_banned(text: str) -> list[str]:
    low = (text or "").lower()
    return [w for w in banned_terms() if w in low]
