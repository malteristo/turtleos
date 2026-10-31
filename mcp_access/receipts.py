"""Receipts for words that leave through a grant.

A receipt names the place, the connection, and the program that asked. It
does not carry the excerpt, the query, or the note, and it says plainly that
the model after that program is not visible. It is written in the owner's
private root — the host grant file stays counts only — and River posts it.
The same place and the same program inside ten minutes is one receipt.

Briefs and lists stay quiet: opening a practice sends titles every time.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.atomic_io import atomic_write_text, file_lock

RECEIPTS_REL = Path("state") / "mcp_receipts.jsonl"
DEBOUNCE = timedelta(minutes=10)
GIVE_UP_AFTER = timedelta(hours=24)
_SNOWFLAKE = 15

_COPY = {
    "en": {
        "who_both": "{client}, through your connection “{principal}”,",
        "who_access": "your connection “{principal}”",
        "who_unknown": "A program",
        "thread": "{who} just read this conversation. {handed}",
        "note": "{who} just read the conversation “{title}”. {handed}",
        "note_untitled": "{who} just read a conversation. {handed}",
        "health": "{who} just read your health picture. {handed}",
        "workshop": "{who} just read files of your workshop (the practice repository). {handed}",
        "letter": "{who} just read a letter you keep here: {name}. {handed}",
        "letter_unnamed": "{who} just read a letter you keep here. {handed}",
        "search": "{who} took a short piece from: {places}. {handed_bits}",
        "already": "{who} has already read: {things}. {handed_past}",
        "thing_health": "your health picture",
        "thing_note": "one conversation",
        "thing_letter": "one letter",
        "handed": "Where it went: {program}, on the device of this connection. turtleOS does not see which model is used after that.",
        "handed_access": "It went to this connection, on the device you linked. turtleOS does not see the program's name there, or which model it uses.",
        "handed_bits": "Where those pieces went: {program}, on the device of this connection. turtleOS does not see which model is used after that.",
        "handed_bits_access": "Those pieces went to this connection, on the device you linked. turtleOS does not see the program's name there, or which model it uses.",
        "handed_past": "Where it went: {program}, on the device of this connection. turtleOS does not see which model was used after that.",
        "handed_past_access": "It went to this connection, on the device you linked. turtleOS does not see the program's name there, or which model it used.",
        "health_place": "your health picture",
        "and": ", and ",
    },
    "de": {
        "who_both": "{client}, über deinen Zugang „{principal}“,",
        "who_access": "dein Zugang „{principal}“",
        "who_unknown": "Ein Programm",
        "thread": "{who} hat dieses Gespräch gerade gelesen. {handed}",
        "note": "{who} hat das Gespräch „{title}“ gerade gelesen. {handed}",
        "note_untitled": "{who} hat ein Gespräch gerade gelesen. {handed}",
        "health": "{who} hat dein Gesundheitsbild gerade gelesen. {handed}",
        "workshop": "{who} hat gerade Dateien deiner Werkstatt (des Praxis-Repositorys) gelesen. {handed}",
        "letter": "{who} hat einen Brief gerade gelesen, den du hier aufbewahrst: {name}. {handed}",
        "letter_unnamed": "{who} hat einen Brief gerade gelesen, den du hier aufbewahrst. {handed}",
        "search": "{who} hat ein kurzes Stück gelesen aus: {places}. {handed_bits}",
        "already": "{who} hat schon gelesen: {things}. {handed_past}",
        "thing_health": "dein Gesundheitsbild",
        "thing_note": "ein Gespräch",
        "thing_letter": "einen Brief",
        "handed": "Wohin es ging: {program}, auf dem Gerät dieses Zugangs. Welches Modell danach genutzt wird, sieht turtleOS nicht.",
        "handed_access": "Das ging an diesen Zugang, auf dem Gerät, mit dem du ihn verbunden hast. Den Namen des Programms dort und welches Modell es nutzt, sieht turtleOS nicht.",
        "handed_bits": "Wohin diese Stücke gingen: {program}, auf dem Gerät dieses Zugangs. Welches Modell danach genutzt wird, sieht turtleOS nicht.",
        "handed_bits_access": "Diese Stücke gingen an diesen Zugang, auf dem Gerät, mit dem du ihn verbunden hast. Den Namen des Programms dort und welches Modell es nutzt, sieht turtleOS nicht.",
        "handed_past": "Wohin es ging: {program}, auf dem Gerät dieses Zugangs. Welches Modell danach genutzt wurde, sieht turtleOS nicht.",
        "handed_past_access": "Das ging an diesen Zugang, auf dem Gerät, mit dem du ihn verbunden hast. Den Namen des Programms dort und welches Modell es genutzt hat, sieht turtleOS nicht.",
        "health_place": "dein Gesundheitsbild",
        "and": " und ",
    },
}

def locale_of(registry: dict, owner: str) -> str:
    loc = str(((registry.get("mages") or {}).get(owner) or {}).get("locale") or "en").strip().lower()
    return loc if loc in _COPY else "en"


def thread_id_from_note_id(note_id: str) -> str | None:
    head = (note_id or "").split("-", 1)[0]
    if head.isdigit() and len(head) >= _SNOWFLAKE:
        return head
    return None


def _t(locale: str) -> dict:
    return _COPY.get(locale) or _COPY["en"]


def _label(value: str) -> str:
    return " ".join((value or "").split())[:120]


def _join(names: list[str], locale: str) -> str:
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + _t(locale)["and"] + names[-1]


def _path(root: Path) -> Path:
    return root / RECEIPTS_REL


def _now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def _load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _save(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    atomic_write_text(path, text)


def _fresh(rows: list[dict], now: datetime) -> list[dict]:
    kept = []
    for row in rows:
        try:
            ts = datetime.fromisoformat(row["ts"])
        except (KeyError, TypeError, ValueError):
            continue
        pending = any(post.get("sent") is None for post in row.get("posts") or [])
        if pending or now - ts < GIVE_UP_AFTER:
            kept.append(row)
    return kept


def _recent(rows: list[dict], key: str, now: datetime) -> bool:
    for row in rows:
        if row.get("key") != key:
            continue
        try:
            ts = datetime.fromisoformat(row["ts"])
        except (KeyError, TypeError, ValueError):
            continue
        if now - ts < DEBOUNCE:
            return True
    return False


def enqueue(root: Path | None, *, key: str, posts: list[dict], now: datetime | None = None) -> bool:
    """Append one receipt. False when there is nowhere to write, or this place was named just now."""
    if root is None or not root.is_dir() or not posts:
        return False
    moment = _now(now)
    path = _path(root)
    with file_lock(path):
        rows = _fresh(_load(path), moment)
        if _recent(rows, key, moment):
            _save(path, rows)
            return False
        rows.append(
            {
                "id": "r_" + secrets.token_hex(6),
                "ts": moment.isoformat(),
                "key": key,
                "posts": [{**post, "sent": None} for post in posts],
            }
        )
        _save(path, rows)
    return True


def enqueue_private_line(root: Path | None, text: str, *, now: datetime | None = None) -> bool:
    """One line in the owner's private channel. Used for a notice that is not tied to a new read."""
    cleaned = " ".join((text or "").split())[:1800]
    if not cleaned:
        return False
    key = "notice:" + hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:12]
    return enqueue(root, key=key, posts=[{"to": "private", "text": cleaned}], now=now)


