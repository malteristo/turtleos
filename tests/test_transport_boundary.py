"""The door-stays-open invariant, enforced.

``runtime/__init__.py`` has said "This package is intentionally independent of
Discord" since the package was created, and nothing ever checked it. The craft
architecture eddy of 2026-08-11 turned that sentence into a decision the Mage
signed off on — *"don't close the door to switching in the future"* — and the
whole architectural content of it is one rule: **the runtime never imports a
transport library.** A rule with no check is a sentence.

Exemption: ``runtime/adapters/`` is where translation is supposed to happen, so
adapters may import a platform SDK. The design calls for one translator per
transport; the exemption below lists the files currently claiming it, so the
number is visible and growth is deliberate rather than accidental.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = REPO_ROOT / "runtime"

TRANSPORT_LIBRARIES = {"discord", "matrix", "nio", "slack_sdk"}

# Files allowed to translate. Every entry is a transport adapter; anything else
# appearing here means the boundary moved and somebody should have noticed.
#
# `adapters/discord.py` is deliberately absent: it is named for Discord but
# translates duck-typed (`message: Any` plus `getattr`), so it needs no
# exemption. The stale-entry test below caught that on its first run, which is
# the whole argument for checking an exemption list rather than curating one.
ADAPTER_EXEMPT = {
    "adapters/lifecycle.py",
    "adapters/structural.py",
}


def _imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def _runtime_modules() -> list[Path]:
    return sorted(p for p in RUNTIME.rglob("*.py") if "__pycache__" not in p.parts)


class TransportBoundaryTests(unittest.TestCase):
    def test_runtime_does_not_import_a_transport_library(self) -> None:
        offenders: list[str] = []
        for path in _runtime_modules():
            rel = path.relative_to(RUNTIME).as_posix()
            if rel in ADAPTER_EXEMPT:
                continue
            leaked = _imported_top_level_modules(path) & TRANSPORT_LIBRARIES
            if leaked:
                offenders.append(f"{rel} imports {sorted(leaked)}")
        self.assertEqual(
            offenders,
            [],
            "runtime/ must stay transport-agnostic — translation belongs in "
            "runtime/adapters/. Offending modules:\n  " + "\n  ".join(offenders),
        )

    def test_the_exemption_list_has_no_stale_entries(self) -> None:
        """An exemption for a file that no longer needs it hides the next leak."""
        for rel in sorted(ADAPTER_EXEMPT):
            path = RUNTIME / rel
            self.assertTrue(path.is_file(), f"exempt file no longer exists: {rel}")
            self.assertTrue(
                _imported_top_level_modules(path) & TRANSPORT_LIBRARIES,
                f"{rel} is exempt but imports no transport library — drop the "
                "exemption so the boundary stays honest",
            )

    def test_the_guard_catches_a_real_leak(self) -> None:
        """Positive control. An empty offender list is not evidence of a guard.

        Written because today's sibling finding was a check whose negative
        control passed while the real path was broken.
        """
        source = "from __future__ import annotations\nimport discord\n"
        tree = ast.parse(source)
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
        self.assertTrue(found & TRANSPORT_LIBRARIES)

    def test_every_runtime_module_is_parseable_by_the_guard(self) -> None:
        """The guard must see the whole package, or it reports absence as health."""
        modules = _runtime_modules()
        self.assertGreater(len(modules), 5)
        for path in modules:
            _imported_top_level_modules(path)


class MessageValueObjectTests(unittest.TestCase):
    def setUp(self) -> None:
        from runtime.messages import Action, IncomingMessage

        self.Action = Action
        self.IncomingMessage = IncomingMessage

    def _incoming(self, **kwargs):
        base = dict(text="hi", practitioner_id="practitioner-a", channel_id="1000")
        base.update(kwargs)
        return self.IncomingMessage(**base)

    def test_messages_module_imports_no_transport_library(self) -> None:
        leaked = _imported_top_level_modules(RUNTIME / "messages.py") & TRANSPORT_LIBRARIES
        self.assertEqual(leaked, set())

    def test_identity_must_be_resolved_by_the_transport(self) -> None:
        with self.assertRaises(ValueError):
            self._incoming(practitioner_id="")

    def test_unknown_modality_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self._incoming(input_modality="telepathy")

    def test_conversation_id_prefers_the_thread(self) -> None:
        self.assertEqual(self._incoming().conversation_id, "1000")
        self.assertEqual(self._incoming(thread_id="2000").conversation_id, "2000")

    def test_live_voice_speaks_and_mirrors_where_it_can_be_read(self) -> None:
        from runtime.messages import OutgoingMessage

        incoming = self._incoming(input_modality="voice_live", mirror_eddy_id="7")
        reply = OutgoingMessage.answering(incoming, "here you go")
        self.assertTrue(reply.speak)
        self.assertEqual(reply.mirror_to_id, "7")

    def test_a_recorded_voice_message_answers_in_text_and_offers_to_read_aloud(self) -> None:
        from runtime.messages import OutgoingMessage

        reply = OutgoingMessage.answering(
            self._incoming(input_modality="voice_message"), "here you go"
        )
        self.assertFalse(reply.speak)
        self.assertIn("read_aloud", [a.key for a in reply.actions])

    def test_text_in_text_out_offers_nothing_extra(self) -> None:
        from runtime.messages import OutgoingMessage

        reply = OutgoingMessage.answering(self._incoming(), "here you go")
        self.assertFalse(reply.speak)
        self.assertEqual(reply.actions, ())

    def test_a_surface_without_buttons_renders_no_actions(self) -> None:
        from runtime.messages import OutgoingMessage

        reply = OutgoingMessage(
            text="…", actions=(self.Action(key="fetch_transcript", label="Fetch transcript"),)
        )
        rich = self._incoming()
        plain = self._incoming(affordances=frozenset({"threads"}))
        self.assertEqual(len(reply.renderable_actions(rich)), 1)
        self.assertEqual(reply.renderable_actions(plain), ())


if __name__ == "__main__":
    unittest.main()
