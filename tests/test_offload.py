"""Blocking tool work must not stop the bot.

Every tool call went through a synchronous `execute_tool(name, args)` invoked from
inside an `async def`, so while a tool ran nothing else in the process could: no
other channel, no other practitioner, no heartbeat. Live since 2026-03-31 and
invisible until a slow tool arrived — at which point it read as "Turtle is hanging"
rather than "one tool is slow." It also cost the Exa search its retry earlier the
same day, because two attempts of a blocking call freeze the loop for twice as long.

The tests that matter here are the ones that *measure the loop*, not the ones that
check `run_blocking` returns a value. A wrapper can be present, awaited, correctly
typed and still block — `asyncio.to_thread` would satisfy every shape assertion and
also join its worker threads at interpreter exit, which is a different defect. So:

* the loop keeps ticking while blocking work runs (the positive control),
* the ticking stops if the same work is called directly (the negative control,
  proving the first test can fail),
* threads are daemon, so a restart is never held by a tool call,
* the tool layer's network calls each carry their own timeout, since this module
  deliberately adds no ceiling of its own and that decision needs a mechanism.
"""

from __future__ import annotations

import ast
import asyncio
import threading
import time
import unittest
from pathlib import Path

from core import offload

REPO = Path(__file__).resolve().parent.parent

BLOCK_SECONDS = 0.30
TICK_INTERVAL = 0.01
# With a 300ms block and 10ms ticks, a free loop manages ~30. Ten is far above what
# a blocked loop can do (zero) and far below the ideal, so the test is not timing
# sensitive on a loaded machine.
MIN_TICKS = 10


async def _count_ticks_during(awaitable) -> tuple[int, object]:
    """Run `awaitable`, counting how many times the loop got control meanwhile."""
    ticks = 0
    stop = False

    async def ticker():
        nonlocal ticks
        while not stop:
            await asyncio.sleep(TICK_INTERVAL)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        result = await awaitable
    finally:
        stop = True
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return ticks, result


def _block(seconds: float = BLOCK_SECONDS) -> str:
    time.sleep(seconds)
    return "done"


class TheLoopKeepsRunningTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_loop_ticks_while_blocking_work_runs(self) -> None:
        """The whole point. A wrapper that blocks anyway passes every other test."""
        ticks, result = await _count_ticks_during(offload.run_blocking(_block))
        self.assertEqual(result, "done")
        self.assertGreaterEqual(
            ticks,
            MIN_TICKS,
            f"the event loop only got control {ticks} times during a "
            f"{BLOCK_SECONDS}s call — it is still being blocked",
        )

    async def test_the_same_work_called_directly_does_block(self) -> None:
        """Negative control: proves the measurement above can fail.

        Without this, a broken ticker that counts nothing would make the test
        above pass forever while measuring nothing at all.
        """

        async def direct():
            return _block()

        ticks, result = await _count_ticks_during(direct())
        self.assertEqual(result, "done")
        self.assertLess(
            ticks,
            MIN_TICKS,
            "a direct blocking call let the loop tick — the tick counter is not "
            "measuring what this file claims it measures",
        )

    async def test_concurrent_calls_overlap(self) -> None:
        """Two channels' tools must be able to run at the same time."""
        started = time.perf_counter()
        results = await asyncio.gather(
            offload.run_blocking(_block),
            offload.run_blocking(_block),
            offload.run_blocking(_block),
        )
        elapsed = time.perf_counter() - started
        self.assertEqual(results, ["done", "done", "done"])
        self.assertLess(
            elapsed,
            BLOCK_SECONDS * 2,
            f"three {BLOCK_SECONDS}s calls took {elapsed:.2f}s — they ran in series",
        )


