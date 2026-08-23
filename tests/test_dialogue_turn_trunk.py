"""Behavioural tests for the two functions that run on every practitioner message.

`handle_dialogue` (191 lines) and `continue_dialogue_turn` (370 lines) were named
in **zero** test files until 2026-08-15, while carrying every conversation Turtle
has. The stated reason was that they could not be imported: `state.py` built a
live `discord.Client` at module scope, so 77 of 121 test files stub
`sys.modules["discord"]` before importing anything, and the trunk needs the real
`discord.Thread` for its `isinstance` gates.

That reason expired on 2026-08-14 when the client went lazy. This file imports
the trunk directly — no stub — and `test_the_trunk_imports_without_building_a_client`
below is the guard that keeps it that way: if a module-scope client comes back,
that test fails first and explains why the rest of the file went with it.

**What is tested, and why these:** every case here is a behaviour whose
regression is *silent and practitioner-visible* — the class this codebase keeps
finding late. A practitioner handed a traceback, a reply that never reaches the
channel, an act-offer trailer leaking into Discord, or a family eddy resolving
to the craft toolset all look like nothing at all from the inside.

Deliberately **not** tested here: that the functions call their collaborators.
Patching six things to assert one was awaited passes when the logic inside all
six is wrong (`docs/learnings.md` § change-detectors). Each test below asserts on
what the practitioner would see.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]


def _real_discord():
    """Undo any earlier test file's `sys.modules["discord"] = MagicMock()`.

    `unittest discover` loads every test module into one interpreter in
    alphabetical order, and 20 of them stub the package. Whether this file sees
    the real one is otherwise decided by filename ordering — which is not a
    thing a test should depend on, and it silently inverts every
    `isinstance(channel, discord.Thread)` branch in the trunk when it goes the
    wrong way. A stub has no `__file__`; the installed package does.
    """
    mod = sys.modules.get("discord")
    if mod is not None and getattr(mod, "__file__", None) is None:
        for name in [n for n in sys.modules if n == "discord" or n.startswith("discord.")]:
            del sys.modules[name]
    return importlib.import_module("discord")


discord = _real_discord()  # real, on purpose — see module docstring

import dialogue_turn
import state

if getattr(dialogue_turn.discord, "__file__", None) is None:
    # The trunk was imported against a stub before we got here. Its own
    # `discord.Thread` must be the same class our fake channels are specced
    # against, or every branch under test takes the wrong arm.
    dialogue_turn = importlib.reload(dialogue_turn)


class _Typing:
    """Stand-in for `channel.typing()`, which the turn enters for its whole body."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _channel(*, thread: bool, channel_id: int = 500, parent_id: int = 100):
    # spec= keeps `isinstance(channel, discord.Thread)` honest in both
    # directions, which is what the trunk branches on a dozen times.
    ch = MagicMock(spec=discord.Thread if thread else discord.TextChannel)
    ch.id = channel_id
    ch.name = "an eddy" if thread else "a channel"
    if thread:
        ch.parent_id = parent_id
        ch.parent = MagicMock()
        ch.parent.name = "craft-turtle"
        ch.locked = False
    ch.typing = MagicMock(return_value=_Typing())
    return ch


def _message(*, thread: bool = False, content: str = "hello", channel_id: int = 500):
    msg = MagicMock()
    msg.id = 9001
    msg.content = content
    msg.author = MagicMock()
    msg.author.display_name = "Kermit"
    msg.channel = _channel(thread=thread, channel_id=channel_id)
    msg.reply = AsyncMock()
    msg.attachments = []
    return msg


