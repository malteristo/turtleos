"""Evening health check-in — opt-in per health instance, not a shared default.

A living ``record/checkin.json`` with ``enabled: true`` is the mechanism.
Missing or disabled means the instance stays quiet. Scores land as owner
testimony through ``save_observation``; they never enter git.

The prompt asks questions you can answer after reading them. Scale nouns
alone are not a prompt. Instances may replace the question list; the two
health roots never read each other.

``mode`` defaults to ``survey``. ``state`` is opt-in on that instance's
file: at the hour the room posts a short picture of today and asks whether
it is the current state. A day with no eddy notes asks one open question
and does not read older material. House stays on survey unless its own
file says otherwise.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from core.atomic_io import atomic_write_json


def _practice_root(practice_dir: str | Path) -> Path:
    """Registry paths are stored with ``~``; a literal read is a disabled instance."""
    return Path(practice_dir).expanduser()


CONFIG_NAME = "record/checkin.json"
STATE_NAME = "record/checkin_state.json"
DEFAULT_HOUR = 21
MODE_SURVEY = "survey"
MODE_STATE = "state"
_EMPTY_DRAFT = "(no response generated)"
STATE_ASK_DE = "Ist das dein aktueller Stand?"
STATE_ASK_EN = "Is this your current state?"
OPEN_STATE_DE = "Heute steht in diesem Raum nichts, woraus sich ein Stand lesen ließe."
OPEN_STATE_EN = "Nothing in this room today supports a picture of your state."
SCALES = ("interest", "decision", "surprise", "approach", "meaning")
SCALE_LABELS_DE = (
    "Interesse",
    "Entscheidung",
    "Überraschung",
    "Hinziehen",
    "Bedeutung",
)


@dataclass(frozen=True)
class CheckinQuestion:
    id: str
    de: str
    en: str


@dataclass(frozen=True)
class CheckinFlag:
    id: str
    aliases: tuple[str, ...]
    de: str
    en: str


DEFAULT_QUESTIONS: tuple[CheckinQuestion, ...] = (
    CheckinQuestion(
        "interest",
        "Wie viel Interesse hast du heute an dem gespürt, was vor dir lag?",
        "How much interest did you feel today in what was in front of you?",
    ),
    CheckinQuestion(
        "decision",
        "Wie leicht konntest du dich heute entscheiden?",
        "How easily could you decide today?",
    ),
    CheckinQuestion(
        "surprise",
        "Hat dich heute ein eigenes Gefühl überrascht?",
        "Were you surprised today by a feeling of your own?",
    ),
    CheckinQuestion(
        "approach",
        "Hat dich etwas hingezogen — nicht nur weggeschoben?",
        "Did anything pull you toward it — not only push you away?",
    ),
    CheckinQuestion(
        "meaning",
        "Hat irgendetwas heute Bedeutung gehabt — nicht nur weil du es für richtig hieltst?",
        "Did anything feel meaningful today — not only because you decided it was the right thing?",
    ),
)
DEFAULT_FLAGS: tuple[CheckinFlag, ...] = (
    CheckinFlag("cannabis", ("c", "cannabis"), "Cannabis heute?", "Cannabis today?"),
    CheckinFlag(
        "therapy", ("t", "therapie", "therapy"), "Therapie heute?", "Therapy today?"
    ),
)

_YES = frozenset({"ja", "yes", "y", "1", "true"})
_NO = frozenset({"nein", "no", "n", "0", "false"})
_SKIP = frozenset({"skip", "überspringen", "ueberspringen", "nicht heute", "later"})


@dataclass(frozen=True)
class CheckinConfig:
    enabled: bool
    hour: int
    locale: str
    questions: tuple[CheckinQuestion, ...] = DEFAULT_QUESTIONS
    flags: tuple[CheckinFlag, ...] = DEFAULT_FLAGS
    mode: str = MODE_SURVEY


@dataclass(frozen=True)
class CheckinEntry:
    scores: tuple[int, int, int, int, int]
    cannabis: bool | None
    therapy: bool | None


def load_config(practice_dir: str | Path) -> CheckinConfig:
    path = _practice_root(practice_dir) / CONFIG_NAME
    if not path.is_file():
        return CheckinConfig(enabled=False, hour=DEFAULT_HOUR, locale="de")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CheckinConfig(enabled=False, hour=DEFAULT_HOUR, locale="de")
    if not isinstance(raw, dict) or raw.get("enabled") is not True:
        return CheckinConfig(enabled=False, hour=DEFAULT_HOUR, locale="de")
    try:
        hour = int(raw.get("hour", DEFAULT_HOUR))
    except (TypeError, ValueError):
        hour = DEFAULT_HOUR
    hour = min(23, max(0, hour))
    locale = str(raw.get("locale") or "de").strip().lower()
    if locale not in ("de", "en"):
        locale = "de"
    questions = _load_questions(raw.get("questions"))
    flags = _load_flags(raw.get("flags"))
    return CheckinConfig(
        enabled=True,
        hour=hour,
        locale=locale,
        questions=questions,
        flags=flags,
        mode=_load_mode(raw.get("mode")),
    )


def _load_mode(raw: Any) -> str:
    value = str(raw or MODE_SURVEY).strip().lower()
    if value in (MODE_SURVEY, MODE_STATE):
        return value
    return MODE_SURVEY


def _load_questions(raw: Any) -> tuple[CheckinQuestion, ...]:
    if not isinstance(raw, list) or not raw:
        return DEFAULT_QUESTIONS
    loaded: list[CheckinQuestion] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("id") or "").strip()
        de = str(item.get("de") or "").strip()
        en = str(item.get("en") or de).strip()
        if qid and de:
            loaded.append(CheckinQuestion(qid, de, en or de))
    return tuple(loaded) if loaded else DEFAULT_QUESTIONS


def _load_flags(raw: Any) -> tuple[CheckinFlag, ...]:
    if raw is None:
        return DEFAULT_FLAGS
    if not isinstance(raw, list):
        return DEFAULT_FLAGS
    loaded: list[CheckinFlag] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fid = str(item.get("id") or "").strip()
        de = str(item.get("de") or "").strip()
        en = str(item.get("en") or de).strip()
        aliases_raw = item.get("aliases") or [fid]
        aliases = tuple(
            str(a).strip().lower() for a in aliases_raw if str(a).strip()
        )
        if fid and de and aliases:
            loaded.append(CheckinFlag(fid, aliases, de, en or de))
    return tuple(loaded)


def write_enabled_config(practice_dir: str | Path, *, hour: int = DEFAULT_HOUR, locale: str = "de") -> Path:
    path = _practice_root(practice_dir) / CONFIG_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        path,
        {"enabled": True, "hour": hour, "locale": locale, "version": 1},
        indent=2,
        lock=True,
    )
    return path


def _state(practice_dir: str | Path) -> dict[str, Any]:
    path = _practice_root(practice_dir) / STATE_NAME
    if not path.is_file():
        return {"posted": {}, "logged": {}, "drafts": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"posted": {}, "logged": {}, "drafts": {}}
    if not isinstance(raw, dict):
        return {"posted": {}, "logged": {}, "drafts": {}}
    posted = raw.get("posted") if isinstance(raw.get("posted"), dict) else {}
    logged = raw.get("logged") if isinstance(raw.get("logged"), dict) else {}
    drafts = raw.get("drafts") if isinstance(raw.get("drafts"), dict) else {}
    return {"posted": posted, "logged": logged, "drafts": drafts}


def _write_state(practice_dir: str | Path, state: dict[str, Any]) -> None:
    path = _practice_root(practice_dir) / STATE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, state, indent=2, lock=True)


def posted_message_id(practice_dir: str | Path, day: date) -> str | None:
    value = _state(practice_dir)["posted"].get(day.isoformat())
    return str(value) if value else None


def already_logged(practice_dir: str | Path, day: date) -> bool:
    return day.isoformat() in _state(practice_dir)["logged"]


def posted_draft(practice_dir: str | Path, day: date) -> str | None:
    value = _state(practice_dir)["drafts"].get(day.isoformat())
    text = str(value or "").strip()
    return text or None


def mark_posted(
    practice_dir: str | Path,
    day: date,
    message_id: int | str,
    *,
    draft: str | None = None,
) -> None:
    state = _state(practice_dir)
    state["posted"][day.isoformat()] = str(message_id)
    text = (draft or "").strip()
    if text:
        state["drafts"][day.isoformat()] = text
    else:
        state["drafts"].pop(day.isoformat(), None)
    _write_state(practice_dir, state)


def mark_logged(practice_dir: str | Path, day: date) -> None:
    state = _state(practice_dir)
    state["logged"][day.isoformat()] = True
    _write_state(practice_dir, state)


def is_skip(text: str) -> bool:
    return (text or "").strip().lower() in _SKIP


def parse_reply(
    text: str,
    *,
    questions: tuple[CheckinQuestion, ...] = DEFAULT_QUESTIONS,
    flags: tuple[CheckinFlag, ...] = DEFAULT_FLAGS,
) -> CheckinEntry | None:
    raw = (text or "").strip()
    if not raw:
        return None
    expected = len(questions)
    tokens = [part for part in re.split(r"[\s,;/]+", raw) if part]
    scores: list[int] = []
    rest_at = 0
    for i, token in enumerate(tokens):
        if token.isdigit() and 0 <= int(token) <= 3:
            scores.append(int(token))
            rest_at = i + 1
            continue
        break
    if len(scores) != expected:
        return None
    rest = " ".join(tokens[rest_at:]).lower()
    by_id = {flag.id: _flag(rest, flag.aliases) for flag in flags}
    return CheckinEntry(
        scores=tuple(scores),  # type: ignore[arg-type]
        cannabis=by_id.get("cannabis"),
        therapy=by_id.get("therapy"),
    )


def _flag(rest: str, names: tuple[str, ...]) -> bool | None:
    if not rest:
        return None
    for name in names:
        found = re.search(rf"\b{name}\b\s*[=:]?\s*(\w+)", rest)
        if found:
            token = found.group(1).lower()
            if token in _YES:
                return True
            if token in _NO:
                return False
    return None


def format_observation(
    entry: CheckinEntry,
    day: date,
    *,
    questions: tuple[CheckinQuestion, ...] = DEFAULT_QUESTIONS,
) -> str:
    parts = [f"Abendcheck {day.isoformat()} sober"]
    ids = [q.id for q in questions] or list(SCALES)
    for name, value in zip(ids, entry.scores):
        parts.append(f"{name}={value}")
    if entry.cannabis is not None:
        parts.append(f"cannabis={'yes' if entry.cannabis else 'no'}")
    if entry.therapy is not None:
        parts.append(f"therapy={'yes' if entry.therapy else 'no'}")
    return " ".join(parts)


def prompt_text(
    *,
    mention: str,
    locale: str = "de",
    questions: tuple[CheckinQuestion, ...] = DEFAULT_QUESTIONS,
    flags: tuple[CheckinFlag, ...] = DEFAULT_FLAGS,
) -> str:
    """Content that must include the mention so Discord notifies."""
    locale = "en" if locale == "en" else "de"
    questions = questions or DEFAULT_QUESTIONS
    n = len(questions)
    if locale == "en":
        lines = [
            "Evening check-in — one minute.",
            f"Sober part of the day. Answer 0–3 after each question (0 not at all · 3 strongly):",
        ]
        yes_no = "yes/no"
        skip = "Or `skip`."
        example_flags = " ".join(
            f"{flag.aliases[0]} yes" if i == 0 else f"{flag.aliases[0]} no"
            for i, flag in enumerate(flags)
        )
    else:
        lines = [
            "Abendcheck — eine Minute.",
            "Nüchterner Teil des Tages. Nach jeder Frage 0–3 (0 gar nicht · 3 stark):",
        ]
        yes_no = "ja/nein"
        skip = "Oder `skip`."
        example_flags = " ".join(
            f"{flag.aliases[0]} ja" if i == 0 else f"{flag.aliases[0]} nein"
            for i, flag in enumerate(flags)
        )
    for i, question in enumerate(questions, start=1):
        text = question.en if locale == "en" else question.de
        lines.append(f"{i}. {text}")
    if flags:
        flag_bits = []
        for flag in flags:
            label = flag.en if locale == "en" else flag.de
            flag_bits.append(f"{label} {yes_no} (`{flag.aliases[0]}`)")
        lines.append("Dann: " + " · ".join(flag_bits))
    example_scores = " ".join(["2"] + ["1"] * (n - 1) if n else [])
    if n == 5:
        example_scores = "2 1 0 1 2"
    example = f"`{example_scores}{(' ' + example_flags) if example_flags else ''}`"
    lines.append(f"Eine Zeile: {example}" if locale == "de" else f"One line: {example}")
    lines.append(skip)
    body = "\n".join(lines)
    mention = mention.strip()
    if mention:
        return f"{mention}\n{body}"
    return body


def notify_kwargs(content: str) -> dict[str, Any]:
    """Positive control: a check-in send must be able to notify."""
    return {"content": content, "silent": False}


def ack_text(entry: CheckinEntry, *, locale: str = "de") -> str:
    scores = "/".join(str(n) for n in entry.scores)
    if locale == "en":
        extra = []
        if entry.cannabis is not None:
            extra.append(f"cannabis {'yes' if entry.cannabis else 'no'}")
        if entry.therapy is not None:
            extra.append(f"therapy {'yes' if entry.therapy else 'no'}")
        suffix = f" · {' · '.join(extra)}" if extra else ""
        return f"Held. Sober {scores}{suffix}. No reading — that is the conversation."
    extra = []
    if entry.cannabis is not None:
        extra.append(f"Cannabis {'ja' if entry.cannabis else 'nein'}")
    if entry.therapy is not None:
        extra.append(f"Therapie {'ja' if entry.therapy else 'nein'}")
    suffix = f" · {' · '.join(extra)}" if extra else ""
    return f"Gehalten. Nüchtern {scores}{suffix}. Keine Deutung — das ist das Gespräch."


def hint_text(
    *,
    locale: str = "de",
    questions: tuple[CheckinQuestion, ...] = DEFAULT_QUESTIONS,
    flags: tuple[CheckinFlag, ...] = DEFAULT_FLAGS,
) -> str:
    n = len(questions or DEFAULT_QUESTIONS)
    example = prompt_text(
        mention="", locale=locale, questions=questions, flags=flags
    )
    # Keep the hint short: count + the example line already in the prompt.
    example_line = next(
        (line for line in example.splitlines() if line.startswith("Eine Zeile:") or line.startswith("One line:")),
        "",
    )
    if locale == "en":
        return f"I need {n} numbers 0–3 after reading the questions, or `skip`. {example_line}".strip()
    return f"{n} Zahlen 0–3 nach den Fragen, oder `skip`. {example_line}".strip()


def message_in_parent(message) -> bool:
    """A thread has a parent. A ``ja`` there is conversation, not the check-in."""
    channel = getattr(message, "channel", None)
    if channel is None:
        return False
    return not getattr(channel, "parent_id", None)


@dataclass(frozen=True)
class StateCapture:
    kind: str
    text: str = ""


def state_source(practice_dir: str | Path, day: date) -> dict[str, Any] | None:
    """Today's eddy notes, plus wording context. None when today has no notes.

    The empty branch returns before any read of the board or the record, so
    an open question cannot be filled from older material.
    """
    root = _practice_root(practice_dir)
    facts = _today_facts(root, day)
    if not facts:
        return None
    last_state, board = _older_wording(root)
    return {"facts": facts, "last_state": last_state, "board": board}


def _today_facts(root: Path, day: date) -> list[str]:
    """Today's eddy-note bodies. The leaf parser, so this job does not import Discord."""
    from story_entries import entry_from_front, parse_eddy_file_entries

    eddies = root / "story" / "eddies"
    if not eddies.is_dir():
        return []
    tz = ZoneInfo(os.environ.get("PRACTICE_TIMEZONE", "Europe/Berlin"))
    facts: list[str] = []
    for note in sorted(eddies.glob("*.md")):
        try:
            content = note.read_text(encoding="utf-8")
        except OSError:
            continue
        for front, body in parse_eddy_file_entries(content):
            entry = entry_from_front(front, body, note, tz)
            if entry is None or entry.timestamp.astimezone(tz).date() != day:
                continue
            text = (entry.body or "").strip()
            if text:
                facts.append(text)
    return facts


