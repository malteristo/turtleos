"""Model routing — two-stack local architecture (TURTLE_SPEC §8.1).

River stack (Qwen):
  Fast local models for river acts, triage, reflection, delegate edits, and
  other background work. Optimized for classification and structured output, not
  conversational depth.

Turtle stack (Gemma):
  Capable local model for eddy dialogue. Native attunement routes all thread
  replies through TURTLE_MODEL unless the channel's own model pick (``!model``) overrides.

API opt-in (optional):
  Set DIALOGUE_MODEL to ``claude-*`` or pick one with ``!model``
  for cloud dialogue. River stays local unless explicitly extended later.
  Every channel's conversation default is TURTLE_MODEL (Gemma). Another model
  answers only after an explicit per-channel pick. CRAFT_MODEL is not that
  default — an env value there used to put craft on Sonnet with no pick.

Env vars:
  RIVER_MODEL, TURTLE_MODEL — primary two-stack knobs
  DIALOGUE_MODEL — magic-attuned main channel + legacy ``local`` alias target;
                   defaults to TURTLE_MODEL when unset
  CRAFT_MODEL — retired as a conversation default; not read by routing
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
# Install Lighter path — ~16 GB RAM. Not a runtime default.
LIGHTER_TURTLE_MODEL = "gemma4:12b"
DIALOGUE_MODEL = _env("DIALOGUE_MODEL", TURTLE_MODEL)
# Not the conversation default. Kept so an old env file still imports.
# Routing uses conversation_model(); a channel leaves Gemma only by a pick.
CRAFT_MODEL = _env("CRAFT_MODEL", "claude-sonnet-5")
# Official qwen3.8 on Ollama is 27B only (tag list checked 2026-10-06).
# River has to stay small enough to sit beside Gemma. There is no 3.8 tag in that size.
RIVER_MODEL = _env("RIVER_MODEL", "qwen3.5:4b")
TRIAGE_MODEL = _env("TRIAGE_MODEL", "qwen3.5:0.8b")
REFLECTION_MODEL = _env("REFLECTION_MODEL", "qwen3.8:27b")
EDIT_DELEGATE_MODEL = _env("EDIT_DELEGATE_MODEL", "qwen3.5:4b")

# Aliases for model selection (None → DIALOGUE_MODEL)
KNOWN_MODELS: dict[str, str | None] = {
    "local": None,
    # API opt-in
    "claude": "claude-sonnet-5",
    "sonnet": "claude-sonnet-5",
    "sonnet-5.5": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
    "gemini": "gemini-2.5-flash",
    "gemini-flash": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.5-pro",
    # River stack (fast local)
    "qwen": "qwen3.5:9b",
    "qwen-4b": "qwen3.5:4b",
    "qwen-27b": "qwen3.5:27b",
    # Turtle stack (capable local)
    "gemma": "gemma4:31b",
    "gemma-12b": LIGHTER_TURTLE_MODEL,
    "gemma-26b": "gemma4:26b",
    "gemma-31b": "gemma4:31b",
    "turtle": TURTLE_MODEL,
}


def conversation_model() -> str:
    """The model a channel speaks with until someone picks another.

    One default for every room, including craft. ``CRAFT_MODEL`` is not read.
    """
    return TURTLE_MODEL


def anthropic_request_extras(model: str) -> dict:
    """Messages fields added for one model. No sampling parameters.

    Sonnet 5.5 thinks up front unless told ``between_tools``, and it rejects
    ``thinking: disabled`` and a non-default temperature. Other models get
    nothing here — Sonnet 5 already accepts an omitted thinking field.
    """
    if model == "claude-sonnet-5-5":
        return {"thinking": {"type": "between_tools"}}
    return {}


def lists_in_menu(model: str) -> bool:
    """A menu row exists only when the request we would send can show its prose."""
    extras = anthropic_request_extras(model)
    if "temperature" in extras:
        return False
    if model == "claude-sonnet-5-5":
        thinking = extras.get("thinking") or {}
        return thinking.get("type") == "between_tools"
    return True


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
        "craft": {
            "model": conversation_model(),
            "backend": "local",
            "role": "Eddy dialogue until a channel picks",
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