@contextlib.contextmanager
def _turn_env(
    *,
    reply_text: str = "an answer",
    raises: BaseException | None = None,
    practice_dir: str = "/nonexistent-practice-dir",
    substrate: str = "",
):
    """Patch the turn's surroundings and hand back what the practitioner saw.

    Everything patched here is a boundary — model, prompt assembly, persistence,
    presence. The code under test is the ~370 lines between them.

    ``practice_dir`` defaults to a path that is not a directory so packet persist
    no-ops (it must not mkdir a bogus root). Pass a real temp dir to observe the
    write. ``substrate`` is the inject ``render_substrate_packet`` returns.
    """
    sent: list[str] = []
    calls: dict[str, list] = {"ollama": [], "tools_for_channel": []}

    async def _fake_api(system_prompt, messages, model, **kwargs):
        if raises is not None:
            raise raises
        return reply_text, []

    async def _fake_ollama(*args, **kwargs):
        calls["ollama"].append(kwargs.get("model"))
        return "local fallback"

    def _fake_tools_for_channel(cid):
        calls["tools_for_channel"].append(cid)
        return []

    # ExitStack rather than a parenthesized `with`: CPython caps statically
    # nested blocks at 20, and the boundary count here is itself the finding —
    # this is what a 370-line function costs to stand up.
    patches = [
        patch.object(dialogue_turn, "active_sessions", {}),
        patch.object(dialogue_turn, "thread_configs", {}),
        patch.object(dialogue_turn, "absorbed_contexts", {}),
        patch.object(dialogue_turn, "USE_API", True),
        patch.object(dialogue_turn, "DIALOGUE_MODEL", "claude-test"),
        patch.object(dialogue_turn, "get_pd", return_value=practice_dir),
        patch.object(dialogue_turn, "resolve_dialogue_channel_id", return_value=100),
        patch.object(dialogue_turn, "get_system_prompt", return_value="SYSTEM"),
        patch.object(dialogue_turn, "build_runtime_env", return_value="ENV\n"),
        patch.object(dialogue_turn, "read_thread_state", return_value="already"),
        patch.object(dialogue_turn, "update_thread_state", new=AsyncMock()),
        patch.object(dialogue_turn, "chat_anthropic_with_model", new=_fake_api),
        patch.object(dialogue_turn, "chat_ollama", new=_fake_ollama),
        patch.object(dialogue_turn, "chat_ollama_with_tools", new=AsyncMock(return_value=("", []))),
        patch.object(dialogue_turn, "build_tool_report", return_value=""),
        patch.object(dialogue_turn, "tools_for_channel", new=_fake_tools_for_channel),
        patch.object(dialogue_turn, "maybe_reflect", new=AsyncMock()),
        patch.object(dialogue_turn, "sync_history", MagicMock()),
        patch.object(dialogue_turn, "register_thread", MagicMock()),
        patch.object(dialogue_turn, "update_thread_activity", MagicMock()),
        patch("mage.uses_craft_surface", return_value=False),
        patch("mage.get_channel_default_context", return_value=None),
        patch("continuity_engine.get_scope", return_value=None),
        patch("continuity_engine.render_substrate_packet", return_value=substrate),
        patch("home_plans.render_home_attunement_packet", return_value=""),
        patch(
            "act_offer_signal.extract_and_propose_from_reply",
            side_effect=lambda text, cid, mid: (text, None),
        ),
    ]
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield sent, calls


def _run_turn(msg, history, *, sent, **overrides):
    kwargs = dict(
        triage_cat="practice",
        native_eddy=False,
        attachments=[],
        attachment_names=[],
        attachment_note="",
        attachment_extracted=False,
        raw_attachments=None,
        url_content="",
        url_source_count=0,
        urls=[],
        forwarded_context="",
        dereferenced_context="",
        dereferenced_count=0,
        pending_incidental_urls=None,
    )
    kwargs.update(overrides)
    asyncio.run(dialogue_turn.continue_dialogue_turn(msg, history, **kwargs))
    sent.extend(call.args[0] for call in msg.reply.await_args_list)