def _older_wording(practice_dir: Path) -> tuple[str, str]:
    return _last_observation_text(practice_dir), _board_excerpt(practice_dir)


def _last_observation_text(practice_dir: Path) -> str:
    path = practice_dir / "record" / "observations.jsonl"
    if not path.is_file():
        return ""
    last = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("superseded_by"):
            continue
        text = str(row.get("text") or "").strip()
        if text:
            last = text
    return last[:500]


def _board_excerpt(practice_dir: Path) -> str:
    path = practice_dir / "health_model.md"
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()[:1200]
    except OSError:
        return ""


_LANGUAGE_NAMES = {"de": "German", "en": "English"}


def formation_prompt(source: dict[str, Any], locale: str = "de") -> str:
    facts = "\n\n".join(source.get("facts") or [])
    last = source.get("last_state") or "(none)"
    board = source.get("board") or "(none)"
    language = _LANGUAGE_NAMES.get(locale, _LANGUAGE_NAMES["de"])
    return (
        f"Write in {language}.\n\n"
        "Today's notes:\n"
        f"{facts}\n\n"
        "Previous recorded state (wording only, not a new fact):\n"
        f"{last}\n\n"
        "Board (wording only, not a new fact):\n"
        f"{board}\n"
    )


def resolve_state_draft(raw: str | None) -> str | None:
    text = (raw or "").strip().strip('"').strip()
    if not text or text == _EMPTY_DRAFT or len(text) < 20:
        return None
    if len(text) > 700:
        text = text[:700].rsplit(" ", 1)[0].rstrip(".,;") + "."
    return text


