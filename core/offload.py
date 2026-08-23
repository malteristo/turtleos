"""Run blocking work off the event loop.

Every tool call went through `execute_tool(name, args)` — a synchronous function —
called from inside an `async def`. So while a tool ran, the whole bot stopped: other
channels, other practitioners, heartbeats, everything. Live since 2026-03-31 and
invisible until a slow tool arrived, at which point it read as "Turtle is hanging"
rather than "one tool is slow." Earlier today it cost the Exa search its retries,
because two attempts of a blocking call freeze the loop for twice as long.

**Why not `asyncio.to_thread`.** It uses the default executor, whose worker threads
are *joined at interpreter exit*. A restart while a 180-second delegate edit is in
flight would wait for it. That exact shape cost 31 seconds on every test run earlier
today, with `ThreadPoolExecutor`, and the fix was the same one used here: a plain
daemon thread, which the interpreter drops. `restart.sh` is a routine operation and
must not be held hostage by a tool call.

**No timeout by default, deliberately.** The bound belongs where the work is: the
delegate edit passes `timeout=180` to `urlopen`, the Exa search joins its own thread
at 8 seconds. Adding a second ceiling here would either duplicate those numbers or
fire on a legitimately slow edit and break working behaviour.
`tests/test_offload.py` keeps that claim honest by requiring every network call in
the tool layer to pass a timeout — so "the handlers are bounded" is checked rather
than believed.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Diagnostics only. A thread count that climbs and never falls is the signature of
# blocking work that never returns, which is otherwise invisible: the turn simply
# never answers and nothing is logged.
_active = 0
_active_lock = threading.Lock()
_peak = 0


def active_count() -> int:
    with _active_lock:
        return _active


def peak_count() -> int:
    with _active_lock:
        return _peak


async def run_blocking(
    fn: Callable[..., T],
    /,
    *args: Any,
    timeout: float | None = None,
    name: str = "",
    **kwargs: Any,
) -> T:
    """Await `fn(*args, **kwargs)` while it runs on a daemon thread.

    Exceptions propagate to the caller as if the call had been direct, so error
    handling upstream keeps working unchanged — which matters, because the tool
    layer classifies exceptions into typed failures and that logic is not moving.

    On `timeout`, `TimeoutError` is raised and the thread is left running. There is
    no way to interrupt arbitrary blocking code, and pretending otherwise would be
    worse than saying so: the result is discarded when it arrives.
    """
    global _active, _peak
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()

    def _deliver(setter: str, value: Any) -> None:
        # The future may already be cancelled — a timeout upstream, or the turn
        # being torn down. Setting a result on it raises InvalidStateError, which
        # would surface from `call_soon_threadsafe` as an unretrievable exception
        # in the loop's exception handler rather than anywhere useful.
        if future.done():
            return
        getattr(future, setter)(value)

    def _hand_back(setter: str, value: Any) -> None:
        # The loop can be gone before the work finishes — shutdown with a tool call
        # still in flight, which is the ordinary case during a restart. Then
        # `call_soon_threadsafe` raises inside this daemon thread and Python prints a
        # bare traceback with no context. Nobody can act on it (the process is
        # leaving) and it teaches readers that tracebacks in the log are normal, which
        # is the disease this codebase already has. Nothing is waiting for the result.
        try:
            loop.call_soon_threadsafe(_deliver, setter, value)
        except RuntimeError:
            pass

    def _runner() -> None:
        global _active
        try:
            result = fn(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 — re-raised in the caller
            _hand_back("set_exception", exc)
        else:
            _hand_back("set_result", result)
        finally:
            with _active_lock:
                _active -= 1

    with _active_lock:
        _active += 1
        _peak = max(_peak, _active)

    thread = threading.Thread(
        target=_runner,
        name=f"offload:{name or getattr(fn, '__name__', 'anonymous')}",
        daemon=True,
    )
    thread.start()

    if timeout is None:
        return await future
    # `shield` so that `wait_for` cancelling its awaitable does not cancel the
    # future the thread is about to complete — without it the thread's delivery
    # lands on a cancelled future every single time.
    return await asyncio.wait_for(asyncio.shield(future), timeout)
