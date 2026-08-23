"""Importing a module must not construct a Discord client.

Added 2026-08-14. `state.py` built Turtle's client at module scope and
`river_state.py` built River's, and nearly everything imports both — so each of
the two deployed processes (`com.turtle.discord`, `com.turtle.river`) constructed
two clients and could only ever log in one. The other was a **zombie**: real
object, never logged in, and awaits on it land on `_MissingSentinel`, which has no
`is_set`. That reads like a discord.py bug rather than a wrong-client bug, which is
how it survived.

The rule against it was already written — a docstring in
`home_plan_ui.resolve_pin_client` says never to use Turtle's client from the River
process. Prose was the entire enforcement. This file is the mechanism.

Three things are checked, because each fails differently:

1. **Import constructs nothing** — proved by a construction *count*, not by the
   absence of a line. "We made it lazy" is a claim; a counter is a measurement.
2. **Nobody re-defeats it** — a module-level `from state import client` in any
   non-entry-point module forces construction the moment that module is imported,
   which silently restores the old behaviour while this file's first test still
   passes. That is the failure this repo keeps having, so it gets a static scan
   with a positive control.
3. **The wrong-client access is reported** — so the open question ("does any live
   path in River actually touch Turtle's client?") gets answered by the log
   instead of by reasoning about it.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parent.parent

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ext.tasks", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

# The two entry points legitimately bind the client they own at import: that
# process is about to log it in. Every other module must access lazily.
ENTRY_POINTS = {"discord_bot.py", "river_bot.py"}

LAZY_MODULES = {
    "state": "client",
    "river_state": "river_client",
}


def _load_fresh(name: str):
    """Load a private copy of a module from source, leaving `sys.modules` alone.

    `importlib.reload` would rebuild the real `state` for every other test in this
    process. A separate copy under a scratch name measures the same import-time
    behaviour without that reach.
    """
    path = REPO / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_fresh_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ImportConstructsNothingTests(unittest.TestCase):
    def _count_after_import(self, name: str, counter_attr: str):
        discord = sys.modules["discord"]
        constructions = []

        def counting_client(*args, **kwargs):
            constructions.append(kwargs)
            return MagicMock()

        with patch.object(discord, "Client", counting_client):
            module = _load_fresh(name)
            at_import = len(constructions)
        return module, constructions, at_import

    def test_importing_state_constructs_no_client(self) -> None:
        module, constructions, at_import = self._count_after_import("state", "_client_constructions")
        self.assertEqual(
            at_import,
            0,
            "importing `state` built a Discord client. Nearly every module imports "
            "state, so this is a client per process that may never log in.",
        )
        self.assertEqual(module._client_constructions, 0)

    def test_importing_river_state_constructs_no_client(self) -> None:
        module, constructions, at_import = self._count_after_import(
            "river_state", "_river_client_constructions"
        )
        self.assertEqual(at_import, 0, "importing `river_state` built a Discord client")
        self.assertEqual(module._river_client_constructions, 0)

    def test_accessing_state_client_constructs_exactly_one(self) -> None:
        """Negative control: laziness must not mean the client never arrives."""
        discord = sys.modules["discord"]
        constructions = []

        def counting_client(*args, **kwargs):
            constructions.append(kwargs)
            return MagicMock()

        with patch.object(discord, "Client", counting_client):
            module = _load_fresh("state")
            self.assertEqual(len(constructions), 0)
            first = module.client
            self.assertEqual(len(constructions), 1, "access must construct")
            second = module.client
            self.assertEqual(len(constructions), 1, "access must memoise, not rebuild")
            self.assertIs(first, second)
            self.assertEqual(module._client_constructions, 1)

    def test_from_import_form_also_works(self) -> None:
        """`from state import client` must keep working — this was a rename-free change."""
        discord = sys.modules["discord"]
        with patch.object(discord, "Client", lambda *a, **k: MagicMock()):
            module = _load_fresh("state")
            self.assertIsNotNone(getattr(module, "client"))

    def test_unknown_attributes_still_raise_attribute_error(self) -> None:
        """A module `__getattr__` that swallows typos hides real bugs."""
        module = _load_fresh("state")
        with self.assertRaises(AttributeError):
            module.clinet  # noqa: B018


class NobodyRebindsAtModuleLevelTests(unittest.TestCase):
    """The static half — the part that stops the laziness being quietly undone."""

    def _offenders(self, tree: ast.Module, module_name: str, attr: str) -> list[int]:
        offenders = []
        for node in tree.body:  # module level only; function-level is the correct form
            if isinstance(node, ast.ImportFrom) and node.module == module_name:
                for alias in node.names:
                    if alias.name == attr:
                        offenders.append(node.lineno)
            if isinstance(node, (ast.If, ast.Try)):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.ImportFrom) and sub.module == module_name:
                        for alias in sub.names:
                            if alias.name == attr:
                                offenders.append(sub.lineno)
        return offenders

    def test_no_production_module_binds_the_client_at_import(self) -> None:
        violations = []
        for path in sorted(REPO.glob("*.py")):
            if path.name in ENTRY_POINTS:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for module_name, attr in LAZY_MODULES.items():
                if path.stem == module_name:
                    continue
                for lineno in self._offenders(tree, module_name, attr):
                    violations.append(f"{path.name}:{lineno} binds {module_name}.{attr}")
        self.assertEqual(
            violations,
            [],
            "a module-level binding forces client construction when this module is "
            "imported, which restores the zombie-client behaviour while the "
            "laziness tests still pass. Move the import inside the function that "
            f"uses it:\n  " + "\n  ".join(violations),
        )

    def test_the_scan_finds_a_planted_violation(self) -> None:
        """Positive control. An empty result is not evidence of absence."""
        planted = ast.parse("from state import client\n")
        self.assertEqual(
            self._offenders(planted, "state", "client"),
            [1],
            "the scanner cannot see the thing it exists to see",
        )
        planted_nested = ast.parse("try:\n    from river_state import river_client\nexcept Exception:\n    pass\n")
        self.assertEqual(self._offenders(planted_nested, "river_state", "river_client"), [2])

    def test_the_scan_accepts_the_correct_form(self) -> None:
        """Function-level access is the fix, and must not be reported as a fault."""
        ok = ast.parse("def f():\n    from state import client\n    return client\n")
        self.assertEqual(self._offenders(ok, "state", "client"), [])

    def test_the_entry_points_still_exist_under_those_names(self) -> None:
        """The exemption list is keyed by filename; a rename would silently widen it."""
        for name in ENTRY_POINTS:
            self.assertTrue((REPO / name).is_file(), f"{name} is exempted but missing")


PROBE = '''
import importlib, os, sys, warnings
sys.path.insert(0, os.getcwd())
from unittest.mock import MagicMock
from pathlib import Path
warnings.filterwarnings("ignore")
for m in ("discord","discord.ext","discord.ext.tasks","discord.ui","anthropic","ollama",
          "openai","google","google.generativeai","aiohttp","yaml","exa_py","tiktoken"):
    sys.modules.setdefault(m, MagicMock())
d = sys.modules["discord"]
for exc in ("HTTPException","NotFound","Forbidden"):
    setattr(d, exc, type(exc,(Exception,),{}))
built = []
class CountingClient:
    def __init__(self, *a, **k): built.append(1)
d.Client = CountingClient
ENTRY = {"discord_bot","river_bot"}
imported = 0
constructed = []
for name in sorted(p.stem for p in Path(".").glob("*.py")):
    if name in ENTRY:
        continue
    before = len(built)
    try:
        importlib.import_module(name)
    except Exception:
        continue
    imported += 1
    if len(built) > before:
        constructed.append(name)
print("IMPORTED", imported)
print("CONSTRUCTED", ",".join(constructed))
'''


class WholeTreeImportTests(unittest.TestCase):
    """The end-to-end version of the invariant, in a subprocess.

    The static scan above catches the *known* way to defeat laziness — a
    module-level `from state import client`. It cannot catch a module that calls
    `state.client` or `get_channel()` at import time, or a new module that builds
    its own client. This imports the whole tree with a counting stub and asserts
    the total.

    Measured before and after the 2026-08-14 change: **2 → 0**. The two were
    `state` (reached first via `artifact_presenter`) and `river_state`, which is
    the shape of the bug — every process built both bots' clients and could log in
    only one, so one was always a zombie.

    Runs as a subprocess because importing 89 modules under mock stubs inside the
    test process would leak those stubs into every test that ran afterwards.
    """

    def test_no_module_constructs_a_client_at_import(self) -> None:
        import subprocess

        result = subprocess.run(
            [sys.executable, "-c", PROBE],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        out = result.stdout
        imported = int(next(ln for ln in out.splitlines() if ln.startswith("IMPORTED")).split()[1])
        constructed_line = next(ln for ln in out.splitlines() if ln.startswith("CONSTRUCTED"))
        constructed = [n for n in constructed_line[len("CONSTRUCTED") :].strip().split(",") if n]

        # Positive control on the probe. Its first version ran from a directory that
        # was not on sys.path, so every import failed, every failure was skipped,
        # and it reported a perfectly clean tree. A probe that measures nothing must
        # not be able to pass.
        self.assertGreater(
            imported,
            50,
            f"the probe only imported {imported} modules — it is measuring nothing, "
            "not finding nothing",
        )
        self.assertEqual(
            constructed,
            [],
            "these modules construct a Discord client at import time. Every process "
            "then holds a client it may never log in, and awaits on it land on "
            f"`_MissingSentinel`: {constructed}",
        )


class OwningProcessTests(unittest.TestCase):
    """Derived from the entry point, because a declaration can be forgotten."""

    def setUp(self) -> None:
        self.state = _load_fresh("state")

    def test_env_override_wins(self) -> None:
        with patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": "river"}):
            self.assertEqual(self.state.owning_process(), "river")

    def test_garbage_override_is_ignored(self) -> None:
        with patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": "banana"}):
            self.assertIn(self.state.owning_process(), {"river", "turtle", "other"})

    def test_river_entry_point_is_recognised(self) -> None:
        fake_main = MagicMock()
        fake_main.__file__ = "/Users/turtle/turtleos/river_bot.py"
        with patch.dict("os.environ", {}, clear=False), patch.dict(
            sys.modules, {"__main__": fake_main}
        ):
            sys.modules["__main__"] = fake_main
            self.assertEqual(self.state.owning_process(), "river")

    def test_turtle_entry_point_is_recognised(self) -> None:
        fake_main = MagicMock()
        fake_main.__file__ = "/Users/turtle/turtleos/discord_bot.py"
        with patch.dict(sys.modules, {"__main__": fake_main}):
            sys.modules["__main__"] = fake_main
            self.assertEqual(self.state.owning_process(), "turtle")

    def test_a_test_runner_is_neither(self) -> None:
        fake_main = MagicMock()
        fake_main.__file__ = "/usr/lib/python3/unittest/__main__.py"
        with patch.dict(sys.modules, {"__main__": fake_main}):
            sys.modules["__main__"] = fake_main
            self.assertEqual(self.state.owning_process(), "other")


class ZombieAccessIsReportedTests(unittest.TestCase):
    """The detector that turns an unanswerable question into a log line."""

    def _construct_under_role(self, role: str):
        discord = sys.modules["discord"]
        with patch.object(discord, "Client", lambda *a, **k: MagicMock()):
            module = _load_fresh("state")
            with patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": role}):
                with patch("sys.stderr") as err:
                    module.client
                    module.client
        written = "".join(
            str(call.args[0]) for call in err.write.call_args_list if call.args
        )
        return written

    def test_river_touching_turtles_client_is_reported(self) -> None:
        written = self._construct_under_role("river")
        self.assertIn("WRONG-CLIENT", written)

    def test_it_reports_once_not_on_every_access(self) -> None:
        written = self._construct_under_role("river")
        self.assertEqual(written.count("WRONG-CLIENT"), 1, "a per-access log is noise")

    def test_the_turtle_process_is_silent(self) -> None:
        written = self._construct_under_role("turtle")
        self.assertNotIn("WRONG-CLIENT", written)

    def test_the_report_names_where_to_go_instead(self) -> None:
        """A warning that does not say what to do instead gets muted, not fixed."""
        written = self._construct_under_role("river")
        self.assertIn("resolve_pin_client", written)

    def test_the_named_alternative_exists(self) -> None:
        source = (REPO / "home_plan_ui.py").read_text(encoding="utf-8")
        self.assertIn("def resolve_pin_client", source)


class GetChannelIsProcessCorrectTests(unittest.TestCase):
    """The payoff of the detector, deployed the same day it was written.

    Within an hour of going live the wrong-client report fired in `river.log` with a
    stack: `offer_ledger.root_for_channel` → `mage.resolve_registry_channel_id` →
    `mage.is_registered_parent_channel` → `state.get_channel("dialogue")`. So every
    offer River recorded constructed Turtle's client inside River's process — where it
    is never logged in, so `get_channel` returned None regardless and the caller's
    third fallback contributed nothing.

    This is the question the report was written to answer instead of reasoning about,
    and it answered it in an hour. The fix keeps the None and drops the zombie.
    """

    def _state_with_channel(self):
        """Stub `discord.Client` for the whole test, not just the import.

        The first version closed the patch after `_load_fresh`, so the later
        `_ensure_client()` call reached whichever `discord` the session happened to
        have — a MagicMock when this file ran alone, the real discord.py when the
        full suite ran, whose `get_channel` returns None with no connection. So the
        negative control passed in isolation and failed in the suite. That is the
        import-order trap documented in `tests/discord_stub.py`, and it caught the
        person who documented it. Keep the patch open for the duration.
        """
        discord = sys.modules["discord"]
        patcher = patch.object(discord, "Client", lambda *a, **k: MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)
        module = _load_fresh("state")
        module.CHANNELS = {"dialogue": "12345"}
        return module

    def test_river_gets_none_and_builds_no_client(self) -> None:
        module = self._state_with_channel()
        with patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": "river"}):
            with patch("sys.stderr"):
                self.assertIsNone(module.get_channel("dialogue"))
        self.assertEqual(
            module._client_constructions,
            0,
            "River asked for Turtle's channel and a client was built to answer it",
        )

    def test_the_report_says_which_of_the_two_things_happened(self) -> None:
        """Refused-without-constructing and constructed-a-zombie are different findings.

        A report that names the wrong one sends the next reader looking for a client
        that was never built — the same defect this repo keeps having, in one string.
        """
        module = self._state_with_channel()
        with patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": "river"}):
            with patch("sys.stderr") as err:
                module.get_channel("dialogue")
        written = "".join(str(c.args[0]) for c in err.write.call_args_list if c.args)
        self.assertIn("without constructing", written)
        self.assertNotIn("constructed Turtle's state.client", written)

    def test_a_direct_client_access_still_reports_a_construction(self) -> None:
        module = self._state_with_channel()
        with patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": "river"}):
            with patch("sys.stderr") as err:
                module.client
        written = "".join(str(c.args[0]) for c in err.write.call_args_list if c.args)
        self.assertIn("constructed Turtle's state.client", written)

    def test_river_is_told_once(self) -> None:
        module = self._state_with_channel()
        with patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": "river"}):
            with patch("sys.stderr") as err:
                module.get_channel("dialogue")
                module.get_channel("dialogue")
        written = "".join(str(c.args[0]) for c in err.write.call_args_list if c.args)
        self.assertEqual(written.count("WRONG-CLIENT"), 1)

    def test_turtle_still_resolves_through_its_client(self) -> None:
        """The negative control: the fix must not disable the working process."""
        module = self._state_with_channel()
        with patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": "turtle"}):
            result = module.get_channel("dialogue")
        self.assertIsNotNone(result, "Turtle must still resolve its own channel")
        self.assertEqual(module._client_constructions, 1)

    def test_an_unknown_name_is_none_everywhere(self) -> None:
        module = self._state_with_channel()
        for role in ("river", "turtle", "other"):
            with self.subTest(role=role):
                with patch.dict("os.environ", {"TURTLE_PROCESS_ROLE": role}):
                    self.assertIsNone(module.get_channel("nonexistent"))

    def test_the_caller_that_triggered_this_still_works_in_river(self) -> None:
        """`is_registered_parent_channel` must not start raising on a None channel."""
        source = (REPO / "mage.py").read_text(encoding="utf-8")
        self.assertIn(
            "dialogue = get_channel(\"dialogue\")",
            source,
            "the call site moved — recheck that it still tolerates None",
        )
        self.assertIn(
            "return dialogue and channel_id == dialogue.id",
            source,
            "the None-tolerant form is what makes returning None safe here",
        )


if __name__ == "__main__":
    unittest.main()
