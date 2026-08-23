"""The layering ratchet: the tangle may shrink, never grow.

`docs/chapters/design-layer-boundaries.md` states the rule this file defends.
The short version: the module-level import graph is acyclic (227 edges, zero
cycles), and adding back the 308 imports written inside function bodies collapses
**50 of 95 modules into one strongly connected component**. Those deferred
imports are not a style choice; they are what keeps a cyclic graph from raising
at boot.

The ceilings below are *recorded facts about 2026-08-15*, not targets. They may
be **lowered** by a change that removes a dependency, and lowering them is the
point. A change that needs them raised is a change that made the tangle worse,
and it should have to say so in the diff.

This is the transport boundary's lesson applied in the other order. There, a
sentence in `runtime/__init__.py` claimed an architecture for 100 days and was
worth nothing until a test made violating it impossible — then `runtime lines
unused by production` ratcheted 466 → 241 because a number nobody could fudge
was attached to it. Here the check and the baseline land *before* any module
moves, so every later move is either visible in the number or was not a move.
"""

from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import import_graph  # noqa: E402


# Measured 2026-08-15. Lower these; do not raise them.
#
# **Re-baselined once, the same day, and the reason is the only one that ever
# licenses a raise.** The first ceilings (cycle 50, fan-in 61) measured the flat
# root namespace only. Creating `core/` exposed the flaw: a module moved into a
# package left the measured universe, so a `git mv` would have read as progress
# — a structural measure a rename can improve is measuring the directory tree,
# not the structure. The instrument now counts packages too, the universe grew
# from 95 modules to 114, and the numbers grew with it. Nothing about the
# codebase got worse between those two readings.
#
# Two of the three modules the cycle gained are `runtime/adapters/lifecycle` and
# `runtime/adapters/structural` — the transport seam's own adapters, entangled
# with the root component and invisible to the previous baseline.
#
# Any future raise needs a reason of that kind, written here. "The number went
# up" is not one.
LARGEST_RUNTIME_CYCLE = 53
HUB_FAN_IN = 63
HUB_MODULE = "mage"


class BaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = import_graph.measure()

    def test_nothing_imports_in_a_circle_at_boot(self) -> None:
        """An invariant, not a ratchet — and the one the deferred imports buy.

        If this ever fails, the bot does not start, so it is enforced by reality
        already. It is here as the counterweight to the next test: the honest
        reading of `0` is *the cycles were moved*, not *there are no cycles*.
        """
        self.assertEqual(
            self.data["import_time_cycles"],
            0,
            "a module-level import cycle will raise ImportError at boot",
        )

    def test_the_runtime_cycle_does_not_grow(self) -> None:
        size = self.data["largest_runtime_cycle"]
        self.assertLessEqual(
            size,
            LARGEST_RUNTIME_CYCLE,
            f"the largest mutual-dependency component grew to {size} modules "
            f"(recorded ceiling {LARGEST_RUNTIME_CYCLE}). Layering is a proposal "
            "to break this component; a change that enlarges it is moving the "
            "wrong way. Lower the ceiling when you remove a dependency.",
        )

    def test_the_hub_does_not_grow(self) -> None:
        """`mage` is imported by 61 of 95 modules — the single largest coupling."""
        self.assertEqual(self.data["hub_module"], HUB_MODULE)
        self.assertLessEqual(
            self.data["hub_fan_in"],
            HUB_FAN_IN,
            f"{HUB_MODULE} gained importers (now {self.data['hub_fan_in']}, "
            f"ceiling {HUB_FAN_IN}). Every new importer is another edge the "
            "layer rule will have to cut.",
        )

    def test_the_ceilings_are_not_stale(self) -> None:
        """A ceiling far above the real number stops being a ratchet.

        The failure this prevents is the quiet one: somebody removes fifty edges,
        never lowers the ceiling, and the guard goes on passing through the next
        fifty that get added back.
        """
        self.assertGreaterEqual(
            self.data["largest_runtime_cycle"],
            LARGEST_RUNTIME_CYCLE,
            f"the cycle shrank to {self.data['largest_runtime_cycle']} — good. "
            f"Lower LARGEST_RUNTIME_CYCLE to match and keep the ratchet tight.",
        )
        self.assertGreaterEqual(
            self.data["hub_fan_in"],
            HUB_FAN_IN,
            f"{HUB_MODULE} fan-in fell to {self.data['hub_fan_in']} — good. "
            f"Lower HUB_FAN_IN to match.",
        )


