"""Continuity Engine — Slice 0: the current layer.

Shell infrastructure (not a model) that makes Turtle *conscious of* present
context: it writes ``state/current.yaml`` under the practice root and renders a
hidden, shell-injected block so Turtle knows roughly when it is and what it runs
on — without the practitioner having to say so each eddy.

Slice 0 scope (``docs/design/continuity-engine-and-substrate.md`` §11):
  - Compose + persist the current layer: clock, timezone, day-part, season,
    host label, inference locality, dialogue + river model ids.
  - Render a plain-language block for the shell to inject into eddy dialogue.
  - Acceptance: Turtle answers "what day is it?" without being told (§12.1).

Design stances honored here:
  - **Hardware honesty (§3.2.3):** identity is read live from the running
    process — the resolved dialogue model for *this* turn and the actual host —
    not a hard-coded config string that can drift from reality.
  - **Vocabulary firewall (§4):** the block uses plain language only; the
    river-ecology terms (bedrock/sediment/alive/current) never appear in it, so
    the model never learns to echo internal jargon back to the practitioner.
  - **Invisible, not opaque (§3.5):** the block is background context, hidden
    from the channel by default, and cheap to inspect via this module's CLI.

Not in Slice 0 (Slice 1+): the alive layer (active threads), scope/narrowing,
sediment, and the last-checkpoint one-liner.
"""

from __future__ import annotations

import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - deployed turtleOS has PyYAML
    yaml = None

CURRENT_SCHEMA_VERSION = 1
DEFAULT_STALE_MINUTES = 15


# ─── Derivations (pure) ──────────────────────────────────────────────