class BehaviourIsUnchangedTests(unittest.IsolatedAsyncioTestCase):
    """Upstream error handling classifies exceptions; that must keep working."""

    async def test_the_return_value_passes_through(self) -> None:
        self.assertEqual(await offload.run_blocking(lambda: 41 + 1), 42)

    async def test_arguments_pass_through(self) -> None:
        def add(a, b, c=0):
            return a + b + c

        self.assertEqual(await offload.run_blocking(add, 1, 2, c=3), 6)

    async def test_exceptions_propagate_to_the_caller(self) -> None:
        """The tool layer turns exceptions into typed failures. Do not swallow them."""

        def boom():
            raise ValueError("tool blew up")

        with self.assertRaises(ValueError) as caught:
            await offload.run_blocking(boom)
        self.assertIn("tool blew up", str(caught.exception))

    async def test_the_exception_type_is_preserved(self) -> None:
        """`TimeoutError` and `ConnectionError` are classified as retryable upstream."""
        for exc_type in (TimeoutError, ConnectionError, KeyError):
            with self.subTest(exc=exc_type.__name__):

                def boom(e=exc_type):
                    raise e("x")

                with self.assertRaises(exc_type):
                    await offload.run_blocking(boom)

    async def test_a_timeout_raises_and_does_not_wedge(self) -> None:
        with self.assertRaises(asyncio.TimeoutError):
            await offload.run_blocking(_block, 5.0, timeout=0.05)

    async def test_a_late_result_after_timeout_is_harmless(self) -> None:
        """The thread cannot be interrupted, so its delivery must land nowhere."""
        with self.assertRaises(asyncio.TimeoutError):
            await offload.run_blocking(_block, 0.15, timeout=0.02)
        await asyncio.sleep(0.25)  # let the abandoned thread finish and deliver
        self.assertEqual(await offload.run_blocking(lambda: "still working"), "still working")


class ThreadsAreDaemonTests(unittest.IsolatedAsyncioTestCase):
    """A restart must never wait on a tool call.

    This is why `asyncio.to_thread` is not used: its executor threads are joined at
    interpreter exit, and a 180-second delegate edit in flight would hold the
    shutdown. The same shape cost 31 seconds on every test run earlier today.
    """

    async def test_the_worker_thread_is_a_daemon(self) -> None:
        seen: list[bool] = []

        def check():
            seen.append(threading.current_thread().daemon)
            return None

        await offload.run_blocking(check)
        self.assertEqual(seen, [True], "a non-daemon worker can hold up ./restart.sh")

    async def test_the_thread_is_named_for_the_work(self) -> None:
        """An unnamed thread in a stack dump tells you nothing about which tool hung."""
        seen: list[str] = []

        def check():
            seen.append(threading.current_thread().name)

        await offload.run_blocking(check, name="exa_search")
        self.assertIn("exa_search", seen[0])

    def test_offload_does_not_use_the_default_executor(self) -> None:
        source = (REPO / "core" / "offload.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {
                "to_thread",
                "run_in_executor",
            }:
                self.fail(
                    f"offload uses asyncio.{node.attr}, whose threads are joined at "
                    "interpreter exit — a tool call would delay every restart"
                )


# Functions that do blocking work: filesystem walks, subprocesses, HTTP, a local
# model rewriting a file. Calling any of them inside an `async def` stops every
# channel until it returns.
BLOCKING_ENTRYPOINTS = {
    "execute_tool",
    "execute_tos_tool",
    "execute_tos_tool_reliable",
    "_execute_tos_tool_raw",
}

# Where the call is legitimate. `tos_tools` is the layer itself, and `canary.py` runs
# as its own launchd process where blocking is free — the in-process path through
# `!diagnose` is the one that needed offloading, and it did not go through here.
BLOCKING_CALL_EXEMPT = {
    "tos_tools.py": "the tool layer itself; these are its internal calls",
    "canary.py": "runs as its own launchd process (com.turtle.canary), no event loop",
}


def _blocking_calls_in_async_defs(tree: ast.AST, module: str) -> list[str]:
    """Find blocking entrypoints called from inside an `async def`."""
    found: list[str] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.async_depth = 0

        def visit_AsyncFunctionDef(self, node):  # noqa: N802
            self.async_depth += 1
            self.generic_visit(node)
            self.async_depth -= 1

        def visit_FunctionDef(self, node):  # noqa: N802
            # A sync function nested inside an async one is the *fix* — it is what
            # gets handed to `run_blocking`. Do not report its body.
            saved, self.async_depth = self.async_depth, 0
            self.generic_visit(node)
            self.async_depth = saved

        def visit_Call(self, node):  # noqa: N802
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if self.async_depth and name in BLOCKING_ENTRYPOINTS:
                found.append(f"{module}:{node.lineno} {name}()")
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


