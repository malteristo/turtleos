"""turtleOS LLM backends — Anthropic, Gemini, Ollama chat functions."""

import asyncio
import json
import os

import httpx

from core.offload import run_blocking
from state import (
    OLLAMA_URL, DIALOGUE_MODEL, ANTHROPIC_API_KEY, GOOGLE_API_KEY,
    HAS_ANTHROPIC, HAS_GEMINI, USE_API, MAX_TOOL_ROUNDS,
    KNOWN_MODELS,
)


def _seconds(name: str, default: float) -> float:
    """Env-tunable deadline. ``0`` disables the guard entirely."""
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Silence *after* the first token — a wedged runner, not a queue.
OLLAMA_STALL_SECONDS = _seconds("OLLAMA_STALL_SECONDS", 180.0)
# Whole-call ceiling so a wedge cannot hold the gate forever.
OLLAMA_TURN_CEILING_SECONDS = _seconds("OLLAMA_TURN_CEILING_SECONDS", 1800.0)
# Non-streaming calls (tool loop) have no token stream to watch; one generous
# read deadline is all they can carry.
OLLAMA_BLOCKING_READ_SECONDS = _seconds("OLLAMA_BLOCKING_READ_SECONDS", 1800.0)

# ─── The inference gate ──────────────────────────────────────────
#
# Per-channel serialization (``dialogue_queue``) was never the gap. On
# 2026-08-07 the family river had four eddies live at once, each correctly
# serialized on its own, and all four arrived together at a single Ollama
# slot: ``llama-server`` runs with ``-np 1`` and ``OLLAMA_NUM_PARALLEL`` is
# unset. Ollama queued them, emitted no bytes to the ones waiting, and the
# client's byte-gap deadline killed them where they stood.
#
# The line exists whether or not we form it. Forming it ourselves is strictly
# better: waits become ordered rather than racing, depth is visible in the
# log, and a queued turn cannot be timed out for waiting. Default 1 mirrors
# the server's real slot count — raise ``OLLAMA_MAX_INFLIGHT`` in step with
# ``OLLAMA_NUM_PARALLEL``, never ahead of it.
OLLAMA_MAX_INFLIGHT = max(1, int(_seconds("OLLAMA_MAX_INFLIGHT", 1)))
_inflight_gate: asyncio.Semaphore | None = None
_inflight_waiting = 0


def _gate() -> asyncio.Semaphore:
    global _inflight_gate
    if _inflight_gate is None:
        _inflight_gate = asyncio.Semaphore(OLLAMA_MAX_INFLIGHT)
    return _inflight_gate


class _InferenceGate:
    """Order the calls to the local runner, and say so when there is a line."""

    async def __aenter__(self):
        global _inflight_waiting
        gate = _gate()
        _inflight_waiting += 1
        if gate.locked():
            print(f"Local inference queued: {_inflight_waiting} waiting")
        await gate.acquire()
        return self

    async def __aexit__(self, *exc):
        global _inflight_waiting
        _inflight_waiting = max(0, _inflight_waiting - 1)
        _gate().release()
        return False


OLLAMA_GATE_WAIT_SECONDS = _seconds("OLLAMA_GATE_WAIT_SECONDS", 300.0)


