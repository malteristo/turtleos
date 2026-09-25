#!/usr/bin/env python3
"""Memory experience shakedown — does Turtle remember what the room remembers?

Replays a scenario against a practice root **offline**: no Discord, the same
model the room uses, the same packet the turn would build. A scenario is a
message (optionally with prior turns) and what a member would need to see in
the reply for it to count as memory-informed.

    python3 scripts/shake_memory.py scenarios/*.yaml            # run
    python3 scripts/shake_memory.py --fixture                    # synthetic control
    python3 scripts/shake_memory.py s.yaml --build              # rebuild memory first
    python3 scripts/shake_memory.py s.yaml --packet-only        # no model call
    python3 scripts/shake_memory.py s.yaml --report out.md      # write findings

Scenario file (YAML):

    id: family-replay-2026-09-01
    root: ~/workshops/family            # practice root — memory is built here
    channel: 123                        # parent channel id, for tool scoping (optional)
    thread: "456"                       # the eddy spoken in — its notes are excluded
    model: gemma4:31b                   # default: the room's dialogue model
    history:                            # optional prior turns
      - role: user
        content: "[Alpha]: …"
    message: "what do you remember about …"
    expect:
      packet_contains_any: [keeper, lighthouse]   # passive memory reached the prompt
      reply_mentions_any: [keeper, lighthouse]    # the reply drew on it
      reply_must_not: ["no archive", "cannot see"] # the failure's own words
      no_false_check: true                         # "I checked" only if a tool ran
      no_native_we: true                           # no "we discussed" on imported history
      planted_native_we_fails: "I remember when we…"  # detector must be able to fail

Scenario files that name real people stay in the practitioner's private
workshop; this repository carries the runner and a synthetic fixture only.
"""
from __future__ import annotations

# Live model calls, and `--build` writes memory/ under a real root. Not for the
# unattended nightly gate (scripts/shake_report.py).
OFFLINE_SAFE = False

import argparse
import asyncio
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    import discord  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    from unittest.mock import MagicMock

    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ext", MagicMock())
    sys.modules.setdefault("discord.ext.tasks", MagicMock())
    sys.modules.setdefault("discord.ui", MagicMock())

import yaml
import memory_agent

# Words a reply uses when it claims to have looked something up. If any appear
# and no tool ran this turn, the reply narrated a search it did not make —
# the 2026-09-01 failure in one sentence.
_CHECK_CLAIMS = re.compile(
    r"\b(I (?:checked|looked|searched|went through|reviewed|scanned|consulted)|"
    r"(?:checking|looking through|searching) (?:our|the|my) (?:history|notes|records|archive))\b",
    re.I,
)


