"""When a room's cloud model fails: say so, keep what was in the air, fall back locally.

Destination: ``docs/design/model-awareness-and-fallback.md``.

Three things here are done by code rather than asked of a model, because a
model can omit them:

- the **notice** a practitioner sees on a fallback reply (``fallback_notice``);
- the **parked record** of what was in the air, written before the local model
  is asked anything (``park``), in the room's own practice root;
- the **hold**: after a *funds* or *access* failure the whole house answers on
  the local model and tries the cloud again only every ``CLOUD_RETRY_SECONDS``.

Also the house usage ledger (``record_usage``) — the cloud is a commons, and a
commons paid from a shared account has to be able to say what it cost.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from core.model_profiles import cost_usd, label_for

CLOUD_RETRY_SECONDS = float(os.environ.get("CLOUD_RETRY_SECONDS", 900))

FUNDS = "funds"
ACCESS = "access"
UNAVAILABLE = "unavailable"
HOLDING_KINDS = frozenset({FUNDS, ACCESS})

_REASON = {
    FUNDS: "the cloud credit balance is out",
    ACCESS: "the cloud key was refused",
    UNAVAILABLE: "the cloud service did not answer",
}


class CloudHeld(Exception):
    """Raised instead of calling the cloud while the house is on hold."""

    def __init__(self, hold: dict):
        super().__init__(hold.get("kind", FUNDS))
        self.hold = hold


def house_dir(*, create: bool = False) -> Path:
    override = os.environ.get("TURTLEOS_HOUSE_DIR")
    path = Path(override) if override else Path(__file__).resolve().parent / "house"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ─── classify ────────────────────────────────────────────────────


def classify(exc: BaseException) -> str:
    if isinstance(exc, CloudHeld):
        return exc.hold.get("kind", FUNDS)
    text = f"{type(exc).__name__}: {exc}".lower()
    status = getattr(exc, "status_code", None)
    if "credit balance" in text or "billing" in text or "purchase credits" in text:
        return FUNDS
    if status in (401, 403) or "authenticationerror" in text or "permissiondenied" in text:
        return ACCESS
    return UNAVAILABLE


# ─── hold ────────────────────────────────────────────────────────


def _hold_path() -> Path:
    return house_dir() / "cloud_hold.json"


def read_hold() -> dict | None:
    try:
        return json.loads(_hold_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def note_failure(kind: str, model: str, exc: BaseException) -> dict | None:
    """Start or refresh the hold for a holding failure. Transient failures do not hold."""
    if kind not in HOLDING_KINDS:
        return None
    existing = read_hold() or {}
    hold = {
        "kind": kind,
        "model": model,
        "since": existing.get("since") or _now_iso(),
        "last_try": time.time(),
        "detail": f"{type(exc).__name__}: {exc}"[:300],
    }
    house_dir(create=True)
    _hold_path().write_text(json.dumps(hold, indent=2) + "\n", encoding="utf-8")
    return hold


def clear_hold() -> bool:
    try:
        _hold_path().unlink()
        return True
    except FileNotFoundError:
        return False


def should_try_cloud(hold: dict | None, now: float | None = None) -> bool:
    if not hold:
        return True
    now = time.time() if now is None else now
    return now - float(hold.get("last_try", 0)) >= CLOUD_RETRY_SECONDS


def mark_tried(hold: dict) -> None:
    hold = dict(hold, last_try=time.time())
    _hold_path().write_text(json.dumps(hold, indent=2) + "\n", encoding="utf-8")


async def probe_hold(ask) -> str | None:
    """While the house is on hold, try the cloud once per retry interval with ``ask(model)``.

    Without this the hold lifted only when someone spoke in a cloud room, so
    credit bought at night stayed unused until morning (09-27).
    Returns a line to report when the hold lifts.
    """
    hold = read_hold()
    if not hold or not should_try_cloud(hold):
        return None
    model = str(hold.get("model") or "")
    if not model.startswith("claude"):
        return None
    try:
        await ask(model)
    except Exception as exc:
        kind = classify(exc)
        if kind in HOLDING_KINDS:
            note_failure(kind, model, exc)
        else:
            mark_tried(hold)
        return None
    clear_hold()
    return f"Cloud is back — {label_for(model)} answered; rooms use it again."


# ─── park ────────────────────────────────────────────────────────


def _parked_dir(pd: str | os.PathLike) -> Path:
    return Path(pd) / "state" / "parked"


def park(
    pd: str | os.PathLike,
    *,
    channel_id: int | str,
    room: str,
    author: str,
    message_text: str,
    cloud_model: str,
    kind: str,
    partial_prose: list[str] | None = None,
    tools_run: list[str] | None = None,
    held_turn: bool = False,
) -> Path:
    """Keep what was in the air. The practitioner's words verbatim; written before any local call."""
    if not Path(pd).is_dir():
        raise FileNotFoundError(f"practice root is not a directory: {pd}")
    directory = _parked_dir(pd)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = directory / f"{stamp}-{channel_id}.md"
    n = 1
    while path.exists():
        n += 1
        path = directory / f"{stamp}-{channel_id}-{n}.md"
    lines = [
        "---",
        "status: parked",
        f"channel_id: {channel_id}",
        f"room: {json.dumps(room)}",
        f"author: {json.dumps(author)}",
        f"cloud_model: {cloud_model}",
        f"kind: {kind}",
        f"held_turn: {str(held_turn).lower()}",
        f"parked_at: {_now_iso()}",
        "---",
        "",
        "## What was asked",
        "",
        message_text or "(empty message)",
        "",
    ]
    if partial_prose:
        lines += ["## What the cloud model had written before it stopped", "", *partial_prose, ""]
    if tools_run:
        lines += ["## What it had looked up", "", *[f"- {t}" for t in tools_run], ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


_STATUS = re.compile(r"^status: (\w+)$", re.M)
_CHANNEL = re.compile(r"^channel_id: (\S+)$", re.M)


def parked_for(pd: str | os.PathLike, channel_id: int | str, status: str = "parked") -> list[Path]:
    directory = _parked_dir(pd)
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        st, ch = _STATUS.search(text), _CHANNEL.search(text)
        if st and ch and st.group(1) == status and ch.group(1) == str(channel_id):
            found.append(path)
    return found


def mark_surfaced(paths: list[Path]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        path.write_text(_STATUS.sub("status: surfaced", text, count=1), encoding="utf-8")


def first_ask(path: Path, limit: int = 120) -> str:
    text = path.read_text(encoding="utf-8")
    body = text.split("## What was asked", 1)[-1].strip().split("\n## ", 1)[0].strip()
    body = re.sub(r"\s+", " ", body)
    return body if len(body) <= limit else body[:limit].rsplit(" ", 1)[0] + " …"


# ─── what the practitioner sees ─────────────────────────────────


def fallback_notice(cloud_model: str, local_model: str, kind: str, *, parked: bool, since: str | None = None) -> str:
    reason = _REASON.get(kind, _REASON[UNAVAILABLE])
    head = f"-# ⚠️ {label_for(cloud_model)} is unavailable — {reason}"
    if since:
        head += f" (since {_local_hhmm(since)})"
    head += f". This reply is from {label_for(local_model)}."
    if parked:
        head += " What you asked is parked and will be picked up when the cloud model is back."
    return head


def return_notice(cloud_model: str, parked: list[Path]) -> str:
    line = f"-# ✅ Back on {label_for(cloud_model)}."
    if parked:
        line += f" {len(parked)} parked item(s) in this room — latest: “{first_ask(parked[-1])}”"
    return line


def _local_hhmm(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d.%m %H:%M")
    except ValueError:
        return iso


def parking_prompt(local_model: str, cloud_model: str, kind: str, message_text: str,
                   partial_prose: list[str], tools_run: list[str]) -> str:
    from core.model_profiles import awareness_block

    parts = [
        awareness_block(local_model, fallback_from=cloud_model),
        f"The cloud model stopped mid-turn: {_REASON.get(kind, _REASON[UNAVAILABLE])}. "
        "The practitioner's request has already been saved by the system.",
        "Your job this turn, in a few sentences and in their language: say plainly that you "
        "are the local model standing in; restate in one or two lines what was in the air, so "
        "they can see it was caught; say it is kept safe and will be picked up when the cloud "
        "model is back. Do not attempt work that needs the stronger model. Do not apologise at length.",
        "",
        "## What was asked",
        message_text or "(empty)",
    ]
    if partial_prose:
        parts += ["", "## What the cloud model had written before it stopped", *partial_prose]
    if tools_run:
        parts += ["", "## What it had looked up", ", ".join(tools_run)]
    return "\n".join(parts) + "\n"


# ─── usage ledger ────────────────────────────────────────────────


def record_usage(
    *, channel_id: int | str, room: str, model: str, usage: dict, eddy: str | None = None
) -> float | None:
    """Append one turn's cloud usage to the house ledger. Returns the cost, or None if unpriced."""
    if not usage or not usage.get("calls"):
        return None
    cost = cost_usd(model, usage)
    row = {
        "ts": _now_iso(),
        "channel_id": str(channel_id),
        "room": room,
        "eddy": eddy,
        "model": model,
        **{k: usage.get(k, 0) for k in (
            "input_tokens", "output_tokens",
            "cache_creation_input_tokens", "cache_read_input_tokens", "calls",
        )},
        "usd": cost,
    }
    with open(house_dir(create=True) / "usage.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return cost