_STATE_SYSTEM = (
    # Today's notes are Turtle's own summaries, not the person's words, so their
    # language is not the room's. The request names the room's language.
    "You write one short description of this person's current state, in the "
    "language the request names. Second person. No questions. No advice. No "
    "diagnosis. Previous state and the board are wording only — they are not "
    "new facts. If today's notes do not support a description, reply with "
    "exactly: (no response generated)"
)


async def _generate_state_draft(prompt: str) -> str:
    from llm import chat_ollama
    from state import REFLECTION_MODEL

    return await chat_ollama(
        _STATE_SYSTEM,
        [{"role": "user", "content": prompt}],
        model=REFLECTION_MODEL,
        num_ctx=8192,
        think=False,
    )


async def compose_state_checkin(
    practice_dir: str | Path,
    day: date,
    *,
    mention: str,
    locale: str,
    generate=None,
) -> tuple[str, str | None]:
    """Post body plus the draft to store. A failed or empty draft posts the open question."""
    source = state_source(practice_dir, day)
    draft = None
    if source is not None:
        generate = generate or _generate_state_draft
        try:
            raw = await generate(formation_prompt(source, locale))
        except Exception:
            raw = None
        draft = resolve_state_draft(raw)
    return state_prompt(mention=mention, locale=locale, draft=draft), draft


