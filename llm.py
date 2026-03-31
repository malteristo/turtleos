"""turtleOS LLM backends — Anthropic, Gemini, Ollama chat functions."""

import json

import httpx

from state import (
    OLLAMA_URL, DIALOGUE_MODEL, ANTHROPIC_API_KEY, GOOGLE_API_KEY,
    HAS_ANTHROPIC, HAS_GEMINI, USE_API, MAX_TOOL_ROUNDS,
    KNOWN_MODELS,
)


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
    for round_num in range(MAX_TOOL_ROUNDS):
        response = await aclient.messages.create(**kwargs)

        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        if not tool_uses:
            text = "\n".join(text_parts).strip() or "(no response generated)"
            return text, tools_executed

        kwargs["messages"].append({"role": "assistant", "content": response.content})
        tool_results = []
        for tu in tool_uses:
            result = execute_tool(tu.name, tu.input) if execute_tool else f"Unknown tool: {tu.name}"
            tools_executed.append({"name": tu.name, "args": tu.input, "result": result})
            print(f"  Tool ({model}): {tu.name} -> {result}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result,
            })
        kwargs["messages"].append({"role": "user", "content": tool_results})

        # On penultimate round, nudge model to respond in text
        if round_num == MAX_TOOL_ROUNDS - 2:
            kwargs["messages"].append({
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": "[System: Tool attempts are not succeeding. Please respond in text, explaining what you were trying to do and what went wrong. Do not call more tools.]",
                }],
            })

    text = "\n".join(text_parts).strip()
    if not text:
        # Build transparent error from tool execution history
        failed = [t for t in tools_executed if "not found" in t.get("result", "").lower()
                  or "cannot" in t.get("result", "").lower()
                  or "error" in t.get("result", "").lower()]
        if failed:
            issues = "; ".join(f"{t['name']}({t['args'].get('filename', t['args'].get('directory', '?'))}) → {t['result'][:80]}" for t in failed[:3])
            text = f"I tried to help but hit access limits: {issues}. Try asking Spirit on the Forge or Anvil for files outside my practice directory."
        else:
            text = "I attempted to answer but my tool calls didn't produce the information I needed. Could you rephrase, or try asking Spirit on the Forge or Anvil?"
    return text, tools_executed


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
    payload = {
        "model": model or DIALOGUE_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "stream": True,
        "options": {"num_ctx": num_ctx},
    }
    if think is not None:
        payload["think"] = think
    reply_chunks = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)) as http:
        async with http.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
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
    content = ""
    for _ in range(MAX_TOOL_ROUNDS):
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)) as http:
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

        if not tool_calls:
            text = content.strip() if content.strip() else "(no response generated)"
            return text, tools_executed

        all_messages.append(msg)
        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            args = func.get("arguments", {})
            result = execute_tool(tool_name, args) if execute_tool else f"Unknown tool: {tool_name}"
            tools_executed.append({"name": tool_name, "args": args, "result": result})
            print(f"  Tool: {tool_name} -> {result}")
            all_messages.append({"role": "tool", "content": result})

    text = content.strip()
    if not text:
        failed = [t for t in tools_executed if "not found" in t.get("result", "").lower()
                  or "cannot" in t.get("result", "").lower()
                  or "error" in t.get("result", "").lower()]
        if failed:
            issues = "; ".join(f"{t['name']}({t['args'].get('filename', t['args'].get('directory', '?'))}) → {t['result'][:80]}" for t in failed[:3])
            text = f"I tried to help but hit access limits: {issues}. Try asking Spirit on the Forge or Anvil for files outside my practice directory."
        else:
            text = "I attempted to answer but my tool calls didn't produce the information I needed. Could you rephrase, or try asking Spirit on the Forge or Anvil?"
    return text, tools_executed
