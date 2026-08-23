"""A patch target is an assertion about where a value lives — so it can be wrong.

`8171845` moved `CHANNELS` from `state.py` to `core/config.py` and left a
re-export behind so every caller kept working. Every caller did. The tests that
*patched* `state.CHANNELS` did not: `mage` binds the name from `core.config` at
import, so `patch("state.CHANNELS", {})` rebinds a name nothing reads, and the
test goes on exercising whatever the environment happens to hold.

That commit found one such test, fixed it, and wrote the principle in its own
message. Two more sat in the tree — `test_shared_river.py` and
`test_admin_space.py` — and the suite reported green on Forge because
`DISCORD_CHANNEL_DIALOGUE` is unset there. The Mini has it set, so the nightly
gate went red on 2026-08-16 while the release notes said green. `test_admin_space`
was worse than red: it kept passing, for an unrelated reason (its mock resolved
the extra id to `None`), so the case it claims to cover — *no dialogue channel
configured* — had quietly stopped being covered at all.

**The class, not the case.** A re-export is a name with two homes and one
reader, and patching the wrong home fails silently in the one direction tests
cannot see: the assertion still runs, against uncontrolled state. So the rule is
mechanical — nothing may patch a name on the module that re-exports it. The list
of such names is read out of `state.py` rather than typed here, so a value moved
to `core/config.py` tomorrow is covered the day it moves.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS = REPO_ROOT / "tests"
STATE = REPO_ROOT / "state.py"

PATCH_CALLS = {"patch", "patch.object", "mock.patch", "patch.dict"}


def _dotted(node: ast.AST) -> str:
    """`patch.dict` from the Attribute/Name nodes that spell it."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def _reexported_into_state() -> set[str]:
    """Names `state.py` imports from `core.config` — its re-exports."""
    tree = ast.parse(STATE.read_text(encoding="utf-8"), filename=str(STATE))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("core."):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _patch_targets(path: Path) -> list[tuple[int, str]]:
    """(lineno, target string) for every string-literal patch target in a file.

    Covers `with patch("a.b")`, bare calls, and `@patch("a.b")` decorators alike,
    because `ast.walk` reaches a Call wherever it is written.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _dotted(node.func) not in PATCH_CALLS:
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.append((node.lineno, first.value))
    return found


def _test_files() -> list[Path]:
    return sorted(p for p in TESTS.rglob("*.py") if "__pycache__" not in p.parts)


class PatchTargetTests(unittest.TestCase):
    def test_no_test_patches_a_reexported_name_on_state(self) -> None:
        reexports = _reexported_into_state()
        offenders: list[str] = []
        for path in _test_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            for lineno, target in _patch_targets(path):
                module, _, attr = target.rpartition(".")
                if module == "state" and attr in reexports:
                    offenders.append(
                        f"{rel}:{lineno} patches state.{attr}, which state only "
                        f"re-exports — patch it where it is read"
                    )
        self.assertEqual(
            offenders,
            [],
            "A patch on a re-export rebinds a name nothing reads, and the test "
            "goes on running against uncontrolled state.\n  " + "\n  ".join(offenders),
        )

    def test_the_reexport_list_is_not_empty(self) -> None:
        """A guard over an empty name set passes forever and means nothing."""
        reexports = _reexported_into_state()
        self.assertIn("CHANNELS", reexports)

    def test_the_scan_finds_targets_in_with_blocks_and_decorators(self) -> None:
        """Positive control on the reader, not the rule.

        The two real offenders were both inside `with` blocks. A scanner that
        only read decorators would have reported a clean tree on the exact day
        the gate was red.
        """
        import tempfile

        source = (
            "from unittest.mock import patch\n"
            "\n"
            "@patch('state.DECORATED')\n"
            "def test_a(_m):\n"
            "    pass\n"
            "\n"
            "def test_b():\n"
            "    with patch('state.IN_WITH', {}):\n"
            "        pass\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe.py"
            probe.write_text(source, encoding="utf-8")
            targets = [t for _, t in _patch_targets(probe)]
        self.assertIn("state.DECORATED", targets)
        self.assertIn("state.IN_WITH", targets)

    def test_the_scan_does_not_call_everything_a_patch(self) -> None:
        """Negative control. A scanner that matched any call would flag prose."""
        import tempfile

        source = "def test_a():\n    helper('state.CHANNELS')\n"
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe.py"
            probe.write_text(source, encoding="utf-8")
            self.assertEqual(_patch_targets(probe), [])


if __name__ == "__main__":
    unittest.main()
