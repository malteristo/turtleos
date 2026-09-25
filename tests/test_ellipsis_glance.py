"""`...` glance — River buttons, Turtle still talks, bar stays, parent river unchanged."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ui", __import__("unittest.mock").mock.MagicMock())

import eddy_lifecycle_bar as bar


class GlanceGestureTests(unittest.TestCase):
    def test_exactly_three_dots_is_the_glance(self) -> None:
        self.assertTrue(bar.is_ellipsis_glance("..."))
        self.assertTrue(bar.is_ellipsis_glance("  ...  "))

    def test_an_aimed_glance_is_the_glance(self) -> None:
        self.assertTrue(bar.is_ellipsis_glance("... later"))
        self.assertTrue(bar.is_ellipsis_glance("... craft"))
        self.assertEqual(bar.glance_toward("... later"), "later")
        self.assertEqual(bar.glance_toward("..."), "")

    def test_the_breath_is_not_the_glance(self) -> None:
        for text in (".", "..", "....", "go", "continue", "next", ".. later"):
            self.assertFalse(bar.is_ellipsis_glance(text), text)

    def test_go_is_dot_or_aimed_dot(self) -> None:
        self.assertTrue(bar.is_go_breath("."))
        self.assertTrue(bar.is_go_breath(". turtle"))
        self.assertTrue(bar.is_go_breath("  . outfacing  "))
        for text in ("..", "...", "... later", "go", "continue"):
            self.assertFalse(bar.is_go_breath(text), text)


class GlanceEligibilityTests(unittest.TestCase):
    def test_craft_parent_is_eligible(self) -> None:
        with patch("mage.supports_eddy_bar", return_value=True):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=False):
                self.assertTrue(bar.glance_eligible(11, 22))

    def test_intake_wait_is_not_eligible(self) -> None:
        with patch("mage.supports_eddy_bar", return_value=True):
            with patch("eddy_spawn.is_awaiting_flow_intake", return_value=True):
                self.assertFalse(bar.glance_eligible(11, 22))

    def test_no_parent_is_not_eligible(self) -> None:
        self.assertFalse(bar.glance_eligible(11, None))


class SharedActListTests(unittest.TestCase):
    def test_live_is_not_bootstrap_reordered(self) -> None:
        with patch("flow_runner.list_flow_ids_for_bar_phase", return_value=["navigator"]):
            boot = bar.lifecycle_act_labels("bootstrap")
            live = bar.lifecycle_act_labels("live")
        self.assertEqual(boot, ["flow"])
        self.assertEqual(live, ["flow", "checkpoint", "share"])
        self.assertNotEqual(boot, live)

    def test_bar_and_glance_use_the_same_labels(self) -> None:
        src = Path("eddy_lifecycle_bar.py").read_text(encoding="utf-8")
        bar_block = src.split("class EddyLifecycleBarView", 1)[1].split(
            "class EddyGlanceView", 1
        )[0]
        glance_block = src.split("class EddyGlanceView", 1)[1].split(
            "async def post_ellipsis_glance", 1
        )[0]
        self.assertIn("lifecycle_act_labels", bar_block)
        self.assertIn("lifecycle_act_labels", glance_block)

    def test_standing_bar_stays_on(self) -> None:
        self.assertTrue(bar.standing_lifecycle_bar_enabled())


class ParentRiverAliasTests(unittest.TestCase):
    def test_parent_river_does_not_treat_ellipsis_as_go_on(self) -> None:
        src = Path("river_handler.py").read_text(encoding="utf-8")
        self.assertNotIn(
            'content in {".", "..", "...", "go", "continue", "next"}',
            src,
        )
        self.assertIn("is_ellipsis_glance", src)
        self.assertIn("post_parent_river_glance", src)
        self.assertIn("is_go_breath", src)

    def test_old_parent_alias_would_fail(self) -> None:
        """Positive control: `...` in the breath set is the retired alias."""
        stale = 'content in {".", "..", "...", "go", "continue", "next"}'
        src = Path("river_handler.py").read_text(encoding="utf-8")
        self.assertNotEqual(stale in src, True)

    def test_a_planted_bar_off_fails_this_slice(self) -> None:
        """Positive control: hiding the bar this chapter is the defect."""
        self.assertTrue(bar.standing_lifecycle_bar_enabled())


class RiverInterceptTests(unittest.TestCase):
    def test_river_posts_the_glance_before_the_touch(self) -> None:
        src = Path("river_bot.py").read_text(encoding="utf-8")
        thread_branch = src.split("if isinstance(message.channel, discord.Thread):", 1)[1]
        glance_at = thread_branch.find("is_ellipsis_glance")
        touch_at = thread_branch.find("touch_eddy_lifecycle_bar")
        self.assertGreater(glance_at, -1)
        self.assertGreater(touch_at, glance_at)
        before_touch = thread_branch[:touch_at]
        self.assertIn("post_ellipsis_glance", before_touch)
        self.assertIn("post_ellipsis_memory", before_touch)
        self.assertIn("return", before_touch[glance_at:])
        memory_at = before_touch.find("post_ellipsis_memory")
        self.assertGreater(memory_at, before_touch.find("post_ellipsis_glance"))


class TimedGlanceIsNotPersistentTests(unittest.TestCase):
    def test_glance_post_does_not_register_a_timed_view(self) -> None:
        """add_view rejects timeout=180. That crash skipped Memory (2026-09-05)."""
        src = Path("eddy_lifecycle_bar.py").read_text(encoding="utf-8")
        block = src.split("async def post_ellipsis_glance", 1)[1].split(
            "def _glance_reach_text", 1
        )[0]
        self.assertIn("timeout=GLANCE_TIMEOUT", src)
        self.assertNotIn("client.add_view", block)

    def test_memory_still_runs_if_the_buttons_fail(self) -> None:
        src = Path("river_bot.py").read_text(encoding="utf-8")
        glance = src.split("if is_ellipsis_glance", 1)[1]
        glance = glance.split("from eddy_spawn", 1)[0]
        self.assertIn("post_ellipsis_memory", glance)
        self.assertLess(glance.find("except"), glance.find("post_ellipsis_memory"))

    def test_go_does_not_schedule_a_contextual_offer(self) -> None:
        src = Path("river_bot.py").read_text(encoding="utf-8")
        thread_branch = src.split("if isinstance(message.channel, discord.Thread):", 1)[1]
        go_at = thread_branch.find("is_go_breath")
        sched_at = thread_branch.find("_maybe_schedule_contextual_offer")
        self.assertGreater(go_at, -1)
        self.assertGreater(sched_at, go_at)
        go_block = thread_branch[go_at:sched_at]
        self.assertIn("return", go_block)


class MemoryMouthTests(unittest.TestCase):
    def test_memory_card_is_visible_and_logs_quiet(self) -> None:
        src = Path("eddy_lifecycle_bar.py").read_text(encoding="utf-8")
        block = src.split("async def post_ellipsis_memory", 1)[1].split(
            "class EddyDissolveConfirmView", 1
        )[0]
        self.assertIn('f"**Memory**\\n{body}"', block)
        self.assertNotIn('f"-# Memory\\n{body}"', block)
        self.assertIn("Ellipsis memory glance quiet", block)
        self.assertIn("Ellipsis memory glance posted", block)


if __name__ == "__main__":
    unittest.main()
