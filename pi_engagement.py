"""The card for one Pi engagement.

Spirit drives the agent. The session shows one card, and updates that same
card: the phase, the branch, a count of looks, which named tests failed, and
which claims are still false. It does not show each local turn, and it does
not show a path.
"""

from __future__ import annotations

API = "https://discord.com/api/v10"


def render(
    *,
    phase: str,
    branch: str,
    progress: str,
    failed: list[str] | tuple[str, ...],
    claims: list[str] | tuple[str, ...],
    looks: int = 0,
) -> str:
    """One card. A working phase carries the count, which is the progress."""
    if phase == "working" and looks:
        head = f"-# Pi · working · {looks}"
    elif looks:
        head = f"-# Pi · {phase} · {looks}"
    else:
        head = f"-# Pi · {phase}"
    lines = [head, f"-# branch `{branch}`" if branch else "-# no branch"]
    if progress:
        lines.append(f"-# {progress}")
    lines.append("-# tests failing: " + (", ".join(failed) if failed else "none"))
    lines.append("-# still false: " + ("; ".join(claims) if claims else "none"))
    return "\n".join(lines)


def _settled(text: str) -> tuple:
    """The phase and the lines that say what failed. A look-count is not a new fact."""
    lines = text.splitlines()
    head = lines[0] if lines else ""
    parts = [part.strip() for part in head.split("·")]
    phase = parts[1].split()[0] if len(parts) > 1 else ""
    body = tuple(line for line in lines if "tests failing" in line or "still false" in line)
    return phase, body


def worth_keeping(previous: str | None, text: str) -> bool:
    if not previous:
        return True
    return _settled(previous) != _settled(text)


def remember_card(practice_dir, eddy: str, text: str):
    """The card, in the session file. A look-count stays on the channel card."""
    from session_record import append_event

    return append_event(practice_dir, eddy, kind="pi", actor="spirit", text=text)


# Discord's components-v2 flag. A layout message is the card, and has no body text.
COMPONENTS_V2 = 1 << 15

_TEXT = {
    "en": {
        "title": "Pi",
        "starting": "Starting",
        "working": "Working",
        "aborted": "Stopped",
        "done": "Finished",
        "looks": "{n} looks",
        "branch": "Branch",
        "no_branch": "No branch yet",
        "tests": "Tests",
        "none": "none",
        "claims": "Still false",
        "clear": "nothing",
    },
    "de": {
        "title": "Pi",
        "starting": "Beginnt",
        "working": "Arbeitet",
        "aborted": "Angehalten",
        "done": "Fertig",
        "looks": "{n} Blicke",
        "branch": "Zweig",
        "no_branch": "Noch kein Zweig",
        "tests": "Tests",
        "none": "keine",
        "claims": "Noch falsch",
        "clear": "nichts",
    },
}


def _t(locale: str) -> dict:
    return _TEXT.get(locale) or _TEXT["en"]


def accent(phase: str, failed, claims) -> str:
    """Blue while it works. Green when it finishes clean. Amber when something is still false."""
    if phase in ("starting", "working"):
        return "info"
    if failed or claims:
        return "attention"
    return "done"


def _clip(text: str, limit: int = 80) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def engagement_view(
    *,
    phase: str,
    branch: str,
    progress: str,
    failed,
    claims,
    looks: int = 0,
    locale: str = "en",
):
    """The bordered card. The accent is the only colour, and it means the phase."""
    import ui_kit

    t = _t(locale)
    bits = [t.get(phase, phase)]
    if progress and progress not in (phase, bits[0]):
        bits.append(progress)
    if looks:
        bits.append(t["looks"].format(n=looks))
    rows = (
        ui_kit.Item(t["branch"], _clip(branch or t["no_branch"])),
        ui_kit.Item(t["tests"], _clip(", ".join(failed) if failed else t["none"])),
        ui_kit.Item(t["claims"], _clip("; ".join(claims) if claims else t["clear"])),
    )
    return ui_kit.build(
        [
            ui_kit.Card(
                title=t["title"],
                quiet=_clip(" · ".join(bits), 200),
                rows=rows,
                accent=accent(phase, failed, claims),
            )
        ]
    )


class Board:
    """Post the card once, then edit that message as the engagement moves.

    The channel message is the bordered card. The session file keeps a line
    when the phase, the failing tests, or the claims change. A further look
    updates the channel card only.
    """

    def __init__(self, thread_id: str, send, remember=None) -> None:
        self.thread_id = str(thread_id)
        self.send = send
        self.remember = remember
        self.message_id: str | None = None
        self.kept: str | None = None

    def send_box(self, text: str, components: list) -> None:
        body = {
            "flags": COMPONENTS_V2,
            "components": components,
            "allowed_mentions": {"parse": []},
        }
        if self.message_id is None:
            status, data = self.send("POST", f"{API}/channels/{self.thread_id}/messages", body)
            if status in (200, 201) and isinstance(data, dict) and data.get("id"):
                self.message_id = str(data["id"])
        else:
            # A message that was plain text cannot become a card while the text remains.
            body["content"] = ""
            self.send("PATCH", f"{API}/channels/{self.thread_id}/messages/{self.message_id}", body)
        if self.remember is not None and worth_keeping(self.kept, text):
            self.remember(text)
            self.kept = text

    def show(self, **fields) -> str:
        import ui_kit

        text = render(**{k: fields[k] for k in ("phase", "branch", "progress", "failed", "claims", "looks") if k in fields})
        view = engagement_view(**fields)
        self.send_box(text, ui_kit.components(view))
        return text