def program_label(client_name: str = "", client_version: str = "") -> str:
    """The program as the client named itself. The version stays on the grant, not in the channel."""
    return _label(client_name)


def _caller(locale: str, *, principal: str, client_name: str, client_version: str = "") -> tuple[str, str, bool]:
    """(who asked, program name, whether the program named itself).

    The model after the program is never known. When the program has not
    named itself, the furthest point visible is the connection and its device.
    """
    copy = _t(locale)
    client = program_label(client_name, client_version)
    access = _label(principal)
    if client and access and client.casefold() != access.casefold():
        return copy["who_both"].format(client=client, principal=access), client, True
    if client:
        return client, client, True
    if access:
        return copy["who_access"].format(principal=access), access, False
    return copy["who_unknown"], "", False


def _handed(locale: str, kind: str, program: str, *, named: bool) -> str:
    key = kind if named else f"{kind}_access"
    return _t(locale)[key].format(program=program)


def _key(caller: str, rest: str) -> str:
    return f"{caller}|{rest}"


def for_note(
    root: Path | None,
    *,
    note_id: str,
    title: str,
    locale: str,
    principal: str = "",
    client_name: str = "",
    client_version: str = "",
    now: datetime | None = None,
) -> bool:
    copy = _t(locale)
    who, program, named = _caller(locale, principal=principal, client_name=client_name, client_version=client_version)
    handed = _handed(locale, "handed", program, named=named)
    label = _label(title)
    private = (copy["note"] if label else copy["note_untitled"]).format(who=who, title=label, handed=handed)
    posts = [{"to": "private", "text": private}]
    thread_id = thread_id_from_note_id(note_id)
    if thread_id:
        posts.insert(0, {"to": "thread", "thread_id": thread_id, "text": copy["thread"].format(who=who, handed=handed)})
    return enqueue(root, key=_key(who, f"note:{note_id}"), posts=posts, now=now)


