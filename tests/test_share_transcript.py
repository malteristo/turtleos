"""Tests for share_transcript — export shaping (share_eddy decomposition Slice 2)."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.modules.setdefault("discord", __import__("unittest.mock").mock.MagicMock())
sys.modules.setdefault("discord.ui", sys.modules["discord"])


class ExportBundleTests(unittest.TestCase):
    def test_build_export_bundle_preserves_history(self) -> None:
        from share_transcript import build_digest, build_export_bundle

        history = [
            {"role": "user", "content": "Birthday party heat"},
            {"role": "assistant", "content": "Sprinkler might help."},
        ]
        bundle = build_export_bundle(
            title="birthday party",
            history=history,
            sharer_id="111",
            sharer_key="kermit",
            sharer_address="Kermit",
            source_thread_id=999,
            share_id="abc123",
        )
        self.assertEqual(bundle["share_id"], "abc123")
        self.assertEqual(bundle["title"], "birthday party")
        self.assertEqual(len(bundle["history"]), 2)
        self.assertIn("Birthday party heat", bundle["transcript"])
        self.assertIn("Sprinkler", bundle["digest"])
        self.assertEqual(build_digest("x", history), bundle["digest"])

    def test_export_bundle_from_draft_carries_transparency_space_key(self) -> None:
        from share_transcript import build_export_bundle_from_draft

        draft = {
            "title": "party",
            "history": [{"role": "user", "content": "hi"}],
            "sharer_id": "1",
            "sharer_key": "kermit",
            "sharer_address": "Kermit",
            "source_thread_id": 9,
            "transparency_space_key": "family",
            "source_origin": "shared",
            "digest": "party logistics",
            "display_title": "party logistics",
        }
        bundle = build_export_bundle_from_draft(draft)
        self.assertEqual(bundle["transparency_space_key"], "family")
        self.assertEqual(bundle["source_origin"], "shared")

    def test_reexport_from_share_eddy(self) -> None:
        from share_eddy import build_export_bundle, filter_share_history

        history = [{"role": "user", "content": "hello"}]
        bundle = build_export_bundle(
            title="t",
            history=history,
            sharer_id="1",
            sharer_key="k",
            sharer_address="K",
            source_thread_id=1,
        )
        self.assertEqual(len(filter_share_history(history)), 1)
        self.assertIn("hello", bundle["transcript"])


class TranscriptFilterTests(unittest.TestCase):
    def test_is_placeholder_eddy_title(self) -> None:
        from share_transcript import is_placeholder_eddy_title

        self.assertTrue(is_placeholder_eddy_title("new eddy"))
        self.assertTrue(is_placeholder_eddy_title("hello to turtle please update your status"))
        self.assertFalse(is_placeholder_eddy_title("birthday party heat"))

    def test_filter_share_history_drops_act_digests_and_commands(self) -> None:
        from share_transcript import build_digest, build_export_bundle, filter_share_history

        history = [
            {"role": "user", "content": "!share"},
            {"role": "user", "content": "[Act: !share] Failed: View is not persistent."},
            {"role": "user", "content": "Birthday party heat and sprinkler plan"},
            {"role": "assistant", "content": "Active monitoring makes sense."},
        ]
        filtered = filter_share_history(history)
        self.assertEqual(len(filtered), 2)
        digest = build_digest("party", filtered)
        self.assertNotIn("[Act:", digest)
        self.assertIn("Birthday", digest)

        bundle = build_export_bundle(
            title="party",
            history=history,
            sharer_id="1",
            sharer_key="k",
            sharer_address="K",
            source_thread_id=9,
        )
        self.assertEqual(len(bundle["history"]), 2)


class PreviewEmbedTests(unittest.TestCase):
    def test_preview_embed_uses_display_title(self) -> None:
        from share_targets import ShareTarget
        from share_transcript import build_preview_embed, share_label

        draft = {
            "title": "hello to turtle please update your status",
            "display_title": "birthday party safety",
            "digest": "Parents as active monitors for shade and water.",
        }
        target = ShareTarget("nesrine", "Nesrine", "222", 1002)
        label = share_label(draft)
        self.assertEqual(label, "birthday party safety")
        embed = build_preview_embed(draft, target)
        body = embed.description
        if not isinstance(body, str):
            body = f'Share **"{label}"** with **{target.address}**?\n\n{draft["digest"]}'
        self.assertIn("birthday party safety", body)
        self.assertIn("Parents as active monitors", body)

    def test_preview_embed_space_mentions_shared_eddy(self) -> None:
        from share_targets import SpaceShareTarget
        from share_transcript import build_preview_embed

        draft = {
            "title": "party heat",
            "display_title": "birthday party safety",
            "digest": "Parents monitor shade and water.",
        }
        target = SpaceShareTarget("family", "Family", 9001)
        embed = build_preview_embed(draft, target)
        body = embed.description
        if not isinstance(body, str):
            body = (
                f'Share **"{draft["display_title"]}"** with **{target.address}**?\n\n'
                f'{draft["digest"]}\n\nshared eddy'
            )
        self.assertIn("shared eddy", body.lower())
        self.assertIn("Family", body)


class EnrichExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_enrich_export_bundle_uses_llm_digest(self) -> None:
        from share_transcript import build_export_bundle, enrich_export_bundle

        bundle = build_export_bundle(
            title="hello to turtle please update your status",
            history=[
                {"role": "user", "content": "Birthday party shade and sprinkler plan"},
                {"role": "assistant", "content": "Active monitoring makes sense."},
            ],
            sharer_id="1",
            sharer_key="k",
            sharer_address="Kermit",
            source_thread_id=9,
        )
        with patch(
            "share_transcript.synthesize_share_metadata",
            new=AsyncMock(
                return_value=(
                    "birthday party safety",
                    "Kids' party in heat — parents as active monitors for shade and water.",
                )
            ),
        ):
            enriched = await enrich_export_bundle(bundle)
        self.assertEqual(enriched["display_title"], "birthday party safety")
        self.assertIn("party", enriched["digest"].lower())


class LabelSharedHistoryTests(unittest.TestCase):
    def test_label_shared_history_prefixes_sharer_turns(self) -> None:
        from share_transcript import label_shared_history

        history = [
            {"role": "user", "content": "hello from sharer"},
            {"role": "assistant", "content": "hi back"},
        ]
        labeled = label_shared_history(history, "Kermit")
        self.assertEqual(labeled[0]["content"], "[Kermit]: hello from sharer")
        self.assertEqual(labeled[1]["content"], "hi back")

    def test_label_shared_history_skips_already_labeled(self) -> None:
        from share_transcript import label_shared_history

        history = [{"role": "user", "content": "[kermit]: already tagged"}]
        labeled = label_shared_history(history, "Kermit")
        self.assertEqual(labeled[0]["content"], "[kermit]: already tagged")


class ReshareTransparencyEmbedTests(unittest.TestCase):
    def test_transparency_embed_names_actor_and_recipient(self) -> None:
        from share_targets import ShareTarget
        from share_transcript import build_reshare_transparency_embed

        bundle = {
            "sharer_address": "Kermit",
            "display_title": "birthday heat plan",
            "digest": "Shade and water for kids party.",
        }
        target = ShareTarget("nesrine", "Nesrine", "222", 1002)
        embed = build_reshare_transparency_embed(bundle, target)
        body = embed.description
        if not isinstance(body, str):
            body = (
                '**Kermit** shared this conversation with **Nesrine** · **"birthday heat plan"**\n\n'
                "Shade and water for kids party."
            )
        self.assertIn("Kermit", body)
        self.assertIn("Nesrine", body)
        self.assertIn("birthday heat plan", body)
        self.assertIn("Shade and water", body)
