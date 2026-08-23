"""A Discord stub whose UI base classes are real classes — when Discord is absent.

Found 2026-08-14 while wiring the transport seam, and the finding is about the test
environment rather than any one test.

**Which `discord` a test gets is decided by module import order.** Nineteen test
files run `sys.modules.setdefault("discord", MagicMock())` at import time. The repo
venv also has the real discord.py 2.7.1 installed. So whichever gets into
`sys.modules` first wins *for the whole session*: files imported before the first
mock-inserting file talk to the real library, everything after talks to a mock. One
suite, two environments, chosen by filename.

Under the mock half, a statement like::

    class LinkOfferView(discord.ui.View):
        ...

does not define a class at all. `discord.ui.View` is a `MagicMock`, so the class
statement resolves through `__mro_entries__` and the name ends up bound to *another
mock* — the class body, with every button label, `custom_id` and callback wiring, is
never executed. Instantiating it raises ``RuntimeError: coroutine raised
StopIteration`` from inside `unittest.mock`, which names nothing and is why this was
never read as "that class does not exist".

That is a large part of why this repo leans on AST guards like
`test_no_decline_buttons`: for the mocked half of the suite, static scanning was the
only thing that could see a button at all.

This module makes the mocked half constructible. It gives `discord.ui.View` and
`discord.ui.Button` real, minimal classes that record what they were built with. It
does **not** try to be discord.py.

**It never touches the real library.** An earlier version set `discord.ui.View` on
whatever module was loaded, which monkeypatched real discord.py for the rest of the
session and broke three unrelated tests with
``AttributeError: 'FakeButton' object has no attribute '_is_v2'``. When the real
library is present it is left completely alone — real classes are better than fake
ones, and the caller's code is identical either way.

Use it in a test file *before* importing the module under test::

    from tests.discord_stub import install_discord_stub
    install_discord_stub(reload=("discord_render",))

    import discord_render
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock


class FakeButton:
    """Records what a button was asked to be."""

    def __init__(self, *, label: str = "", style=None, custom_id: str = "", **kwargs):
        self.label = label
        self.style = style
        self.custom_id = custom_id
        self.extra = kwargs
        self.callback = None


class FakeView:
    """Enough of `discord.ui.View` to construct a subclass and inspect its items."""

    def __init__(self, *, timeout: float | None = None, **kwargs):
        self.timeout = timeout
        self.children: list = []

    def add_item(self, item) -> None:
        self.children.append(item)


class FakeButtonStyle:
    primary = "primary"
    secondary = "secondary"
    success = "success"
    danger = "danger"


def is_real_discord(module: object) -> bool:
    """True for the actual library. `__version__` is the cheapest honest signal."""
    return isinstance(getattr(module, "__version__", None), str)


def install_discord_stub(*, reload: tuple[str, ...] = ()):
    """Make Discord's UI base classes constructible. Returns the `discord` module.

    When the real library is importable it is returned untouched — see the module
    docstring for what happened the one time this function patched it.

    `reload` names modules to re-import afterwards. A module that executed its
    `class X(discord.ui.View)` statement while `View` was still a bare mock has a
    mock where its class should be, and only re-executing the module fixes that.
    This is a parameter rather than a note in a docstring because a caller who
    forgets gets the StopIteration described above, which explains nothing.
    """
    discord = sys.modules.get("discord")

    if discord is None:
        try:
            discord = importlib.import_module("discord")
        except ImportError:
            discord = MagicMock()
            sys.modules["discord"] = discord

    if is_real_discord(discord):
        for module_name in reload:
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
        return discord

    # A MagicMock is not a package. `from discord.ext import tasks` then
    # raises "discord is not a package" — which is how a file that stubbed
    # with setdefault still failed when run alone (test_resolve_guild_member
    # via commands.py, 2026-08-18).
    discord.__path__ = []
    for name in ("discord.ext", "discord.ext.tasks", "discord.ui"):
        sub = sys.modules.setdefault(name, MagicMock())
        if name != "discord.ext.tasks":
            sub.__path__ = []
        sys.modules[name] = sub
    discord.ext = sys.modules["discord.ext"]
    discord.ext.tasks = sys.modules["discord.ext.tasks"]
    discord.ui = sys.modules["discord.ui"]

    if not isinstance(getattr(discord, "HTTPException", None), type):
        discord.HTTPException = type("HTTPException", (Exception,), {})
    for exc in ("NotFound", "Forbidden"):
        if not isinstance(getattr(discord, exc, None), type):
            setattr(discord, exc, type(exc, (Exception,), {}))

    # MagicMock(spec=discord.Member) raises InvalidSpecError on 3.11+ when
    # Member is itself a Mock. Tests that used spec= against the real
    # library's types inherit that failure the moment the stub wins.
    # Client and Intents stay MagicMock: state.py constructs Client(intents=...)
    # and calls .get_channel; a real empty type rejects both.
    for name in (
        "Member",
        "Thread",
        "TextChannel",
        "Message",
        "User",
        "Guild",
        "Interaction",
    ):
        if not isinstance(getattr(discord, name, None), type):
            setattr(discord, name, type(name, (), {}))

    discord.ui.View = FakeView
    discord.ui.Button = FakeButton
    discord.ButtonStyle = FakeButtonStyle

    for module_name in reload:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
        else:
            importlib.import_module(module_name)

    return discord
