#!/usr/bin/env python3
"""Distill a ChatGPT export into exogenous notes. Offline job. Not a turn tool.

    python3 scripts/entwine_distill.py ZIP \\
        --personal ~/workshops/<owner> \\
        --health ~/workshops/health \\
        --inventory ~/workshops/<owner>/archives/chatgpt/<sha256> \\
        --limit 5 --dry-run

The live local model does not open the zip. Capable classify is ``--model
claude-…`` (API). Tests use ``--classify-json``. ``--quiet`` prints ids and
routes, not titles or bodies.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

LOCAL_DIALOGUE_MODELS = frozenset(
    {
        "gemma4:31b",
        "gemma4:26b",
        "qwen3.5:27b",
        "qwen3.5:9b",
        "qwen3.5:4b",
        "qwen3.5:0.8b",
    }
)
OFFLINE_CAPABLE_MODELS = frozenset({"qwen3.6:35b-a3b"})

from entwine_chatgpt import (
    CLASSIFY_SYSTEM,
    EntwineRoots,
    deterministic_skip,
    entwine_conversation,
    extract_conversation,
    format_classify_user,
    inventory_chatgpt_zip,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("zip_path", help="ChatGPT export zip")
    parser.add_argument("--personal", required=True, help="owner's personal practice root")
    parser.add_argument("--health", help="owner's isolated health root")
    parser.add_argument(
        "--forbidden",
        action="append",
        default=[],
        help="roots that must never receive a write (repeatable)",
    )
    parser.add_argument("--inventory", help="existing inventory.json directory (optional)")
    parser.add_argument("--ids", help="comma-separated conversation ids")
    parser.add_argument("--limit", type=int, default=0, help="max conversations to open")
    parser.add_argument("--min-user", type=int, default=0, help="ignore rows with fewer user messages")
    parser.add_argument(
        "--spread",
        action="store_true",
        help="space the limit across the inventory instead of taking the first rows",
    )
    parser.add_argument("--dry-run", action="store_true", help="extract and skip, write nothing")
    parser.add_argument("--quiet", action="store_true", help="print id and route only — no titles")
    parser.add_argument(
        "--classify-json",
        help="path to a JSON object {id: classifier_reply} for tests / replay",
    )
    parser.add_argument(
        "--model",
        help="capable API model (claude-…). Do not pass the live local dialogue model.",
    )
    args = parser.parse_args()
    zip_path = Path(args.zip_path).expanduser()
    roots = EntwineRoots(
        personal=Path(args.personal).expanduser(),
        health=Path(args.health).expanduser() if args.health else None,
    )
    forbidden = [Path(item).expanduser() for item in args.forbidden]
    inventory = _load_inventory(zip_path, args.inventory)
    wanted = [item.strip() for item in (args.ids or "").split(",") if item.strip()]
    rows = inventory.get("conversations") or []
    if wanted:
        rows = [row for row in rows if row.get("id") in set(wanted)]
    if args.min_user:
        rows = [row for row in rows if int(row.get("user_messages") or 0) >= args.min_user]
    rows = _select_rows(rows, limit=args.limit, spread=args.spread)
    replay = _load_replay(args.classify_json)
    written = 0
    skipped = 0
    routes: dict[str, int] = {}
    for row in rows:
        conv_id = str(row.get("id") or "")
        if args.dry_run:
            conversation = extract_conversation(zip_path, conv_id)
            reason = deterministic_skip(conversation)
            _emit(conv_id, reason or "classify", quiet=args.quiet)
            skipped += 1 if reason else 0
            continue
        classify = _classifier(conv_id, replay, args.model)
        if classify is None:
            print(f"{conv_id}\tneed-classifier", file=sys.stderr)
            continue
        try:
            paths = entwine_conversation(
                zip_path,
                conv_id,
                roots,
                classify=classify,
                forbidden_roots=forbidden,
            )
        except Exception as exc:
            print(f"{conv_id}\tFAIL {type(exc).__name__}", file=sys.stderr)
            continue
        written += len(paths)
        for path in paths:
            route = "health" if "/health/" in str(path) or path.as_posix().endswith("-health.md") else "personal"
            if "route: health" in path.read_text(encoding="utf-8"):
                route = "health"
            routes[route] = routes.get(route, 0) + 1
        _emit(conv_id, f"wrote {len(paths)}", quiet=args.quiet)
    print(
        f"done · rows {len(rows)} · wrote {written} · "
        f"health {routes.get('health', 0)} · personal {routes.get('personal', 0)} · "
        f"dry-skip {skipped}"
    )
    return 0


def _select_rows(rows: list, *, limit: int, spread: bool) -> list:
    if not limit or limit >= len(rows):
        return rows if not limit else rows[:limit]
    if not spread or len(rows) <= limit:
        return rows[:limit]
    step = max(1, len(rows) // limit)
    picked = rows[::step][:limit]
    return picked


def _emit(conv_id: str, status: str, *, quiet: bool) -> None:
    print(f"{conv_id}\t{status}")


def _classifier(conv_id: str, replay: dict[str, str], model: str | None):
    if conv_id in replay:
        return lambda _conversation, *, _id=conv_id: replay[_id]
    if not model:
        return None
    if model in LOCAL_DIALOGUE_MODELS:
        raise ValueError(
            "the live local dialogue model does not open the zip; "
            "pass claude-… or the offline capable model qwen3.6:35b-a3b"
        )

    def classify(conversation: dict, *, _model: str = model) -> str:
        return _classify_capable(conversation, _model)

    return classify


def _classify_capable(conversation: dict, model: str) -> str:
    import asyncio

    user = format_classify_user(conversation)
    if model.startswith("claude-"):
        from llm import chat_anthropic_with_model

        text, _tools = asyncio.run(
            chat_anthropic_with_model(
                CLASSIFY_SYSTEM,
                [{"role": "user", "content": user}],
                model,
            )
        )
        return text
    if model in OFFLINE_CAPABLE_MODELS:
        from llm import chat_ollama

        return asyncio.run(
            chat_ollama(
                CLASSIFY_SYSTEM,
                [{"role": "user", "content": user}],
                model=model,
                num_ctx=16384,
                think=False,
            )
        )
    raise ValueError(f"unsupported capable model: {model}")


def _load_inventory(zip_path: Path, inventory_dir: str | None) -> dict:
    if inventory_dir:
        path = Path(inventory_dir).expanduser()
        if path.is_dir():
            path = path / "inventory.json"
        return json.loads(path.read_text(encoding="utf-8"))
    return inventory_chatgpt_zip(zip_path)


def _load_replay(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    raw = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("classify-json must be an object keyed by conversation id")
    return {str(key): (value if isinstance(value, str) else json.dumps(value)) for key, value in raw.items()}


if __name__ == "__main__":
    raise SystemExit(main())
