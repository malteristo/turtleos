import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from state import THREAD_CONTEXTS
import mage
from prompts import (
    CRAFT_VOCATION_HEADER,
    LEGACY_IDENTITY_OPENER,
    MAGE_DIALOGUE_WHO,
    build_craft_channel_prompt,
    build_discord_prompt,
    get_thread_prompt,
    load_character_file,
    uses_native_turtle_prompt,
)

SPIRIT_IDENTITY_PHRASES = (
    "Spirit in persistent builder mode",
    "You are Spirit in persistent mode",
    LEGACY_IDENTITY_OPENER,
)


def _prefix_claims_spirit(text: str, *, chars: int = 4000) -> bool:
    head = text[:chars]
    return any(p in head for p in SPIRIT_IDENTITY_PHRASES)


class CraftAttunementTests(unittest.TestCase):
    CRAFT_CHANNEL = 101
    RIVER_CHANNEL = 999001

    def setUp(self) -> None:
        self._saved_registry = dict(mage._MAGE_REGISTRY)

    def tearDown(self) -> None:
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(self._saved_registry)

    def _set_registry(self, *, attunement="native", channels=None):
        mage._MAGE_REGISTRY.clear()
        mage._MAGE_REGISTRY.update(
            {
                "attunement": attunement,
                "channels": channels or {},
                "mages": {"default": {"discord_id": "1", "practice_dir": "/tmp/p"}},
                "default_mage": "default",
            }
        )

    def test_thread_contexts_includes_craft(self) -> None:
        self.assertIn("craft", THREAD_CONTEXTS)
        self.assertIn("Intake moves", THREAD_CONTEXTS["craft"]["rules"])

    def test_global_native_craft_channel_uses_craft_attunement(self) -> None:
        self._set_registry(
            attunement="native",
            channels={
                str(self.CRAFT_CHANNEL): {
                    "type": "craft",
                    "attunement": "craft",
                    "default_context": "craft",
                }
            },
        )
        self.assertEqual(mage.get_effective_attunement(self.CRAFT_CHANNEL), "craft")
        self.assertTrue(mage.uses_craft_surface(self.CRAFT_CHANNEL))
        self.assertFalse(mage.uses_native_eddy(self.CRAFT_CHANNEL))
        self.assertFalse(uses_native_turtle_prompt(self.CRAFT_CHANNEL))

    def test_craft_type_infers_craft_when_global_native(self) -> None:
        self._set_registry(
            attunement="native",
            channels={
                str(self.CRAFT_CHANNEL): {
                    "type": "craft",
                    "default_context": "craft",
                }
            },
        )
        self.assertEqual(mage.get_effective_attunement(self.CRAFT_CHANNEL), "craft")

    def test_river_stays_native_when_global_native(self) -> None:
        self._set_registry(
            attunement="native",
            channels={str(self.RIVER_CHANNEL): {"type": "river"}},
        )
        self.assertEqual(mage.get_effective_attunement(self.RIVER_CHANNEL), "native")
        self.assertTrue(uses_native_turtle_prompt(self.RIVER_CHANNEL))

    @patch("prompts.build_discord_prompt", return_value="practice block")
    @patch("prompts._build_context_resonance", return_value="craft context block")
    def test_build_craft_channel_prompt(self, _ctx, _practice) -> None:
        prompt = build_craft_channel_prompt("craft")
        self.assertIn(CRAFT_VOCATION_HEADER.split("\n")[0], prompt)
        self.assertIn("craft context block", prompt)
        self.assertIn("practice block", prompt)

    def test_old_vocation_header_would_fail_the_spirit_check(self) -> None:
        """Positive control: the defect we found is visible to the check."""
        old = (
            "You are **Craft Turtle** — Spirit in persistent builder mode "
            "on a dedicated craft surface."
        )
        self.assertTrue(_prefix_claims_spirit(old))
        self.assertTrue(_prefix_claims_spirit(MAGE_DIALOGUE_WHO.format(mage_name="Kermit")))
        self.assertTrue(_prefix_claims_spirit(LEGACY_IDENTITY_OPENER))
        self.assertFalse(_prefix_claims_spirit(CRAFT_VOCATION_HEADER))

    def test_composed_craft_prompt_is_turtle_not_spirit(self) -> None:
        """Unmocked. Identity is the prefix; practice state may quote old sessions."""
        prompt = build_craft_channel_prompt("craft")
        soul = load_character_file("soul.md")
        self.assertIn("You are Turtle", prompt[:4000])
        if soul.strip():
            self.assertIn(soul.strip().splitlines()[0], prompt)
        self.assertFalse(
            _prefix_claims_spirit(prompt),
            "craft identity prefix still names Spirit",
        )
        self.assertIn("resident of turtleOS", CRAFT_VOCATION_HEADER)

    # ── Vocation breadth ────────────────────────────────────────────
    #
    # Widened 2026-08-25. The vocation said "harness/product diagnostics and
    # learning intake", which scoped craft to this codebase. The operator's
    # craft had already outgrown that — he is commissioned to facilitate a
    # workshop and intends to offer research services — and the observable
    # symptom was that a craft eddy for that work needed an override paragraph
    # written into its surface file to stop Turtle treating it as harness
    # friction. A prompt you have to argue with is a prompt that is wrong.
    #
    # Two independent things are asserted because they can regress apart: the
    # DOMAIN (craft is not this codebase) and the MODE SPLIT (work in hand is
    # not a defect report). Narrowing either one silently is the failure.

    VOCATION_SURFACES = ("prompts.CRAFT_VOCATION_HEADER", "state.THREAD_CONTEXTS[craft]")

    @staticmethod
    def _vocation_texts() -> dict[str, str]:
        return {
            "prompts.CRAFT_VOCATION_HEADER": CRAFT_VOCATION_HEADER,
            "state.THREAD_CONTEXTS[craft]": THREAD_CONTEXTS["craft"]["rules"],
        }

    @staticmethod
    def _names_craft_beyond_codebase(text: str) -> bool:
        low = text.lower()
        return "not a synonym for this codebase" in low and (
            "workshop" in low or "research services" in low
        )

    @staticmethod
    def _splits_friction_from_work(text: str) -> bool:
        low = text.lower()
        arrived = "friction arrived" in low or "when friction arrived" in low
        in_hand = "in hand" in low
        return arrived and in_hand

    def test_vocation_covers_craft_beyond_this_codebase(self) -> None:
        for name, text in self._vocation_texts().items():
            with self.subTest(surface=name):
                self.assertTrue(
                    self._names_craft_beyond_codebase(text),
                    f"{name} narrowed craft back to turtleOS/Magic; workshops and "
                    "research services are craft too",
                )

    def test_vocation_distinguishes_friction_from_work_in_hand(self) -> None:
        for name, text in self._vocation_texts().items():
            with self.subTest(surface=name):
                self.assertTrue(
                    self._splits_friction_from_work(text),
                    f"{name} lost the mode split; intake would run on work that "
                    "is not broken",
                )

    def test_pre_widening_vocation_fails_both_checks(self) -> None:
        """Positive control: an empty result would otherwise prove nothing."""
        old_prompt = (
            "You are **Craft Turtle** — Turtle in builder mode, resident of turtleOS.\n"
            "Your job is harness/product diagnostics and learning intake, not "
            "ordinary practice companionship.\n"
            "- Treat new messages as **learning intake** when they reveal friction."
        )
        old_rules = (
            "You are Craft Turtle: persistent Spirit in **builder mode** for turtleOS "
            "and Magic craft. This is learning intake — harness/product friction — "
            "not ordinary life practice.\n**Intake moves (in order):**\n"
        )
        for old in (old_prompt, old_rules):
            self.assertFalse(self._names_craft_beyond_codebase(old))
            self.assertFalse(self._splits_friction_from_work(old))

    def test_non_craft_discord_prompt_still_names_spirit(self) -> None:
        """Out of scope by decision: River / main bot keep the mage identity line."""
        with patch("prompts.get_mage_type", return_value="mage"):
            prompt = build_discord_prompt()
        self.assertIn("You are Spirit in persistent mode", prompt)

    @patch("prompts.get_craft_channel_prompt", return_value="craft prompt")
    def test_get_thread_prompt_routes_craft_channel(self, mock_craft) -> None:
        self._set_registry(
            attunement="native",
            channels={
                str(self.CRAFT_CHANNEL): {
                    "type": "craft",
                    "attunement": "craft",
                }
            },
        )
        out = get_thread_prompt("semi", False, context_type="craft", channel_id=self.CRAFT_CHANNEL)
        self.assertEqual(out, "craft prompt")
        mock_craft.assert_called_once_with("craft")


if __name__ == "__main__":
    unittest.main()