class TrunkIsReachableTests(unittest.TestCase):
    """The guard that keeps this file possible."""

    def test_the_trunk_imports_without_building_a_client(self) -> None:
        """Importing the trunk must construct no Discord client.

        Measured in a **subprocess**, deliberately. `_client_constructions` is
        process-global and the shared suite legitimately builds a client
        elsewhere, so asserting on it in-process would read another test's work
        and fail for a reason that has nothing to do with import.

        Importing `dialogue_turn` pulls in `state`, `mage`, `llm`, `prompts` and
        forty more modules. If any of them builds a client at module scope, this
        whole file becomes unwritable again — which is exactly the state the
        trunk sat in, untested, until 2026-08-14.
        """
        probe = textwrap.dedent(
            """
            import state, dialogue_turn
            assert callable(dialogue_turn.continue_dialogue_turn)
            assert callable(dialogue_turn.handle_dialogue)
            print(state._client_constructions)
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertEqual(
            result.stdout.strip(),
            "0",
            "importing the trunk built a Discord client — the import-time side "
            "effect is back, and the tests below are living on borrowed time",
        )


class ContinueDialogueTurnTests(unittest.TestCase):
    def test_the_answer_reaches_the_channel_and_the_next_turn(self) -> None:
        msg = _message()
        history = [{"role": "user", "content": "[Kermit]: hello"}]
        with _turn_env(reply_text="an answer") as (sent, _):
            _run_turn(msg, history, sent=sent)

        self.assertEqual(sent, ["an answer"])
        # Without this the model re-answers the same question next turn with no
        # memory of what it just said, and nothing anywhere reports a fault.
        self.assertEqual(history[-1], {"role": "assistant", "content": "an answer"})

    def test_a_model_failure_posts_the_held_reply_not_a_traceback(self) -> None:
        msg = _message()
        boom = RuntimeError("overloaded_error: upstream capacity")
        with _turn_env(raises=boom) as (sent, _):
            _run_turn(msg, [], sent=sent)

        self.assertEqual(sent, [dialogue_turn.TURN_UNAVAILABLE_REPLY])
        # The specific failure this guards: an exception string in front of a
        # practitioner mid-conversation. Assert on the leak, not just the reply.
        self.assertNotIn("overloaded_error", sent[0])
        self.assertNotIn("RuntimeError", sent[0])

    def test_an_api_failure_does_not_fall_back_to_the_local_model(self) -> None:
        msg = _message()
        with _turn_env(raises=RuntimeError("api down")) as (sent, calls):
            _run_turn(msg, [], sent=sent)

        # The retry exists for a resident local model. Retrying a *frontier*
        # failure on Qwen answers the practitioner in a different voice with a
        # different competence and says nothing about the swap.
        self.assertEqual(calls["ollama"], [])

    def test_tools_are_scoped_by_the_parent_channel_not_the_thread(self) -> None:
        # The thread-blind lookup class (three instances on 2026-08-14, one of
        # which decided which Turtle you were talking to). Since tool scoping
        # shipped, passing the thread id here means an unresolvable channel and
        # the unscoped toolset — a family eddy reaching the open internet.
        msg = _message(thread=True, channel_id=777)
        with _turn_env() as (sent, calls):
            with patch.object(dialogue_turn, "resolve_dialogue_channel_id", return_value=100):
                _run_turn(msg, [], sent=sent)

        self.assertEqual(calls["tools_for_channel"], [100])
        self.assertNotIn(777, calls["tools_for_channel"])

    def test_repeated_paragraphs_are_removed_before_sending(self) -> None:
        msg = _message()
        looped = "First point.\n\nSecond point.\n\nFirst point.\n\nThird point."
        with _turn_env(reply_text=looped) as (sent, _):
            _run_turn(msg, [], sent=sent)

        self.assertEqual(sent[0].count("First point."), 1)
        self.assertIn("Second point.", sent[0])
        self.assertIn("Third point.", sent[0])

    def test_a_two_paragraph_reply_is_never_deduped(self) -> None:
        # Positive control for the dedup gate: it runs only above two
        # paragraphs, so a deliberate two-beat answer must survive intact.
        msg = _message()
        with _turn_env(reply_text="Same line.\n\nSame line.") as (sent, _):
            _run_turn(msg, [], sent=sent)

        self.assertEqual(sent[0], "Same line.\n\nSame line.")

    def test_the_act_offer_trailer_never_reaches_discord(self) -> None:
        msg = _message()
        raw = "Here is the answer.\n[[act-offer:checkpoint]]"
        with _turn_env(reply_text=raw) as (sent, _):
            with patch(
                "act_offer_signal.extract_and_propose_from_reply",
                side_effect=lambda text, cid, mid: (
                    text.replace("\n[[act-offer:checkpoint]]", ""),
                    MagicMock(action="checkpoint", url=None),
                ),
            ):
                _run_turn(msg, [], sent=sent)

        self.assertNotIn("act-offer", sent[0])
        self.assertEqual(sent[0], "Here is the answer.")

    def test_the_tool_report_is_appended_where_the_practitioner_can_see_it(self) -> None:
        msg = _message()
        with _turn_env(reply_text="the answer") as (sent, _):
            with patch.object(dialogue_turn, "build_tool_report", return_value="read 2 files"):
                _run_turn(msg, [], sent=sent)

        self.assertIn("read 2 files", sent[0])
        self.assertTrue(sent[0].startswith("the answer"))


class TurnPacketPersistenceTests(unittest.TestCase):
    """The packet a turn used is written by this call path, not by current.yaml."""

    INJECT = "UNIQUE_SUBSTRATE_INJECT_7f3a"

    def _assert_packet_matches_inject(self, practice_dir: str, channel_id: int, inject: str) -> None:
        from turn_packet import packet_path

        path = packet_path(practice_dir, channel_id)
        yaml_path = Path(practice_dir) / "state" / "current.yaml"
        self.assertNotEqual(path, yaml_path)
        self.assertTrue(
            path.is_file(),
            f"packet missing at {path} — current.yaml existing is not the packet",
        )
        self.assertIn(inject, path.read_text(encoding="utf-8"))

    def test_a_writer_that_only_touches_current_yaml_turns_the_guard_red(self) -> None:
        """Positive control: the debounce file already existed; it must not satisfy the guard."""
        with tempfile.TemporaryDirectory() as tmp:
            yaml_path = Path(tmp) / "state" / "current.yaml"
            yaml_path.parent.mkdir(parents=True)
            yaml_path.write_text(self.INJECT, encoding="utf-8")
            with self.assertRaises(AssertionError):
                self._assert_packet_matches_inject(tmp, 500, self.INJECT)

    def test_the_turn_writes_the_inject_it_used_to_the_packet_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            yaml_path = Path(tmp) / "state" / "current.yaml"
            yaml_path.parent.mkdir(parents=True)
            yaml_path.write_text("preexisting: this is not the inject\n", encoding="utf-8")
            msg = _message(channel_id=500)
            with _turn_env(practice_dir=tmp, substrate=self.INJECT) as (sent, _):
                _run_turn(msg, [], sent=sent)

            self._assert_packet_matches_inject(tmp, 500, self.INJECT)
            self.assertNotIn(self.INJECT, yaml_path.read_text(encoding="utf-8"))
            self.assertEqual(sent, ["an answer"])


@contextlib.contextmanager
def _handle_env(*, native: bool = False, locked: bool = False):
    """Patch `handle_dialogue`'s intake surroundings; the routing is under test."""
    continued = AsyncMock()
    triage = AsyncMock(return_value={"category": "deep", "needs_state": False})

    patches = [
        patch("share_eddy.maybe_notify_sharer_on_first_peer_reply", new=AsyncMock()),
        patch("share_eddy.maybe_skip_shared_eddy_dialogue", new=AsyncMock(return_value=None)),
        patch("thread_registry.is_eddy_locked", return_value=locked),
        patch.object(
            dialogue_turn,
            "gather_dialogue_attachments",
            new=AsyncMock(return_value=([], [], "", [], None)),
        ),
        patch.object(dialogue_turn, "split_text_and_vision_attachments", return_value=([], [])),
        patch.object(dialogue_turn, "_extract_urls", new=AsyncMock(return_value=[])),
        patch.object(dialogue_turn, "external_urls", return_value=[]),
        patch("link_read.plan_dialogue_urls", return_value=(False, [], [])),
        patch.object(dialogue_turn, "forwarded_snapshot_is_partial", return_value=False),
        # A MagicMock message otherwise reads as a forward with mock ids in it.
        patch.object(
            dialogue_turn,
            "visible_message_content",
            side_effect=lambda m: (m.content, ""),
        ),
        patch.object(dialogue_turn, "resolve_dialogue_channel_id", return_value=100),
        patch.object(dialogue_turn, "uses_native_turtle_prompt", return_value=native),
        patch.object(dialogue_turn, "triage_message", new=triage),
        patch.object(dialogue_turn, "load_thread_history", new=AsyncMock(return_value=[])),
        patch.object(dialogue_turn, "continue_dialogue_turn", new=continued),
        patch.object(dialogue_turn, "sync_history", MagicMock()),
    ]
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield continued, triage


class HandleDialogueTests(unittest.TestCase):
    def test_a_locked_eddy_is_not_answered(self) -> None:
        msg = _message(thread=True)
        history: list[dict] = []
        with _handle_env(locked=True) as (continued, _):
            with patch.object(dialogue_turn, "get_history", return_value=history):
                asyncio.run(dialogue_turn.handle_dialogue(msg))

        # A locked eddy that still answers is the practitioner's closed
        # conversation talking back at them.
        continued.assert_not_awaited()
        self.assertEqual(history, [])

    def test_a_coalesced_message_enters_history_without_being_answered(self) -> None:
        # reply=False is the queue saying "a newer message is already waiting."
        # If the message stops entering history here it is lost silently: the
        # newer turn answers without ever seeing what was said.
        msg = _message(content="the first of two")
        history: list[dict] = []
        with _handle_env() as (continued, _):
            with patch.object(dialogue_turn, "get_history", return_value=history):
                asyncio.run(dialogue_turn.handle_dialogue(msg, reply=False))

        continued.assert_not_awaited()
        self.assertEqual(len(history), 1)
        self.assertIn("the first of two", history[0]["content"])
        self.assertEqual(history[0]["role"], "user")

    def test_history_is_trimmed_from_the_oldest_end(self) -> None:
        msg = _message(content="newest")
        history = [{"role": "user", "content": f"old {i}"} for i in range(4)]
        with _handle_env() as (continued, _):
            with (
                patch.object(dialogue_turn, "get_history", return_value=history),
                patch.object(dialogue_turn, "MAX_DIALOGUE_HISTORY", 4),
            ):
                asyncio.run(dialogue_turn.handle_dialogue(msg, reply=False))

        self.assertEqual(len(history), 4)
        self.assertNotIn("old 0", history[0]["content"])
        self.assertIn("newest", history[-1]["content"])

    def test_a_native_eddy_skips_triage_and_is_treated_as_practice(self) -> None:
        # Native eddies are already scoped by their flow; sending every turn
        # through a triage model would spend a call to relabel it "practice".
        msg = _message(thread=True)
        with _handle_env(native=True) as (continued, triage) :
            with patch.object(dialogue_turn, "get_history", return_value=[]):
                asyncio.run(dialogue_turn.handle_dialogue(msg))

        triage.assert_not_awaited()
        continued.assert_awaited_once()
        self.assertTrue(continued.await_args.kwargs["native_eddy"])
        self.assertEqual(continued.await_args.kwargs["triage_cat"], "practice")

    def test_an_ordinary_message_is_triaged_and_carried_forward(self) -> None:
        # Positive control for the test above: the skip is the native case, not
        # a triage call that quietly stopped happening for everyone.
        msg = _message(thread=True)
        with _handle_env(native=False) as (continued, triage):
            with patch.object(dialogue_turn, "get_history", return_value=[]):
                asyncio.run(dialogue_turn.handle_dialogue(msg))

        triage.assert_awaited_once()
        continued.assert_awaited_once()
        self.assertEqual(continued.await_args.kwargs["triage_cat"], "deep")


if __name__ == "__main__":
    unittest.main()