class DetectorTests(unittest.TestCase):
    """Positive controls. A cycle finder that finds nothing proves nothing."""

    def _measure(self, files: dict[str, str]):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, body in files.items():
                (root / name).write_text(textwrap.dedent(body), encoding="utf-8")
            return import_graph.measure(root)

    def test_a_cycle_hidden_in_a_function_body_is_found(self) -> None:
        # The whole point of the instrument: this graph boots fine and is still
        # a cycle. Reading only module-level imports reports it as clean.
        data = self._measure(
            {
                "alpha.py": "import beta\n\ndef go():\n    return beta\n",
                "beta.py": "def go():\n    import alpha\n    return alpha\n",
            }
        )
        self.assertEqual(data["import_time_cycles"], 0)
        self.assertEqual(data["runtime_cycles"], 1)
        self.assertEqual(data["largest_runtime_cycle"], 2)
        self.assertEqual(data["deferred_edges"], 1)

    def test_a_module_level_cycle_is_reported_at_boot(self) -> None:
        data = self._measure(
            {
                "alpha.py": "import beta\n",
                "beta.py": "import alpha\n",
            }
        )
        self.assertEqual(data["import_time_cycles"], 1)
        self.assertEqual(data["deferred_edges"], 0)

    def test_a_straight_line_is_not_a_cycle(self) -> None:
        # Negative control: without this, a detector that calls everything a
        # cycle would pass both tests above.
        data = self._measure(
            {
                "alpha.py": "import beta\n",
                "beta.py": "import gamma\n",
                "gamma.py": "x = 1\n",
            }
        )
        self.assertEqual(data["import_time_cycles"], 0)
        self.assertEqual(data["runtime_cycles"], 0)
        self.assertEqual(data["largest_runtime_cycle"], 0)

    def test_third_party_and_relative_imports_are_not_local_edges(self) -> None:
        # `from . import x` cannot name a sibling top-level module, and counting
        # `import json` as an edge would inflate every number in this file.
        data = self._measure(
            {
                "alpha.py": "import json\nfrom . import something\nimport beta\n",
                "beta.py": "import os\n",
            }
        )
        self.assertEqual(data["module_level_edges"], 1)
        self.assertEqual(data["distinct_edges"], 1)

    def test_moving_a_module_into_a_package_does_not_hide_it(self) -> None:
        """The anti-gaming control, and the reason the ceilings were re-baselined.

        If the measure only saw the flat root namespace, `git mv alpha core/`
        would shrink every number in this file without removing one dependency.
        The cycle below crosses the package boundary in both directions and must
        still be found.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "core").mkdir()
            (root / "core" / "__init__.py").write_text("", encoding="utf-8")
            (root / "alpha.py").write_text(
                "from core import beta\n\ndef go():\n    return beta\n", encoding="utf-8"
            )
            (root / "core" / "beta.py").write_text(
                "def go():\n    import alpha\n    return alpha\n", encoding="utf-8"
            )
            data = import_graph.measure(root)

        # Three nodes: `alpha`, the package `core` (its `__init__`), `core.beta`.
        self.assertEqual(data["modules"], 3)
        self.assertEqual(data["root_modules"], 1)
        self.assertEqual(data["packaged_modules"], 2)
        # `from core import beta` names the module in the alias, not the module
        # field — resolving only the latter would land the edge on the package.
        self.assertEqual(data["runtime_cycles"], 1)
        self.assertEqual(data["largest_runtime_cycle"], 2)
        self.assertIn("core.beta", data["largest_runtime_cycle_members"])

    def test_a_module_importing_itself_is_not_an_edge(self) -> None:
        data = self._measure({"alpha.py": "def go():\n    import alpha\n    return alpha\n"})
        self.assertEqual(data["deferred_edges"], 0)
        self.assertEqual(data["runtime_cycles"], 0)


if __name__ == "__main__":
    unittest.main()
