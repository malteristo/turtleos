"""Model routing — two-stack local architecture (TURTLE_SPEC §8.1).

River stack (Qwen):
  Fast local models for river acts, triage, reflection, delegate edits, and
  other background work. Optimized for classification and structured output, not
  conversational depth.

Turtle stack (Gemma):
  Capable local model for eddy dialogue. Native attunement routes all thread
  replies through TURTLE_MODEL unless ``!thread --model`` overrides.

API opt-in (optional):
  Set DIALOGUE_MODEL to ``claude-*`` or use ``!thread --model claude|gemini-*``
  for cloud dialogue. River stays local unless explicitly extended later.

Env vars:
  RIVER_MODEL, TURTLE_MODEL — primary two-stack knobs
  DIALOGUE_MODEL — magic-attuned main channel + legacy ``local`` alias target;
                   defaults to TURTLE_MODEL when unset
  TRIAGE_MODEL, REFLECTION_MODEL, EDIT_DELEGATE_MODEL — Qwen background stack
"""

from __future__ import annotations

import os
from typing import TypedDict


class ModelSlot(TypedDict):
    model: str
    backend: str
    role: str


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# Primary stack (instance defaults — not platform law; see TURTLE_SPEC §5.7, §7.4)
TURTLE_MODEL = _env("TURTLE_MODEL", "gemma4:31b")
DIALOGUE_MODEL = _env("DIALOGUE_MODEL", TURTLE_MODEL)
RIVER_MODEL = _env("RIVER_MODEL", "qwen3.5:4b")
TRIAGE_MODEL = _env("TRIAGE_MODEL", "qwen3.5:0.8b")
REFLECTION_MODEL = _env("REFLECTION_MODEL", "qwen3.5:27b")
EDIT_DELEGATE_MODEL = _env("EDIT_DELEGATE_MODEL", "qwen3.5:4b")

# Aliases for !thread / panel model selection (None → DIALOGUE_MODEL)
KNOWN_MODELS: dict[str, str | None] = {
    "local": None,
    # API opt-in
    "claude": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
    "gemini-flash": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.5-pro",
    # River stack (fast local)
    "qwen": "qwen3.5:9b",
    "qwen-4b": "qwen3.5:4b",
    "qwen-27b": "qwen3.5:27b",
    # Turtle stack (capable local)
    "gemma": "gemma4:31b",
    "gemma-26b": "gemma4:26b",
    "gemma-31b": "gemma4:31b",
    "turtle": TURTLE_MODEL,
}


def dialogue_backend(use_api: bool) -> str:
    return "API" if use_api else "local"


def model_stack(use_api: bool) -> dict[str, ModelSlot]:
    """Current model routing for status surfaces and operator logs."""
    return {
        "river": {
            "model": RIVER_MODEL,
            "backend": "local",
            "role": "River acts",
        },
        "turtle": {
            "model": TURTLE_MODEL,
            "backend": "local",
            "role": "Eddy dialogue",
        },
        "dialogue": {
            "model": DIALOGUE_MODEL,
            "backend": dialogue_backend(use_api),
            "role": "Magic-attuned main / local alias",
        },
        "triage": {
            "model": TRIAGE_MODEL,
            "backend": "local",
            "role": "Message triage",
        },
        "reflection": {
            "model": REFLECTION_MODEL,
            "backend": "local",
            "role": "Session reflection & health",
        },
        "delegate": {
            "model": EDIT_DELEGATE_MODEL,
            "backend": "local",
            "role": "Delegate file edits",
        },
    }


def format_stack_line(key: str, slot: ModelSlot) -> str:
    return f"{slot['role']}: `{slot['model']}` ({slot['backend']})"