class NoBlockingToolCallInAnyAsyncFunctionTests(unittest.TestCase):
    """The class, not the case.

    The first version of this guard scanned `llm.py` only, because that is where the
    defect was found. Widening it to every module immediately turned up two more:
    `cmd_practice_io.cmd_search` ran a practice-wide file search directly in a
    command handler, and `!diagnose` in `commands.py` ran the entire canary board —
    four tool invocations, model probes, filesystem walks — inside the handler, so
    the bot stopped for as long as the whole diagnostic took.

    Two cases in the first sweep is the argument for scanning the tree rather than
    the file you were looking at.
    """

    def test_no_module_calls_a_blocking_tool_entrypoint_from_async_code(self) -> None:
        offenders: list[str] = []
        for path in sorted(REPO.glob("*.py")):
            if path.name in BLOCKING_CALL_EXEMPT:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            offenders.extend(_blocking_calls_in_async_defs(tree, path.name))
        self.assertEqual(
            offenders,
            [],
            "a blocking tool call inside an async function stops every channel until "
            "it returns. Wrap it: `await run_blocking(fn, *args, name=...)`.\n  "
            + "\n  ".join(offenders),
        )

    def test_the_scan_finds_a_planted_call(self) -> None:
        """Positive control, including the nested-sync-function shape."""
        planted = ast.parse(
            "async def handler():\n"
            "    result = execute_tos_tool('x', {})\n"
            "    return result\n"
        )
        self.assertEqual(len(_blocking_calls_in_async_defs(planted, "planted.py")), 1)

    def test_the_scan_accepts_the_offloaded_shape(self) -> None:
        """Negative control: the fix must not read as the defect.

        A sync helper defined inside an async function and handed to `run_blocking`
        is exactly how `!diagnose` was fixed, and a guard that flagged it would push
        the next person toward a worse pattern.
        """
        ok = ast.parse(
            "async def handler():\n"
            "    def work():\n"
            "        return execute_tos_tool('x', {})\n"
            "    return await run_blocking(work)\n"
        )
        self.assertEqual(_blocking_calls_in_async_defs(ok, "ok.py"), [])

    def test_every_exemption_names_a_reason_and_still_exists(self) -> None:
        """A stale exemption silently widens the hole it was cut for."""
        for name, reason in BLOCKING_CALL_EXEMPT.items():
            with self.subTest(module=name):
                self.assertTrue((REPO / name).is_file(), f"{name} is exempt but gone")
                self.assertGreater(len(reason), 20, f"{name} needs a real reason")


class TheToolLoopIsWiredTests(unittest.TestCase):
    """`llm.py` must not call `execute_tool` directly again.

    A guard rather than a comment because there are two call sites, one per backend,
    and adding a third backend is the obvious way to reintroduce the defect.
    """

    def setUp(self) -> None:
        self.source = (REPO / "llm.py").read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_execute_tool_is_never_called_directly(self) -> None:
        offenders = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "execute_tool":
                offenders.append(node.lineno)
        self.assertEqual(
            offenders,
            [],
            "a synchronous tool call on the event loop stops every channel until it "
            f"returns. Wrap it in `await run_blocking(...)`: lines {offenders}",
        )

    def test_every_backend_that_runs_tools_goes_through_run_blocking(self) -> None:
        calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "run_blocking"
        ]
        self.assertGreaterEqual(
            len(calls), 2, "both the Anthropic and Ollama tool loops must be wrapped"
        )
        for call in calls:
            self.assertTrue(
                any(kw.arg == "name" for kw in call.keywords),
                "pass `name=` so a hung tool is identifiable in a stack dump",
            )

    def test_the_guard_would_catch_a_direct_call(self) -> None:
        """Positive control — the scan looks for a shape, so plant that shape."""
        planted = ast.parse("result = execute_tool(name, args)\n")
        found = [
            n.lineno
            for n in ast.walk(planted)
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "execute_tool"
        ]
        self.assertEqual(found, [1])