async def checkin_content(
    config: CheckinConfig,
    practice_dir: str | Path,
    day: date,
    *,
    mention: str,
    generate=None,
) -> tuple[str, str | None]:
    """Survey stays the default. State mode is the only path that asks the one question."""
    if config.mode == MODE_STATE:
        return await compose_state_checkin(
            practice_dir,
            day,
            mention=mention,
            locale=config.locale,
            generate=generate,
        )
    return (
        prompt_text(
            mention=mention,
            locale=config.locale,
            questions=config.questions,
            flags=config.flags,
        ),
        None,
    )


def state_prompt(*, mention: str, locale: str = "de", draft: str | None = None) -> str:
    locale = "en" if locale == "en" else "de"
    if draft:
        ask = STATE_ASK_EN if locale == "en" else STATE_ASK_DE
        how = (
            "`ja` if this is it. `no, rather …` in your own words. Or `skip`."
            if locale == "en"
            else "`ja` wenn es stimmt. `nein, eher …` in deinen Worten. Oder `skip`."
        )
        body = f"{draft.strip()}\n\n{ask}\n{how}"
    else:
        lead = OPEN_STATE_EN if locale == "en" else OPEN_STATE_DE
        ask = (
            "What is your state right now? Reply to this message. Or `skip`."
            if locale == "en"
            else "Was ist gerade dein Stand? Antworte auf diese Nachricht. Oder `skip`."
        )
        body = f"{lead}\n\n{ask}"
    mention = (mention or "").strip()
    if mention:
        return f"{mention}\n{body}"
    return body


