"""Which surfaces may see which tools.

`TOS_TOOLS` was a flat list handed to every caller, so a capability added for
one room arrived in all of them. Acceptable for reading a practice file, wrong
for reaching the open internet: web search was asked for *in the craft channel*,
and a family conversation should not be able to trigger one. This is the
seneschal register gate of 2026-08-06 one layer up — there, nothing asked what
kind of conversation it was before offering a working plan.
"""
from __future__ import annotations

import ast
import pathlib
import types
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import tos_tools

REPO_ROOT = Path(__file__).resolve().parents[1]


def _tool_names(tools) -> set[str]:
    out = set()
    for tool in tools:
        name = (tool.get("function") or {}).get("name") or tool.get("name") or ""
        if name:
            out.add(name)
    return out


class ToolScopeTests(unittest.TestCase):
    def test_exa_is_offered_in_craft_and_nowhere_else(self) -> None:
        self.assertIn("exa_search", _tool_names(tos_tools.tools_for_attunement("craft")))
        for attunement in ("native", "magic", "", "semi"):
            self.assertNotIn(
                "exa_search",
                _tool_names(tos_tools.tools_for_attunement(attunement)),
                attunement,
            )

    def test_unscoped_tools_reach_every_surface(self) -> None:
        """Scoping must be the exception, or every new tool needs a decision."""
        for attunement in ("craft", "native", "magic", ""):
            names = _tool_names(tos_tools.tools_for_attunement(attunement))
            self.assertIn("read_practice_file", names, attunement)
            self.assertIn("run_turtleos_shell", names, attunement)

    def test_craft_sees_everything_native_sees(self) -> None:
        native = _tool_names(tos_tools.tools_for_attunement("native"))
        craft = _tool_names(tos_tools.tools_for_attunement("craft"))
        self.assertTrue(native.issubset(craft))

    def test_an_unresolvable_channel_fails_closed(self) -> None:
        """A scoped capability stays absent rather than leaking on an error."""
        self.assertNotIn(
            "exa_search", _tool_names(tos_tools.tools_for_channel(None))
        )
        self.assertNotIn(
            "exa_search", _tool_names(tos_tools.tools_for_channel("not-a-channel"))
        )

    def test_every_scoped_name_is_a_real_tool(self) -> None:
        """A scope on a tool that does not exist silently protects nothing."""
        declared = _tool_names(tos_tools.TOS_TOOLS)
        for name in tos_tools._TOOL_SCOPES:
            self.assertIn(name, declared, f"scoped tool {name} is not in TOS_TOOLS")

    def test_every_tool_has_a_dispatch_case(self) -> None:
        """A schema with no dispatch is a tool that fails after being offered."""
        source = (REPO_ROOT / "tos_tools.py").read_text(encoding="utf-8")
        for name in _tool_names(tos_tools.TOS_TOOLS):
            self.assertIn(f'name == "{name}"', source, f"{name} has no dispatch case")

    def test_schemas_all_use_the_function_wrapper(self) -> None:
        """The shape Craft Turtle's own exa proposal got wrong.

        It wrote `{"name": …, "input_schema": …}` — raw Anthropic format — because
        it had the schema's line number from `rg` and could not read the wrapper
        around it. Applied as written it would have registered a malformed tool.
        """
        for tool in tos_tools.TOS_TOOLS:
            self.assertEqual(tool.get("type"), "function", tool)
            fn = tool.get("function")
            self.assertIsInstance(fn, dict)
            self.assertIn("name", fn)
            self.assertIn("parameters", fn)
            self.assertNotIn("input_schema", tool)
            self.assertNotIn("input_schema", fn)


class NoUnscopedAssemblyTests(unittest.TestCase):
    """Every place that hands tools to a model must go through the scoped call.

    An unscoped site is not a style problem — it is the one that reintroduces
    web search into a family river, and it would look exactly like the six
    sites that existed before this test.
    """

    def test_no_module_passes_the_raw_tool_list_to_a_model(self) -> None:
        offenders: list[str] = []
        for path in sorted(REPO_ROOT.glob("*.py")):
            if path.name == "tos_tools.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for kw in node.keywords:
                    if kw.arg == "tos_tools" and isinstance(kw.value, ast.Name):
                        if kw.value.id == "TOS_TOOLS":
                            offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(
            offenders,
            [],
            "pass tools_for_channel(<channel or thread id>) instead of the raw "
            "TOS_TOOLS list:\n  " + "\n  ".join(offenders),
        )

    def test_the_guard_would_catch_a_raw_pass(self) -> None:
        """Positive control — an empty offender list is not evidence of a guard."""
        tree = ast.parse("chat(x, tos_tools=TOS_TOOLS, execute_tool=e)")
        found = [
            kw
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for kw in node.keywords
            if kw.arg == "tos_tools"
            and isinstance(kw.value, ast.Name)
            and kw.value.id == "TOS_TOOLS"
        ]
        self.assertEqual(len(found), 1)


