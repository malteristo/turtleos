#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from runtime.audit import AuditLog, AuditRecord
from runtime.handoff import submit_practice_handoff
from runtime.model_probe import submit_model_probe
from runtime.paths import RuntimePaths
from runtime.readiness import RuntimeReadiness
from runtime.tasks import TaskStore


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # Runtime CLI should fail loudly and plainly.
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Turtle native runtime CLI")
    parser.add_argument("--principal", default="default", help="registry principal to operate as")
    parser.add_argument("--registry", default="mage_registry.yaml", help="path to mage_registry.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    handoff = subparsers.add_parser("handoff", help="submit a handoff as a durable runtime task")
    handoff.add_argument("--artifact", choices=["boom", "session", "proposal"], required=True)
    handoff.add_argument("--title", required=True)
    body_group = handoff.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body")
    body_group.add_argument("--body-file", type=Path)
    handoff.add_argument("--source", default="spirit")
    handoff.add_argument("--interface", default="cli")
    handoff.add_argument("--scope", default="practice")
    handoff.add_argument("--trust-level", default="operator")
    handoff.set_defaults(func=cmd_handoff)

    task = subparsers.add_parser("task", help="inspect runtime tasks")
    task_subparsers = task.add_subparsers(dest="task_command", required=True)
    task_list = task_subparsers.add_parser("list", help="list recent tasks")
    task_list.add_argument("--limit", type=int, default=20)
    task_list.set_defaults(func=cmd_task_list)
    task_show = task_subparsers.add_parser("show", help="show one task")
    task_show.add_argument("task_id")
    task_show.set_defaults(func=cmd_task_show)
    task_failures = task_subparsers.add_parser("failures", help="list active failed tasks")
    task_failures.add_argument("--limit", type=int, default=20)
    task_failures.set_defaults(func=cmd_task_failures)
    task_clear = task_subparsers.add_parser("clear-test-failures", help="mark deliberate test failures as cleared")
    task_clear.add_argument("--dry-run", action="store_true")
    task_clear.set_defaults(func=cmd_task_clear_test_failures)

    audit = subparsers.add_parser("audit", help="show audit records for one task")
    audit.add_argument("task_id")
    audit.set_defaults(func=cmd_audit)

    readiness = subparsers.add_parser("readiness", help="show native runtime readiness sensorium")
    readiness.add_argument("--limit", type=int, default=10, help="number of recent tasks/failures to include")
    readiness.set_defaults(func=cmd_readiness)

    probe = subparsers.add_parser("probe", help="run provider-neutral model probes")
    probe_subparsers = probe.add_subparsers(dest="probe_command", required=True)
    probe_run = probe_subparsers.add_parser("run", help="run the same prompt/context through explicit providers")
    probe_run.add_argument("--title", required=True)
    probe_run.add_argument("--provider", action="append", required=True, help="provider:model, e.g. ollama:qwen3.5:9b")
    prompt_group = probe_run.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file", type=Path)
    context_group = probe_run.add_mutually_exclusive_group()
    context_group.add_argument("--context", default="")
    context_group.add_argument("--context-file", type=Path)
    probe_run.add_argument("--source", default="spirit")
    probe_run.add_argument("--interface", default="cli")
    probe_run.add_argument("--scope", default="model-probe")
    probe_run.add_argument("--trust-level", default="operator")
    probe_run.set_defaults(func=cmd_probe_run)
    return parser


def cmd_handoff(args: argparse.Namespace) -> int:
    body = read_body(args)
    task = submit_practice_handoff(
        principal=args.principal,
        artifact=args.artifact,
        title=args.title,
        body=body,
        source=args.source,
        interface=args.interface,
        registry_path=Path(args.registry),
        scope=args.scope,
        trust_level=args.trust_level,
    )
    print_json({"task_id": task.task_id, "state": task.state, "artifact_refs": task.artifact_refs})
    return 0


def cmd_task_list(args: argparse.Namespace) -> int:
    paths = runtime_paths(args)
    store = TaskStore(paths.tasks_dir)
    rows: list[dict[str, Any]] = []
    for task in store.list()[: args.limit]:
        rows.append(
            {
                "task_id": task.task_id,
                "state": task.state,
                "kind": task.kind,
                "title": task.title,
                "updated_at": task.updated_at,
                "artifact_refs": task.artifact_refs,
            }
        )
    print_json(rows)
    return 0


def cmd_task_show(args: argparse.Namespace) -> int:
    paths = runtime_paths(args)
    task = TaskStore(paths.tasks_dir).load(args.task_id)
    print_json(task.to_dict())
    return 0


def cmd_task_failures(args: argparse.Namespace) -> int:
    paths = runtime_paths(args)
    store = TaskStore(paths.tasks_dir)
    failures = [task for task in store.list() if task.state == "failed"][: args.limit]
    print_json([summarize_task_for_cli(task) for task in failures])
    return 0


def cmd_task_clear_test_failures(args: argparse.Namespace) -> int:
    paths = runtime_paths(args)
    store = TaskStore(paths.tasks_dir)
    audit = AuditLog(paths.audit_dir)
    cleared = []
    for task in store.list():
        if not is_test_failure(task):
            continue
        if not args.dry_run:
            task.mark_cleared("deliberate runtime smoke/test failure cleared from active readiness")
            record = audit.append(
                AuditRecord(
                    "task.cleared",
                    "ok",
                    task_id=task.task_id,
                    event_id=task.source_event_id,
                    details={"reason": task.checkpoint.get("cleared", {}).get("reason")},
                )
            )
            task.audit_refs.append(record.record_id)
            store.save(task)
        cleared.append(summarize_task_for_cli(task))
    print_json({"dry_run": args.dry_run, "cleared": cleared})
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    paths = runtime_paths(args)
    print_json(AuditLog(paths.audit_dir).records_for_task(args.task_id))
    return 0


def cmd_readiness(args: argparse.Namespace) -> int:
    paths = runtime_paths(args)
    print_json(RuntimeReadiness(paths).assess(limit=args.limit))
    return 0


def cmd_probe_run(args: argparse.Namespace) -> int:
    prompt = read_text_arg(args.prompt, args.prompt_file)
    context = read_text_arg(args.context, args.context_file)
    task = submit_model_probe(
        principal=args.principal,
        title=args.title,
        prompt=prompt,
        context=context,
        providers=args.provider,
        source=args.source,
        interface=args.interface,
        registry_path=Path(args.registry),
        scope=args.scope,
        trust_level=args.trust_level,
    )
    print_json({"task_id": task.task_id, "state": task.state, "artifact_refs": task.artifact_refs})
    return 0 if task.state == "completed" else 1


def runtime_paths(args: argparse.Namespace) -> RuntimePaths:
    return RuntimePaths.for_principal(args.principal, registry_path=Path(args.registry))


def read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        return args.body_file.read_text(encoding="utf-8")
    return args.body


def read_text_arg(value: str | None, path: Path | None) -> str:
    if path:
        return path.read_text(encoding="utf-8")
    return value or ""


def summarize_task_for_cli(task) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "state": task.state,
        "kind": task.kind,
        "title": task.title,
        "updated_at": task.updated_at,
        "failure": task.failure,
        "artifact_refs": task.artifact_refs,
    }


def is_test_failure(task) -> bool:
    if task.state != "failed":
        return False
    event = task.checkpoint.get("event", {}) if isinstance(task.checkpoint, dict) else {}
    source = event.get("source", "")
    interface = event.get("interface", "")
    title = task.title.lower()
    if source == "smoke-suite" or interface in {"script", "cli-test"}:
        return True
    return "smoke test" in title or "smoke failure" in title or "test failure" in title


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