async def chat_ollama_json(
    prompt: str,
    *,
    model: str,
    num_ctx: int = 2048,
    timeout_s: float = 30.0,
) -> str:
    """One small greedy JSON call, **through the gate**. Returns raw content.

    This exists because the two fail-closed gates in the system — the
    seneschal's register check and the theme gate — each posted to Ollama with
    their own `httpx` client and their own 8–10s deadline, bypassing
    ``_InferenceGate`` entirely. On a host with one inference slot that is the
    worst possible arrangement: instead of *queueing* behind the dialogue turn
    holding the slot, they *competed* with it and hit their own timeout. Both
    fail closed, so under load the seneschal suppressed every offer and the
    theme gate dropped every label — silently, and precisely on the dense
    evenings the gates exist for. Found 2026-08-08 when a live control could
    not be run for this reason.

    The deadline is measured **after acquisition**, which is the whole point: a
    call that waits four minutes in line and then answers in two seconds has
    not failed. Waiting is bounded separately by ``OLLAMA_GATE_WAIT_SECONDS``,
    so a wedged runner still cannot hold a checkpoint forever.

    ``temperature: 0`` is not a default, it is a requirement. A gate must give
    the same answer to the same input or no comparison between two versions of
    it means anything — a lesson the register gate paid for with an A/B that
    turned out to be sampling noise.
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"num_ctx": num_ctx, "temperature": 0},
        "format": "json",
        "keep_alive": "10m",
    }

    async def _call() -> str:
        async with _InferenceGate():
            timeout = httpx.Timeout(
                connect=10.0, read=timeout_s, write=10.0, pool=None
            )
            async with httpx.AsyncClient(timeout=timeout) as http:
                resp = await http.post(f"{OLLAMA_URL}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
        return data.get("message", {}).get("content", "") or ""

    return await asyncio.wait_for(
        _call(), timeout=OLLAMA_GATE_WAIT_SECONDS + timeout_s
    )


def reset_gate_for_tests() -> None:
    global _inflight_gate, _inflight_waiting
    _inflight_gate = None
    _inflight_waiting = 0


def resolve_model(model_str: str) -> tuple[str, bool]:
    """Resolve model name to (model_id, use_api) tuple."""
    if model_str in KNOWN_MODELS:
        resolved = KNOWN_MODELS[model_str]
        if resolved is None:
            return DIALOGUE_MODEL, USE_API
        if resolved.startswith("claude-"):
            return resolved, HAS_ANTHROPIC and bool(ANTHROPIC_API_KEY)
        return resolved, False
    if model_str.startswith("claude-"):
        return model_str, HAS_ANTHROPIC and bool(ANTHROPIC_API_KEY)
    if model_str.startswith("gemini-"):
        return model_str, HAS_GEMINI and bool(GOOGLE_API_KEY)
    return model_str, False


async def chat_anthropic(system_prompt, messages):
    return await chat_anthropic_with_model(system_prompt, messages, DIALOGUE_MODEL)


async def chat_anthropic_with_model(system_prompt, messages, model, use_tools=False,
                                     tos_tools=None, execute_tool=None):
    """Chat with Anthropic API, optionally with tOS tool use.

    Args:
        tos_tools: List of tool definitions (TOS_TOOLS format)
        execute_tool: Function to execute a tool call: execute_tool(name, args) -> str
    """
    import anthropic as _anthropic
    aclient = _anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    anthropic_tools = []
    if use_tools and tos_tools:
        for tool in tos_tools:
            anthropic_tools.append({
                "name": tool["function"]["name"],
                "description": tool["function"]["description"],
                "input_schema": tool["function"]["parameters"],
            })

    kwargs = dict(model=model, max_tokens=4096, system=system_prompt, messages=list(messages))
    if anthropic_tools:
        kwargs["tools"] = anthropic_tools

    tools_executed = []
    # Prose accumulates across rounds. Claude routinely writes the whole reply
    # *and* calls a tool in the same content block — a checkpoint offer at the
    # end of a good answer is the common case. Reading `text_parts` only on the
    # round that happened to end without a tool call threw that reply away, and
    # the next round (nothing left to add) came back empty, so the practitioner
    # got the "ended on the tool call without prose" recovery line *instead of*
    # the answer the model had already written. Measured 2026-08-13 in
    # craft-turtle: three intakes, one eddy where the reply existed in the API
    # response and never reached Discord.
    prose_parts: list[str] = []
    for round_num in range(MAX_TOOL_ROUNDS):
        response = await aclient.messages.create(**kwargs)

        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        round_text = "\n".join(text_parts).strip()
        if round_text:
            prose_parts.append(round_text)

        if not tool_uses:
            text = "\n\n".join(prose_parts).strip()
            if not text and tools_executed:
                text = _text_after_tools_only(tools_executed)
            return text or "(no response generated)", tools_executed

        kwargs["messages"].append({"role": "assistant", "content": response.content})
        tool_results = []
        round_failed = False
        for tu in tool_uses:
            # Off the event loop. `execute_tool` is synchronous — file reads,
            # subprocesses, HTTP, a local model doing a whole-file rewrite — and
            # calling it here stopped every other channel until it returned. See
            # `offload.run_blocking`; the bounds stay in the handlers.
            result = (
                await run_blocking(execute_tool, tu.name, tu.input, name=tu.name)
                if execute_tool
                else f"Unknown tool: {tu.name}"
            )
            tools_executed.append({"name": tu.name, "args": tu.input, "result": result})
            print(f"  Tool ({model}): {tu.name} -> {result}")
            if _tool_result_failed(result):
                round_failed = True
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result,
            })
        # Last chance to write prose. Only claim tools are failing when they
        # actually are — the old unconditional nudge fired on the second round
        # of every turn and told the model its *successful* survey had failed.
        # It also rode in a *second* consecutive user message behind the
        # tool_result turn; it belongs in the same block, where the API expects
        # a tool_result turn to end.
        if round_num == MAX_TOOL_ROUNDS - 2:
            nudge = (
                "[System: Tool attempts are not succeeding. Please respond in text, "
                "explaining what you were trying to do and what went wrong. Do not call more tools.]"
                if round_failed else
                "[System: This is your last tool round. Answer in text now, from what you already "
                "have. Do not call more tools.]"
            )
            tool_results.append({"type": "text", "text": nudge})

        kwargs["messages"].append({"role": "user", "content": tool_results})

    text = "\n\n".join(prose_parts).strip()
    if not text:
        # Build transparent error from tool execution history
        failed = [t for t in tools_executed if _tool_result_failed(t.get("result", ""))]
        if failed:
            issues = "; ".join(f"{t['name']}({t['args'].get('filename', t['args'].get('directory', '?'))}) → {t['result'][:80]}" for t in failed[:3])
            text = f"I tried to help but hit access limits: {issues}. Try asking Spirit on the Forge or Anvil for files outside my practice directory."
        elif tools_executed:
            text = _text_after_tools_only(tools_executed)
        else:
            text = "I attempted to answer but my tool calls didn't produce the information I needed. Could you rephrase, or try asking Spirit on the Forge or Anvil?"
    return text, tools_executed


# Failures announce themselves. ``format_tool_result`` prefixes every typed
# failure with ``ToolResult[kind]``; the handful of tools that still return a
# bare sentence say so at the start of it. The previous test was a free-floating
# substring search for "error"/"cannot"/"not found" over the *whole* result,
# which any successful source-code read can satisfy — ``inspect_turtleos_module``
# on a module that handles errors read as a failed tool call.
_BARE_FAILURE_PREFIXES = (
    "toolresult[",
    "cannot ",
    "unknown tool:",
    "offer rejected:",
    "old_text not found",
)


def _tool_result_failed(result: str) -> bool:
    lower = (result or "").strip().lower()
    return lower.startswith(_BARE_FAILURE_PREFIXES)


def _text_after_tools_only(tools_executed: list) -> str:
    """When the model ends on a tool call with no prose, say what landed.

    Measured 2026-08-11: Claude called ``offer_river_act`` after an inlined
    ``message.txt`` paste and returned empty content — Discord showed
    ``(no response generated)`` even though the Save offer had queued.

    Since the prose fix this is a genuine last resort, and it no longer promises
    a button: River only posts one on natively-attuned surfaces, so in
    craft-turtle the old wording announced chrome that could never arrive.
    """
    offers = [t for t in tools_executed if t.get("name") == "offer_river_act"]
    if offers:
        last = offers[-1]
        action = (last.get("args") or {}).get("action", "act")
        url = (last.get("args") or {}).get("url") or ""
        detail = f"{action}" + (f" · {url}" if url else "")
        return (
            f"I queued a **{detail}** offer and then returned no text — that is a "
            "fault on my side, not an answer. Ask again and I will write the reply."
        )
    names = ", ".join(t.get("name", "?") for t in tools_executed[:3])
    return (
        f"I ran tools ({names}) but did not get a text reply from the model. "
        "Ask again if you want a written take."
    )


async def chat_gemini(system_prompt, messages, model="gemini-2.5-flash", attachments=None):
    """Chat with Gemini, optionally with multimodal attachments.
    Returns (reply_text, tools_executed) for consistency."""
    if not HAS_GEMINI or not GOOGLE_API_KEY:
        return "[Gemini not available — missing google-genai or API key]", []

    from google import genai

    gclient = genai.Client(api_key=GOOGLE_API_KEY)

    gemini_history = []
    for msg in messages[:-1]:
        role = "user" if msg["role"] == "user" else "model"
        gemini_history.append(genai.types.Content(
            role=role,
            parts=[genai.types.Part.from_text(text=msg["content"])],
        ))

    last_msg = messages[-1]
    last_parts = [genai.types.Part.from_text(text=last_msg["content"])]
    if attachments:
        for mime, data, filename in attachments:
            last_parts.append(genai.types.Part.from_bytes(data=data, mime_type=mime))
    gemini_history.append(genai.types.Content(role="user", parts=last_parts))

    try:
        response = await gclient.aio.models.generate_content(
            model=model,
            contents=gemini_history,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=4096,
            ),
        )
        text = response.text or "(no response generated)"
        return text, []
    except Exception as e:
        print(f"Gemini chat error: {type(e).__name__}: {e}")
        return f"[Gemini error: {type(e).__name__}: {e}]", []


async def chat_ollama(system_prompt, messages, model=None, num_ctx=16384, think=None):
    """Stream a local completion. Waiting in line is not a failure.

    The read timeout used to be 300s. In a streaming request httpx measures
    ``read`` as the gap *between bytes*, and a request parked in Ollama's
    single slot emits none — so the deadline fired while queued, on the turn
    that had not started yet. Local inference gets no byte-gap deadline now.
    Two bounded guards replace it, and they measure faults rather than load:

    - ``OLLAMA_STALL_SECONDS`` (default 180) applies only *after* the first
      token. Once generation starts, tokens arrive steadily; a long silence
      mid-sentence is a wedged runner, not a queue.
    - ``OLLAMA_TURN_CEILING_SECONDS`` (default 1800) bounds the whole call so
      a wedged server cannot hold a channel's turn lock forever. At the
      measured ~172s per 31B turn that is roughly ten deep — past any real
      conversation, short of never.
    """
    payload = {
        "model": model or DIALOGUE_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "stream": True,
        "options": {"num_ctx": num_ctx},
    }
    if think is not None:
        payload["think"] = think

    async def _stream() -> str:
        reply_chunks = []
        timeout = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=None)
        async with httpx.AsyncClient(timeout=timeout) as http:
            async with http.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                lines = resp.aiter_lines().__aiter__()
                while True:
                    try:
                        if reply_chunks:
                            line = await asyncio.wait_for(
                                lines.__anext__(), timeout=OLLAMA_STALL_SECONDS
                            )
                        else:
                            line = await lines.__anext__()
                    except StopAsyncIteration:
                        break
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            reply_chunks.append(token)
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        return "".join(reply_chunks).strip() or "(no response generated)"

    async with _InferenceGate():
        if OLLAMA_TURN_CEILING_SECONDS:
            return await asyncio.wait_for(_stream(), timeout=OLLAMA_TURN_CEILING_SECONDS)
        return await _stream()


async def chat_ollama_with_tools(system_prompt, messages, model_override=None,
                                  tos_tools=None, execute_tool=None):
    """Ollama dialogue with tOS tool support (non-streaming).

    Args:
        tos_tools: List of tool definitions
        execute_tool: Function to execute a tool call: execute_tool(name, args) -> str
    """
    model = model_override or DIALOGUE_MODEL
    all_messages = [{"role": "system", "content": system_prompt}, *messages]
    tools_executed = []
    # Same accumulation as the Anthropic loop, for the same reason: a local
    # model that writes a sentence and then calls a tool had that sentence
    # dropped on the floor. This path serves the family rivers, where nobody is
    # positioned to notice a reply went missing.
    prose_parts: list[str] = []
    for _ in range(MAX_TOOL_ROUNDS):
        blocking_timeout = httpx.Timeout(
            connect=10.0, read=OLLAMA_BLOCKING_READ_SECONDS, write=10.0, pool=None
        )
        async with _InferenceGate():
            async with httpx.AsyncClient(timeout=blocking_timeout) as http:
                payload = {
                    "model": model,
                    "messages": all_messages,
                    "tools": tos_tools or [],
                    "stream": False,
                    "options": {"num_ctx": 32768},
                }
                resp = await http.post(f"{OLLAMA_URL}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()

        msg = data.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        if content.strip():
            prose_parts.append(content.strip())

        if not tool_calls:
            text = "\n\n".join(prose_parts).strip()
            return text or "(no response generated)", tools_executed

        all_messages.append(msg)
        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            args = func.get("arguments", {})
            result = (
                await run_blocking(execute_tool, tool_name, args, name=tool_name)
                if execute_tool
                else f"Unknown tool: {tool_name}"
            )
            tools_executed.append({"name": tool_name, "args": args, "result": result})
            print(f"  Tool: {tool_name} -> {result}")
            all_messages.append({"role": "tool", "content": result})

    text = "\n\n".join(prose_parts).strip()
    if not text:
        failed = [t for t in tools_executed if _tool_result_failed(t.get("result", ""))]
        if failed:
            issues = "; ".join(f"{t['name']}({t['args'].get('filename', t['args'].get('directory', '?'))}) → {t['result'][:80]}" for t in failed[:3])
            text = f"I tried to help but hit access limits: {issues}. Try asking Spirit on the Forge or Anvil for files outside my practice directory."
        else:
            text = "I attempted to answer but my tool calls didn't produce the information I needed. Could you rephrase, or try asking Spirit on the Forge or Anvil?"
    return text, tools_executed
