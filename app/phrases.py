"""Phrases loader with placeholder substitution."""

import json
from pathlib import Path
from typing import Any


_phrases: dict[str, Any] = {}


def load_phrases(path: Path | str = "phrases.json") -> None:
    """Load phrases from JSON file. Called once at bot startup."""
    global _phrases
    with open(path, "r", encoding="utf-8") as f:
        _phrases = json.load(f)


def get_question_text(num: int) -> str:
    """Get question text by number (1-4)."""
    return _phrases["questions"][f"q{num}"]["text"]


def get_question_label(num: int) -> str:
    """Get question short label by number (1-4)."""
    return _phrases["questions"][f"q{num}"]["label"]


def get_button(key: str) -> str:
    """Get button text by key."""
    return _phrases["buttons"][key]


def get_system(key: str, **kwargs: Any) -> str:
    """Get system message by key with optional placeholder substitution."""
    text = _phrases["system"][key]
    if kwargs:
        text = text.format(**kwargs)
    return text
