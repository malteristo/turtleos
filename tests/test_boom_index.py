"""Boom cites a topic, a spark, and an intention. It does not cite their text."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import boom_index


class Index(unittest.TestCase):
    def test_a_heading_a_spark_and_an_intention_are_cited_and_a_planted_body_is_not(self) -> None:
        planted = "PLANTED_BODY_MUST_STAY_OUT"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            desk = root / "desk"
            (desk / "boom").mkdir(parents=True)
            (desk / "intentions" / "active").mkdir(parents=True)
            (desk / "boom.md").write_text(
                f"# Boom\n\n## Dumped section\n\n{planted} in the buffer.\n",
                encoding="utf-8",
            )
            (desk / "boom" / "landlord.md").write_text(
                f"# The landlord\n\n{planted} in the topic.\n",
                encoding="utf-8",
            )
            (desk / "boom" / "bright.md").write_text(
                f"# Bright\n\n{planted} on the bright surface.\n",
                encoding="utf-8",
            )
            (desk / "intentions" / "active" / "hai.md").write_text(
                f"# The Göttingen hour\n\n{planted} in the intention.\n",
                encoding="utf-8",
            )
            practice = root / "practice"
            eddies = practice / "story" / "eddies"
            eddies.mkdir(parents=True)
            chronicle = root / "desk" / "story" / "eddies"
            chronicle.mkdir(parents=True)
            (chronicle / "2.md").write_text(
                "---\n"
                "thread: '2'\n"
                "title: A chronicle\n"
                "trigger: idle\n"
                "timestamp: '2026-10-15T11:00:00+02:00'\n"
                "related-topics: []\n"
                "proposed-themes: []\n"
                "sparks:\n"
                "  - name: The hour\n"
                "    topic: livelihood\n"
                "    status: open\n"
                "  - name: Closed one\n"
                "    topic: old\n"
                "    status: dropped\n"
                "---\n\n"
                f"{planted} in the chronicle.\n",
                encoding="utf-8",
            )
            (eddies / "1.md").write_text(
                "---\n"
                "thread: '1'\n"
                "title: A thought\n"
                "trigger: idle\n"
                "timestamp: '2026-10-15T10:00:00+02:00'\n"
                "related-topics: []\n"
                "proposed-themes: []\n"
                "sparks:\n"
                "  - name: The car\n"
                "    topic: tomorrow\n"
                "    status: open\n"
                "---\n\n"
                f"{planted} in the eddy.\n",
                encoding="utf-8",
            )
            text = boom_index.render_index(root, practice)
            self.assertIn("The landlord", text)
            self.assertIn("The Göttingen hour", text)
            self.assertIn("The car", text)
            self.assertIn("The hour", text)
            self.assertNotIn("Closed one", text)
            self.assertNotIn("Dumped section", text)
            self.assertNotIn("Bright", text)
            self.assertNotIn(planted, text)

    def test_past_the_cap_the_rest_are_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            boom = Path(tmp) / "desk" / "boom"
            boom.mkdir(parents=True)
            for i in range(3):
                (boom / f"t{i}.md").write_text(f"# Topic {i}\n", encoding="utf-8")
            with mock.patch.object(boom_index, "_CAP", 2):
                text = boom_index.render_index(Path(tmp), None)
            self.assertIn("Topic 0", text)
            self.assertIn("and 1 more", text)
            self.assertNotIn("Topic 2", text)

    def test_a_missing_workshop_says_the_bands_are_empty(self) -> None:
        text = boom_index.render_index(None, None)
        self.assertEqual(text.count("None."), 3)
        self.assertIn("Cite only what is listed", text)
