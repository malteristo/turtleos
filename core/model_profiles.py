"""What each model is, what it costs, and what practice it suits.

Turtle reads the ``suits`` / ``not_for`` lines about the model actually
answering (``awareness_block``), so it can say what kind of practice is possible
right now. Prices are Anthropic standard API rates in USD per million tokens,
checked 2026-09-26; a model with no row gets ``None`` for cost, never a guess.

``tests/test_model_profiles.py`` fails when a model named in ``core/models.py``
has no profile here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProfile:
    model: str
    label: str
    backend: str  # "local" | "cloud"
    tier: str  # "frontier" | "local-capable" | "local-fast"
    suits: str
    not_for: str
    input_per_mtok: float | None = None
    output_per_mtok: float | None = None
    cache_write_per_mtok: float | None = None
    cache_read_per_mtok: float | None = None


_FRONTIER_SUITS = (
    "reading and changing code, long analysis across many files, design work, "
    "careful reasoning over the whole context"
)
_LOCAL_SUITS = (
    "conversation, reflection, remembering this room, short lookups, "
    "keeping things safe until a stronger model is available"
)
_LOCAL_NOT_FOR = (
    "changing code, long multi-step analysis, anything that must be exactly right "
    "across many files — say so and park it rather than attempt it"
)

PROFILES: dict[str, ModelProfile] = {
    p.model: p
    for p in [
        ModelProfile("claude-opus-5-5", "Claude Opus 5.5", "cloud", "frontier",
                     _FRONTIER_SUITS, "nothing in particular; it costs the most per turn",
                     4.0, 20.0, 5.0, 0.20),
        ModelProfile("claude-sonnet-5", "Claude Sonnet 5", "cloud", "frontier",
                     _FRONTIER_SUITS, "the hardest long-horizon work, where Opus is stronger",
                     2.0, 10.0, 2.50, 0.20),
        ModelProfile("claude-sonnet-4-6", "Claude Sonnet 4.6", "cloud", "frontier",
                     _FRONTIER_SUITS, "the hardest long-horizon work, where Opus is stronger",
                     3.0, 15.0, 3.75, 0.30),
        ModelProfile("gemini-2.5-flash", "Gemini 2.5 Flash", "cloud", "frontier",
                     "fast reading of images and documents, quick answers",
                     "careful code changes"),
        ModelProfile("gemini-2.5-pro", "Gemini 2.5 Pro", "cloud", "frontier",
                     _FRONTIER_SUITS, "nothing in particular"),
        ModelProfile("gemma4:31b", "Gemma 4 31B (local)", "local", "local-capable",
                     _LOCAL_SUITS, _LOCAL_NOT_FOR),
        ModelProfile("gemma4:26b", "Gemma 4 26B (local)", "local", "local-capable",
                     _LOCAL_SUITS, _LOCAL_NOT_FOR),
        ModelProfile("gemma4:12b", "Gemma 4 12B (local)", "local", "local-capable",
                     _LOCAL_SUITS, _LOCAL_NOT_FOR),
        ModelProfile("qwen3.6:35b-a3b", "Qwen 3.6 35B (local)", "local", "local-capable",
                     _LOCAL_SUITS, _LOCAL_NOT_FOR),
        ModelProfile("qwen3.5:27b", "Qwen 3.5 27B (local)", "local", "local-capable",
                     "reflection and summaries in the background", _LOCAL_NOT_FOR),
        ModelProfile("qwen3.5:9b", "Qwen 3.5 9B (local)", "local", "local-fast",
                     "naming, sorting and short summaries in the background",
                     "conversation with a practitioner"),
        ModelProfile("qwen3.5:4b", "Qwen 3.5 4B (local)", "local", "local-fast",
                     "River acts and quick structured decisions",
                     "conversation with a practitioner"),
        ModelProfile("qwen3.5:0.8b", "Qwen 3.5 0.8B (local)", "local", "local-fast",
                     "message triage", "anything a practitioner reads"),
    ]
}


def profile_for(model: str | None) -> ModelProfile | None:
    return PROFILES.get(model or "")


def label_for(model: str | None) -> str:
    profile = profile_for(model)
    return profile.label if profile else (model or "unknown model")


def is_cloud(model: str | None) -> bool:
    profile = profile_for(model)
    if profile:
        return profile.backend == "cloud"
    return bool(model) and str(model).startswith(("claude-", "gemini-"))


def cost_usd(model: str | None, usage: dict) -> float | None:
    """Cost of one turn's usage. ``None`` when the model has no price on record."""
    profile = profile_for(model)
    if not profile or profile.input_per_mtok is None or profile.output_per_mtok is None:
        return None
    write_rate = profile.cache_write_per_mtok if profile.cache_write_per_mtok is not None else profile.input_per_mtok
    read_rate = profile.cache_read_per_mtok if profile.cache_read_per_mtok is not None else profile.input_per_mtok
    total = (
        usage.get("input_tokens", 0) * profile.input_per_mtok
        + usage.get("output_tokens", 0) * profile.output_per_mtok
        + usage.get("cache_creation_input_tokens", 0) * write_rate
        + usage.get("cache_read_input_tokens", 0) * read_rate
    ) / 1_000_000
    return round(total, 6)


def awareness_block(model: str | None, *, fallback_from: str | None = None) -> str:
    """The lines Turtle reads about the model answering this turn."""
    profile = profile_for(model)
    label = label_for(model)
    lines = ["## The model answering now"]
    if profile:
        where = "runs on this house's own hardware" if profile.backend == "local" else "is a cloud model the house pays for"
        lines.append(f"- You are **{label}**; it {where}.")
        lines.append(f"- Suited for: {profile.suits}.")
        lines.append(f"- Not for: {profile.not_for}.")
    else:
        lines.append(f"- You are **{label}**. No profile is on record for it; do not claim abilities you have not shown.")
    if fallback_from:
        lines.append(
            f"- **This room normally uses {label_for(fallback_from)}, which is unavailable.** "
            "You are the fallback. Never speak as that model. Ordinary conversation is fine; "
            "work that needs the stronger model is parked, not attempted — say so plainly."
        )
    return "\n".join(lines) + "\n\n"
