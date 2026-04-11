"""turtleOS triage layer — sub-2B model message classification."""

import json

import httpx

from state import OLLAMA_URL, TRIAGE_MODEL


TRIAGE_PROMPT = """Classify this Discord message. Output ONLY valid JSON, nothing else.

Categories:
- "command" — starts with ! (already handled, skip)
- "greeting" — casual hello, hey, good morning
- "casual" — brief, light, social (emoji reactions, short comments, banter)
- "practice" — about boom, bright, compass, intentions, practice state, sessions
- "deep" — philosophical, emotional, complex reasoning, life questions
- "link" — shares a URL for discussion
- "continuation" — single dot "." or brief continuation of prior topic
- "task" — asks Turtle to do something specific (edit file, create thread, etc.)

Output format: {"category": "<category>", "needs_state": <true/false>}

needs_state = true when the response benefits from loading practice files (boom, bright, compass).
needs_state = false for greetings, casual chat, simple tasks.

Message: """


def _heuristic_triage(text: str) -> dict:
    """Fast content-based classification when triage model is unavailable."""
    t = text.strip().lower()

    # Commands
    if t.startswith("!"):
        return {"category": "command", "needs_state": False}

    # Continuation
    if t in (".", "..", "...", "go", "continue", "next"):
        return {"category": "continuation", "needs_state": False}

    # Greetings
    greetings = ("hello", "hey", "hi", "good morning", "good evening", "gm", "gn", "morning")
    if any(t.startswith(g) for g in greetings) and len(t) < 30:
        return {"category": "greeting", "needs_state": False}

    # Links
    if "http://" in t or "https://" in t:
        return {"category": "link", "needs_state": False}

    # Tasks (imperative verbs)
    task_starters = ("create ", "make ", "write ", "edit ", "update ", "add ", "remove ",
                     "delete ", "show ", "list ", "search ", "find ", "read ", "open ")
    if any(t.startswith(v) for v in task_starters):
        return {"category": "task", "needs_state": True}

    # Short casual messages
    if len(t) < 20 and not "?" in t:
        return {"category": "casual", "needs_state": False}

    # Questions or longer text — default to practice with state
    return {"category": "practice", "needs_state": True}


async def triage_message(text: str) -> dict:
    """Pre-classify a message using the triage model (sub-2B, sub-second)."""
    default = {"category": "practice", "needs_state": True}
    try:
        prompt = TRIAGE_PROMPT + text[:500]
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)) as http:
            payload = {
                "model": TRIAGE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {"num_ctx": 2048},
                "format": "json",
                "keep_alive": "10m",
            }
            resp = await http.post(f"{OLLAMA_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        raw = data.get("message", {}).get("content", "").strip()
        result = json.loads(raw)
        if "category" not in result:
            return default
        result.setdefault("needs_state", True)
        return result
    except Exception as e:
        print(f"Triage failed ({type(e).__name__}), using heuristic fallback: {e}")
        return _heuristic_triage(text)


async def prewarm_triage():
    """Pre-warm the triage model so first message classification is instant."""
    try:
        result = await triage_message("hello")
        print(f"Triage pre-warmed: {result}")
    except Exception as e:
        print(f"Triage pre-warm failed: {e}")