def classify_state_capture(
    text: str,
    *,
    in_parent: bool,
    already_logged: bool,
    references_prompt: bool,
    has_draft: bool,
) -> StateCapture | None:
    """One answer, in the parent, while today's prompt is still open.

    A thread, a second reply, or anything that is not ``ja`` / ``nein, eher …``
    / ``skip`` (or a reply to the open question) is conversation.
    """
    if not in_parent or already_logged:
        return None
    parsed = _parse_state_reply(text)
    if parsed is not None and parsed.kind == "skip":
        return parsed
    if parsed is not None and parsed.kind == "confirm":
        return parsed if has_draft else None
    if parsed is not None and parsed.kind == "correct":
        return parsed
    if references_prompt and not has_draft:
        body = (text or "").strip()
        if body:
            return StateCapture("stated", body)
    return None


def _parse_state_reply(text: str) -> StateCapture | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if is_skip(raw):
        return StateCapture("skip")
    if raw.lower().rstrip(".!") in {"ja", "yes", "j"}:
        return StateCapture("confirm")
    match = re.match(
        r"^(?:nein|no)\s*(?:,\s*|\s+)(?:eher\s+|rather\s+)?(.+)$",
        raw,
        re.IGNORECASE | re.DOTALL,
    )
    if match and match.group(1).strip():
        return StateCapture("correct", match.group(1).strip())
    return None


