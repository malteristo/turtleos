#!/usr/bin/env python3
"""Add one operation to grants whose profile now includes it.

A profile edit does not widen a grant. This is the explicit add. An operation
the profile does not list is refused, and that grant is left as it was.

The credential is not printed.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mcp_access.grants import GrantStore


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: grant_add_operation.py <operation>", file=sys.stderr)
        return 2
    operation = argv[1]
    store = GrantStore()
    grants = store.all()
    if not grants:
        print("no grants")
        return 0
    for grant in grants:
        result = store.add_operation(grant.id, operation)
        print(f"{grant.id} {grant.profile} {grant.principal}: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
