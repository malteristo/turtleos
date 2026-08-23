"""Test files that import discord must stub first — else the suite's order is the test.

Four files failed this morning when run alone under system Python (no discord.py):
``test_auto_admit``, ``test_mage_channel_resolution``, ``test_resolve_guild_member``,
``test_dialogue_routing``. They passed under ``unittest discover`` because an earlier
file had already stuffed a MagicMock into ``sys.modules["discord"]``. That is a green
suite whose membership depends on filename order.

The try/except-then-stub pattern (``test_consent.py`` and neighbours) is a different
act: those files *can* run alone. This guard flags only an unconditional top-level
``import discord`` with no preceding stub in the same file.

Use: ``sys.modules.setdefault("discord", MagicMock())`` before the import, or
``tests.discord_stub.install_discord_stub``.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def _unconditional_discord_imports_without_stub(source: str) -> list[int]:
    """Line numbers of module-level ``import discord`` with no stub yet in this file."""
    tree = ast.parse(source)
    stubbed = False
    offenders: list[int] = []
    for node in tree.body:
        if _node_stubs_discord(node):
            stubbed = True
        if isinstance(node, ast.Try):
            # Conditional import: isolation is the except-branch's job.
            continue
        if _node_imports_discord(node) and not stubbed:
            offenders.append(node.lineno)
    return offenders


def _node_stubs_discord(node: ast.stmt) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.ImportFrom):
            mod = child.module or ""
            if mod.endswith("discord_stub") or "discord_stub" in mod:
                return True
        if isinstance(child, ast.Call):
            for arg in child.args:
                if isinstance(arg, ast.Constant) and arg.value == "discord":
                    func = child.func
                    name = ast.unparse(func)
                    if "setdefault" in name or "install_discord_stub" in name:
                        return True
    return False


def _node_imports_discord(node: ast.stmt) -> bool:
    if isinstance(node, ast.Import):
        return any(a.name == "discord" or a.name.startswith("discord.") for a in node.names)
    if isinstance(node, ast.ImportFrom):
        return bool(node.module and node.module.split(".")[0] == "discord")
    return False


class DiscordImportIsolationTests(unittest.TestCase):
    def test_positive_control_flags_a_bare_import(self) -> None:
        """Empty is not evidence. A file that is the defect must be seen."""
        self.assertEqual(
            _unconditional_discord_imports_without_stub("import discord\n"),
            [1],
        )
        self.assertEqual(
            _unconditional_discord_imports_without_stub(
                "from unittest.mock import MagicMock\n"
                "import sys\n"
                "sys.modules.setdefault('discord', MagicMock())\n"
                "import discord\n"
            ),
            [],
        )
        self.assertEqual(
            _unconditional_discord_imports_without_stub(
                "try:\n    import discord\nexcept ImportError:\n    pass\n"
            ),
            [],
        )

    def test_the_stub_is_enough_to_import_ext_and_to_spec(self) -> None:
        """The four files failed for two reasons past a missing `import discord`.

        `from discord.ext import tasks` needs a package, and
        `MagicMock(spec=discord.Member)` needs Member to be a real type.
        Both must work when discord.py is absent, or isolation is a comment.
        """
        from unittest.mock import MagicMock

        from tests.discord_stub import install_discord_stub, is_real_discord

        discord = install_discord_stub()
        if is_real_discord(discord):
            self.skipTest("discord.py is installed; this asserts the absent-lib path")
        from discord.ext import tasks  # noqa: F401

        MagicMock(spec=discord.Member)
        MagicMock(spec=discord.Thread)
        MagicMock(spec=discord.TextChannel)
        client = discord.Client(intents=discord.Intents.default())
        client.get_channel(1)

    def test_no_test_module_imports_discord_unstubbed(self) -> None:
        found: list[str] = []
        for path in sorted(TESTS.glob("test_*.py")):
            lines = _unconditional_discord_imports_without_stub(
                path.read_text(encoding="utf-8")
            )
            for lineno in lines:
                found.append(f"{path.name}:{lineno}")
        self.assertEqual(
            found,
            [],
            "these test modules import discord at collection time without stubbing "
            "first; they pass in discover only if an earlier file stubbed it: "
            + ", ".join(found),
        )


if __name__ == "__main__":
    unittest.main()
