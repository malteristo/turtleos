#!/usr/bin/env python3
"""Inventory a ChatGPT export zip. Metadata only. No note writes.

    python3 scripts/entwine_inventory.py ~/Downloads/export.zip --out ~/workshops/<root>/archives/chatgpt

Writes ``inventory.json`` and ``inventory.md`` under ``--out/<sha256>/``.
The zip is not copied. Message bodies never leave the parser.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from entwine_chatgpt import inventory_chatgpt_zip, write_inventory


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("zip_path", help="ChatGPT export zip")
    parser.add_argument(
        "--out",
        required=True,
        help="directory that will receive <sha256>/inventory.json",
    )
    args = parser.parse_args()
    zip_path = Path(args.zip_path).expanduser()
    inventory = inventory_chatgpt_zip(zip_path)
    dest = Path(args.out).expanduser() / inventory["zip_sha256"]
    written = write_inventory(dest, inventory)
    print(
        f"{inventory['conversation_count']} conversations · "
        f"{inventory['message_count']} messages · "
        f"sha256 {inventory['zip_sha256'][:12]} → {written}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
