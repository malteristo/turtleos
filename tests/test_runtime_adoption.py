"""How much of `runtime/` production code actually uses — recorded, so it ratchets.

`tests/test_transport_boundary.py` proves that `runtime/` imports no platform SDK.
That is true, it is well built, and on 2026-08-14 an independent reviewer pointed
out it answers the wrong question:

> "The question is whether any Discord input reaches `runtime/`, and it does not —
> the seam is bypassed entirely by 40 modules that handle raw `discord.Message`
> objects. The guard is real, the boundary it guards is not load-bearing, and the
> guard's own excellence is what makes the illusion durable."

Verified the same day: `IncomingMessage` and `OutgoingMessage` appeared only in
their own module, the design chapter, and their own test. Five `runtime/` modules,
466 lines — tested, enforced, never executed — while the design chapter called
slice 1 "shipped."

This file exists so that fact is *recorded rather than noticed*. The numbers below
are a ledger, not a target: when a production path finally constructs a value
object, this test fails and someone lowers the number on purpose. That is the
ratchet. `ADAPTER_EXEMPT` in the boundary test works the same way, and the same
rule applies — the number must fall because something started using the runtime,
never because a file moved.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import quality_baseline  # noqa: E402

# Modules under `runtime/` that no production module imports.
# Lower this deliberately, with the commit that wires one up.
#
#   2026-08-14 (morning)  5 modules / 466 lines — the reviewer's finding
#   2026-08-14 (later)    3 modules / 241 lines — `messages.py` and
#                         `adapters/discord.py` became load-bearing when the link
#                         offer was routed through the seam
UNWIRED_MODULE_COUNT = 3
UNWIRED_LINE_COUNT = 241

# The two value objects the whole transport design rests on.
SEAM_TYPES = ("IncomingMessage", "OutgoingMessage")

# Production modules that cross the seam, as of 2026-08-14. This list should grow.
# It is asserted rather than merely counted because "some module somewhere uses it"
# is satisfiable by a module that only mentions the name in a comment, and because a
# path silently dropping back to raw `discord.Message` handling is the regression
# this file was created to catch.
SEAM_CROSSINGS = {
    "discord_render.py": ["IncomingMessage", "OutgoingMessage"],
    "link_read.py": ["IncomingMessage", "OutgoingMessage"],
}


def _production_files() -> list[Path]:
    return [
        p
        for p in REPO.rglob("*.py")
        if "venv" not in p.parts
        and "tests" not in p.parts
        and "runtime" not in p.parts
        and "scripts" not in p.parts
    ]


class RecordedAdoptionTests(unittest.TestCase):
    def test_the_unwired_count_matches_the_record(self) -> None:
        modules, lines = quality_baseline._runtime_adoption()
        self.assertEqual(
            (modules, lines),
            (UNWIRED_MODULE_COUNT, UNWIRED_LINE_COUNT),
            "runtime adoption changed. If it went DOWN, good — lower the constants "
            "in this file and say which production path now uses the runtime. If it "
            "went UP, a new runtime module was added that nothing calls, which is "
            "the thing this file exists to make visible.",
        )

    def test_the_seam_is_crossed_by_the_paths_that_claim_to(self) -> None:
        """Was `test_the_seam_types_are_still_unreachable`. It failed on purpose.

        Until 2026-08-14 no production module constructed either value object, and
        this test asserted that — so that the day one did, someone would have to
        come here and say which path. That day is this one: `post_link_offer` builds
        an `IncomingMessage` from the Discord message, asks
        `runtime.link_offers.link_offer_for` for an `OutgoingMessage`, and hands it
        to `discord_render` to post.

        The assertion is now the inverse and still a ratchet: these paths must keep
        crossing the seam, and new ones get added here deliberately.
        """
        reached = {}
        for path in _production_files():
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            hits = [t for t in SEAM_TYPES if t in text]
            if hits:
                reached[path.relative_to(REPO).as_posix()] = hits
        self.assertEqual(
            reached,
            SEAM_CROSSINGS,
            "the set of production paths crossing the transport seam changed. More "
            "is good — add it here. FEWER means a path went back to handling raw "
            "transport objects, which is the regression this file exists to catch.",
        )

    def test_the_crossing_is_a_real_construction_not_a_mention(self) -> None:
        """A name in a comment would satisfy the test above. This one needs a call.

        The bug being guarded against is the one that started all of this: a seam
        that is documented, tested and referenced, but never actually constructed.
        """
        import ast

        constructed: set[str] = set()
        for name in SEAM_CROSSINGS:
            tree = ast.parse((REPO / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                called = getattr(func, "attr", None) or getattr(func, "id", None)
                if called in SEAM_TYPES or called in {
                    "incoming_from_discord",
                    "link_offer_for",
                    "answering",
                    "renderable_actions",
                }:
                    constructed.add(name)
        self.assertEqual(
            constructed,
            set(SEAM_CROSSINGS),
            "a listed module references the seam types without ever calling into "
            f"them: {set(SEAM_CROSSINGS) - constructed}",
        )


class ClaimHonestyTests(unittest.TestCase):
    """The chapter may not call the seam adopted while this test still passes."""

    CHAPTER = REPO / "docs" / "chapters" / "design-transport-abstraction.md"

    def test_the_chapter_states_how_far_adoption_actually_goes(self) -> None:
        """The claim and the code have to move together, in both directions.

        This test used to require the words "no production importers", which was
        true when written and became false the moment the link offer was wired —
        a guard pinning a stale claim is the same defect as a claim with no guard.
        It now requires the chapter to name how many `runtime/` modules production
        still cannot reach, so the sentence cannot drift from the number.
        """
        text = self.CHAPTER.read_text(encoding="utf-8")
        self.assertIn(
            "no production importers",
            text,
            "the chapter must still say plainly which parts of the runtime nothing "
            "constructs — 'shipped' read as 'in use' to an outside reviewer",
        )
        self.assertIn(
            str(UNWIRED_MODULE_COUNT),
            text,
            f"the chapter must name the current count ({UNWIRED_MODULE_COUNT}) so "
            "the prose cannot drift away from the measurement",
        )
        self.assertIn(
            "One production path crosses the seam",
            text,
            "and it must state that adoption has begun, without overstating it",
        )

    def test_the_measure_is_reported_where_quality_is_judged(self) -> None:
        doc = (REPO / "docs" / "quality-measures.md").read_text(encoding="utf-8")
        self.assertIn("runtime lines unused", doc)


if __name__ == "__main__":
    unittest.main()
