"""`!pi` names the installed agent and the model, and an update has to match the release.

A planted checksum that does not match leaves the current Pi in place. A matching
one replaces it. The card never shows a key that was sitting beside the model.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

try:
    import discord  # noqa: F401
except ImportError:
    raise unittest.SkipTest("needs discord.py")

import pi_card
import ui_kit
from tests.test_mcp_list import alltext


def _tarball(body: bytes = b"echo ok\n") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo("pi/pi")
        info.size = len(body)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(body))
    return buf.getvalue()


def _sums(blob: bytes, digest: str | None = None) -> str:
    return f"{digest or hashlib.sha256(blob).hexdigest()}  pi-darwin-arm64.tar.gz\n"


class Words(unittest.TestCase):
    def test_every_string_exists_in_english_and_german(self):
        self.assertEqual(ui_kit.parity(pi_card._TEXT), [])


class TheCard(unittest.TestCase):
    def text(self, **kw):
        view = pi_card.surface(on_check=self._press, on_ask=self._press, on_confirm=self._press, on_keep=self._press, **kw)
        self.assertEqual(ui_kit.violations(view), [])
        return alltext(view)

    @staticmethod
    async def _press(_interaction):
        return None

    def test_it_names_the_version_and_the_model_and_not_a_key(self):
        planted = "PLANTED_KEY"
        model = pi_card.parse_model(
            '{"providers": {"ollama": {"apiKey": "%s", "models": [{"id": "qwen3.8:27b"}]}}}' % planted
        )
        text = self.text(version="1.2.0", model=model)
        self.assertIn("1.2.0", text)
        self.assertIn("qwen3.8:27b", text)
        self.assertNotIn(planted, text)
        self.assertIn("Check for an update", text)
        self.assertNotIn("Update Pi", text)

    def test_the_current_release_offers_no_update(self):
        text = self.text(version="1.2.0", model="qwen3.8:27b", latest="v1.2.0")
        self.assertIn("current release", text)
        self.assertNotIn("Update", text)

    def test_a_newer_release_asks_before_it_updates(self):
        text = self.text(version="1.2.0", model="qwen3.8:27b", latest="v1.3.0")
        self.assertIn("Update to 1.3.0", text)
        asked = self.text(version="1.2.0", model="qwen3.8:27b", latest="v1.3.0", asking=True)
        self.assertIn("Update Pi", asked)
        self.assertIn("Keep this version", asked)

    def test_a_later_patch_is_newer_and_a_smaller_minor_is_not(self):
        self.assertTrue(pi_card.is_newer("1.2.0", "v1.2.1"))
        self.assertFalse(pi_card.is_newer("1.10.0", "1.9.0"))
        self.assertFalse(pi_card.is_newer("1.2.0", "1.2.0"))


class TheInstall(unittest.TestCase):
    def test_a_bad_checksum_leaves_the_installed_pi_alone(self):
        blob = _tarball()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            share = root / "pi-1.2.0"
            share.mkdir()
            (share / "pi").write_text("old")
            link = root / "bin" / "pi"
            link.parent.mkdir()
            link.symlink_to(share / "pi")
            with self.assertRaises(pi_card.ChecksumError):
                pi_card.install_verified(blob, _sums(blob, "0" * 64), root / "pi-9.9.9", link)
            self.assertEqual(link.read_text(), "old")
            self.assertFalse((root / "pi-9.9.9").exists())

    def test_a_matching_checksum_replaces_the_binary(self):
        blob = _tarball(b"echo new\n")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            link = root / "bin" / "pi"
            pi_card.install_verified(blob, _sums(blob), root / "pi-9.9.9", link)
            self.assertEqual(link.read_text(), "echo new\n")
            self.assertTrue(link.is_symlink())

    def test_a_path_that_escapes_the_archive_is_refused(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            info = tarfile.TarInfo("../escaped")
            payload = b"nope"
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        blob = buf.getvalue()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            link = root / "bin" / "pi"
            with self.assertRaises(pi_card.ChecksumError):
                pi_card.install_verified(blob, _sums(blob), root / "pi-bad", link)
            self.assertFalse(link.exists())


class TheDoor(unittest.IsolatedAsyncioTestCase):
    async def test_only_the_magic_room_gets_the_card(self):
        import commands

        message = MagicMock()
        message.author.id = 1
        message.reply = AsyncMock()
        prim = MagicMock()
        prim.name = "craft"
        with patch("mage.get_channel_primitive", return_value=prim), patch(
            "mage.resolve_dialogue_channel_id", return_value=1
        ), patch("room_models.locale_for", return_value="en"):
            await commands.cmd_pi(message, "")
        message.reply.assert_awaited()
        self.assertIn("#magic", message.reply.await_args.args[0])
        self.assertNotIn("view", message.reply.await_args.kwargs)

        message.reply.reset_mock()
        prim.name = "magic"
        with patch("mage.get_channel_primitive", return_value=prim), patch(
            "mage.resolve_dialogue_channel_id", return_value=1
        ), patch("room_models.locale_for", return_value="en"), patch(
            "pi_card.read_installed", return_value=("1.2.0", "qwen3.8:27b")
        ):
            await commands.cmd_pi(message, "")
        self.assertIn("view", message.reply.await_args.kwargs)
        self.assertIn("1.2.0", alltext(message.reply.await_args.kwargs["view"]))
