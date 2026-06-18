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
    read_flow_intake,
    split_front_matter,
    write_flow_checkpoint,
    write_flow_intake,
    build_flow_prompt_sections,
    flow_presence_line,
    flow_entry_blurb,
    resolve_flow_for_close,
    list_resolvable_flow_ids,
    strip_model_operational_lines,
    strip_question_sentences,
    apply_flow_reply_guard,
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
        self.assertNotIn("-# flow:", joined)
        self.assertNotIn("emit on first reply", joined)

    def test_flow_presence_line(self) -> None:
        spec = load_flow_spec("shelter")
        assert spec is not None
        self.assertEqual(flow_presence_line(spec), "Shelter")

    def test_strip_model_operational_lines(self) -> None:
        raw = "I'm here.\n\n-# flow: Shelter\n\n-# read state/notes/shelter-last.md\n\nStill here."
        cleaned, stripped = strip_model_operational_lines(raw)
        self.assertEqual(len(stripped), 2)
        self.assertNotIn("-# flow:", cleaned)
        self.assertIn("I'm here.", cleaned)
        self.assertIn("Still here.", cleaned)

        meta = "You made it.\n\n*(No question. End here.)*"
        cleaned_meta, stripped_meta = strip_model_operational_lines(meta)
        self.assertEqual(len(stripped_meta), 1)
        self.assertNotIn("No question", cleaned_meta)
        self.assertIn("You made it.", cleaned_meta)

    def test_strip_question_sentences(self) -> None:
        raw = (
            "I'm here with you. There's no need to carry it alone right now. "
            "Would you like to just sit with it for a moment, or is there one small thing?"
        )
        cleaned, stripped = strip_question_sentences(raw)
        self.assertEqual(len(stripped), 1)
        self.assertNotIn("?", cleaned)
        self.assertIn("I'm here with you.", cleaned)

    def test_apply_flow_reply_guard_shelter_first_reply(self) -> None:
        raw = "I'm here. Would you like to sit with it?"
        cleaned, notes = apply_flow_reply_guard(raw, "shelter", [])
        self.assertNotIn("?", cleaned)
        self.assertTrue(notes)
        self.assertIn("I'm here.", cleaned)

    def test_apply_flow_reply_guard_skips_after_first_reply(self) -> None:
        history = [{"role": "assistant", "content": "first"}]
        raw = "Still here. Want to talk?"
        cleaned, notes = apply_flow_reply_guard(raw, "shelter", history)
        self.assertEqual(cleaned, raw)
        self.assertEqual(notes, [])

    def test_build_flow_prompt_sections_shelter_turn_override_last(self) -> None:
        from prompts import build_native_eddy_prompt

        prompt = build_native_eddy_prompt("shelter")
        self.assertIn("Turn override (final", prompt)
        self.assertGreater(prompt.rfind("Turn override"), prompt.rfind("Discord Eddy"))

    def test_list_flow_ids_dedupes_practice_over_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            practice_flows = os.path.join(tmp, "flows")
            template_flows = os.path.join(tmp, "template", "flows")
            os.makedirs(practice_flows)
            os.makedirs(template_flows)
            with open(os.path.join(practice_flows, "shelter.md"), "w") as f:
                f.write("---\ntitle: Shelter\n---\n")
            with open(os.path.join(template_flows, "shelter.md"), "w") as f:
                f.write("---\ntitle: Shelter\n---\n")
            with open(os.path.join(template_flows, "navigator.md"), "w") as f:
                f.write("---\ntitle: Navigator\n---\n")

            import flow_runner as fr

            old_dirs = fr._flow_search_dirs

            def fake_dirs(pd=None):
                return [practice_flows, template_flows]

            fr._flow_search_dirs = fake_dirs
            try:
                self.assertEqual(fr.list_flow_ids(tmp), ["shelter", "navigator"])
            finally:
                fr._flow_search_dirs = old_dirs

    def test_list_resolvable_flow_ids_includes_shipped_flows(self) -> None:
        flows = list_resolvable_flow_ids()
        for flow_id in ("shelter", "navigator", "thread", "companion"):
            self.assertIn(flow_id, flows)
        self.assertEqual(len(flows), len(set(flows)))

    def test_load_shipped_flow_templates(self) -> None:
        expected = {
            "navigator": ("Navigator", "state/notes/navigator-last.md"),
            "thread": ("Thread", "state/notes/thread-last.md"),
            "companion": ("Companion", "state/notes/companion-last.md"),
        }
        for flow_id, (title, write_path) in expected.items():
            spec = load_flow_spec(flow_id)
            self.assertIsNotNone(spec, flow_id)
            assert spec is not None
            self.assertEqual(spec.title, title)
            self.assertIn(write_path, spec.writes)

    def test_navigator_intake_spec(self) -> None:
        spec = load_flow_spec("navigator")
        assert spec is not None
        self.assertTrue(spec.entry_contract)
        assert spec.intake is not None
        self.assertEqual(spec.intake.path, "state/notes/navigator-intake.md")
        self.assertTrue(spec.intake.skippable)
        self.assertEqual(len(spec.intake.fields), 2)
        self.assertEqual(spec.intake.fields[0].id, "intention")
        self.assertTrue(spec.intake.fields[0].required)

    def test_write_and_read_flow_intake(self) -> None:
        spec = load_flow_spec("navigator")
        assert spec is not None
        with tempfile.TemporaryDirectory() as tmp:
            rel = write_flow_intake(
                spec,
                {"intention": "Ship turtleOS", "territory": "Install friction"},
                tmp,
            )
            self.assertEqual(rel, "state/notes/navigator-intake.md")
            content = read_flow_intake(spec, tmp)
            self.assertIn("Ship turtleOS", content)
            sections, _ = build_flow_prompt_sections("navigator", tmp)
            joined = "\n".join(sections)
            self.assertIn("Flow Intake", joined)
            self.assertIn("do not re-ask", joined.lower())

    def test_read_flow_intake_values_for_prefill(self) -> None:
        from flow_runner import parse_flow_intake_markdown, read_flow_intake_values

        raw = (
            "# Navigator — intake\n**Captured:** 2026-06-18\n\n"
            "## intention\n\nShip turtleOS\n\n## territory\n\nInstall friction\n"
        )
        parsed = parse_flow_intake_markdown(raw)
        self.assertEqual(parsed["intention"], "Ship turtleOS")
        self.assertEqual(parsed["territory"], "Install friction")

        spec = load_flow_spec("navigator")
        assert spec is not None
        with tempfile.TemporaryDirectory() as tmp:
            write_flow_intake(
                spec,
                {"intention": "Return visit goal", "territory": "Still stuck on deploy"},
                tmp,
            )
            values = read_flow_intake_values(spec, tmp)
            self.assertEqual(values["intention"], "Return visit goal")
            self.assertEqual(values["territory"], "Still stuck on deploy")

    def test_flow_orientation_description(self) -> None:
        from flow_runner import flow_orientation_description

        spec = load_flow_spec("navigator")
        assert spec is not None
        text = flow_orientation_description(spec)
        self.assertIn("Prepare", text)
        self.assertIn("Skip", text)

        with tempfile.TemporaryDirectory() as tmp:
            write_flow_intake(spec, {"intention": "Prior goal", "territory": ""}, tmp)
            text_return = flow_orientation_description(spec, tmp)
            self.assertIn("review or update", text_return)

    def test_flow_entry_blurb(self) -> None:
        spec = load_flow_spec("shelter")
        assert spec is not None
        blurb = flow_entry_blurb(spec)
        self.assertIn("Fresh start", blurb)

    def test_resolve_flow_for_close_by_context_type(self) -> None:
        spec = load_flow_spec("shelter")
        assert spec is not None
        configs = {123: {"context_type": "shelter"}}
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "here"}]
        resolved = resolve_flow_for_close(123, history, configs)
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.title, "Shelter")

    def test_resolve_flow_for_close_by_thread_name(self) -> None:
        history = [{"role": "user", "content": "cats"}, {"role": "assistant", "content": "here"}]
        resolved = resolve_flow_for_close(
            456, history, {}, channel_name="seeking_shelter_from_rain"
        )
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertEqual(resolved.title, "Shelter")

    def test_resolve_flow_for_close_by_shelter_phrase(self) -> None:
        history = [
            {"role": "user", "content": "heavy day, need shelter"},
            {"role": "assistant", "content": "I'm here"},
        ]
        resolved = resolve_flow_for_close(789, history, {}, channel_name="new eddy")
        self.assertIsNotNone(resolved)


class FlowPresenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_post_flow_presence_if_needed(self) -> None:
        from eddy_spawn import post_flow_presence_if_needed

        channel = MagicMock()
        channel.id = 999001
        sent: list[str] = []

        async def _send(text: str) -> None:
            sent.append(text)

        channel.send = _send

        cfg = {"context_type": "shelter", "flow_presence_posted": False}
        spec = load_flow_spec("shelter")
        assert spec is not None
        expected = f"-# {flow_presence_line(spec)}"
        with unittest.mock.patch("mage.get_attunement_profile", return_value="native"):
            posted = await post_flow_presence_if_needed(channel, cfg)
        self.assertTrue(posted)
        self.assertEqual(sent, [expected])
        self.assertTrue(cfg.get("flow_presence_posted"))

        sent.clear()
        self.assertFalse(await post_flow_presence_if_needed(channel, cfg))

    async def test_post_flow_presence_skips_non_native(self) -> None:
        from eddy_spawn import post_flow_presence_if_needed

        channel = MagicMock()
        channel.id = 999002
        channel.send = unittest.mock.AsyncMock()
        cfg = {"context_type": "shelter", "flow_presence_posted": False}
        with unittest.mock.patch("mage.get_attunement_profile", return_value="magic"):
            self.assertFalse(await post_flow_presence_if_needed(channel, cfg))
        channel.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
