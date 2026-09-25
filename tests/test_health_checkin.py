"""Evening health check-in: opt-in, parse, isolation, notify payload."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from channel_primitives import resolve_primitive
from health_checkin import (
    DEFAULT_QUESTIONS,
    MODE_STATE,
    OPEN_STATE_DE,
    STATE_ASK_DE,
    CheckinConfig,
    CheckinQuestion,
    ack_text,
    already_logged,
    checkin_content,
    classify_state_capture,
    compose_state_checkin,
    due_now,
    format_observation,
    health_channel_targets,
    is_skip,
    load_config,
    mark_logged,
    message_in_parent,
    notify_kwargs,
    parse_reply,
    posted_draft,
    posted_message_id,
    prompt_text,
    send_then_mark,
    state_source,
    write_enabled_config,
)
from health_record import save_observation


def _health_primitive(channel_id: str = "7", mage: str = "health-kermit", subject: str = "kermit"):
    return resolve_primitive(
        {
            "spaces": {
                mage: {
                    "members": [subject],
                    "subject": subject,
                    "memory": "isolated",
                }
            },
            "channels": {
                channel_id: {
                    "primitive": "health",
                    "base": "solo",
                    "mage": mage,
                    "subject": subject,
                }
            },
        },
        channel_id,
    )


class ParseTests(unittest.TestCase):
    def test_five_scores_and_flags(self) -> None:
        entry = parse_reply("2 1 0 1 2 c ja t nein")
        self.assertEqual(entry.scores, (2, 1, 0, 1, 2))
        self.assertTrue(entry.cannabis)
        self.assertFalse(entry.therapy)

    def test_commas_and_english_flags(self) -> None:
        entry = parse_reply("3,3,1,2,0 cannabis=yes therapy=no")
        self.assertEqual(entry.scores, (3, 3, 1, 2, 0))
        self.assertTrue(entry.cannabis)
        self.assertFalse(entry.therapy)

    def test_prose_is_not_a_checkin(self) -> None:
        self.assertIsNone(parse_reply("I felt better with the kids today."))

    def test_out_of_range_rejected(self) -> None:
        self.assertIsNone(parse_reply("2 1 4 1 2"))

    def test_skip_words(self) -> None:
        self.assertTrue(is_skip("skip"))
        self.assertTrue(is_skip("nicht heute"))
        self.assertFalse(is_skip("2 1 0 1 2"))


class ConfigAndDueTests(unittest.TestCase):
    def test_missing_file_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(tmp)
            self.assertFalse(config.enabled)
            self.assertFalse(due_now(config, datetime(2026, 9, 11, 22, 0)))

    def test_enabled_file_is_due_at_hour(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_enabled_config(tmp, hour=21)
            config = load_config(tmp)
            self.assertTrue(config.enabled)
            self.assertFalse(due_now(config, datetime(2026, 9, 11, 20, 59)))
            self.assertTrue(due_now(config, datetime(2026, 9, 11, 21, 0)))

    def test_custom_questions_load_from_instance_file(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmp:
            write_enabled_config(tmp, hour=21)
            path = Path(tmp) / "record" / "checkin.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["questions"] = [
                {
                    "id": "pain",
                    "de": "Wie stark war der Schmerz heute?",
                    "en": "How strong was the pain today?",
                }
            ]
            raw["flags"] = []
            path.write_text(json.dumps(raw), encoding="utf-8")
            config = load_config(tmp)
            self.assertEqual([q.id for q in config.questions], ["pain"])
            self.assertEqual(config.flags, ())
            content = prompt_text(
                mention="",
                locale="de",
                questions=config.questions,
                flags=config.flags,
            )
            self.assertIn("Schmerz", content)
            self.assertNotIn("Interesse", content)


class IsolationTests(unittest.TestCase):
    def test_house_without_config_is_not_a_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            house = Path(tmp) / "health"
            own = Path(tmp) / "health-kermit"
            house.mkdir()
            own.mkdir()
            write_enabled_config(own, hour=21)
            registry = {
                "mages": {"operator": {"discord_id": "99"}},
                "spaces": {
                    "health": {
                        "practice_dir": str(house),
                        "subject": "partner",
                        "members": ["partner", "operator"],
                    },
                    "health-own": {
                        "practice_dir": str(own),
                        "subject": "operator",
                        "members": ["operator"],
                    },
                },
                "channels": {
                    "1": {
                        "primitive": "health",
                        "base": "shared",
                        "mage": "health",
                        "subject": "partner",
                    },
                    "2": {
                        "primitive": "health",
                        "base": "solo",
                        "mage": "health-own",
                        "subject": "operator",
                    },
                },
            }
            targets = health_channel_targets(registry)
            self.assertEqual([t["channel_id"] for t in targets], [2])
            self.assertEqual(targets[0]["discord_id"], "99")
            self.assertNotIn(str(house), [t["practice_dir"] for t in targets])

    def test_tilde_practice_dir_still_opts_in(self) -> None:
        """Live registry stores ``~/workshops/...``. A literal Path() misses the file."""
        probe = Path.home() / f".turtle-checkin-probe-{os.getpid()}"
        if probe.exists():
            shutil.rmtree(probe)
        probe.mkdir()
        try:
            write_enabled_config(probe, hour=21)
            tilde = "~/" + str(probe.relative_to(Path.home()))
            self.assertTrue(load_config(tilde).enabled)
            registry = {
                "mages": {"operator": {"discord_id": "99"}},
                "spaces": {
                    "health-own": {
                        "practice_dir": tilde,
                        "subject": "operator",
                        "members": ["operator"],
                    }
                },
                "channels": {
                    "2": {
                        "primitive": "health",
                        "base": "solo",
                        "mage": "health-own",
                        "subject": "operator",
                    }
                },
            }
            targets = health_channel_targets(registry)
            self.assertEqual([t["channel_id"] for t in targets], [2])
            self.assertEqual(Path(targets[0]["practice_dir"]), probe)
        finally:
            shutil.rmtree(probe, ignore_errors=True)


class RecordTests(unittest.TestCase):
    def test_owner_scores_land_as_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            entry = parse_reply("2 1 0 1 2 c ja t nein")
            result = save_observation(
                tmp,
                primitive=_health_primitive(),
                actor="kermit",
                text=format_observation(entry, date(2026, 9, 11)),
            )
            mark_logged(tmp, date(2026, 9, 11))
            self.assertEqual(result["decision"], "applied")
            lines = (Path(tmp) / "record" / "observations.jsonl").read_text()
            self.assertIn("interest=2", lines)
            self.assertIn("cannabis=yes", lines)
            self.assertTrue(already_logged(tmp, date(2026, 9, 11)))
            board = (Path(tmp) / "health_model.md").read_text()
            self.assertIn("Abendcheck 2026-09-11", board)

    def test_mark_logged_suppresses_second_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(already_logged(tmp, date(2026, 9, 11)))
            mark_logged(tmp, date(2026, 9, 11))
            self.assertTrue(already_logged(tmp, date(2026, 9, 11)))


class NotifyTests(unittest.TestCase):
    def test_prompt_mentions_and_must_not_be_silent(self) -> None:
        content = prompt_text(mention="<@99>", locale="de")
        self.assertIn("<@99>", content)
        self.assertIn("Abendcheck", content)
        payload = notify_kwargs(content)
        self.assertEqual(payload["content"], content)
        self.assertIs(payload["silent"], False)

    def test_prompt_asks_questions_not_nouns(self) -> None:
        content = prompt_text(mention="<@99>", locale="de")
        self.assertIn("?", content)
        self.assertIn("Wie viel Interesse", content)
        self.assertNotIn("Interesse · Entscheidung · Überraschung · Hinziehen · Bedeutung", content)
        for question in DEFAULT_QUESTIONS:
            self.assertIn(question.de, content)

    def test_instance_questions_do_not_leak_to_sibling(self) -> None:
        house_q = (
            CheckinQuestion(
                "pain",
                "Wie stark war der Schmerz heute?",
                "How strong was the pain today?",
            ),
        )
        own = prompt_text(mention="", locale="de")
        house = prompt_text(mention="", locale="de", questions=house_q, flags=())
        self.assertIn("Wie viel Interesse", own)
        self.assertNotIn("Schmerz", own)
        self.assertIn("Schmerz", house)
        self.assertNotIn("Wie viel Interesse", house)
        self.assertIsNone(parse_reply("2 1 0 1 2", questions=house_q))
        self.assertEqual(parse_reply("2", questions=house_q).scores, (2,))

    def test_ack_does_not_name_a_diagnosis(self) -> None:
        entry = parse_reply("2 1 0 1 2 c ja t nein")
        text = ack_text(entry, locale="de")
        self.assertIn("Gehalten", text)
        self.assertNotIn("Dysthymie", text)
        self.assertNotIn("you have", text.lower())


class CaptureGateTests(unittest.TestCase):
    def test_notify_payload_fails_if_silenced(self) -> None:
        payload = notify_kwargs(prompt_text(mention="<@1>"))
        silenced = dict(payload, silent=True)
        self.assertTrue(payload["silent"] is False)
        self.assertTrue(silenced["silent"] is True)


def _eddy_note(root: Path, body: str, *, day: str = "2026-09-23T10:00:00+02:00") -> None:
    folder = root / "story" / "eddies"
    folder.mkdir(parents=True)
    (folder / "1-today.md").write_text(
        "---\n"
        f'timestamp: "{day}"\n'
        'thread: "1"\n'
        "title: today\n"
        "trigger: manual\n"
        "---\n\n"
        f"{body}\n",
        encoding="utf-8",
    )


class StateModeTests(unittest.TestCase):
    def test_missing_mode_stays_survey_and_unknown_mode_does_too(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_enabled_config(tmp, hour=21)
            self.assertEqual(load_config(tmp).mode, "survey")
            path = Path(tmp) / "record" / "checkin.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["mode"] = "banana"
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(load_config(tmp).mode, "survey")
            raw["mode"] = MODE_STATE
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(load_config(tmp).mode, MODE_STATE)

    def test_survey_config_still_asks_the_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_enabled_config(tmp, hour=21)
            survey = load_config(tmp)
            content, draft = asyncio.run(
                checkin_content(survey, tmp, date(2026, 9, 23), mention="<@9>")
            )
            self.assertIsNone(draft)
            self.assertIn("Wie viel Interesse", content)
            path = Path(tmp) / "record" / "checkin.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["mode"] = MODE_STATE
            path.write_text(json.dumps(raw), encoding="utf-8")
            state = load_config(tmp)
            self.assertIsInstance(state, CheckinConfig)
            quiet, _draft = asyncio.run(
                checkin_content(
                    state,
                    tmp,
                    date(2026, 9, 23),
                    mention="<@9>",
                    generate=mock.AsyncMock(side_effect=AssertionError("model")),
                )
            )
            self.assertNotIn("Wie viel Interesse", quiet)
            self.assertIn(OPEN_STATE_DE, quiet)

    def test_empty_day_does_not_read_older_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "health_model.md").write_text("OLDER-BOARD-FACT\n", encoding="utf-8")

            def boom(_root):
                raise AssertionError("older material was read on an empty day")

            with mock.patch("health_checkin._older_wording", boom):
                self.assertIsNone(state_source(root, date(2026, 9, 23)))
            content, draft = asyncio.run(
                compose_state_checkin(
                    root,
                    date(2026, 9, 23),
                    mention="<@9>",
                    locale="de",
                    generate=mock.AsyncMock(side_effect=AssertionError("model")),
                )
            )
            self.assertIsNone(draft)
            self.assertIn(OPEN_STATE_DE, content)
            self.assertNotIn("OLDER-BOARD-FACT", content)
            self.assertNotIn(STATE_ASK_DE, content)

    def test_planted_same_root_fact_reaches_the_draft_and_house_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            own = Path(tmp) / "own"
            house = Path(tmp) / "house"
            own.mkdir()
            house.mkdir()
            _eddy_note(own, "OWN-PLANTED-FACT from this room today.")
            _eddy_note(house, "HOUSE-PLANTED-FACT from the other room today.")
            seen: dict[str, str] = {}

            async def generate(prompt: str) -> str:
                seen["prompt"] = prompt
                return "Heute trägt der Stand OWN-PLANTED-FACT."

            content, draft = asyncio.run(
                compose_state_checkin(
                    own, date(2026, 9, 23), mention="<@9>", locale="de", generate=generate
                )
            )
            self.assertIn("OWN-PLANTED-FACT", seen["prompt"])
            self.assertNotIn("HOUSE-PLANTED-FACT", seen["prompt"])
            self.assertIn("OWN-PLANTED-FACT", draft or "")
            self.assertIn(STATE_ASK_DE, content)
            self.assertNotIn("HOUSE-PLANTED-FACT", content)

    def test_failed_generation_posts_the_open_question_without_the_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _eddy_note(root, "OWN-PLANTED-FACT should not be invented into a state.")
            content, draft = asyncio.run(
                compose_state_checkin(
                    root,
                    date(2026, 9, 23),
                    mention="",
                    locale="de",
                    generate=mock.AsyncMock(return_value=""),
                )
            )
            self.assertIsNone(draft)
            self.assertIn(OPEN_STATE_DE, content)
            self.assertNotIn("OWN-PLANTED-FACT", content)

    def test_failed_send_does_not_mark_posted(self) -> None:
        async def down(_content: str):
            raise RuntimeError("discord down")

        with tempfile.TemporaryDirectory() as tmp:
            ok = asyncio.run(
                send_then_mark(
                    tmp, date(2026, 9, 23), "body", down, draft="a draft long enough to store"
                )
            )
            self.assertFalse(ok)
            self.assertIsNone(posted_message_id(tmp, date(2026, 9, 23)))
            self.assertIsNone(posted_draft(tmp, date(2026, 9, 23)))

    def test_successful_send_stores_the_draft(self) -> None:
        async def up(_content: str) -> str:
            return "55"

        with tempfile.TemporaryDirectory() as tmp:
            ok = asyncio.run(
                send_then_mark(
                    tmp,
                    date(2026, 9, 23),
                    "body",
                    up,
                    draft="Heute ist der Stand ruhig und benennbar.",
                )
            )
            self.assertTrue(ok)
            self.assertEqual(posted_message_id(tmp, date(2026, 9, 23)), "55")
            self.assertIn("ruhig", posted_draft(tmp, date(2026, 9, 23)) or "")

    def test_eddy_and_second_reply_are_conversation(self) -> None:
        self.assertFalse(
            message_in_parent(SimpleNamespace(channel=SimpleNamespace(parent_id=4)))
        )
        self.assertTrue(message_in_parent(SimpleNamespace(channel=SimpleNamespace())))
        self.assertIsNone(
            classify_state_capture(
                "ja",
                in_parent=False,
                already_logged=False,
                references_prompt=True,
                has_draft=True,
            )
        )
        self.assertIsNone(
            classify_state_capture(
                "ja",
                in_parent=True,
                already_logged=True,
                references_prompt=True,
                has_draft=True,
            )
        )
        self.assertIsNone(
            classify_state_capture(
                "I had a long afternoon.",
                in_parent=True,
                already_logged=False,
                references_prompt=True,
                has_draft=True,
            )
        )

    def test_ja_and_correction_are_one_event_each_and_prep_loses_them_when_deleted(self) -> None:
        draft = "Heute trägt der Stand OWN-PLANTED-FACT."
        with tempfile.TemporaryDirectory() as tmp:
            for n in range(10):
                save_observation(
                    tmp,
                    primitive=_health_primitive(),
                    actor="kermit",
                    text=f"Abendcheck 2026-09-{n + 1:02d} sober interest=1",
                )
            before = (Path(tmp) / "record" / "observations.jsonl").read_text(encoding="utf-8")
            confirmed = save_observation(
                tmp,
                primitive=_health_primitive(),
                actor="kermit",
                text=draft,
                verdict="confirmed",
            )
            self.assertEqual(confirmed["decision"], "applied")
            lines = (Path(tmp) / "record" / "observations.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 11)
            self.assertEqual(before.strip().splitlines()[0], lines[0])
            row = json.loads(lines[-1])
            self.assertEqual(row["verdict"], "confirmed")
            self.assertEqual(row["text"], draft)
            self.assertNotIn("turtle_draft", row)

            corrected = save_observation(
                tmp,
                primitive=_health_primitive(),
                actor="kermit",
                text="eher ruhiger als der Entwurf sagt",
                verdict="corrected",
                turtle_draft=draft,
            )
            self.assertEqual(corrected["decision"], "applied")
            lines = (Path(tmp) / "record" / "observations.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 12)
            row = json.loads(lines[-1])
            self.assertEqual(row["verdict"], "corrected")
            self.assertEqual(row["text"], "eher ruhiger als der Entwurf sagt")
            self.assertEqual(row["turtle_draft"], draft)

            from health_record import appointment_prep

            prep = appointment_prep(tmp).read_text(encoding="utf-8")
            self.assertIn("OWN-PLANTED-FACT", prep)
            self.assertIn("eher ruhiger", prep)
            (Path(tmp) / "record" / "observations.jsonl").unlink()
            hollow = appointment_prep(tmp).read_text(encoding="utf-8")
            self.assertNotIn("OWN-PLANTED-FACT", hollow)
            self.assertNotIn("eher ruhiger", hollow)

    def test_bare_ja_confirms_and_nein_keeps_his_words(self) -> None:
        confirm = classify_state_capture(
            "ja",
            in_parent=True,
            already_logged=False,
            references_prompt=False,
            has_draft=True,
        )
        self.assertIsNotNone(confirm)
        assert confirm is not None
        self.assertEqual(confirm.kind, "confirm")
        correct = classify_state_capture(
            "nein, eher ruhiger als gedacht",
            in_parent=True,
            already_logged=False,
            references_prompt=False,
            has_draft=True,
        )
        self.assertIsNotNone(correct)
        assert correct is not None
        self.assertEqual(correct.kind, "correct")
        self.assertEqual(correct.text, "ruhiger als gedacht")
        stated = classify_state_capture(
            "ruhig, und das ist alles",
            in_parent=True,
            already_logged=False,
            references_prompt=True,
            has_draft=False,
        )
        self.assertIsNotNone(stated)
        assert stated is not None
        self.assertEqual(stated.kind, "stated")
        loose = classify_state_capture(
            "ruhig, und das ist alles",
            in_parent=True,
            already_logged=False,
            references_prompt=False,
            has_draft=False,
        )
        self.assertIsNone(loose)


class StateLanguageTests(unittest.TestCase):
    """Today's notes are Turtle's English summaries; the room's locale names the language."""

    def _prompt_for(self, locale: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            _eddy_note(Path(tmp), "You described a quiet day with a long walk.")
            seen: dict[str, str] = {}

            async def generate(prompt: str) -> str:
                seen["prompt"] = prompt
                return "Heute war der Stand ruhig, mit einem langen Spaziergang."

            asyncio.run(
                compose_state_checkin(
                    tmp, date(2026, 9, 23), mention="", locale=locale, generate=generate
                )
            )
            return seen["prompt"]

    def test_german_room_asks_for_german_over_english_notes(self) -> None:
        prompt = self._prompt_for("de")
        self.assertIn("Write in German.", prompt)
        self.assertNotIn("Write in English.", prompt)

    def test_english_room_asks_for_english(self) -> None:
        prompt = self._prompt_for("en")
        self.assertIn("Write in English.", prompt)
        self.assertNotIn("Write in German.", prompt)

    def test_system_prompt_does_not_follow_the_notes_language(self) -> None:
        from health_checkin import _STATE_SYSTEM

        self.assertNotIn("language of today's notes", _STATE_SYSTEM)


class CheckinScheduleTests(unittest.TestCase):
    """An hourly loop fires at the last restart's minute, so 21:00 became 21:58."""

    def test_checkin_tick_is_well_inside_the_hour(self) -> None:
        import re

        # Other suites stub discord.ext.tasks, so the decorator is read from source.
        src = (Path(__file__).resolve().parents[1] / "background.py").read_text(encoding="utf-8")
        tick = re.search(r"^HEALTH_CHECKIN_TICK_MINUTES = (\d+)$", src, re.M)
        self.assertIsNotNone(tick)
        assert tick is not None
        self.assertLessEqual(int(tick.group(1)), 10)
        self.assertRegex(
            src,
            r"@tasks\.loop\(minutes=HEALTH_CHECKIN_TICK_MINUTES\)\nasync def health_checkin_loop",
        )

    def test_bot_starts_the_checkin_loop_and_the_canary_watches_it(self) -> None:
        root = Path(__file__).resolve().parents[1]
        bot = (root / "discord_bot.py").read_text(encoding="utf-8")
        canary = (root / "background.py").read_text(encoding="utf-8")
        self.assertIn("health_checkin_loop.start()", bot)
        self.assertIn('"health_checkin": health_checkin_loop.is_running()', canary)

    def test_daily_note_pass_no_longer_posts_checkins(self) -> None:
        import story_daily

        with mock.patch.object(
            story_daily,
            "_run_scheduled_health_checkins",
            mock.AsyncMock(side_effect=AssertionError("check-in rode the hourly pass")),
        ), mock.patch("dates.run_scheduled_date_reminders", mock.AsyncMock()):
            asyncio.run(story_daily.run_scheduled_daily_note(practice_dirs=[]))

    def test_checkin_pass_swallows_and_reports_failure(self) -> None:
        import story_daily

        with mock.patch.object(
            story_daily,
            "_run_scheduled_health_checkins",
            mock.AsyncMock(side_effect=RuntimeError("down")),
        ):
            self.assertEqual(asyncio.run(story_daily.run_scheduled_health_checkins()), 0)
