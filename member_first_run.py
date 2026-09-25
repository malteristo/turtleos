"""First minute in a new member's private river.

Dest: docs/design/member-onboarding.md criterion 3 — one obvious action;
they talk before they are taught. The hosted welcome embed is a different door.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
FIRST_RUN_PATH = REPO_ROOT / "template" / "practitioner" / "first_run_en.md"
FIRST_RUN_MAX_CHARS = 160
REQUIRED_PHRASE = "new eddy"
# Hosted-manual leftovers. A first-run that teaches these has failed the dest.
FORBIDDEN_PHRASES = (
    "bound",
    "!admin",
    "homework",
    "flow library",
    "river key",
    "how it works",
)


def first_run_text() -> str:
    text = FIRST_RUN_PATH.read_text(encoding="utf-8").strip()
    problems = first_run_problems(text)
    if problems:
        raise ValueError("first-run copy fails dest criterion 3: " + "; ".join(problems))
    return text


def first_run_problems(text: str) -> list[str]:
    """Empty is not evidence of absence — the known-long hosted welcome must fail."""
    problems: list[str] = []
    body = (text or "").strip()
    if not body:
        problems.append("empty")
    if len(body) > FIRST_RUN_MAX_CHARS:
        problems.append(f"too long ({len(body)} > {FIRST_RUN_MAX_CHARS})")
    if REQUIRED_PHRASE not in body.lower():
        problems.append(f"missing {REQUIRED_PHRASE!r}")
    lowered = body.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            problems.append(f"teaches {phrase!r}")
    return problems


async def post_member_first_run(channel) -> object | None:
    """Send the first-run. Caller marks onboarding posted so the hosted embed stays off."""
    import discord

    text = first_run_text()
    try:
        msg = await channel.send(text, silent=True)
    except discord.HTTPException as exc:
        print(f"member first-run failed for {getattr(channel, 'id', '?')}: {exc}")
        return None

    try:
        await msg.pin()
    except discord.HTTPException:
        pass
    return msg
