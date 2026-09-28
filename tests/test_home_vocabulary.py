"""A member's own channel is their home channel; River is only the agent.

Destination: autoresearch/proposals/2026-09-27-home-channels.md (sanctioned
2026-09-27). The guard reads what members can see — string literals in the
shipped Python (docstrings and comments are for maintainers and are not read)
and the member-facing templates. Registry type ids (`river`, `hosted-river`,
`shared-river`) and module names stay: decided, not forgotten — see the
proposal.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ROOM_AS_RIVER = re.compile(
    r"\b(your|their|his|her|own|private|practice|personal)\s+rivers?\b"
    r"|(?<![-\w])river\s+channels?\b"
    r"|#river-"
    r"|\bclaim\s+your\s+river\b"
    r"|\bin\s+the\s+river\b",
    re.IGNORECASE,
)

MEMBER_TEMPLATES = ("template/practitioner", "template/flows")

# Not scanned: tests, operator scripts under scripts/, and the agent's own prompt files under template/character,
# where "river channel" instructs River about its surface rather than naming a
# member's room. Dated announcements under template/announcements are records of
# what was posted and stay as posted.
SKIP_DIRS = {"tests", "scripts", "venv", ".venv", "node_modules", "autoresearch", "archive", "issues"}


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(
                getattr(body[0], "value", None), ast.Constant
            ):
                ids.add(id(body[0].value))
    return ids


def python_hits() -> list[str]:
    hits = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if rel.parts[0] in SKIP_DIRS or rel.parts[0].startswith("."):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        docs = _docstring_ids(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
                and ROOM_AS_RIVER.search(node.value)
            ):
                hits.append(f"{rel}:{node.lineno}: {node.value.strip()[:80]}")
    return hits


def template_hits() -> list[str]:
    hits = []
    for folder in MEMBER_TEMPLATES:
        for path in (ROOT / folder).rglob("*.md"):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if ROOM_AS_RIVER.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:80]}")
    return hits


class HomeVocabularyTests(unittest.TestCase):
    def test_member_facing_strings_do_not_call_a_room_a_river(self):
        self.assertEqual(python_hits(), [])

    def test_member_templates_do_not_call_a_room_a_river(self):
        self.assertEqual(template_hits(), [])

    def test_the_pattern_catches_the_old_wording(self):
        # Positive control: every phrase the sweep removed would be caught.
        for old in (
            "This is now your private river (`#river-sam`).",
            "Message pinned in river channel.",
            "pick this up in your river.",
            "# Claim your river",
            "**In the river**, Turtle does not chat",
            "a notify act in **their own river**",
        ):
            self.assertRegex(old, ROOM_AS_RIVER)
        for fine in ("River posts the card.", "shared-river", "hosted-river", "River owns the parent channel"):
            self.assertNotRegex(fine, ROOM_AS_RIVER)


if __name__ == "__main__":
    unittest.main()
