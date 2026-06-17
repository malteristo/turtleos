import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

from flow_runner import (
    load_flow_spec,
    read_state_bundle,
    split_front_matter,
    write_flow_checkpoint,
    build_flow_prompt_sections,
)


class FlowRunnerTests(unittest.TestCase):
    def test_split_front_matter(self) -> None:
        raw = "---\ntitle: Shelter\nreads: []\nwrites: [state/notes/x.md]\n---\n\nBody here."
        meta, body = split_front_matter(raw)
        self.assertEqual(meta["title"], "Shelter")
        self.assertEqual(body, "Body here.")

    def test_load_shelter_template(self) -> None:
        spec = load_flow_spec("shelter")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.title, "Shelter")
        self.assertIn("state/notes/shelter-last.md", spec.writes)
        self.assertIn("Hold space", spec.body)

    def test_read_state_bundle_missing_file(self) -> None:
        spec = load_flow_spec("shelter")
        assert spec is not None
        with tempfile.TemporaryDirectory() as tmp:
            bundle = read_state_bundle(spec, tmp)
            self.assertEqual(bundle["state/notes/shelter-last.md"], "")

    def test_write_flow_checkpoint(self) -> None:
        spec = load_flow_spec("shelter")
        assert spec is not None
        with tempfile.TemporaryDirectory() as tmp:
            history = [
                {"role": "user", "content": "heavy day"},
                {"role": "assistant", "content": "I'm here with you."},
            ]
            written = write_flow_checkpoint(spec, history, "Kermit", tmp)
            self.assertEqual(written, ["state/notes/shelter-last.md"])
            path = os.path.join(tmp, "state/notes/shelter-last.md")
            self.assertTrue(os.path.isfile(path))
            text = open(path).read()
            self.assertIn("heavy day", text)

    def test_build_flow_prompt_sections(self) -> None:
        sections, spec = build_flow_prompt_sections("shelter")
        self.assertIsNotNone(spec)
        joined = "\n".join(sections)
        self.assertIn("Shelter", joined)
        self.assertIn("-# flow: Shelter", joined)


if __name__ == "__main__":
    unittest.main()
