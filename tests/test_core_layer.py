"""`core/` may not import anything outside `core/`. Enforced, not requested.

The rule and the reasoning live in `core/__init__.py` and
`docs/chapters/design-layer-boundaries.md`. This file is what makes them true.

The precedent is `tests/test_transport_boundary.py`: `runtime/__init__.py`
claimed transport independence in a docstring for 100 days, the claim happened
to be true, and it was worth nothing — because nothing would have noticed the
day it stopped being true. A layer is a rule the codebase refuses to violate or
it is a paragraph.

**No exemption list, deliberately.** The transport boundary needs one because
adapters exist to translate. Nothing in `core/` translates anything, so the
first entry would mean the layer was mis-drawn — and an empty exemption list
that never gets a first entry is the strongest form of the rule.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE = REPO_ROOT / "core"

TRANSPORT_LIBRARIES = {"discord", "matrix", "nio", "slack_sdk"}


def _project_modules() -> set[str]:
    """Top-level names that are project modules rather than libraries."""
    names = {p.stem for p in REPO_ROOT.glob("*.py") if p.stem != "__init__"}
    names |= {p.name for p in REPO_ROOT.glob("*/__init__.py")} - {"core"}
    names |= {p.parent.name for p in REPO_ROOT.glob("*/__init__.py")}
    names.discard("core")
    return names


def _core_files() -> list[Path]:
    return sorted(p for p in CORE.rglob("*.py") if "__pycache__" not in p.parts)


def _imports(path: Path) -> list[tuple[int, str]]:
    """(lineno, dotted name) for every import, module-level or inside a function."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue  # relative: cannot leave the package
            if node.module:
                found.append((node.lineno, node.module))
    return found


class CoreLayerTests(unittest.TestCase):
    def test_core_imports_nothing_from_outside_core(self) -> None:
        outsiders = _project_modules()
        offenders: list[str] = []
        for path in _core_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            for lineno, dotted in _imports(path):
                top = dotted.split(".")[0]
                if top in outsiders:
                    offenders.append(f"{rel}:{lineno} imports {dotted}")
        self.assertEqual(
            offenders,
            [],
            "core/ is the bottom layer: nothing in it may depend on a module "
            "above it. Move the dependency down, or the module out.\n  "
            + "\n  ".join(offenders),
        )

    def test_core_imports_no_transport_library(self) -> None:
        # Implied by the test above only while every transport import sits in a
        # root module. Stated separately so it keeps holding if that changes.
        offenders: list[str] = []
        for path in _core_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            for lineno, dotted in _imports(path):
                if dotted.split(".")[0] in TRANSPORT_LIBRARIES:
                    offenders.append(f"{rel}:{lineno} imports {dotted}")
        self.assertEqual(offenders, [], "\n  ".join(offenders))

    def test_the_scan_reads_imports_inside_function_bodies(self) -> None:
        """Positive control on the reader, not the rule.

        683 of this project's imports are written inside functions. A scan that
        only walked module level would pass `core/` forever while a deferred
        `import mage` sat in a helper — which is exactly how the graph got
        cyclic without anything reporting a cycle.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe.py"
            probe.write_text(
                "def go():\n    import mage\n    return mage\n", encoding="utf-8"
            )
            found = [dotted for _, dotted in _imports(probe)]
        self.assertIn("mage", found)

    def test_the_rule_has_something_to_be_true_about(self) -> None:
        """A guard over an empty directory passes forever and means nothing."""
        modules = [p.name for p in _core_files() if p.name != "__init__.py"]
        self.assertGreaterEqual(
            len(modules),
            10,
            f"core/ holds {len(modules)} modules; the layer was drawn around 10",
        )

    def test_project_modules_are_actually_detected(self) -> None:
        """Positive control on the offender set.

        If `_project_modules` returned nothing, the boundary test above would
        pass no matter what `core/` imported.
        """
        outsiders = _project_modules()
        for expected in ("mage", "state", "dialogue_turn", "runtime"):
            self.assertIn(expected, outsiders)
        self.assertNotIn("core", outsiders)


if __name__ == "__main__":
    unittest.main()
