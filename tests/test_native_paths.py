"""A `!` command is for what the system does not do natively (his rule, 2026-10-14).

`!fetch` and `!date` were retired because Turtle reads a pasted link and keeps a date
said in words. A retirement that left the native path thin would be a capability lost,
so each claim below has its mechanism, and each mechanism a positive control.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import act_offer_signal as aos
import cmd_dispatch
import dates as fd
import help_card


class TypedDoorsAnswerOnceTests(unittest.IsolatedAsyncioTestCase):
    def _message(self, text):
        m = MagicMock()
        m.content = text
        m.author = SimpleNamespace(id=1)
        m.channel = SimpleNamespace(id=5)
        m.reply = AsyncMock()
        return m

    async def _typed(self, text, locale="en"):
        m = self._message(text)
        with patch("room_models.locale_for", return_value=locale):
            handled = await cmd_dispatch.try_direct_command(m)
        return handled, m

    async def test_typed_fetch_and_date_say_where_they_went(self):
        for text, needle in (
            ("!fetch https://example.com/a", "Paste the link"),
            ("!date 24.12. kita fest", "tell me the date"),
        ):
            handled, m = await self._typed(text)
            self.assertTrue(handled, text)
            self.assertIn(needle, m.reply.await_args.args[0], text)

    async def test_every_retired_command_answers_once_in_both_languages(self):
        """The whole table, not the two that were written first (the class, then the case)."""
        for name in help_card.RETIRED:
            for locale in ("en", "de"):
                handled, m = await self._typed(f"!{name} something", locale=locale)
                self.assertTrue(handled, name)
                m.reply.assert_awaited_once()
                self.assertIn(f"!{name}", m.reply.await_args.args[0], (name, locale))
        self.assertNotIn("{cmd}", help_card.retired_answer("new", locale="de"))

    async def test_german_gets_german(self):
        handled, m = await self._typed("!fetch https://example.com/a", locale="de")
        self.assertTrue(handled)
        self.assertIn("Füg den Link", m.reply.await_args.args[0])

    async def test_the_typed_door_never_runs_the_act(self):
        from commands import DIRECT_COMMANDS

        fetch = AsyncMock(return_value="fetched")
        with patch.dict(DIRECT_COMMANDS, {"fetch": fetch}):
            handled, _ = await self._typed("!fetch https://example.com/a")
        self.assertTrue(handled)
        fetch.assert_not_awaited()

    async def test_positive_control_a_live_command_is_not_caught(self):
        self.assertIsNone(help_card.retired_answer("status"))
        self.assertIsNone(help_card.retired_answer("dissolve"))

    def test_the_save_button_still_has_its_act(self):
        """The typed door closed; the offer button runs the same act by handler."""
        from commands import DIRECT_COMMANDS

        self.assertIn("fetch", DIRECT_COMMANDS)
        self.assertIn("fetch", cmd_dispatch.CONTEXTUAL_ACTION_COMMANDS)
        self.assertNotIn("date", DIRECT_COMMANDS, "nothing runs the typed date any more")

    def test_a_shut_door_has_no_room_behind_it(self):
        """Only `!fetch` keeps a handler, because a button runs it. Anything else is dead code."""
        from commands import DIRECT_COMMANDS

        self.assertEqual(help_card.handlers_left(DIRECT_COMMANDS), frozenset())
        self.assertEqual(
            help_card.RETIRED_KEEPS_ACT,
            frozenset({"fetch", "read", "artifacts", "export", "share", "keep", "ignore", "checkpoint"}),
        )
        # Positive control: the guard does see a handler that was left behind.
        self.assertEqual(
            help_card.handlers_left({**DIRECT_COMMANDS, "focus": object()}), frozenset({"focus"})
        )

    def test_a_retired_command_is_neither_listed_nor_a_member_command(self):
        for name in help_card.RETIRED:
            self.assertNotIn(name, help_card.listed_commands())
            self.assertNotIn(name, cmd_dispatch._PRACTITIONER_COMMANDS)
            for locale in ("en", "de"):
                self.assertTrue(help_card.retired_answer(name, locale=locale))


class NoRetiredNameIsSpokenTests(unittest.TestCase):
    """The class behind the case: a retired command still named in words a person reads.

    A button payload (`"!read path"`) is not prose and is exempt; prose names a command
    in backticks. Docstrings are for the next developer, not for a person, so they are
    skipped (a docstring may say what a retired command used to do).
    """

    ROOT = Path(__file__).resolve().parent.parent
    SKIP_DIRS = {"tests", "venv", "scripts", "autoresearch", "__pycache__", "docs", "issues", "test-runs"}
    EXEMPT_FILES = {"help_card.py"}  # the table that names them

    def _pattern(self):
        import re

        names = "|".join(re.escape(n) for n in sorted(help_card.RETIRED, key=len, reverse=True))
        return re.compile(rf"`!(?:{names})(?![\w-])")

    def _strings(self, source: str):
        import ast

        tree = ast.parse(source)
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                first = node.body[0] if node.body else None
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    docstrings.add(id(first.value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                yield node.lineno, node.value

    def test_no_prose_names_a_retired_command(self):
        pattern = self._pattern()
        hits = []
        for path in self.ROOT.rglob("*.py"):
            rel = path.relative_to(self.ROOT)
            if set(rel.parts) & self.SKIP_DIRS or path.name in self.EXEMPT_FILES or any(part.startswith(".") for part in rel.parts):
                continue
            for lineno, text in self._strings(path.read_text(encoding="utf-8")):
                if pattern.search(text):
                    hits.append(f"{rel}:{lineno}")
        self.assertEqual(hits, [], "prose still tells a person to type a retired command")

    def test_positive_control_the_scan_sees_one(self):
        pattern = self._pattern()
        self.assertTrue(any(pattern.search(t) for _, t in self._strings('x = "Use `!read <path>` for that"')))
        self.assertFalse(any(pattern.search(t) for _, t in self._strings('x = "!read notes/a.md"')))
        self.assertFalse(any(pattern.search(t) for _, t in self._strings('x = "Use `!pin` here"')))


class KeepDateSignalTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        runtime = Path(self._tmp.name)
        p = patch("mage.get_runtime_dir", return_value=str(runtime))
        p.start()
        self.addCleanup(p.stop)
        aos.clear_act_offer_signal()

    def test_a_date_survives_the_trip_from_turtle_to_river(self):
        aos.propose_act_offer(
            42, 7, "keep_date", title="Anna's birthday", when="2026-11-03", recurrence="yearly", birth_year=1990
        )
        intent = aos.consume_act_offer(42, 7)
        assert intent is not None
        self.assertEqual(
            (intent.action, intent.title, intent.when, intent.recurrence, intent.birth_year),
            ("keep_date", "Anna's birthday", "2026-11-03", "yearly", 1990),
        )

    def test_a_date_that_is_not_a_date_is_refused(self):
        for bad in ("next thursday", "2026-13-40", "", "24.12."):
            with self.assertRaises(ValueError, msg=bad):
                aos.propose_act_offer(42, 7, "keep_date", title="x", when=bad)

    def test_a_date_without_a_title_or_with_a_wild_year_is_refused(self):
        with self.assertRaises(ValueError):
            aos.propose_act_offer(42, 7, "keep_date", title="  ", when="2026-11-03")
        with self.assertRaises(ValueError):
            aos.propose_act_offer(42, 7, "keep_date", title="x", when="2026-11-03", birth_year=1066)
        with self.assertRaises(ValueError):
            aos.propose_act_offer(42, 7, "keep_date", title="x", when="2026-11-03", recurrence="weekly")

    def test_the_tool_path_queues_it(self):
        with aos.act_offer_turn_context(42, 7):
            said = aos.propose_act_offer_from_tool(
                "keep_date", title="dentist", when="2026-10-22"
            )
        self.assertIn("keep_date 2026-10-22 dentist", said)
        self.assertIsNotNone(aos.consume_act_offer(42, 7))

    def test_the_tool_path_reports_a_refusal_in_words(self):
        with aos.act_offer_turn_context(42, 7):
            said = aos.propose_act_offer_from_tool("keep_date", title="dentist", when="Thursday")
        self.assertIn("Offer rejected", said)
        self.assertIsNone(aos.consume_act_offer(42, 7))

    def test_the_local_trailer_carries_a_date_with_and_without_recurrence(self):
        reply, intent = aos.extract_and_propose_from_reply(
            "Noted.\n[[act-offer:keep_date 2026-11-03 yearly Anna's birthday]]", 42, 7
        )
        self.assertEqual(reply, "Noted.")
        assert intent is not None
        self.assertEqual((intent.recurrence, intent.title), ("yearly", "Anna's birthday"))
        _, plain = aos.extract_and_propose_from_reply(
            "Ok.\n[[act-offer:keep_date 2026-10-22 dentist at nine]]", 42, 8
        )
        assert plain is not None
        self.assertEqual((plain.recurrence, plain.title), ("none", "dentist at nine"))

    def test_a_trailer_with_no_real_date_posts_nothing_and_is_still_stripped(self):
        reply, intent = aos.extract_and_propose_from_reply(
            "Ok.\n[[act-offer:keep_date thursday dentist]]", 42, 9
        )
        self.assertIsNone(intent)
        self.assertEqual(reply, "Ok.")

    def test_checkpoint_and_save_are_unchanged(self):
        _, intent = aos.extract_and_propose_from_reply("x\n[[act-offer:save https://e.com/a]]", 42, 10)
        assert intent is not None
        self.assertEqual((intent.action, intent.url), ("save", "https://e.com/a"))

    def test_turtle_is_told_about_it(self):
        """A capability Turtle is never told of is a declaration without a reader."""
        import tos_tools
        import prompts

        schema = next(
            t for t in tos_tools.TOS_TOOLS if t["function"]["name"] == "offer_river_act"
        )["function"]["parameters"]["properties"]
        for field in ("title", "when", "recurrence", "birth_year"):
            self.assertIn(field, schema)
        self.assertIn("keep_date", prompts.NATIVE_EDDY_DISCORD_HINT)
        full = prompts.build_discord_prompt()
        self.assertIn("keep_date", full)
        import re

        for name in help_card.RETIRED:
            # `[Act: !fetch]` names the act in the digest; the typed command is what is gone.
            pattern = re.compile(rf"(?<!Act: )!{re.escape(name)}(?![\w-])")
            self.assertIsNone(pattern.search(full), f"the prompt advertises retired !{name}")
            self.assertIsNone(pattern.search(prompts.NATIVE_EDDY_DISCORD_HINT), name)
        # Positive control: the pattern does catch an advertised command, and spares `!dates`.
        self.assertTrue(re.search(r"!date(?![\w-])", "use !date now"))
        self.assertFalse(re.search(r"!date(?![\w-])", "use !dates now"))
        self.assertIsNone(re.compile(r"(?<!Act: )!fetch(?![\w-])").search("after [Act: !fetch] discuss"))


class KeepAndIgnoreAreSaidNotTypedTests(unittest.IsolatedAsyncioTestCase):
    """`!keep` and `!ignore` were typed; now Turtle offers them and River draws the button."""

    def test_turtle_may_offer_them_and_nothing_else_new(self):
        for action in ("keep", "ignore"):
            kind, err = aos.validate_offer_args(action)
            self.assertEqual((kind, err), (action, None))
        kind, err = aos.validate_offer_args("purge")
        self.assertIsNone(kind)
        self.assertIn("keep", err)
        for body, action in (("keep", "keep"), ("ignore", "ignore")):
            cleaned, got, _ = aos.parse_act_offer_trailer(f"Sure.\n[[act-offer:{body}]]")
            self.assertEqual((cleaned, got), ("Sure.", action))

    def test_river_draws_a_button_whose_press_runs_the_handler(self):
        import river_eddy_seneschal as res
        from commands import DIRECT_COMMANDS

        for action, command, label in (
            ("keep", "!keep", "Keep this eddy"),
            ("ignore", "!ignore", "Don't remember this"),
        ):
            intent = aos.ActOfferIntent(action=action, practitioner_message_id=1)
            offer = res._offer_from_turtle_intent(intent)
            self.assertEqual(offer.actions, [(label, command)])
            name = command[1:]
            self.assertIn(name, DIRECT_COMMANDS, "the press runs this handler")
            self.assertIn(name, cmd_dispatch.CONTEXTUAL_ACTION_COMMANDS, "the button gate")

    def test_turtle_is_told_about_them(self):
        import prompts
        import tos_tools

        full = prompts.build_discord_prompt()
        for needle in ("`keep`", "`ignore`", "act-offer:ignore"):
            self.assertIn(needle, full)
        # A native eddy is built from its own hint, not from the Acts section above:
        # a capability told to one prompt and not the other is a declaration with no reader.
        for needle in ("action=keep", "action=ignore"):
            self.assertIn(needle, prompts.NATIVE_EDDY_DISCORD_HINT)
        text = next(t for t in tos_tools.TOS_TOOLS if t["function"]["name"] == "offer_river_act")["function"]
        self.assertIn("ignore", text["description"])

    async def _ignore(self, args):
        import cmd_sessions as cs

        class FakeThread:
            id = 700
            parent_id = 5
            name = "an eddy"

        message = MagicMock()
        message.channel = FakeThread()
        message.author = SimpleNamespace(id=9)
        message.reply = AsyncMock()
        purge = AsyncMock()
        send = AsyncMock()
        with patch.object(cs.discord, "Thread", FakeThread), patch.object(
            cs, "is_practice_channel", return_value=True
        ), patch("runtime.adapters.lifecycle.purge_ignored_eddy", purge), patch(
            "thread_registry.update_thread_continuity"
        ), patch("cmd_dispatch.send_with_actions", send):
            await cs.cmd_ignore(message, args)
        return message, purge, send

    async def test_ignore_asks_with_a_button_and_removes_nothing_until_it_is_pressed(self):
        import state

        state.pending_ignore_confirm.clear()
        message, purge, send = await self._ignore([])
        purge.assert_not_awaited()
        send.assert_awaited_once()
        self.assertEqual(send.await_args.args[2], [("Leave no trace", "!ignore confirm")])
        # The press is the second call.
        message, purge, send = await self._ignore(["confirm"])
        purge.assert_awaited_once()

    async def test_positive_control_a_confirm_with_no_question_removes_nothing(self):
        import state

        state.pending_ignore_confirm.clear()
        message, purge, send = await self._ignore(["confirm"])
        purge.assert_not_awaited()
        self.assertIn("Nothing to confirm", message.reply.await_args.args[0])


class RiverDrawsTheDateButtonTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_intent_becomes_a_keep_offer_with_what_turtle_read(self):
        import river_eddy_seneschal as res

        intent = aos.ActOfferIntent(
            action="keep_date",
            practitioner_message_id=7,
            title="Anna's birthday",
            when="2026-11-03",
            recurrence="yearly",
            birth_year=1990,
        )
        source = MagicMock()
        channel = MagicMock()
        channel.fetch_message = AsyncMock(return_value=source)
        offer = AsyncMock(return_value=True)
        with (
            patch("dates.offer_date_keep", offer),
            patch("dates.locale_for_practice_dir", return_value="en"),
            patch("mage.get_pd", return_value="/tmp/none"),
        ):
            ok = await res._offer_keep_date_from_intent(channel, intent, 7)
        self.assertTrue(ok)
        commitment = offer.await_args.args[1]
        self.assertEqual(
            (commitment.when, commitment.title, commitment.recurrence, commitment.birth_year),
            (date(2026, 11, 3), "Anna's birthday", "yearly", 1990),
        )
        self.assertIs(offer.await_args.args[0], source, "the button answers the message he wrote")

    async def test_nothing_is_kept_until_the_button_is_pressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            import river_eddy_seneschal as res

            intent = aos.ActOfferIntent(
                action="keep_date", practitioner_message_id=7, title="x", when="2026-11-03"
            )
            channel = MagicMock()
            channel.fetch_message = AsyncMock(return_value=MagicMock(reply=AsyncMock(), channel=MagicMock(id=1)))
            with patch("mage.get_pd", return_value=tmp), patch("dates.locale_for_practice_dir", return_value="en"):
                await res._offer_keep_date_from_intent(channel, intent, 7)
            self.assertEqual(fd.list_dates(tmp), [])


class DatesAreInTheTurnTests(unittest.TestCase):
    def test_a_birthday_months_away_can_be_answered(self):
        with tempfile.TemporaryDirectory() as tmp:
            today = date(2026, 10, 14)
            far = today + timedelta(days=200)
            fd.add_date(tmp, title="Anna's birthday", when=far.isoformat(), today=today)
            near = fd.render_upcoming_dates_context(tmp, today=today)
            self.assertNotIn("Anna", near, "positive control: the old 30-day window cannot answer it")
            year = fd.render_upcoming_dates_context(tmp, today=today, within_days=366, limit=15)
            self.assertIn("Anna's birthday", year)

    def test_the_turn_carries_the_dates(self):
        import continuity_engine as ce

        with tempfile.TemporaryDirectory() as tmp:
            soon = date.today() + timedelta(days=90)
            fd.add_date(tmp, title="Tomorrow-ish dentist", when=soon.isoformat(), today=date.today())
            block = ce.render_substrate_packet(tmp)
            self.assertIn("Tomorrow-ish dentist", block)
            self.assertNotIn("Tomorrow-ish dentist", ce.render_substrate_packet(tempfile.mkdtemp()))


if __name__ == "__main__":
    unittest.main()