class ExaSearchTests(unittest.TestCase):
    def test_missing_key_says_so_instead_of_answering(self) -> None:
        import os

        saved = os.environ.pop("EXA_API_KEY", None)
        try:
            out = tos_tools._exa_search("anything")
            self.assertIn("EXA_API_KEY", out)
            self.assertIn("unavailable", out)
        finally:
            if saved is not None:
                os.environ["EXA_API_KEY"] = saved

    def test_empty_query_is_refused(self) -> None:
        self.assertIn("needs a query", tos_tools._exa_search("   "))

    def test_result_count_is_clamped(self) -> None:
        self.assertEqual(tos_tools.EXA_MAX_RESULTS, 10)

    def test_exa_retries_now_that_the_tool_loop_is_off_the_event_loop(self) -> None:
        """Two attempts, because the reason for one expired.

        This test was `test_exa_does_not_retry_while_the_tool_loop_blocks_the_event_loop`
        and asserted a cap of 1. The reason was real: a timeout classifies as
        transient and therefore retryable, and while tools ran synchronously on the
        event loop a second attempt doubled the window in which Turtle answered
        nobody *anywhere*. Tool execution now runs on a daemon thread
        (`offload.run_blocking`), so a retry costs this turn's latency and no one
        else's — and a third-party network call is exactly where a retry earns its
        keep.

        Worth noting how cheap this was to find: the old name stated its own
        precondition, so when the precondition changed the failing test said what to
        do about it. A test named `test_exa_attempts_is_one` would have read as a
        regression.
        """
        self.assertEqual(tos_tools._max_tool_attempts("exa_search"), 2)
        from tool_result import classify_tool_text

        timed_out = classify_tool_text(
            "exa_search", f"exa search timed out after {tos_tools.EXA_TIMEOUT_SECONDS}s — report…"
        )
        self.assertTrue(
            timed_out["retryable"],
            "the classifier does read this as retryable — the attempt cap is what holds it to one",
        )

    def test_the_timeout_is_wired_to_something(self) -> None:
        """The constant existed from the start and was passed to nothing.

        `exa_py` takes no timeout on the client or the call, so the only bound is
        the one `_exa_search` imposes itself. A test that merely asserted the
        constant's value would have passed for the whole period it did nothing,
        so this reads the call site instead.
        """
        import ast

        src = pathlib.Path(tos_tools.__file__).read_text(encoding="utf-8")
        fn = next(
            n
            for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.FunctionDef) and n.name == "_exa_search"
        )
        uses = [
            n
            for n in ast.walk(fn)
            if isinstance(n, ast.Name) and n.id == "EXA_TIMEOUT_SECONDS"
        ]
        self.assertTrue(uses, "EXA_TIMEOUT_SECONDS is declared but never used in _exa_search")
        # Passed to a call, not merely mentioned. The failure being guarded is a
        # constant that reads as a limit while appearing only in an f-string, so
        # naming the specific waiting function would tie the test to today's
        # mechanism — a daemon `join`, an executor `result`, a client kwarg. Any
        # of those is fine; a bare reference is not.
        passed_to_a_call = [
            call
            for call in ast.walk(fn)
            if isinstance(call, ast.Call)
            and any(
                getattr(arg, "id", "") == "EXA_TIMEOUT_SECONDS"
                for arg in list(call.args) + [kw.value for kw in call.keywords]
            )
        ]
        self.assertTrue(
            passed_to_a_call,
            "EXA_TIMEOUT_SECONDS is referenced but never passed to anything that waits",
        )

    def test_a_hanging_search_returns_within_the_bound(self) -> None:
        """The behaviour, not the wiring: a call that never returns still returns."""
        import os
        import time
        from unittest.mock import patch

        saved = os.environ.get("EXA_API_KEY")
        os.environ["EXA_API_KEY"] = "test-key"

        class _Hangs:
            def __init__(self, *a, **k):
                pass

            def search_and_contents(self, *a, **k):
                time.sleep(30)

        fake = types.ModuleType("exa_py")
        fake.Exa = _Hangs
        try:
            with patch.dict(sys.modules, {"exa_py": fake}), patch.object(
                tos_tools, "EXA_TIMEOUT_SECONDS", 0.3
            ):
                t0 = time.monotonic()
                out = tos_tools._exa_search("anything")
                elapsed = time.monotonic() - t0
            self.assertIn("timed out", out)
            self.assertLess(elapsed, 5, "the abandoned worker must not be waited on")
        finally:
            if saved is None:
                os.environ.pop("EXA_API_KEY", None)
            else:
                os.environ["EXA_API_KEY"] = saved

    def test_a_working_search_is_not_bounded_away(self) -> None:
        """Negative control — the bound must not break the ordinary path."""
        import os
        from unittest.mock import patch

        saved = os.environ.get("EXA_API_KEY")
        os.environ["EXA_API_KEY"] = "test-key"

        class _Result:
            title = "A page"
            url = "https://example.test/a"
            published_date = None
            highlights = ["an excerpt"]

        class _Works:
            def __init__(self, *a, **k):
                pass

            def search_and_contents(self, *a, **k):
                return types.SimpleNamespace(results=[_Result()])

        fake = types.ModuleType("exa_py")
        fake.Exa = _Works
        try:
            with patch.dict(sys.modules, {"exa_py": fake}):
                out = tos_tools._exa_search("anything", num_results=1)
            self.assertIn("Found 1 result(s)", out)
            self.assertIn("an excerpt", out)
        finally:
            if saved is None:
                os.environ.pop("EXA_API_KEY", None)
            else:
                os.environ["EXA_API_KEY"] = saved


if __name__ == "__main__":
    unittest.main()
