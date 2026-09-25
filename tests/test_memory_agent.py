"""Memory agent — formation, heat, passive block, and the §15.5 boundary.

Fixture rooms are synthetic. The private "kermit" root and shared "family"
root below are registry keys, not people; the notes are invented.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

try:  # pragma: no cover — environment branch
    import discord  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    sys.modules.setdefault("discord", MagicMock())
    sys.modules.setdefault("discord.ext", MagicMock())
    sys.modules.setdefault("discord.ext.tasks", MagicMock())

import memory_agent as ma

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone(timedelta(hours=2)))


def _note(root: Path, thread: str, title: str, when: datetime, themes: list[str], body: str) -> None:
    eddies = root / "story" / "eddies"
    eddies.mkdir(parents=True, exist_ok=True)
    path = eddies / f"{thread}-{ma._slug(title)}.md"
    entry = (
        "---\n"
        f"thread: '{thread}'\n"
        f"title: {title}\n"
        "trigger: idle\n"
        f"timestamp: '{when.isoformat(timespec='seconds')}'\n"
        f"proposed-themes: [{', '.join(themes)}]\n"
        "participants: [alpha, beta]\n"
        "---\n\n"
        f"{body}\n\n"
    )
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(entry)


def _seed_family(root: Path) -> None:
    # A recurring topic across many conversations, last touched 8 days ago —
    # outside the 7-day recency window, well inside a 21-day half-life.
    for i in range(6):
        when = NOW - timedelta(days=40 - i * 6)
        _note(
            root,
            f"1000{i}",
            f"lighthouse visit {i}",
            when,
            ["the lighthouse keeper situation"],
            "You told Turtle the lighthouse keeper had again moved the boundary "
            "stones and Beta felt unseen by the keeper's silence.",
        )
    # A one-off, very recent.
    _note(
        root, "20000", "camping plan", NOW - timedelta(days=1),
        ["camping trip logistics"],
        "You and Beta compared camping dates and the tent situation.",
    )
    # A one-off, old — should not form a topic.
    _note(
        root, "30000", "a stray remark", NOW - timedelta(days=50),
        ["stray remark"], "You mentioned the orchard ladder once.",
    )


class KeywordFormation(unittest.TestCase):
    def test_recurring_topic_forms_and_cooled_one_off_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)
            entries = ma.collect_entries([("family", root)])
            self.assertEqual(len(entries), 8)
            topics = ma.form_topics_keyword(entries, NOW)
            labels = " ".join(t.label for t in topics)
            self.assertIn("lighthouse", labels)
            self.assertIn("camping", labels)  # recent one-off survives via RECENT_DAYS
            self.assertNotIn("orchard", labels)
            lighthouse = next(t for t in topics if "lighthouse" in t.label)
            self.assertEqual(lighthouse.conversations, 6)
            self.assertEqual(lighthouse.last_seen, (NOW - timedelta(days=10)).strftime("%Y-%m-%d"))
            self.assertGreater(lighthouse.heat, 2.0)

    def test_heat_decays_by_half_life(self):
        e = ma.MemoryEntry("r:1", "r", "t", "x", NOW - timedelta(days=ma.HEAT_HALF_LIFE_DAYS), [], "", "p")
        self.assertAlmostEqual(ma.heat_of([e], NOW), 0.5, places=3)

    def test_build_writes_readable_memory_and_is_rebuildable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)
            first = ma.build_room_memory(root, now=NOW)
            mdir = ma.memory_dir(root)
            self.assertTrue((mdir / "topics.yaml").exists())
            self.assertTrue((mdir / "topics.md").exists())
            pages = sorted((mdir / "topics").glob("*.md"))
            self.assertEqual(len(pages), len(first))
            page = next(p for p in pages if "lighthouse" in p.name).read_text()
            self.assertIn("6 conversations", page)
            self.assertIn("## Sources", page)
            # Positive control for "derived, not standing": a stale page is
            # removed on rebuild and the rebuilt view equals the first.
            (mdir / "topics" / "ghost.md").write_text("stale")
            second = ma.build_room_memory(root, now=NOW)
            self.assertFalse((mdir / "topics" / "ghost.md").exists())
            self.assertEqual(
                [(t.id, t.conversations) for t in first],
                [(t.id, t.conversations) for t in second],
            )


class ModelFormation(unittest.TestCase):
    def test_invented_entry_ids_are_dropped_and_singletons_pruned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)
            entries = ma.collect_entries([("family", root)])
            raw = (
                'Here you go:\n{"topics": ['
                '{"label": "The lighthouse keeper", "summary": "Boundary stones and silence.",'
                ' "keywords": ["lighthouse", "keeper"],'
                ' "entries": ["family:1", "family:2", "family:3", "family:99"]},'
                '{"label": "Orchard", "summary": "", "keywords": [], "entries": ["family:8"]}'
                "]}"
            )
            topics = ma.parse_formation_reply(raw, entries, NOW)
            self.assertEqual([t.label for t in topics], ["The lighthouse keeper"])
            # The model listed 3 ids; the keywords find all 6 conversations.
            self.assertEqual(topics[0].conversations, 6)
            self.assertEqual(topics[0].formed_by, "model")

    def test_a_label_judging_a_member_falls_back_to_its_keywords(self):
        names = {"alpha", "beta"}
        label, summary = ma.neutralize_naming(
            "Beta's Hypocrisy and Double Standards", "Beta keeps blaming Alpha.",
            ["boundary stones", "garden", "Beta"], names,
        )
        self.assertEqual(label, "boundary stones / garden")
        self.assertEqual(summary, "")
        # Positive controls: a name alone and a verdict word alone both pass.
        self.assertEqual(
            ma.neutralize_naming("Bo's fourth birthday", "Party plans.", [], {"bo"}),
            ("Bo's fourth birthday", "Party plans."),
        )
        self.assertEqual(
            ma.neutralize_naming("Defining narcissism", "A concept the room read about.", [], names),
            ("Defining narcissism", "A concept the room read about."),
        )

    def test_formation_applies_the_naming_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)
            entries = ma.collect_entries([("family", root)])
            raw = (
                '{"topics": [{"label": "Beta\'s loyalty to the keeper", "summary": "x",'
                ' "keywords": ["lighthouse", "keeper"], "entries": []}]}'
            )
            topics = ma.parse_formation_reply(raw, entries, NOW)
            self.assertEqual(topics[0].label, "lighthouse / keeper")

    def test_keywords_assign_by_reading_the_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)
            entries = ma.collect_entries([("family", root)])
            self.assertEqual(len(ma.assign_by_keywords(entries, ["Lighthouse"])), 6)
            self.assertEqual(len(ma.assign_by_keywords(entries, ["tent"])), 1)
            self.assertEqual(ma.assign_by_keywords(entries, ["", "ab"]), [])

    def test_rebuild_falls_back_to_keyword_when_model_yields_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)

            async def silent(_system, _messages):
                return "(no response generated)"

            topics = asyncio.run(ma.rebuild_room_memory(root, now=NOW, chat=silent))
            self.assertTrue(topics)
            self.assertTrue(all(t.formed_by == "keyword" for t in topics))
            record = (ma.memory_dir(root) / "topics.yaml").read_text()
            self.assertIn("formed_by: keyword", record)


class PassiveBlock(unittest.TestCase):
    def test_cooled_topic_surfaces_when_the_message_reaches_for_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)
            # Push many hotter topics in so the lighthouse is not in the top-N.
            for i in range(4):
                for j in range(3):
                    _note(
                        root, f"5{i}{j}00", f"garden thing {i}-{j}", NOW - timedelta(days=j),
                        [f"garden bed {i} planting"], f"You planted bed number {i} with beans.",
                    )
            ma.build_room_memory(root, now=NOW)
            considered: list[dict] = []
            block = ma.render_topic_memory_block(
                root, "what do you remember about the lighthouse keeper?", considered=considered
            )
            self.assertIn("lighthouse", block.lower())
            self.assertIn("Do not say you checked", block)
            self.assertTrue(any(c["selected"] for c in considered))
            quiet = ma.render_topic_memory_block(root, "hello there")
            self.assertTrue(quiet.startswith("What this space keeps returning to"))

    def test_current_thread_excluded_and_excerpts_shown_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)
            entries = ma.collect_entries([("family", root)])
            # Two topics that share every lighthouse entry.
            raw = (
                '{"topics": ['
                '{"label": "Keeper", "summary": "", "keywords": ["keeper"], "entries": []},'
                '{"label": "Stones", "summary": "", "keywords": ["stones"], "entries": []}]}'
            )
            topics = ma.parse_formation_reply(raw, entries, NOW)
            ma.build_room_memory(root, now=NOW, topics=topics, formed_by="model")
            block = ma.render_topic_memory_block(root, "", exclude_thread="10005")
            self.assertNotIn("lighthouse visit 5", block)
            self.assertEqual(block.count("lighthouse visit 4"), 1)
            self.assertIn("lighthouse visit 3", block)

    def test_no_memory_built_renders_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ma.render_topic_memory_block(tmp, "anything"), "")

    def test_compact_rendering_keeps_the_topic_and_gives_up_excerpts(self):
        # A turn already carrying a transcript should still remember the room,
        # just not at full length (2026-09-03: 3.5 minutes on a local 31B).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)
            ma.build_room_memory(root, now=NOW)
            full = ma.render_topic_memory_block(root, "")
            compact = ma.render_topic_memory_block(root, "", excerpts_per_topic=1)
            self.assertIn("lighthouse", compact.lower())
            self.assertLess(len(compact), len(full))
            # One excerpt line per topic heading.
            headings = sum(1 for l in compact.splitlines() if l.startswith("- "))
            excerpts = sum(1 for l in compact.splitlines() if l.startswith("    · "))
            self.assertEqual(excerpts, headings)

    def test_craft_render_drops_shared_room_topics_native_keeps_them(self):
        """Planted kermit index includes family. Craft must not remember it.

        Positive control: native render still carries the lighthouse. If the
        filter is removed, craft and native match and this fails.
        """
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("kermit", "partner", "family"):
                (base / name).mkdir()
            _seed_family(base / "family")
            for i in range(6):
                _note(
                    base / "kermit",
                    f"k{i}",
                    f"workshop shelf {i}",
                    NOW - timedelta(days=40 - i * 6),
                    ["workshop shelf layout"],
                    "The workshop shelf keeps getting rebuilt around the same tools.",
                )
            registry = {
                "mages": {
                    "kermit": {"practice_dir": str(base / "kermit")},
                    "partner": {"practice_dir": str(base / "partner")},
                },
                "spaces": {
                    "family": {
                        "practice_dir": str(base / "family"),
                        "members": ["kermit", "partner"],
                    },
                },
            }
            kroots = ma.memory_roots_for(
                base / "kermit", registry=registry, key="kermit", kind="mage"
            )
            ma.build_room_memory(base / "kermit", kroots, now=NOW)
            considered_native: list[dict] = []
            native = ma.render_topic_memory_block(
                base / "kermit", considered=considered_native
            )
            self.assertIn("lighthouse", native.lower())
            self.assertIn("workshop", native.lower())
            self.assertTrue(
                any(
                    "lighthouse" in str(c.get("label") or "").lower() and c.get("selected")
                    for c in considered_native
                ),
                "native control: family topic must be selectable or the plant failed",
            )
            considered_craft: list[dict] = []
            craft = ma.render_topic_memory_block(
                base / "kermit",
                considered=considered_craft,
                exclude_shared_rooms=True,
            )
            self.assertNotIn("lighthouse", craft.lower())
            self.assertNotIn(" in family", craft.lower())
            self.assertIn("workshop", craft.lower())
            self.assertFalse(
                any("lighthouse" in str(c.get("label") or "").lower() for c in considered_craft)
            )
            self.assertTrue(any(c.get("selected") for c in considered_craft))


class Glance(unittest.TestCase):
    def test_a_shared_name_is_not_relatedness(self):
        """Positive control: one shared given name must not select the family topic.

        If excerpts or a single-word overlap count, family lands on research.
        """
        topics = [
            {
                "id": "family",
                "label": "Sunday lunch conflict",
                "summary": "",
                "keywords": ["alpha", "beta", "sunday-lunch"],
                "heat": 90,
                "entries": [
                    {
                        "title": "derek lomas tu delft roles",
                        "excerpt": "Alpha asked Beta about the Sunday lunch again.",
                    }
                ],
            },
            {
                "id": "magic",
                "label": "Magic practice",
                "summary": "",
                "keywords": ["magic", "positive", "library"],
                "heat": 10,
                "entries": [
                    {
                        "title": "source library",
                        "excerpt": "Positive AI as practiced.",
                    }
                ],
            },
        ]
        text = (
            "Alpha asked for research on Derek Lomas and Positive AI "
            "and the Source Library"
        )
        related = ma.select_related_topics(topics, text)
        labels = [t["label"] for t in related]
        self.assertIn("Magic practice", labels)
        self.assertNotIn("Sunday lunch conflict", labels)

    def test_related_not_hottest(self):
        """A hot topic the conversation does not reach must not appear.

        If this goes green after swapping in select_topics, the glance
        started filling heat again.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "kermit"
            _seed_family(root)
            for i in range(6):
                _note(
                    root,
                    f"w{i}",
                    f"workshop shelf {i}",
                    NOW - timedelta(days=20 - i * 3),
                    ["workshop shelf layout"],
                    "The workshop shelf keeps getting rebuilt around the same tools.",
                )
            ma.build_room_memory(root, now=NOW)
            heat = ma.render_topic_memory_block(root, "hello there")
            self.assertIn("lighthouse", heat.lower())
            related = ma.render_memory_glance(
                root, "the workshop shelf layout and the tools on it"
            )
            self.assertIn("workshop", related.lower())
            self.assertNotIn("lighthouse", related.lower())
            self.assertNotIn("I remember", related)
            quiet = ma.render_memory_glance(root, "...")
            self.assertEqual(quiet, "")
            hello = ma.render_memory_glance(root, "hello there")
            self.assertEqual(hello, "")

    def test_current_thread_is_reach_not_excerpt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)
            ma.build_room_memory(root, now=NOW)
            note = ma.note_text_for_thread(root, "10005")
            self.assertIn("lighthouse visit 5", note)
            reach = ma.conversation_reach_text(
                "lighthouse keeper",
                dialogue=[{"role": "user", "content": "..."}],
                note_text=note,
            )
            self.assertIn("lighthouse", reach.lower())
            self.assertNotIn("...", reach)
            shown = ma.render_memory_glance(root, reach, exclude_thread="10005")
            self.assertIn("lighthouse", shown.lower())
            self.assertNotIn("lighthouse visit 5", shown)

    def test_craft_glance_drops_shared_rooms(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("kermit", "partner", "family"):
                (base / name).mkdir()
            _seed_family(base / "family")
            for i in range(6):
                _note(
                    base / "kermit",
                    f"k{i}",
                    f"workshop shelf {i}",
                    NOW - timedelta(days=40 - i * 6),
                    ["workshop shelf layout"],
                    "The workshop shelf keeps getting rebuilt around the same tools.",
                )
            registry = {
                "mages": {
                    "kermit": {"practice_dir": str(base / "kermit")},
                    "partner": {"practice_dir": str(base / "partner")},
                },
                "spaces": {
                    "family": {
                        "practice_dir": str(base / "family"),
                        "members": ["kermit", "partner"],
                    },
                },
            }
            kroots = ma.memory_roots_for(
                base / "kermit", registry=registry, key="kermit", kind="mage"
            )
            ma.build_room_memory(base / "kermit", kroots, now=NOW)
            both = "lighthouse keeper and the workshop shelf"
            native = ma.render_memory_glance(base / "kermit", both)
            self.assertIn("lighthouse", native.lower())
            self.assertIn("workshop", native.lower())
            craft = ma.render_memory_glance(
                base / "kermit", both, exclude_shared_rooms=True
            )
            self.assertNotIn("lighthouse", craft.lower())
            self.assertIn("workshop", craft.lower())


class Maintenance(unittest.TestCase):
    async def _silent(self, _system, _messages):
        return ""

    def test_stale_root_is_rebuilt_only_when_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "family"
            _seed_family(root)
            rooms = [(root, ma.own_root(root))]
            self.assertTrue(ma.memory_is_stale(root), "no memory yet is stale")
            # Someone is talking: deferred, nothing written.
            (root / "dialogue").mkdir()
            (root / "dialogue" / "1.json").write_text("[]")
            rebuilt = asyncio.run(ma.maintain_room_memories(rooms, chat=self._silent))
            self.assertEqual(rebuilt, [])
            self.assertFalse((ma.memory_dir(root) / "topics.yaml").exists())
            # Quiet for an hour: rebuilt, then current.
            old = (datetime.now() - timedelta(hours=1)).timestamp()
            os.utime(root / "dialogue" / "1.json", (old, old))
            rebuilt = asyncio.run(ma.maintain_room_memories(rooms, chat=self._silent))
            self.assertEqual(rebuilt, [str(root)])
            self.assertFalse(ma.memory_is_stale(root))
            # A newer note makes it stale again — the state, not a schedule.
            _note(root, "99999", "fresh news", datetime.now().astimezone(), ["news"], "New.")
            self.assertTrue(ma.memory_is_stale(root))
            rebuilt = asyncio.run(ma.maintain_room_memories(rooms, chat=self._silent))
            self.assertEqual(rebuilt, [str(root)])
            self.assertEqual(asyncio.run(ma.maintain_room_memories(rooms, chat=self._silent)), [])


class Boundary(unittest.TestCase):
    """§15.5 asymmetry: personal roots remember their shared rooms; shared rooms
    remember only themselves; no root ever reads another personal root."""

    def _registry(self, base: Path) -> dict:
        return {
            "mages": {
                "kermit": {"practice_dir": str(base / "kermit")},
                "partner": {"practice_dir": str(base / "partner")},
                "guest": {"practice_dir": str(base / "guest")},
            },
            "spaces": {
                "family": {"practice_dir": str(base / "family"), "members": ["kermit", "partner"]},
                "closed": {"practice_dir": str(base / "closed"), "members": ["kermit"], "archived": True},
            },
        }

    def _rooms(self, base: Path, root: str) -> list[str]:
        registry = self._registry(base)
        kind = "space" if root in registry["spaces"] else ("mage" if root in registry["mages"] else None)
        key = root if kind else None
        return [r for r, _ in ma.memory_roots_for(base / root, registry=registry, key=key, kind=kind)]

    def test_roots_follow_membership_and_never_cross_personal_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("kermit", "partner", "guest", "family", "closed"):
                (base / name).mkdir()
            self.assertEqual(self._rooms(base, "family"), ["family"])
            self.assertEqual(self._rooms(base, "kermit"), ["kermit", "family"])
            self.assertEqual(self._rooms(base, "partner"), ["partner", "family"])
            self.assertEqual(self._rooms(base, "guest"), ["guest"])
            # Positive control: membership is what grants, and an archived
            # space grants nothing even to its member.
            self.assertNotIn("closed", self._rooms(base, "kermit"))
            for a in ("kermit", "partner", "guest"):
                for b in ("kermit", "partner", "guest"):
                    if a != b:
                        self.assertNotIn(b, self._rooms(base, a))

    def test_unregistered_root_is_its_own_memory_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = ma.memory_roots_for(tmp, registry={"spaces": {"x": {"members": ["*"]}}}, key=None, kind=None)
            self.assertEqual(len(roots), 1)

    def test_resolved_boundary_overrides_membership_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            registry = self._registry(base)
            roots = ma.memory_roots_for(
                base / "kermit",
                registry=registry,
                key="kermit",
                kind="mage",
                boundary="personal_without_shared",
            )
            self.assertEqual([room for room, _ in roots], ["kermit"])

            merged = ma.memory_roots_for(
                base / "kermit",
                registry=registry,
                key="kermit",
                kind="mage",
                boundary="personal_plus_shared",
            )
            self.assertIn("family", [room for room, _ in merged])

    def test_live_registry_glue_resolves_through_mage(self):
        # The pure rule is tested above; this is the one edge that hands it the
        # live registry, patched to the fixture so it proves the glue, not the data.
        import mage

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("kermit", "family"):
                (base / name).mkdir()
            with patch.object(mage, "_MAGE_REGISTRY", self._registry(base)):
                self.assertEqual([r for r, _ in mage.memory_roots(base / "kermit")], ["kermit", "family"])
                self.assertEqual([r for r, _ in mage.memory_roots(base / "family")], ["family"])

    def test_personal_build_carries_shared_room_and_marks_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("kermit", "partner", "family"):
                (base / name).mkdir()
            _seed_family(base / "family")
            _note(
                base / "partner", "777", "private thought", NOW - timedelta(days=2),
                ["harbour secret"], "A harbour secret nobody shared.",
            )
            registry = self._registry(base)
            kroots = ma.memory_roots_for(base / "kermit", registry=registry, key="kermit", kind="mage")
            topics = ma.build_room_memory(base / "kermit", kroots, now=NOW)
            labels = " ".join(t.label for t in topics)
            self.assertIn("lighthouse", labels)
            self.assertNotIn("harbour", labels)
            page = next(
                p for p in (ma.memory_dir(base / "kermit") / "topics").glob("*.md")
                if "lighthouse" in p.name
            ).read_text()
            self.assertIn("in family", page)
            # And the shared room's own build never sees the private root.
            froots = ma.memory_roots_for(base / "family", registry=registry, key="family", kind="space")
            fam = ma.build_room_memory(base / "family", froots, now=NOW)
            self.assertNotIn("harbour", " ".join(t.label for t in fam))
            record = (ma.memory_dir(base / "family") / "topics.yaml").read_text()
            self.assertNotIn("partner", record)


def _exogenous_note(
    root: Path,
    conversation_id: str,
    title: str,
    when: datetime,
    body: str,
    *,
    route: str = "personal",
    source: str = "exogenous/chatgpt",
    themes: list[str] | None = None,
) -> None:
    folder = root / "story" / "exogenous" / "chatgpt"
    folder.mkdir(parents=True, exist_ok=True)
    theme_line = ", ".join(f'"{t}"' for t in (themes or ["imported lighthouse notes"]))
    (folder / f"{conversation_id}.md").write_text(
        "---\n"
        f"source: {source}\n"
        f"conversation_id: {conversation_id}\n"
        f"title: {title}\n"
        f"created: '{when.isoformat(timespec='seconds')}'\n"
        f"updated: '{when.isoformat(timespec='seconds')}'\n"
        "origin_platform: chatgpt\n"
        "origin_agent: ChatGPT\n"
        f"route: {route}\n"
        "entwined: '2026-09-10'\n"
        f"proposed-themes: [{theme_line}]\n"
        "---\n\n"
        f"{body}\n",
        encoding="utf-8",
    )


class ExogenousCollection(unittest.TestCase):
    def test_collect_entries_reads_exogenous_and_skips_skip_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "harbour"
            _exogenous_note(
                root,
                "abc123",
                "lighthouse from chatgpt",
                NOW - timedelta(days=1),
                "The keeper had moved the boundary stones again.",
            )
            _exogenous_note(
                root,
                "skip-me",
                "toy chat",
                NOW - timedelta(days=1),
                "SECRET_SKIP_BODY",
                route="skip",
            )
            entries = ma.collect_entries([("harbour", root)])
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].origin, "exogenous/chatgpt")
            self.assertEqual(entries[0].thread, "abc123")
            self.assertIn("story/exogenous/chatgpt/abc123.md", entries[0].source_path)
            self.assertNotIn("SECRET_SKIP_BODY", " ".join(e.body for e in entries))
            ma.build_room_memory(root, now=NOW)
            self.assertFalse(ma.memory_is_stale(root, [("harbour", root)]))
            _exogenous_note(
                root,
                "later",
                "later lighthouse",
                NOW,
                "A later imported note about the keeper.",
            )
            self.assertTrue(ma.memory_is_stale(root, [("harbour", root)]))

    def test_packet_labels_imported_origin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "harbour"
            for i in range(2):
                _exogenous_note(
                    root,
                    f"keep{i}",
                    f"lighthouse import {i}",
                    NOW - timedelta(days=i),
                    "The lighthouse keeper had moved the boundary stones again.",
                    themes=["the lighthouse keeper situation"],
                )
            ma.build_room_memory(root, now=NOW)
            block = ma.render_topic_memory_block(
                root, "what do you remember about the lighthouse keeper?"
            )
            self.assertIn(ma.EXOGENOUS_ORIGIN_PHRASE, block)
            self.assertIn("imported did not happen in this room", block)
            self.assertNotIn("story/eddies", block)

    def test_false_native_we_is_detected(self) -> None:
        self.assertTrue(
            ma.has_native_we_voice(
                "I remember when we discussed the lighthouse last year."
            )
        )
        self.assertFalse(
            ma.has_native_we_voice(
                "From a ChatGPT conversation you imported, one thread mentioned "
                "the lighthouse."
            )
        )
        # Positive control: an empty detector would pass the lie.
        self.assertTrue(ma.has_native_we_voice("When we talked about the stones, you were tired."))


if __name__ == "__main__":
    unittest.main()