class HandlerBoundsExistTests(unittest.TestCase):
    """`offload` adds no ceiling on purpose, so the handlers' own bounds are the bound.

    That is a decision, not an oversight — the delegate edit passes `timeout=180`,
    the Exa search joins its thread at 8 seconds, and a second ceiling here would
    either duplicate those numbers or fire on a legitimately slow edit. A decision
    still needs a mechanism, which is this: every network call in the tool layer
    must carry a timeout, so the claim cannot quietly stop being true.
    """

    # `urlopen` is unambiguous. `get`/`post`/`request` are not — the first version of
    # this guard matched them by name alone and reported 25 offenders, every one a
    # dictionary lookup. A guard that cries wolf gets deleted, so the verb only counts
    # when the receiver is plausibly an HTTP client.
    ALWAYS_NETWORK = {"urlopen"}
    HTTP_VERBS = {"get", "post", "put", "request"}
    HTTP_RECEIVERS = ("requests", "httpx", "session", "http", "urllib")

    @classmethod
    def _unbounded_calls(cls, tree: ast.AST) -> list[str]:
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None)
            if name is None:
                continue
            if name in cls.ALWAYS_NETWORK:
                pass
            elif name in cls.HTTP_VERBS:
                receiver = ast.unparse(node.func.value).lower()
                if not any(r in receiver for r in cls.HTTP_RECEIVERS):
                    continue
            else:
                continue
            if not any(kw.arg == "timeout" for kw in node.keywords):
                offenders.append(f"line {node.lineno}: {name}() with no timeout")
        return offenders

    def test_every_network_call_in_the_tool_layer_has_a_timeout(self) -> None:
        source = (REPO / "tos_tools.py").read_text(encoding="utf-8")
        offenders = self._unbounded_calls(ast.parse(source))
        self.assertEqual(
            offenders,
            [],
            "an unbounded network call in the tool layer can hang a turn forever. "
            "`offload` deliberately imposes no ceiling, so this is the only bound "
            f"there is:\n  " + "\n  ".join(offenders),
        )

    def test_the_scan_would_catch_a_missing_timeout(self) -> None:
        """Positive control, in each shape that matters."""
        for src in (
            "urllib.request.urlopen(req)",
            "requests.get(url)",
            "httpx.post(url, json=body)",
            "session.get(url)",
        ):
            with self.subTest(src=src):
                self.assertEqual(len(self._unbounded_calls(ast.parse(src))), 1, src)

    def test_the_scan_accepts_a_bounded_call(self) -> None:
        for src in (
            "urllib.request.urlopen(req, timeout=180)",
            "requests.get(url, timeout=5)",
        ):
            with self.subTest(src=src):
                self.assertEqual(self._unbounded_calls(ast.parse(src)), [])

    def test_the_scan_ignores_dictionary_lookups(self) -> None:
        """Negative control. The first version of this guard reported 25 of these."""
        for src in (
            "kwargs.get('model')",
            "func.get('name', '')",
            "result.get('ok') or record.get('kind')",
            "os.environ.get('EXA_API_KEY')",
        ):
            with self.subTest(src=src):
                self.assertEqual(self._unbounded_calls(ast.parse(src)), [], src)

    def test_the_exa_retry_was_restored(self) -> None:
        """The removal named its own restoration condition; this records that it happened."""
        import tos_tools

        self.assertEqual(
            tos_tools._max_tool_attempts("exa_search"),
            2,
            "the retry was removed because two blocking attempts froze the loop for "
            "twice as long. Tool execution is off the loop now, so the reason is gone",
        )



class AShutdownMidCallIsQuietTests(unittest.TestCase):
    """A restart with a tool call in flight must not print a traceback nobody can use.

    The loop closing while work is still running is the *ordinary* case during a
    deploy, not an edge one. Left unguarded it raises inside the daemon thread and
    Python prints a bare traceback with no context — unactionable (the process is
    leaving) and corrosive, because a log that cries wolf at every restart is how a
    codebase teaches its readers to stop looking. This one already learned that the
    hard way: four defects in a day that lived entirely in unread logs.
    """

    def test_delivering_into_a_closed_loop_does_not_raise(self) -> None:
        from core import offload

        started = threading.Event()
        may_finish = threading.Event()

        def slow() -> str:
            started.set()
            may_finish.wait(5)
            return "late"

        async def go() -> None:
            task = asyncio.ensure_future(offload.run_blocking(slow))
            await asyncio.get_running_loop().run_in_executor(None, started.wait, 5)
            task.cancel()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(go())
        finally:
            loop.close()

        errors: list[BaseException] = []
        threading.excepthook = lambda a: errors.append(a.exc_value)
        try:
            may_finish.set()
            time.sleep(0.4)
        finally:
            threading.excepthook = threading.__excepthook__

        self.assertEqual(
            errors, [], f"the offload thread raised after loop close: {errors}"
        )

    def test_the_guard_still_delivers_when_the_loop_is_alive(self) -> None:
        """Negative control: swallowing RuntimeError must not swallow real results."""
        from core import offload

        async def go() -> str:
            return await offload.run_blocking(lambda: "delivered")

        self.assertEqual(asyncio.run(go()), "delivered")

    def test_the_guard_still_delivers_exceptions(self) -> None:
        from core import offload

        def boom() -> None:
            raise ValueError("propagated")

        async def go() -> None:
            await offload.run_blocking(boom)

        with self.assertRaises(ValueError):
            asyncio.run(go())

if __name__ == "__main__":
    unittest.main()
