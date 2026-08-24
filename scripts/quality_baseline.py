#!/usr/bin/env python3
"""Compute the structural half of the quality measures in `docs/quality-measures.md`.

Written 2026-08-14. The point of this script is that the numbers in that document
are *generated*, not typed. A document holding hand-copied metrics is the exact
shape that let `docs/acceptance/README.md` drift 41 commits: it asked its reader
to remember, and remembering is not a mechanism.

The measures that matter most here — how long a defect was live, and whether a
fixed defect's class came back — cannot be computed from the tree. They need a
human or an agent to date the defect against the commit that introduced it. Those
live in the ledger tables of the same document, hand-kept and append-only. What
this script covers is the part a machine can see.

Usage:
    python3 scripts/quality_baseline.py            # human-readable report
    python3 scripts/quality_baseline.py --row      # one markdown row to append
    python3 scripts/quality_baseline.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Derived trees a first-timer (or a publish) can leave on disk. Counting them
# as production doubled the baseline when `.publish-worktree/` existed.
_NOISE_PARTS = frozenset({".publish-worktree", "venv", "node_modules", ".git"})


def is_tree_noise(path: Path) -> bool:
    return any(part in _NOISE_PARTS for part in path.parts)


def _py_files(directory: Path, pattern: str = "*.py") -> list[Path]:
    return sorted(p for p in directory.glob(pattern) if p.is_file())


def _loc(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        try:
            total += len(path.read_text(encoding="utf-8").splitlines())
        except OSError:
            continue
    return total


def _imports_transport(path: Path) -> bool:
    """Whether this module imports Discord directly, by AST rather than by grep.

    A string mentioning `import discord` in a docstring or a test fixture is not
    an import, and the count is being used to judge whether a boundary is moving.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[0] == "discord" for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] == "discord":
                return True
    return False


def _runtime_adoption() -> tuple[int, int]:
    """How much of `runtime/` nothing outside `runtime/` uses — modules, then lines.

    An independent review on 2026-08-14 found the sharpest thing anybody has said
    about this repo: `runtime/messages.py` — the documented seam between a chat
    platform and the runtime — had **zero production importers**. The boundary
    guard was real and passing; nothing crossed the boundary it guarded. Its own
    excellence is what made the gap durable, because a green test reads as a
    working architecture.

    So the claim gets a number. This is the figure that has to fall for the
    transport work to mean anything, and it can only fall by a production path
    actually using a value object — not by moving a file.
    """
    runtime_dir = REPO / "runtime"
    if not runtime_dir.is_dir():
        return 0, 0

    modules: dict[str, Path] = {}
    for path in runtime_dir.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        rel = path.relative_to(REPO).with_suffix("")
        modules[".".join(rel.parts)] = path

    consumers = [
        p
        for p in REPO.rglob("*.py")
        if not is_tree_noise(p)
        and "tests" not in p.parts
        and "runtime" not in p.parts
        and "scripts" not in p.parts
    ]

    used: set[str] = set()
    for path in consumers:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    used.update(m for m in modules if alias.name == m)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod in modules:
                    used.add(mod)
                # `from runtime import messages`
                for alias in node.names:
                    used.update(m for m in modules if m == f"{mod}.{alias.name}")

    unwired = sorted(set(modules) - used)
    lines = _loc([modules[m] for m in unwired])
    return len(unwired), lines


def _test_count() -> int | None:
    """Number of collected tests. None when collection fails — never a guess.

    "Fails" includes *partial* failure, and that distinction is the whole point.
    pytest prints `1297 tests collected, 3 errors` and exits non-zero: a file
    that cannot be imported contributes nothing to the count and nothing to the
    line either. Reading the number alone reports a total that silently omits
    every test in every unimportable file — measured 2026-08-15, when two files
    had been erroring at collection for long enough that nobody knew, and the
    series had been printing a confident number the whole time.

    A measure that cannot see a whole test file going dark is the failure this
    document exists to catch, one level up. So: any collection error, no number.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    for line in reversed(proc.stdout.splitlines()):
        if "test" in line and "collected" in line:
            if "error" in line:
                return None
            for token in line.split():
                if token.isdigit():
                    return int(token)
    return None


def _transport_exemptions() -> int | None:
    """Size of the transport-boundary exemption list — the honest record of the seam.

    This is the number that should fall, and only because a module stopped
    needing a transport. It is read from the test rather than counted by hand.
    """
    path = REPO / "tests" / "test_transport_boundary.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "ADAPTER_EXEMPT" in names:
                try:
                    return len(ast.literal_eval(node.value))
                except (ValueError, TypeError):
                    return None
    return None


def measure() -> dict:
    root_modules = _py_files(REPO)
    test_files = _py_files(REPO / "tests")
    packages = sorted(
        p.parent.name
        for p in REPO.rglob("__init__.py")
        if not is_tree_noise(p)
    )
    prod_loc = _loc(root_modules) + _loc(
        [
            p
            for p in REPO.rglob("*.py")
            if not is_tree_noise(p) and p.parent != REPO and "tests" not in p.parts
        ]
    )
    test_loc = _loc(test_files)
    over_1000 = sorted(
        (len(p.read_text(encoding="utf-8").splitlines()), p.name) for p in root_modules
    )
    over_1000 = [name for loc, name in over_1000 if loc >= 1000]
    unwired_modules, unwired_lines = _runtime_adoption()

    return {
        "date": date.today().isoformat(),
        "root_modules": len(root_modules),
        "packages": len(packages),
        "modules_over_1000_lines": len(over_1000),
        "largest_module_lines": max(
            (len(p.read_text(encoding="utf-8").splitlines()) for p in root_modules), default=0
        ),
        "production_loc": prod_loc,
        "test_loc": test_loc,
        "test_to_production_ratio": round(test_loc / prod_loc, 2) if prod_loc else 0.0,
        "test_files": len(test_files),
        "tests_collected": _test_count(),
        "modules_importing_transport": sum(1 for p in root_modules if _imports_transport(p)),
        "transport_boundary_exemptions": _transport_exemptions(),
        "runtime_modules_unused_by_production": unwired_modules,
        "runtime_lines_unused_by_production": unwired_lines,
        "shake_scripts": len(_py_files(REPO / "scripts", "shake_*.py")),
    }


# The order these appear in the document's generated table. Adding a metric here
# without adding the column is caught by `tests/test_quality_measures.py`.
ROW_FIELDS = (
    "date",
    "root_modules",
    "packages",
    "modules_over_1000_lines",
    "production_loc",
    "test_loc",
    "test_to_production_ratio",
    "tests_collected",
    "modules_importing_transport",
    "transport_boundary_exemptions",
    "runtime_lines_unused_by_production",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--row", action="store_true", help="one markdown table row")
    args = parser.parse_args()

    data = measure()

    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    if args.row:
        cells = ["—" if data.get(f) is None else str(data.get(f)) for f in ROW_FIELDS]
        print("| " + " | ".join(cells) + " |")
        return 0

    width = max(len(k) for k in data)
    for key, value in data.items():
        print(f"{key.replace('_', ' '):<{width}}  {'—' if value is None else value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
