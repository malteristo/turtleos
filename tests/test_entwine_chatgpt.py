"""ChatGPT export inventory — metadata only, no bodies, no live path."""

from __future__ import annotations

import ast
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from entwine_chatgpt import (
    CLASSIFY_SYSTEM,
    EntwineRoots,
    assert_entwine_route,
    entwine_conversation,
    extract_conversation,
    format_classify_user,
    inventory_chatgpt_zip,
    parse_classifier_reply,
    render_inventory_markdown,
    sha256_file,
    write_inventory,
)

REPO = Path(__file__).resolve().parents[1]
SECRET = "SECRET_BODY_TOKEN_should_never_inventory"
LIVE_MODULES = (
    "dialogue_turn.py",
    "discord_bot.py",
    "tos_tools.py",
    "memory_agent.py",
    "river_bot.py",
)


def _node(role: str, text: str, node_id: str, parent: str | None = None) -> dict:
    node = {
        "id": node_id,
        "message": {
            "id": node_id,
            "author": {"role": role},
            "content": {"content_type": "text", "parts": [text]},
        },
    }
    if parent:
        node["parent"] = parent
    return node


def _conversation(**overrides) -> dict:
    conv = {
        "conversation_id": "conv-1",
        "id": "conv-1",
        "title": "Fixture title",
        "create_time": 1700000000.0,
        "update_time": 1700001000.0,
        "is_archived": False,
        "is_do_not_remember": False,
        "default_model_slug": "gpt-4o",
        "mapping": {
            "a": _node("user", f"hello {SECRET}", "a"),
            "b": _node("assistant", "hi", "b", parent="a"),
        },
    }
    conv.update(overrides)
    return conv


