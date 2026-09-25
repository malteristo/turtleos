"""Spoken River requests become displays, not classify-and-hope."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from river_display import (
    channel_menu_specs,
    filter_records_by_days,
    likely_thread_action,
    parse_display_request,
    thread_button_specs,
    threads_title,
)


class ParseDisplayRequestTests(unittest.TestCase):
    def test_threads_last_five_days(self) -> None:
        act = parse_display_request("show me threads from the last 5 days")
        self.assertEqual(act, {"type": "show_threads", "days": 5})

    def test_waiting_wins_over_threads(self) -> None:
        self.assertEqual(
            parse_display_request("what eddies are waiting"),
            {"type": "show_waiting"},
        )
        self.assertEqual(
            parse_display_request("where's the heat"),
            {"type": "show_waiting"},
        )
        self.assertEqual(
            parse_display_request("what's ready for a session"),
            {"type": "show_waiting"},
        )

    def test_strips_river_address_and_mention(self) -> None:
        act = parse_display_request("River, show me threads from the last 5 days")
        self.assertEqual(act["days"], 5)
        self.assertEqual(parse_display_request("<@123> show threads last week")["days"], 7)

    def test_channel_menu(self) -> None:
        self.assertEqual(
            parse_display_request("show me the channel menu"),
            {"type": "show_channel_menu"},
        )
        self.assertEqual(
            parse_display_request("what can I do here"),
            {"type": "show_channel_menu"},
        )

    def test_ordinary_river_drop_is_not_a_display(self) -> None:
        self.assertIsNone(parse_display_request("hi"))
        self.assertIsNone(
            parse_display_request("i keep starting projects and never finishing them")
        )


class ThreadDisplayHelpersTests(unittest.TestCase):
    def test_gone_has_no_action(self) -> None:
        self.assertEqual(likely_thread_action("gone"), "")
        self.assertEqual(likely_thread_action("live"), "Open")
        self.assertEqual(likely_thread_action("resting"), "Open")

    def test_days_filter_keeps_recent_only(self) -> None:
        records = [
            {"name": "new", "age_seconds": 3600, "state": "live", "thread_id": "1"},
            {"name": "old", "age_seconds": 10 * 86400, "state": "live", "thread_id": "2"},
        ]
        kept = filter_records_by_days(records, 5)
        self.assertEqual([row["name"] for row in kept], ["new"])

    def test_buttons_are_name_only_links(self) -> None:
        specs = thread_button_specs(
            [
                {
                    "name": "talking",
                    "state": "live",
                    "thread_id": "11",
                    "age_seconds": 60,
                },
                {
                    "name": "closed",
                    "state": "gone",
                    "thread_id": "22",
                    "age_seconds": 60,
                },
            ],
            guild_id=99,
        )
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["label"], "talking")
        self.assertNotIn("Open", specs[0]["label"])
        self.assertNotIn("11", specs[0]["label"])
        self.assertEqual(specs[0]["url"], "https://discord.com/channels/99/11")

    def test_glance_body_is_one_list_not_a_button_echo(self) -> None:
        from river_display import compose_thread_glance_body

        body = compose_thread_glance_body(
            [
                {"state": "live", "line": "**new eddy** · 1h", "name": "new eddy"},
                {"state": "live", "line": "**older** · 2d", "name": "older"},
                {"state": "resting", "line": "**asleep** · 12d", "name": "asleep"},
            ]
        )
        self.assertIn("new eddy", body)
        self.assertIn("older", body)
        self.assertIn("1 parked", body)
        self.assertNotIn("Open", body)

    def test_waiting_body_is_whose_move_not_an_inventory(self) -> None:
        from river_display import compose_waiting_body, waiting_title

        rows = [
            {"name": "ready one", "state": "ready", "line": "**ready one** · session"},
            {"name": "held one", "state": "waiting", "line": "**held one** · you"},
        ]
        body = compose_waiting_body(rows)
        self.assertIn("ready one", body)
        self.assertIn("session", body)
        self.assertNotIn("SECRET", body)
        self.assertEqual(waiting_title(rows), "Waiting — 2")
        self.assertEqual(waiting_title([]), "Waiting — none")
        self.assertIn("Nothing is waiting", compose_waiting_body([]))

    def test_window_line_is_counts_not_names(self) -> None:
        from river_display import river_window_line

        line = river_window_line(
            [
                {
                    "name": "SECRET-EDDY",
                    "state": "live",
                    "age_seconds": 3600,
                },
                {
                    "name": "old-secret",
                    "state": "live",
                    "age_seconds": 10 * 86400,
                },
                {
                    "name": "parked-secret",
                    "state": "resting",
                    "age_seconds": 3600,
                },
            ],
            parent_name="craft-turtle",
        )
        self.assertIn("#craft-turtle: 1 live in the last 5 days", line)
        self.assertIn("survey_eddies opens the list", line)
        self.assertIn("Do not recite", line)
        self.assertNotIn("SECRET-EDDY", line)
        self.assertNotIn("old-secret", line)
        self.assertNotIn("parked-secret", line)

    def test_title_names_the_window(self) -> None:
        grouped = {"live": ["a"], "kept": [], "sealed": [], "resting": [], "gone": []}
        self.assertIn("last 5d", threads_title(grouped, 5))

    def test_channel_menu_uses_declared_controls(self) -> None:
        specs = channel_menu_specs(("new_eddy", "threads", "artifacts"))
        self.assertEqual([row["id"] for row in specs], ["new_eddy", "threads", "artifacts"])
        self.assertEqual(channel_menu_specs(("mystery",)), [])


class HandleSpokenDisplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_thread_request_skips_classify(self) -> None:
        from river_handler import handle_river_message

        message = MagicMock()
        message.content = "show me threads from the last 5 days"
        message.attachments = []
        message.author.display_name = "Kermit"
        message.channel = MagicMock()

        with patch("river_handler.classify_river_acts", new_callable=AsyncMock) as classify, patch(
            "river_handler.render_acts", new_callable=AsyncMock, return_value={"acts": [], "views": 1}
        ) as render, patch("river_handler._river_client_for_channel", return_value=None):
            await handle_river_message(message)
            classify.assert_not_awaited()
            acts = render.await_args.args[1]
            self.assertEqual(acts, [{"type": "show_threads", "days": 5}])

    async def test_waiting_request_skips_classify(self) -> None:
        from river_handler import handle_river_message

        message = MagicMock()
        message.content = "what's waiting"
        message.attachments = []
        message.author.display_name = "Kermit"
        message.channel = MagicMock()

        with patch("river_handler.classify_river_acts", new_callable=AsyncMock) as classify, patch(
            "river_handler.render_acts", new_callable=AsyncMock, return_value={"acts": [], "views": 1}
        ) as render, patch("river_handler._river_client_for_channel", return_value=None):
            await handle_river_message(message)
            classify.assert_not_awaited()
            self.assertEqual(render.await_args.args[1], [{"type": "show_waiting"}])

    async def test_craft_thought_files_intake_without_classify(self) -> None:
        from river_handler import handle_river_message

        message = MagicMock()
        message.content = "I want harvest acts without a button"
        message.attachments = []
        message.author.display_name = "Kermit"
        message.channel = MagicMock()

        with patch("craft_intake.is_craft_intake_channel", return_value=True), patch(
            "river_handler.classify_river_acts", new_callable=AsyncMock
        ) as classify, patch(
            "river_handler.render_acts",
            new_callable=AsyncMock,
            return_value={"acts": ["file_intake"], "views": 0},
        ) as render, patch("river_handler._river_client_for_channel", return_value=None):
            await handle_river_message(message)
            classify.assert_not_awaited()
            self.assertEqual(render.await_args.args[1], [{"type": "file_intake"}])


class SettleParentActsTests(unittest.TestCase):
    def test_craft_without_display_files_intake(self) -> None:
        from river_display import settle_parent_acts

        self.assertEqual(
            settle_parent_acts([], craft=True),
            [{"type": "file_intake"}],
        )
        self.assertEqual(
            settle_parent_acts([{"type": "acknowledge"}], craft=True),
            [{"type": "file_intake"}],
        )

    def test_display_wins_over_craft_default(self) -> None:
        from river_display import settle_parent_acts

        acts = [{"type": "show_threads", "days": 5}]
        self.assertEqual(settle_parent_acts(acts, craft=True), acts)
        waiting = [{"type": "show_waiting"}]
        self.assertEqual(settle_parent_acts(waiting, craft=True), waiting)

    def test_private_river_does_not_file(self) -> None:
        from river_display import settle_parent_acts

        self.assertEqual(settle_parent_acts([], craft=False), [])


class CraftControlsTests(unittest.TestCase):
    def test_craft_declares_threads_health_does_not_declare_artifacts(self) -> None:
        from channel_primitives import primitive_definition

        craft = primitive_definition("craft")
        health = primitive_definition("health")
        self.assertIn("threads", craft.parent_controls)
        self.assertIn("new_eddy", health.parent_controls)
        self.assertNotIn("artifacts", health.parent_controls)


class TurtleWindowPacketTests(unittest.TestCase):
    def test_runtime_env_names_the_window_not_the_eddies(self) -> None:
        import dialogue_runtime

        thread_type = type("Thread", (), {})
        orig = dialogue_runtime.discord.Thread
        dialogue_runtime.discord.Thread = thread_type
        parent = MagicMock()
        parent.name = "craft-turtle"
        parent.id = 1
        parent.threads = []
        channel = MagicMock()
        channel.__class__ = thread_type
        channel.parent = parent
        channel.id = 2
        channel.name = "this eddy"
        message = MagicMock()
        message.channel = channel
        message.author.display_name = "Kermit"
        planted = [
            {
                "name": "SECRET-EDDY",
                "state": "live",
                "age_seconds": 60,
                "line": "SECRET-EDDY",
            }
        ]
        try:
            with patch("dialogue_runtime.get_mage_name", return_value="Kermit"), patch(
                "dialogue_runtime.get_mage_key", return_value="kermit"
            ), patch(
                "dialogue_runtime.get_current_channel_primitive", return_value=None
            ), patch(
                "dialogue_runtime.get_thread_awareness", return_value="live"
            ), patch(
                "dialogue_runtime.read_thread_state", return_value=""
            ), patch(
                "dialogue_runtime.get_related_thread_awareness", return_value=""
            ), patch(
                "thread_registry.load_registry", return_value={"threads": {}}
            ), patch(
                "cmd_threads.collect_five_state_thread_records",
                return_value=planted,
            ):
                env = dialogue_runtime.build_runtime_env(message, None)
        finally:
            dialogue_runtime.discord.Thread = orig

        self.assertIn("1 live in the last 5 days", env)
        self.assertIn("survey_eddies", env)
        self.assertNotIn("SECRET-EDDY", env)


if __name__ == "__main__":
    unittest.main()
