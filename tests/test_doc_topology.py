"""The documentation tree makes three claims about itself. These fail when it stops.

2026-08-18. Two files were both called architecture — ``ARCHITECTURE.md`` (the
software) and ``docs/architecture.md`` (one deployment) — and the boundary
between them had leaked in three places: the Mini-to-Forge sync mapping was
written out in both and both were wrong in the same way for 50 days; the root
file carried a second spec-to-module table that ``docs/traceability-matrix.md``
declares itself the single index for; and the root file paraphrased an identity
file that had long since stopped having that shape.

The repair renamed the deployment file to ``docs/live-runtime.md`` and wrote
three claims into the docs. A claim with no mechanism is a defect here even when
it is currently true, so each one is checked:

1. **No relative link in a tracked markdown file dangles.** A rename is exactly
   the operation that breaks these, and at the time this was written the tree
   had 327 relative links and zero broken, so the guard goes in at full strength
   with no exemption list. If one is ever needed, add it here with the reason —
   an exemption that is a decision looks nothing like one that is neglect, and
   only a written reason tells them apart.

2. **Only the matrix keeps a spec index.** Enumerated by *shape*, not by name:
   any table with several rows opening on a spec section is an index, whatever
   the file is called. The deleted table had 26 such rows and no name that would
   have appeared on a list of indexes — which is why the consolidation that
   counted three of them missed it.

3. **The sync mapping is stated once.** ``ARCHITECTURE.md`` delegates it to
   ``docs/live-runtime.md`` and must not restate the paths.

Each check carries a positive control: the same assertion is run against mutated
text and must fail. An empty result is not evidence of absence, and a doc test
that cannot fail is a decoration.

Dated chapters under ``docs/chapters/`` and ``autoresearch/proposals/`` still say
``docs/architecture.md``, by decision: they are records of what was true when
they were written, and rewriting them would falsify the record. They mention the
old name in prose rather than in links, so nothing here has to make an exception
for them — if one of them ever *links* to it, that is a real break and this fails.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SPEC_ROW = re.compile(r"^\|\s*§\d", re.MULTILINE)

# A file may mention a spec section in a table without being an index — a design
# doc citing the section it implements, for instance. An index is a *run* of
# them. Measured 2026-08-18: the matrix had 52 such rows, the next-highest file
# had 1, and the table this guard exists to prevent had 26.
INDEX_ROW_THRESHOLD = 5
THE_ONE_INDEX = "docs/traceability-matrix.md"

# Path literals from the Mini → Forge pull. `docs/automation/*` name the
# automation-reports leg on purpose — that mapping is their subject, not a
# second copy of the whole table — so the claim checked here is the narrow one
# actually written in the docs: ARCHITECTURE.md delegates and does not restate.
SYNC_PATH_LITERALS = ("desk/craft/automation-reports", "state/notes/*.md")


def tracked_markdown() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [REPO / rel for rel in out]


def dangling_links(path: Path, text: str) -> list[str]:
    broken = []
    for target in LINK.findall(text):
        target = target.split("#")[0].split(" ")[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if not (path.parent / target).resolve().exists():
            broken.append(target)
    return broken


class DocLinksResolve(unittest.TestCase):
    def test_no_tracked_markdown_link_dangles(self):
        broken = {}
        checked = 0
        for path in tracked_markdown():
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            checked += 1
            targets = dangling_links(path, text)
            if targets:
                broken[path.relative_to(REPO).as_posix()] = targets
        self.assertGreater(checked, 50, "read almost nothing — the walk is broken")
        self.assertEqual(broken, {}, f"dangling links: {broken}")

    def test_the_link_check_can_fail(self):
        """Positive control: a link to a file that is not there is caught."""
        broken = dangling_links(
            REPO / "ARCHITECTURE.md",
            "see [the deployment](docs/architecture.md) for topology",
        )
        self.assertEqual(broken, ["docs/architecture.md"])


class OnlyOneSpecIndex(unittest.TestCase):
    def test_no_second_spec_index(self):
        offenders = {}
        for path in tracked_markdown():
            rel = path.relative_to(REPO).as_posix()
            if rel == THE_ONE_INDEX:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rows = len(SPEC_ROW.findall(text))
            if rows >= INDEX_ROW_THRESHOLD:
                offenders[rel] = rows
        self.assertEqual(
            offenders,
            {},
            "a second spec index appeared; the matrix is the only one — "
            f"offenders (file: rows): {offenders}",
        )

    def test_the_matrix_is_still_an_index(self):
        """Negative control: the guard would be vacuous if the matrix emptied."""
        text = (REPO / THE_ONE_INDEX).read_text(encoding="utf-8")
        self.assertGreaterEqual(len(SPEC_ROW.findall(text)), INDEX_ROW_THRESHOLD)

    def test_the_index_check_can_fail(self):
        """Positive control: the shape of the deleted table is detected."""
        table = "\n".join(f"| §{n} Thing | `mod.py` | Implemented |" for n in range(8))
        self.assertGreaterEqual(len(SPEC_ROW.findall(table)), INDEX_ROW_THRESHOLD)


class SyncMappingStatedOnce(unittest.TestCase):
    def test_architecture_delegates_the_mapping(self):
        text = (REPO / "ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertIn(
            "docs/live-runtime.md",
            text,
            "ARCHITECTURE.md must point at the deployment doc for sync paths",
        )
        restated = [lit for lit in SYNC_PATH_LITERALS if lit in text]
        self.assertEqual(
            restated,
            [],
            "ARCHITECTURE.md restates sync paths it delegates; that is how both "
            f"copies went stale together: {restated}",
        )

    def test_the_deployment_doc_actually_holds_the_mapping(self):
        text = (REPO / "docs" / "live-runtime.md").read_text(encoding="utf-8")
        for lit in SYNC_PATH_LITERALS:
            self.assertIn(lit, text, f"the one copy lost {lit}")


if __name__ == "__main__":
    unittest.main()