def _write_zip(path: Path, files: dict[str, str | bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return path


class InventoryTests(unittest.TestCase):
    def test_shards_are_corpus_shared_list_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "export.zip"
            _write_zip(
                zip_path,
                {
                    "conversations-000.json": json.dumps(
                        [
                            _conversation(),
                            _conversation(
                                conversation_id="conv-2",
                                id="conv-2",
                                title="Do not remember me",
                                is_do_not_remember=True,
                                mapping={
                                    "a": _node("user", "skip", "a"),
                                },
                            ),
                        ]
                    ),
                    "shared_conversations.json": json.dumps(
                        [{"conversation_id": "shared-only", "title": "Not corpus"}]
                    ),
                    "chat.html": "<html>not corpus</html>",
                    "blob.dat": b"\x00\x01",
                },
            )
            inventory = inventory_chatgpt_zip(zip_path)
            ids = {row["id"] for row in inventory["conversations"]}
            self.assertEqual(ids, {"conv-1", "conv-2"})
            self.assertEqual(inventory["conversation_count"], 2)
            self.assertEqual(inventory["user_messages"], 2)
            self.assertEqual(inventory["assistant_messages"], 1)
            self.assertEqual(inventory["shard_count"], 1)
            flagged = next(
                row for row in inventory["conversations"] if row["id"] == "conv-2"
            )
            self.assertTrue(flagged["is_do_not_remember"])
            self.assertEqual(inventory["origin_agent"], "ChatGPT")
            self.assertEqual(inventory["zip_sha256"], sha256_file(zip_path))

    def test_unsharded_conversations_json_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "legacy.zip"
            _write_zip(
                zip_path,
                {
                    "conversations.json": json.dumps(
                        [_conversation(conversation_id="legacy-1", id="legacy-1")]
                    )
                },
            )
            inventory = inventory_chatgpt_zip(zip_path)
            self.assertEqual(inventory["conversation_count"], 1)
            self.assertEqual(inventory["conversations"][0]["id"], "legacy-1")

    def test_message_parts_never_enter_inventory_or_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "secret.zip"
            _write_zip(
                zip_path,
                {"conversations-000.json": json.dumps([_conversation()])},
            )
            inventory = inventory_chatgpt_zip(zip_path)
            dumped = json.dumps(inventory)
            self.assertNotIn(SECRET, dumped)
            self.assertNotIn("mapping", dumped)
            self.assertNotIn("parts", dumped)
            markdown = render_inventory_markdown(inventory)
            self.assertNotIn(SECRET, markdown)
            written = write_inventory(Path(tmp) / "out", inventory)
            self.assertTrue(written.is_file())
            self.assertNotIn(SECRET, written.read_text(encoding="utf-8"))
            self.assertNotIn(
                SECRET,
                (Path(tmp) / "out" / "inventory.md").read_text(encoding="utf-8"),
            )

    def test_missing_shards_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "empty.zip"
            _write_zip(zip_path, {"chat.html": "<html></html>"})
            with self.assertRaisesRegex(ValueError, "conversations"):
                inventory_chatgpt_zip(zip_path)

    def test_unsafe_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "unsafe.zip"
            _write_zip(
                zip_path,
                {
                    "../escape.json": json.dumps([_conversation()]),
                    "conversations-000.json": json.dumps([_conversation()]),
                },
            )
            with self.assertRaisesRegex(ValueError, "unsafe path"):
                inventory_chatgpt_zip(zip_path)

    def test_live_dialogue_modules_do_not_import_entwine(self) -> None:
        imported = []
        for name in LIVE_MODULES:
            path = REPO / name
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] == "entwine_chatgpt":
                            imported.append(name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.split(".")[0] == "entwine_chatgpt":
                        imported.append(name)
        self.assertEqual(imported, [], imported)

    def test_family_is_not_an_entwine_route(self) -> None:
        self.assertEqual(assert_entwine_route("personal"), "personal")
        self.assertEqual(assert_entwine_route("health"), "health")
        self.assertEqual(assert_entwine_route("skip"), "skip")
        with self.assertRaisesRegex(ValueError, "shared room"):
            assert_entwine_route("family")

    def test_git_does_not_track_a_live_export(self) -> None:
        proc = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z"],
            capture_output=True,
            check=True,
        )
        tracked = [name.decode() for name in proc.stdout.split(b"\x00") if name]
        forbidden = [
            name
            for name in tracked
            if name.endswith(".zip")
            and "chatgpt" in name.lower()
            or Path(name).name.startswith("conversations-")
            or Path(name).name == "conversations.json"
        ]
        self.assertEqual(forbidden, [], forbidden)


class DistillTests(unittest.TestCase):
    def test_classifier_prompt_forbids_family_route(self) -> None:
        self.assertIn("Never use family", CLASSIFY_SYSTEM)
        self.assertIn("still route personal", CLASSIFY_SYSTEM)
        user = format_classify_user(
            {
                "title": "fixture",
                "messages": [{"role": "user", "text": f"hello {SECRET}"}],
            }
        )
        self.assertIn(SECRET, user)
        self.assertIn("user:", user)
        from scripts.entwine_distill import _classifier

        with self.assertRaisesRegex(ValueError, "live local"):
            _classifier("x", {}, "gemma4:31b")
        self.assertTrue(callable(_classifier("x", {}, "qwen3.6:35b-a3b")))
    def test_extract_sees_bodies_inventory_still_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "export.zip"
            _write_zip(
                zip_path,
                {"conversations-000.json": json.dumps([_conversation()])},
            )
            extracted = extract_conversation(zip_path, "conv-1")
            self.assertIn(SECRET, extracted["messages"][0]["text"])
            dumped = json.dumps(inventory_chatgpt_zip(zip_path))
            self.assertNotIn(SECRET, dumped)

    def test_do_not_remember_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path, personal, health, family = self._layout(tmp)
            written = entwine_conversation(
                zip_path,
                "skip-me",
                EntwineRoots(personal=personal, health=health),
                classify=lambda _c: '{"splits":[{"route":"personal","title":"x","body":"nope"}]}',
                forbidden_roots=[family],
            )
            self.assertEqual(written, [])
            self.assertEqual(list((personal / "story" / "exogenous").rglob("*.md")), [])

    def test_family_route_fails_and_forbidden_root_cannot_receive_a_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path, personal, health, family = self._layout(tmp)
            conversation = extract_conversation(zip_path, "conv-1")
            with self.assertRaisesRegex(ValueError, "shared room"):
                parse_classifier_reply(
                    '{"splits":[{"route":"family","title":"kids","body":"the children"}]}',
                    conversation,
                )
            with self.assertRaisesRegex(ValueError, "forbidden root"):
                entwine_conversation(
                    zip_path,
                    "conv-1",
                    EntwineRoots(personal=family, health=health),
                    classify=lambda _c: (
                        '{"splits":[{"route":"personal","title":"kids",'
                        '"body":"the children were mentioned"}]}'
                    ),
                    forbidden_roots=[family],
                )

    def test_mixed_split_writes_health_and_personal_and_redacts_assistant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path, personal, health, family = self._layout(tmp, mixed=True)
            written = entwine_conversation(
                zip_path,
                "mixed-1",
                EntwineRoots(personal=personal, health=health),
                classify=lambda _c: json.dumps(
                    {
                        "splits": [
                            {
                                "route": "health",
                                "title": "fever days",
                                "body": "She had fever for three weeks. SECRET_DIAGNOSIS_TOKEN leaked.",
                                "observed": [
                                    "Fever for three weeks. The doctor said it was EBV.",
                                    "SECRET_DIAGNOSIS_TOKEN",
                                ],
                            },
                            {
                                "route": "personal",
                                "title": "kids mention",
                                "body": "She asked how to talk about the children.",
                            },
                        ]
                    }
                ),
                forbidden_roots=[family],
                entwined="2026-09-10",
            )
            self.assertEqual(len(written), 2)
            health_note = health / "story" / "exogenous" / "chatgpt" / "mixed-1-health.md"
            personal_note = personal / "story" / "exogenous" / "chatgpt" / "mixed-1-personal.md"
            self.assertTrue(health_note.is_file())
            self.assertTrue(personal_note.is_file())
            self.assertFalse((family / "story" / "exogenous").exists())
            health_text = health_note.read_text(encoding="utf-8")
            self.assertIn("source: exogenous/chatgpt", health_text)
            self.assertIn("route: health", health_text)
            self.assertIn("fever for three weeks", health_text.lower())
            self.assertNotIn("SECRET_DIAGNOSIS_TOKEN", health_text)
            harvest = (health / "record" / "entwine_observed.md").read_text(encoding="utf-8")
            self.assertIn("doctor said it was EBV", harvest)
            self.assertNotIn("SECRET_DIAGNOSIS_TOKEN", harvest)
            self.assertNotIn("SECRET_DIAGNOSIS_TOKEN", personal_note.read_text(encoding="utf-8"))

    def test_cli_writes_from_replay_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path, personal, health, family = self._layout(tmp)
            replay = Path(tmp) / "replay.json"
            replay.write_text(
                json.dumps(
                    {
                        "conv-1": {
                            "splits": [
                                {
                                    "route": "personal",
                                    "title": "hello",
                                    "body": "She said hello.",
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    "python3",
                    str(REPO / "scripts" / "entwine_distill.py"),
                    str(zip_path),
                    "--personal",
                    str(personal),
                    "--health",
                    str(health),
                    "--forbidden",
                    str(family),
                    "--ids",
                    "conv-1",
                    "--classify-json",
                    str(replay),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            note = personal / "story" / "exogenous" / "chatgpt" / "conv-1.md"
            self.assertTrue(note.is_file())
            self.assertIn("She said hello.", note.read_text(encoding="utf-8"))
            self.assertNotIn(SECRET, note.read_text(encoding="utf-8"))

    def _layout(self, tmp: str, *, mixed: bool = False):
        base = Path(tmp)
        zip_path = base / "export.zip"
        personal = base / "personal"
        health = base / "health"
        family = base / "family"
        for path in (personal, health, family):
            path.mkdir()
        conversations = [
            _conversation(),
            _conversation(
                conversation_id="skip-me",
                id="skip-me",
                is_do_not_remember=True,
                mapping={"a": _node("user", "please forget", "a")},
            ),
        ]
        if mixed:
            conversations.append(
                {
                    "conversation_id": "mixed-1",
                    "id": "mixed-1",
                    "title": "mixed thread",
                    "create_time": 1700002000.0,
                    "update_time": 1700003000.0,
                    "is_archived": False,
                    "is_do_not_remember": False,
                    "mapping": {
                        "a": _node(
                            "user",
                            "I had fever for three weeks and the doctor said it was EBV. "
                            "Also how do I talk about the children.",
                            "a",
                        ),
                        "b": _node(
                            "assistant",
                            "SECRET_DIAGNOSIS_TOKEN you clearly have a rare syndrome.",
                            "b",
                            parent="a",
                        ),
                    },
                }
            )
        _write_zip(zip_path, {"conversations-000.json": json.dumps(conversations)})
        return zip_path, personal, health, family


if __name__ == "__main__":
    unittest.main()