def state_ack(kind: str, *, locale: str = "de") -> str:
    locale = "en" if locale == "en" else "de"
    if locale == "en":
        if kind == "confirm":
            return "Held. That stands as confirmed."
        if kind == "correct":
            return "Held. Your wording stands. The draft stays beside it, labelled as mine."
        return "Held."
    if kind == "confirm":
        return "Gehalten. Das steht als bestätigt."
    if kind == "correct":
        return "Gehalten. Deine Fassung steht. Der Entwurf bleibt daneben, als meiner gekennzeichnet."
    return "Gehalten."


async def send_then_mark(
    practice_dir: str | Path,
    day: date,
    content: str,
    deliver,
    *,
    draft: str | None = None,
) -> bool:
    """Mark the day posted only after the send returns. A failed send leaves the day open."""
    try:
        message_id = await deliver(content)
    except Exception as exc:
        print(
            f"Health check-in post failed for {practice_dir}: "
            f"{type(exc).__name__}: {exc}"
        )
        return False
    mark_posted(
        practice_dir,
        day,
        message_id or f"posted-{day.isoformat()}",
        draft=draft,
    )
    return True


def due_now(config: CheckinConfig, now: datetime) -> bool:
    if not config.enabled:
        return False
    return now.hour >= config.hour


def health_channel_targets(registry: dict) -> list[dict[str, Any]]:
    """Health instances that opted in. A shared instance without a config file is absent."""
    from channel_primitives import resolve_primitive

    targets: list[dict[str, Any]] = []
    spaces = registry.get("spaces") or {}
    mages = registry.get("mages") or {}
    for channel_id, entry in (registry.get("channels") or {}).items():
        if not isinstance(entry, dict) or entry.get("archived") or entry.get("orphaned"):
            continue
        primitive = resolve_primitive(registry, channel_id)
        if primitive is None or primitive.name != "health" or not primitive.subject:
            continue
        key = str(entry.get("mage") or "")
        owner = spaces.get(key) if key in spaces else mages.get(key)
        if not isinstance(owner, dict):
            continue
        root = str(owner.get("practice_dir") or "").strip()
        if not root:
            continue
        config = load_config(root)
        if not config.enabled:
            continue
        subject = mages.get(primitive.subject) or {}
        discord_id = str(subject.get("discord_id") or "").strip()
        try:
            ch_id = int(channel_id)
        except (TypeError, ValueError):
            continue
        targets.append(
            {
                "channel_id": ch_id,
                "practice_dir": str(_practice_root(root)),
                "subject": primitive.subject,
                "discord_id": discord_id,
                "config": config,
            }
        )
    return targets