def for_health(
    root: Path | None,
    *,
    locale: str,
    principal: str = "",
    client_name: str = "",
    client_version: str = "",
    now: datetime | None = None,
) -> bool:
    who, program, named = _caller(locale, principal=principal, client_name=client_name, client_version=client_version)
    text = _t(locale)["health"].format(who=who, handed=_handed(locale, "handed", program, named=named))
    return enqueue(
        root,
        key=_key(who, "health"),
        posts=[{"to": "health", "text": text}, {"to": "private", "text": text}],
        now=now,
    )


def for_letter(
    root: Path | None,
    *,
    doc_id: str,
    filename: str,
    locale: str,
    principal: str = "",
    client_name: str = "",
    client_version: str = "",
    now: datetime | None = None,
) -> bool:
    copy = _t(locale)
    who, program, named = _caller(locale, principal=principal, client_name=client_name, client_version=client_version)
    handed = _handed(locale, "handed", program, named=named)
    name = _label(filename)
    text = (copy["letter"] if name else copy["letter_unnamed"]).format(who=who, name=name, handed=handed)
    return enqueue(root, key=_key(who, f"letter:{doc_id}"), posts=[{"to": "private", "text": text}], now=now)


def for_workshop(
    root: Path | None,
    *,
    locale: str,
    principal: str = "",
    client_name: str = "",
    client_version: str = "",
    now: datetime | None = None,
) -> bool:
    """One receipt per ten minutes for reading the workshop, however many files a session opens.

    A summon reads dozens of files; one line per file would be a flood that
    teaches the owner to ignore receipts. The place is the workshop, never a file name.
    """
    who, program, named = _caller(locale, principal=principal, client_name=client_name, client_version=client_version)
    text = _t(locale)["workshop"].format(who=who, handed=_handed(locale, "handed", program, named=named))
    return enqueue(root, key=_key(who, "workshop"), posts=[{"to": "private", "text": text}], now=now)


def already_read(
    locale: str,
    *,
    principal: str = "",
    client_name: str = "",
    client_version: str = "",
    health: bool = False,
    conversation: bool = False,
    letter: bool = False,
) -> str:
    """One line for a read that already happened, when the log cannot name which one."""
    copy = _t(locale)
    who, program, named = _caller(locale, principal=principal, client_name=client_name, client_version=client_version)
    things = []
    if health:
        things.append(copy["thing_health"])
    if conversation:
        things.append(copy["thing_note"])
    if letter:
        things.append(copy["thing_letter"])
    return copy["already"].format(
        who=who, things=_join(things, locale), handed_past=_handed(locale, "handed_past", program, named=named)
    )


def _places(hits: list[dict], locale: str) -> list[tuple[str, str]]:
    """(debounce key, words she sees). Titles and filenames only — never a snippet."""
    copy = _t(locale)
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for hit in hits:
        ref = str(hit.get("ref") or "")
        if ref.endswith("/picture"):
            key, label = "health", copy["health_place"]
        elif "/documents/" in ref:
            key = "letter:" + ref.rsplit("/", 1)[-1]
            label = _label(str(hit.get("title") or ""))
        elif "/note/" in ref:
            key = "note:" + ref.rsplit("/", 1)[-1]
            label = _label(str(hit.get("title") or ""))
        else:
            continue
        if not label or key in seen:
            continue
        seen.add(key)
        found.append((key, label))
    return found


def for_search(
    root: Path | None,
    hits: list[dict],
    *,
    locale: str,
    principal: str = "",
    client_name: str = "",
    client_version: str = "",
    now: datetime | None = None,
) -> bool:
    places = _places(hits, locale)
    if not places:
        return False
    who, program, named = _caller(locale, principal=principal, client_name=client_name, client_version=client_version)
    names = _join([label for _, label in places], locale)
    key = _key(who, "search:" + "|".join(sorted(k for k, _ in places)))
    text = _t(locale)["search"].format(
        who=who, places=names, handed_bits=_handed(locale, "handed_bits", program, named=named)
    )
    return enqueue(root, key=key, posts=[{"to": "private", "text": text}], now=now)


def pending_posts(rows: list[dict], now: datetime | None = None) -> list[tuple[dict, int]]:
    """(receipt, post index) still to send. A post older than a day is given up."""
    moment = _now(now)
    due = []
    for row in rows:
        try:
            ts = datetime.fromisoformat(row["ts"])
        except (KeyError, TypeError, ValueError):
            continue
        stale = moment - ts >= GIVE_UP_AFTER
        for index, post in enumerate(row.get("posts") or []):
            if post.get("sent") is not None:
                continue
            if stale:
                post["sent"] = "skipped:too-old"
                continue
            due.append((row, index))
    return due
