"""River's heartbeat — river_heartbeat.py."""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parent.parent

from tests.discord_stub import install_discord_stub

install_discord_stub()

import river_heartbeat as hb  # noqa: E402
from river_heartbeat import Chore, record_discord_state, report_if_changed, tick  # noqa: E402

HOMES = {"10", "20"}


def _registry():
    return {
        "mages": {"kermit": {"discord_id": "1"}, "sam": {"discord_id": "2"}},
        "channels": {
            "10": {"type": "river", "mage": "kermit", "name": "river",
                   "discord_name": "home-kermit", "discord_category": "Rivers"},
            "20": {"type": "hosted-river", "mage": "sam", "name": "home-sam",
                   "discord_name": "home-sam", "discord_category": "Home"},
            "30": {"type": "shared-river", "mage": "family", "discord_category": "Practice"},
            "40": {"type": "hosted-river", "mage": "gone", "archived": True,
                   "discord_name": "home-gone"},
        },
    }


class RecordDiscordStateTests(unittest.TestCase):
    def test_the_registry_follows_what_discord_shows(self):
        # 2026-09-27: the operator renamed the category to "Home" and his own
        # channel to #home-kermit; the registry kept "Rivers" / "river" until
        # he was asked to run an admin command.
        registry = _registry()
        live = {"10": ("home-kermit", "Home"), "20": ("home-sam", "Home"),
                "30": ("family", "Practice"), "40": ("home-gone", "Archive")}
        changed = record_discord_state(registry, live, HOMES)
        rows = registry["channels"]
        self.assertEqual((rows["10"]["name"], rows["10"]["discord_category"]), ("home-kermit", "Home"))
        self.assertEqual(rows["30"]["discord_name"], "family")
        self.assertNotIn("name", rows["30"], "shared rooms keep their registry label")
        self.assertEqual(rows["40"]["discord_name"], "home-gone", "archived rows are left alone")
        self.assertEqual(len(changed), 2)

    def test_a_channel_discord_no_longer_has_is_not_touched(self):
        registry = _registry()
        self.assertEqual(record_discord_state(registry, {}, HOMES), [])
        self.assertEqual(registry["channels"]["10"]["discord_category"], "Rivers")

    def test_nothing_changes_when_in_step(self):
        registry = _registry()
        live = {"10": ("home-kermit", "Home"), "20": ("home-sam", "Home"), "30": ("family", "Practice")}
        record_discord_state(registry, live, HOMES)
        self.assertEqual(record_discord_state(registry, live, HOMES), [])


class TickTests(unittest.TestCase):
    def setUp(self):
        self.house = tempfile.TemporaryDirectory()
        p = patch.dict(os.environ, {"TURTLEOS_HOUSE_DIR": self.house.name})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.house.cleanup)

    def test_due_chores_run_and_the_beat_is_recorded(self):
        runs = []

        async def chore(client):
            runs.append(client)
            return "did a thing"

        report = AsyncMock()
        chores = [Chore("a", 60, chore)]
        asyncio.run(tick("C", chores, now=1000.0, report=report))
        asyncio.run(tick("C", chores, now=1030.0, report=report))
        asyncio.run(tick("C", chores, now=1061.0, report=report))
        self.assertEqual(len(runs), 2)
        self.assertEqual(report.await_count, 2)
        self.assertTrue(hb.heartbeat_is_fresh(now=1061.0 + 60))
        self.assertFalse(hb.heartbeat_is_fresh(now=1061.0 + hb.STALE_AFTER_SECONDS + 1))

    def test_a_failing_chore_is_recorded_and_the_others_still_run(self):
        async def boom(client):
            raise RuntimeError("no guild")

        async def fine(client):
            return None

        state = asyncio.run(tick(None, [Chore("boom", 60, boom), Chore("fine", 60, fine)], now=5.0))
        self.assertFalse(state["chores"]["boom"]["ok"])
        self.assertIn("no guild", state["chores"]["boom"]["error"])
        self.assertTrue(state["chores"]["fine"]["ok"])
        self.assertEqual(state["beat"], 5.0)

    def test_no_beat_is_stale(self):
        self.assertFalse(hb.heartbeat_is_fresh())

    def test_the_house_check_posts_only_when_its_findings_change(self):
        first = report_if_changed(["⚠️ a"])
        second = report_if_changed(["⚠️ a"])
        third = report_if_changed([])
        self.assertIn("⚠️ a", first)
        self.assertIsNone(second)
        self.assertIn("clear", third)

    def test_a_chore_that_never_ran_is_due_at_once(self):
        ran = []

        async def chore(client):
            ran.append(1)

        asyncio.run(tick(None, [Chore("hourly", 3600, chore)], now=10.0))
        self.assertEqual(ran, [1])

    def test_work_startup_already_did_waits_for_its_first_interval(self):
        ran = []

        async def chore(client):
            ran.append(1)

        chores = [Chore("rejoin", 1800, chore, first_after=1800)]
        asyncio.run(tick(None, chores, now=100.0, started=100.0))
        self.assertEqual(ran, [])
        self.assertIsNotNone(hb.read_state().get("beat"))
        asyncio.run(tick(None, chores, now=1901.0, started=100.0))
        self.assertEqual(ran, [1])

    def test_a_run_from_before_a_restart_does_not_skip_first_after(self):
        async def chore(client):
            pass

        asyncio.run(tick(None, [Chore("rejoin", 1800, chore)], now=50.0, started=50.0))
        ran = []

        async def again(client):
            ran.append(1)

        asyncio.run(tick(None, [Chore("rejoin", 1800, again, first_after=1800)], now=60.0, started=60.0))
        self.assertEqual(ran, [])

    def test_river_reports_through_its_own_client(self):
        # log_activity without channel= resolves through Turtle's client and is
        # refused in River's process (WRONG-CLIENT, 09-27): the report never posted.
        src = (Path(__file__).resolve().parents[1] / "river_bot.py").read_text()
        body = src.split("async def report(summary: str)", 1)[1].split("\n    _heartbeat_task", 1)[0]
        self.assertIn("river_client.get_channel", body)
        self.assertIn("channel=channel", body)

    def test_every_chore_the_house_relies_on_is_scheduled(self):
        # The bar sweep and offer loop used to be their own tasks in river_bot;
        # folding them in must not drop them.
        source = (ROOT / "river_bot.py").read_text(encoding="utf-8")
        body = source[source.index("def _house_chores():"):]
        for name in ("connection_offers", "eddy_bars", "discord_names", "shared_access",
                     "eddy_membership", "house_check", "cloud_credit", "missed_joins", "error_triage"):
            self.assertIn(f'Chore("{name}"', body)
        self.assertNotIn("_river_bar_safety_sweep_loop", source)
        self.assertNotIn("_mcp_offer_loop", source)
        self.assertIn("_start_heartbeat_once()", source)


class CanaryTests(unittest.TestCase):
    def test_the_canary_watches_the_heartbeat(self):
        source = (ROOT / "background.py").read_text(encoding="utf-8")
        loop = source[source.index("async def health_canary_loop"):source.index("def _canary_detail")]
        self.assertIn('checks["river_heartbeat"] = heartbeat_is_fresh()', loop)
        self.assertIn('check_name == "river_heartbeat"', source)


if __name__ == "__main__":
    unittest.main()