def _day_part(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def _season(month: int, southern: bool = False) -> str:
    """Meteorological season. Northern hemisphere by default; flip for southern."""
    northern = {
        12: "winter", 1: "winter", 2: "winter",
        3: "spring", 4: "spring", 5: "spring",
        6: "summer", 7: "summer", 8: "summer",
        9: "autumn", 10: "autumn", 11: "autumn",
    }
    season = northern[month]
    if southern:
        flip = {"winter": "summer", "summer": "winter",
                "spring": "autumn", "autumn": "spring"}
        season = flip[season]
    return season


def _inference_locality(dialogue_model: str, use_api: bool) -> str:
    if use_api:
        return "cloud"
    if dialogue_model.startswith("claude") or dialogue_model.startswith("gemini"):
        return "cloud"
    return "local"


def _host_label() -> str:
    """Live-read the running machine. ``CE_HOST_LABEL`` overrides with a friendly
    name (e.g. "Mac Mini M4 Pro"); otherwise the label reflects the actual host,
    never a hard-coded string that could lie about where Turtle is running."""
    override = os.environ.get("CE_HOST_LABEL", "").strip()
    if override:
        return override
    node = platform.node() or "unknown-host"
    tail = " ".join(p for p in (platform.system(), platform.machine()) if p)
    return f"{node} ({tail})" if tail else node


def _river_model_default() -> str:
    try:
        from models import RIVER_MODEL

        return RIVER_MODEL
    except Exception:
        return os.environ.get("RIVER_MODEL", "")


# ─── Compose (pure — no file I/O) ────────────────────────────────────


def compose_current(
    *,
    dialogue_model: str | None = None,
    river_model: str | None = None,
    use_api: bool = False,
    host_label: str | None = None,
    now: datetime | None = None,
    southern_hemisphere: bool | None = None,
) -> dict[str, Any]:
    """Compose the current-layer dict from live signals.

    ``dialogue_model`` should be the model that will actually answer this turn
    (the shell resolves it per-eddy), so the substrate reflects reality rather
    than a static default.
    """
    now = now or datetime.now().astimezone()
    tzname = getattr(now.tzinfo, "key", None) or now.tzname() or "local"
    dm = dialogue_model if dialogue_model is not None else os.environ.get("TURTLE_MODEL", "")
    rm = river_model if river_model is not None else _river_model_default()
    if southern_hemisphere is None:
        southern = os.environ.get("CE_SOUTHERN_HEMISPHERE", "").strip().lower() in (
            "1", "true", "yes",
        )
    else:
        southern = bool(southern_hemisphere)

    return {
        "version": CURRENT_SCHEMA_VERSION,
        "updated_at": now.isoformat(timespec="seconds"),
        "local": {
            "timezone": tzname,
            "weekday": now.strftime("%A"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "day_part": _day_part(now.hour),
            "season": _season(now.month, southern=southern),
        },
        "machine": {
            "host_label": host_label or _host_label(),
            "inference": _inference_locality(dm, use_api),
            "dialogue_model": dm,
            "river_model": rm,
        },
        # Slice 1+ fields (scope, alive headers, last-checkpoint one-liner) are
        # intentionally absent in Slice 0.
        "scope": None,
    }


def render_current_block(data: dict[str, Any]) -> str:
    """Render the plain-language shell-inject block (vocabulary firewall §4).

    Mirrors the design's prose example (§7.1): a labelled, non-practitioner
    block with a when-line and a machine-line, plus a one-line conduct nudge.
    """
    local = data.get("local", {})
    machine = data.get("machine", {})

    when = " ".join(p for p in (local.get("weekday", ""), local.get("day_part", "")) if p)
    when = when or "now"
    date = local.get("date", "")
    tz = local.get("timezone", "")
    season = local.get("season", "")

    when_line = when
    if date:
        when_line += f", {date}"
    if tz:
        when_line += f" ({tz})"
    if season:
        when_line += f" · {season}"

    dm = machine.get("dialogue_model", "")
    host = machine.get("host_label", "")
    locality = "Local" if machine.get("inference") == "local" else "Cloud"
    run_line = f"{locality} inference"
    if dm:
        run_line += f": {dm}"
    if host:
        run_line += f" on {host}"

    return (
        "[Practice substrate — shell-injected, not a practitioner message]\n"
        f"{when_line}. {run_line}.\n"
        "Stay oriented in time and place; surface these only when they serve "
        "the reply, never as a recital.\n\n"
    )


# ─── Persistence (best-effort) ───────────────────────────────────────


def current_yaml_path(practice_dir: str | os.PathLike) -> Path:
    return Path(practice_dir) / "state" / "current.yaml"


def write_current(practice_dir: str | os.PathLike, data: dict[str, Any]) -> Path:
    if yaml is None:
        raise RuntimeError("PyYAML is required to write current.yaml")
    path = current_yaml_path(practice_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def read_current(practice_dir: str | os.PathLike) -> dict[str, Any] | None:
    path = current_yaml_path(practice_dir)
    if not path.exists() or yaml is None:
        return None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def _age_minutes(data: dict[str, Any] | None, now: datetime | None = None) -> float | None:
    ts = (data or {}).get("updated_at")
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    now = now or datetime.now().astimezone()
    if parsed.tzinfo is None:
        now = now.replace(tzinfo=None)
    return (now - parsed).total_seconds() / 60.0


def is_stale(
    data: dict[str, Any] | None,
    max_age_minutes: float = DEFAULT_STALE_MINUTES,
    now: datetime | None = None,
) -> bool:
    age = _age_minutes(data, now=now)
    return age is None or age >= max_age_minutes


# ─── Shell entry point ───────────────────────────────────────────────


def refresh_and_render(
    practice_dir: str | os.PathLike,
    *,
    dialogue_model: str | None = None,
    river_model: str | None = None,
    use_api: bool = False,
    host_label: str | None = None,
    stale_minutes: float = DEFAULT_STALE_MINUTES,
) -> str:
    """Compose fresh current data, persist it when missing/stale, return the
    shell-inject block.

    The returned block is always freshly composed, so injected time is always
    accurate; the on-disk file write is debounced (only when missing or older
    than ``stale_minutes``) to avoid churn on every dialogue turn (design §8:
    "re-compose current if stale >15 min").
    """
    data = compose_current(
        dialogue_model=dialogue_model,
        river_model=river_model,
        use_api=use_api,
        host_label=host_label,
    )
    try:
        existing = read_current(practice_dir)
        if existing is None or is_stale(existing, max_age_minutes=stale_minutes):
            write_current(practice_dir, data)
    except Exception as exc:  # persistence is best-effort; the inject still works
        print(f"CE current.yaml write skipped: {type(exc).__name__}: {exc}")
    return render_current_block(data)


def _main(argv: list[str]) -> int:
    practice_dir = argv[1] if len(argv) > 1 else os.environ.get("PRACTICE_DIR", ".")
    data = compose_current()
    if yaml is not None:
        print("# composed current.yaml:")
        print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    print("# rendered inject block:")
    print(render_current_block(data))
    if "--write" in argv[2:]:
        print(f"# wrote {write_current(practice_dir, data)}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
