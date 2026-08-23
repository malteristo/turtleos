#!/usr/bin/env python3
"""The true dependency graph of the flat module namespace, cycles included.

**Why this exists.** An independent review on 2026-08-14 ranked "kill import-time
side effects and enforce three layers" as the highest-leverage restructuring
available, and named `683 imports deferred inside function bodies` as the reason
the graph is invisible: *"not style but load-bearing scaffolding holding a
cycle-ridden graph together."* That was a claim about structure with no
instrument behind it. This is the instrument.

**What it found on first run (2026-08-15), and it is sharper than the review.**
The module-level import graph is **acyclic** — 227 edges, zero cycles. Add the
308 function-body imports back and **50 of 95 modules collapse into a single
strongly connected component.** Half the codebase is one mutual-dependency blob,
held apart at import time, and only at import time, by imports written inside
functions.

That is the whole layering problem stated as one number. `core/` → `services/`
→ `transport/` is a proposal to break that component; until it shrinks, no
amount of moving files has changed anything. Moving a module between directories
does not move this number. Only removing a dependency does.

**Why an instrument before a restructuring.** The transport boundary is the
worked example in this repo: the rule existed as a sentence in
`runtime/__init__.py` for 100 days and was worth nothing until
`test_transport_boundary.py` made violating it impossible. `runtime lines unused
by production` then ratcheted 466 → 241 because a number nobody could fudge was
attached to it. Same shape here, in the other order: the check and the baseline
first, so every later move is either visible in the number or was not a move.

Usage:
    python3 scripts/import_graph.py            # human-readable
    python3 scripts/import_graph.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _resolve(dotted: str, package: str | None, level: int, known: set[str]) -> str | None:
    """Map an import to a node in the graph, or None if it leaves the project.

    Package-aware on purpose. When `core/` was created on 2026-08-15 the first
    version of this function looked at top-level names only, which meant a
    module moved from the root into a package left the measured universe
    entirely — and the ratchet would have read that as progress. **A structural
    measure that a `git mv` can improve is measuring the directory tree, not the
    structure.** So `core.atomic_io` is a node, and an import of it is an edge.
    """
    if level > 0:
        if package is None:
            return None
        candidate = f"{package}.{dotted}" if dotted else package
    else:
        candidate = dotted
    parts = candidate.split(".")
    # Longest prefix wins: `from runtime.adapters import x` is an edge to
    # `runtime.adapters` when that is a module, and to `runtime` otherwise.
    for stop in range(len(parts), 0, -1):
        name = ".".join(parts[:stop])
        if name in known:
            return name
    return None


def _local_imports(
    path: Path,
    known: set[str],
    *,
    me: str | None = None,
    package: str | None = None,
) -> tuple[set[str], set[str]]:
    """Imports of project modules, split by whether they run at import time.

    Returns ``(module_level, deferred)``. An import inside *any* function body
    is deferred — that is precisely the set that keeps a cycle from raising at
    boot while leaving the dependency entirely real at runtime.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    inside_function: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                inside_function.add(id(child))

    module_level: set[str] = set()
    deferred: set[str] = set()
    me = me if me is not None else path.stem
    for node in ast.walk(tree):
        resolved: list[str | None] = []
        if isinstance(node, ast.Import):
            resolved = [_resolve(a.name, package, 0, known) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = _resolve(node.module or "", package, node.level, known)
            resolved = [base]
            if node.level > 0 or node.module:
                # `from core import models` names the module in `names`, not in
                # `module` — without this the edge lands on the package instead.
                prefix = (node.module or "") if node.level == 0 else (
                    f"{package}.{node.module}" if node.module else (package or "")
                )
                for alias in node.names:
                    dotted = f"{prefix}.{alias.name}" if prefix else alias.name
                    if dotted in known:
                        resolved.append(dotted)
        else:
            continue
        for target in resolved:
            if target is not None and target != me:
                (deferred if id(node) in inside_function else module_level).add(target)

    return module_level, deferred


def _strongly_connected(graph: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan, iterative — the recursive form overflows on a 50-node component."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0

    for root in graph:
        if root in index:
            continue
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, child_i = work[-1]
            if child_i == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack[node] = True
            recursed = False
            children = sorted(graph.get(node, ()))
            for i in range(child_i, len(children)):
                child = children[i]
                if child not in index:
                    work[-1] = (node, i + 1)
                    work.append((child, 0))
                    recursed = True
                    break
                if on_stack.get(child):
                    low[node] = min(low[node], index[child])
            if recursed:
                continue
            if low[node] == index[node]:
                component = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    component.append(w)
                    if w == node:
                        break
                if len(component) > 1:
                    components.append(sorted(component))
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

    return sorted(components, key=len, reverse=True)


SKIP_DIRS = {"venv", ".venv", "__pycache__", "tests", "scripts", "archive", ".git"}


def _discover(root: Path) -> tuple[dict[str, Path], dict[str, str | None]]:
    """Every project module: the flat root namespace **and** packages.

    Packages are included so that moving a module into one does not remove it
    from the measurement. `core/atomic_io.py` is the node `core.atomic_io`.
    """
    modules: dict[str, Path] = {}
    package_of: dict[str, str | None] = {}

    for path in sorted(root.glob("*.py")):
        if path.stem == "__init__":
            continue
        modules[path.stem] = path
        package_of[path.stem] = None

    for pkg_init in sorted(root.glob("*/__init__.py")):
        pkg_dir = pkg_init.parent
        if pkg_dir.name in SKIP_DIRS:
            continue
        for path in sorted(pkg_dir.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(root).with_suffix("")
            parts = list(rel.parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            name = ".".join(parts)
            if not name:
                continue
            modules[name] = path
            package_of[name] = ".".join(parts[:-1]) if len(parts) > 1 else parts[0]

    return modules, package_of


def measure(root: Path | None = None) -> dict:
    """Measure the project namespace at ``root`` (defaults to the repo root)."""
    root = Path(root) if root is not None else REPO
    modules, package_of = _discover(root)

    module_level: dict[str, set[str]] = defaultdict(set)
    deferred: dict[str, set[str]] = defaultdict(set)
    for name, path in modules.items():
        top, later = _local_imports(
            path, set(modules), me=name, package=package_of.get(name)
        )
        module_level[name] = top
        deferred[name] = later

    boot_graph = {m: module_level[m] for m in modules}
    true_graph = {m: module_level[m] | deferred[m] for m in modules}

    fan_in: Counter[str] = Counter()
    for deps in true_graph.values():
        for dep in deps:
            fan_in[dep] += 1

    boot_cycles = _strongly_connected(boot_graph)
    true_cycles = _strongly_connected(true_graph)
    largest = true_cycles[0] if true_cycles else []
    hub, hub_count = (fan_in.most_common(1) or [("", 0)])[0]

    return {
        "modules": len(modules),
        "root_modules": sum(1 for m in modules if package_of.get(m) is None),
        "packaged_modules": sum(1 for m in modules if package_of.get(m) is not None),
        "module_level_edges": sum(len(v) for v in boot_graph.values()),
        "deferred_edges": sum(len(deferred[m]) for m in modules),
        "distinct_edges": sum(len(v) for v in true_graph.values()),
        "modules_with_deferred_imports": sum(1 for m in modules if deferred[m]),
        "import_time_cycles": len(boot_cycles),
        "runtime_cycles": len(true_cycles),
        "largest_runtime_cycle": len(largest),
        "largest_runtime_cycle_members": largest,
        "hub_module": hub,
        "hub_fan_in": hub_count,
        "top_fan_in": fan_in.most_common(8),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    data = measure()
    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    print(f"{'modules (root + packages)':40} {data['modules']}")
    print(f"{'  in the flat root namespace':40} {data['root_modules']}")
    print(f"{'  inside a package':40} {data['packaged_modules']}")
    print(f"{'module-level edges':40} {data['module_level_edges']}")
    print(f"{'deferred edges (inside functions)':40} {data['deferred_edges']}")
    print(f"{'distinct edges':40} {data['distinct_edges']}")
    print(f"{'modules deferring at least one import':40} {data['modules_with_deferred_imports']}")
    print(f"{'cycles at import time':40} {data['import_time_cycles']}")
    print(f"{'cycles counting deferred imports':40} {data['runtime_cycles']}")
    print(f"{'largest such cycle':40} {data['largest_runtime_cycle']}")
    print(f"{'busiest module':40} {data['hub_module']} ({data['hub_fan_in']} importers)")
    print()
    print("top fan-in:")
    for name, count in data["top_fan_in"]:
        print(f"  {name:30} {count}")
    if data["largest_runtime_cycle"]:
        print()
        print(f"largest cycle ({data['largest_runtime_cycle']} modules):")
        members = data["largest_runtime_cycle_members"]
        for i in range(0, len(members), 4):
            print("  " + "  ".join(f"{m:22}" for m in members[i : i + 4]).rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