def _load_scenario(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("id", path.stem)
    data["root"] = os.path.expanduser(str(data.get("root") or ""))
    data.setdefault("history", [])
    data.setdefault("expect", {})
    return data


def _fixture_scenario(tmp: Path) -> dict:
    """A synthetic room whose topic is older than the recency window."""
    root = tmp / "harbour"
    eddies = root / "story" / "eddies"
    eddies.mkdir(parents=True)
    now = datetime.now().astimezone()
    for i in range(5):
        when = now - timedelta(days=9 + i * 6)
        (eddies / f"{i}-keeper.md").write_text(
            "---\n"
            f"thread: '{i}'\ntitle: the lighthouse keeper, again\ntrigger: idle\n"
            f"timestamp: '{when.isoformat(timespec='seconds')}'\n"
            "proposed-themes: [the lighthouse keeper's boundary stones]\n"
            "participants: [Alpha, Beta]\n---\n\n"
            "Alpha said the lighthouse keeper had moved the boundary stones again, "
            "and Beta felt the keeper's silence afterwards as a refusal to talk. "
            "They agreed the pattern repeats each visit: a small change to the "
            "garden, then no acknowledgement when asked.\n\n"
        )
    return {
        "id": "fixture-lighthouse",
        "root": str(root),
        "thread": "0",
        "message": "Turtle, what do you remember about the situation with the lighthouse keeper?",
        "history": [],
        "expect": {
            "packet_contains_any": ["lighthouse", "keeper"],
            "reply_mentions_any": ["lighthouse", "keeper", "boundary stones"],
            "reply_must_not": ["no archive", "no detailed archive", "cannot see"],
            "no_false_check": True,
        },
    }


def _exogenous_fixture_scenario(tmp: Path) -> dict:
    """Imported history that must not become native 'we talked' memory."""
    root = tmp / "harbour-import"
    folder = root / "story" / "exogenous" / "chatgpt"
    folder.mkdir(parents=True)
    now = datetime.now().astimezone()
    for i in range(2):
        when = now - timedelta(days=i)
        (folder / f"keep{i}.md").write_text(
            "---\n"
            "source: exogenous/chatgpt\n"
            f"conversation_id: keep{i}\n"
            f"title: lighthouse import {i}\n"
            f"created: '{when.isoformat(timespec='seconds')}'\n"
            "origin_platform: chatgpt\n"
            "origin_agent: ChatGPT\n"
            "route: personal\n"
            "entwined: '2026-09-10'\n"
            "proposed-themes: [the lighthouse keeper situation]\n"
            "---\n\n"
            "The lighthouse keeper had moved the boundary stones again.\n",
            encoding="utf-8",
        )
    return {
        "id": "fixture-exogenous-chatgpt",
        "root": str(root),
        "thread": "live-eddy",
        "message": "Turtle, what do you remember about the lighthouse keeper?",
        "history": [],
        "expect": {
            "packet_contains_any": ["imported", "chatgpt", "lighthouse"],
            "packet_must_not": ["story/eddies"],
            "planted_native_we_fails": (
                "I remember when we discussed the lighthouse last year."
            ),
            "reply_must_not": [
                "I remember when we",
                "we discussed this last year",
                "when we talked",
            ],
            "no_native_we": True,
            "no_false_check": True,
        },
    }


_BUILT_ROOTS: set[str] = set()


async def _run(scenario: dict, *, build: bool, packet_only: bool, tools: bool) -> dict:
    from mage import _practice_dir_ctx

    root = Path(scenario["root"])
    if not root.is_dir():
        return {"id": scenario["id"], "error": f"root not a directory: {root}"}
    token = _practice_dir_ctx.set(str(root))
    try:
        import memory_agent
        from continuity_engine import render_substrate_packet

        # Once per root per run: a model-formed build is minutes of inference,
        # and four scenarios against one room are four reads of one memory.
        if build and str(root) not in _BUILT_ROOTS:
            from mage import memory_roots

            chat = None
            if not packet_only:
                from background import reflection_chat

                chat = reflection_chat
            topics = await memory_agent.rebuild_room_memory(root, memory_roots(root), chat=chat)
            _BUILT_ROOTS.add(str(root))
            print(f"  built {len(topics)} topics ({'model' if any(t.formed_by == 'model' for t in topics) else 'keyword'})")

        model = scenario.get("model")
        if not model:
            from state import TURTLE_MODEL

            model = TURTLE_MODEL
        considered: list[dict] = []
        packet = render_substrate_packet(
            root,
            dialogue_model=model,
            current_thread=str(scenario.get("thread") or "") or None,
            message_text=scenario["message"],
            topics_considered=considered,
        )
        result = {
            "id": scenario["id"],
            "model": model,
            "packet_chars": len(packet),
            "topics_selected": [c["label"] for c in considered if c.get("selected")],
            "checks": {},
            "reply": "",
            "tools": [],
        }
        expect = scenario["expect"]
        low_packet = packet.lower()
        if expect.get("packet_contains_any"):
            result["checks"]["packet_contains_any"] = any(
                str(w).lower() in low_packet for w in expect["packet_contains_any"]
            )
        if expect.get("packet_must_not"):
            result["checks"]["packet_must_not"] = not any(
                str(w).lower() in low_packet for w in expect["packet_must_not"]
            )
        planted = expect.get("planted_native_we_fails")
        if planted:
            result["checks"]["planted_native_we_fails"] = memory_agent.has_native_we_voice(
                str(planted)
            )
        if packet_only:
            result["packet"] = packet
            return result

        from prompts import get_native_eddy_prompt

        system_prompt = packet + get_native_eddy_prompt(None)
        messages = list(scenario["history"]) + [{"role": "user", "content": scenario["message"]}]

        tools_executed: list[dict] = []
        if tools:
            from llm import chat_ollama_with_tools
            from tos_tools import execute_tos_tool, memory_tools_for_channel

            reply, tools_executed = await chat_ollama_with_tools(
                system_prompt,
                messages,
                model_override=model,
                tos_tools=memory_tools_for_channel(scenario.get("channel")),
                execute_tool=execute_tos_tool,
                max_rounds=2,
            )
        else:
            from llm import chat_ollama

            reply = await chat_ollama(system_prompt, messages, model=model, num_ctx=32768, think=False)

        result["reply"] = reply
        result["tools"] = [t.get("name") for t in tools_executed]
        low = reply.lower()
        if expect.get("reply_mentions_any"):
            result["checks"]["reply_mentions_any"] = any(
                str(w).lower() in low for w in expect["reply_mentions_any"]
            )
        if expect.get("reply_must_not"):
            result["checks"]["reply_must_not"] = not any(
                str(w).lower() in low for w in expect["reply_must_not"]
            )
        if expect.get("no_false_check"):
            claims = bool(_CHECK_CLAIMS.search(reply))
            result["checks"]["no_false_check"] = (not claims) or bool(tools_executed)
        if expect.get("no_native_we"):
            result["checks"]["no_native_we"] = not memory_agent.has_native_we_voice(reply)
        return result
    finally:
        _practice_dir_ctx.reset(token)


def _render(results: list[dict]) -> str:
    lines = [f"# Memory shakedown — {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}", ""]
    for r in results:
        if r.get("error"):
            lines += [f"## {r['id']} — ERROR", "", r["error"], ""]
            continue
        verdict = "PASS" if all(r["checks"].values()) else "FAIL"
        lines += [f"## {r['id']} — {verdict}", ""]
        lines.append(f"- model: `{r['model']}` · packet {r['packet_chars']} chars · tools: {r['tools'] or 'none'}")
        lines.append(f"- topics carried: {', '.join(r['topics_selected']) or 'none'}")
        for name, ok in r["checks"].items():
            lines.append(f"- {'✓' if ok else '✗'} {name}")
        if r.get("reply"):
            lines += ["", "> " + r["reply"].replace("\n", "\n> "), ""]
        if r.get("packet"):
            lines += ["", "```", r["packet"], "```", ""]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenarios", nargs="*", help="scenario YAML files")
    parser.add_argument("--fixture", action="store_true", help="run the synthetic control scenario")
    parser.add_argument("--build", action="store_true", help="rebuild memory/ under the root first")
    parser.add_argument("--packet-only", action="store_true", help="render the packet, call no model")
    parser.add_argument("--no-tools", action="store_true", help="plain call instead of the remembering pair")
    parser.add_argument("--report", metavar="PATH", help="write the markdown report here")
    args = parser.parse_args()

    scenarios = [_load_scenario(Path(p)) for p in args.scenarios]
    tmp_ctx = tempfile.TemporaryDirectory() if args.fixture else None
    if tmp_ctx is not None:
        fixture_root = Path(tmp_ctx.name)
        scenarios.insert(0, _fixture_scenario(fixture_root))
        scenarios.insert(1, _exogenous_fixture_scenario(fixture_root))
        args.build = True
    if not scenarios:
        parser.error("no scenarios given (pass files or --fixture)")

    results = []
    for sc in scenarios:
        print(f"== {sc['id']}")
        results.append(asyncio.run(_run(sc, build=args.build, packet_only=args.packet_only, tools=not args.no_tools)))
        checks = results[-1].get("checks", {})
        print("   " + (" ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in checks.items()) or results[-1].get("error", "")))

    report = _render(results)
    if args.report:
        Path(args.report).write_text(report, encoding="utf-8")
        print(f"report → {args.report}")
    else:
        print(report)
    if tmp_ctx is not None:
        tmp_ctx.cleanup()
    return 0 if all(all(r.get("checks", {}).values()) and not r.get("error") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
