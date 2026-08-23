"""Family dates registry, lead-time due, scheduled surfacing, routing, commands."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import dates as fd
import mage


# Deliberately small ints — not snowflake-shaped, so the sanitation guard
# never has to reason about whether a fixture ID is real.
PRIVATE_RIVER = 101
HOSTED_RIVER = 102
FAMILY_CHANNEL = 103


def _registry(tmp: str) -> dict:
    return {
        "mages": {
            "alpha": {"practice_dir": f"{tmp}/alpha", "primary": True, "locale": "en"},
            "beta": {"practice_dir": f"{tmp}/beta", "locale": "de"},
        },
        "spaces": {
            "family": {
                "practice_dir": f"{tmp}/family",
                "members": ["alpha", "beta"],
                "locale": "de",
            },
        },
        "channels": {
            str(PRIVATE_RIVER): {"mage": "alpha", "type": "river"},
            str(HOSTED_RIVER): {"mage": "beta", "type": "hosted-river"},
            str(FAMILY_CHANNEL): {"mage": "family", "type": "shared-river"},
        },
    }


class TestDatesRegistry(unittest.TestCase):
    def test_add_list_persist_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            entry = fd.add_date(
                tmp,
                title="kita fest",
                when="2026-12-24",
                recurrence="none",
                lead_days=[14, 1],
                captured_by="a member",
                notes="bring cake",
            )
            self.assertEqual(entry["title"], "kita fest")
            self.assertEqual(entry["date"], "2026-12-24")
            self.assertEqual(entry["recurrence"], "none")
            self.assertEqual(entry["lead_days"], [14, 1])
            self.assertEqual(entry["captured_by"], "a member")
            self.assertEqual(entry["notes"], "bring cake")
            self.assertTrue(entry["id"])

            listed = fd.list_dates(tmp)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["id"], entry["id"])

            # Reload from disk (new process simulation)
            again = fd.list_dates(tmp)
            self.assertEqual(again[0]["title"], "kita fest")
            self.assertEqual(again[0]["lead_days"], [14, 1])

            path = fd.registry_path(tmp)
            self.assertTrue(path.is_file())
            text = path.read_text(encoding="utf-8")
            self.assertIn("kita fest", text)
            self.assertIn("version:", text)

    def test_default_lead_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            entry = fd.add_date(tmp, title="appointment", when="2026-09-01")
            self.assertEqual(entry["lead_days"], [7, 0])

    def test_birth_year_optional(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            entry = fd.add_date(
                tmp,
                title="a member birthday",
                when="2019-03-15",
                recurrence="yearly",
                birth_year=2019,
            )
            self.assertEqual(entry.get("birth_year"), 2019)
            bare = fd.add_date(
                tmp, title="unnamed fest", when="2026-06-01", recurrence="yearly"
            )
            self.assertNotIn("birth_year", bare)


class TestHumanDateRendering(unittest.TestCase):
    """The month name in words is the dd.mm/mm.dd disambiguator."""

    def test_human_date_de_and_en(self) -> None:
        d = date(2026, 9, 12)  # a Saturday
        self.assertEqual(
            fd.human_date(d, locale="de"), "Samstag, 12. September 2026"
        )
        self.assertEqual(
            fd.human_date(d, locale="en"), "Saturday, September 12, 2026"
        )
        self.assertEqual(
            fd.human_date(d, locale="de", with_weekday=False),
            "12. September 2026",
        )

    def test_confirm_text_echoes_month_in_words(self) -> None:
        c = fd.DateCommitment(when=date(2026, 9, 12), title="kita fest")
        de = fd.compose_date_confirm_text(c, locale="de")
        self.assertIn("September", de)
        self.assertIn("Samstag", de)
        self.assertNotIn("12.9", de)
        en = fd.compose_date_confirm_text(c, locale="en")
        self.assertIn("September", en)

    def test_reminder_copy_uses_month_in_words(self) -> None:
        entry = {"title": "kita fest", "date": "2026-09-12", "recurrence": "none"}
        de = fd.compose_reminder_text(
            entry, lead_day=7, occurrence=date(2026, 9, 12), locale="de"
        )
        self.assertIn("September", de)


class TestSwappedDateHint(unittest.TestCase):
    """mm.dd typed as dd.mm gets a helpful swap suggestion, not a crash."""

    def test_month_slot_over_12_suggests_swap_de(self) -> None:
        with self.assertRaises(fd.DateError) as ctx:
            fd.parse_date_token("9.28.", locale="de", today=date(2026, 8, 4))
        msg = str(ctx.exception)
        self.assertIn("28.9.", msg)
        self.assertIn("Tag.Monat", msg)

    def test_month_slot_over_12_suggests_swap_en(self) -> None:
        with self.assertRaises(fd.DateError) as ctx:
            fd.parse_date_token("9.28.2026", locale="en")
        msg = str(ctx.exception)
        self.assertIn("28.9.", msg)
        self.assertIn("day.month", msg)

    def test_impossible_date_refuses_politely(self) -> None:
        with self.assertRaises(fd.DateError):
            fd.parse_date_token("31.2.", locale="de", today=date(2026, 8, 4))
        with self.assertRaises(fd.DateError):
            fd.parse_date_token("2026-02-31")

    def test_leap_day_short_form_rolls_to_valid_year(self) -> None:
        # 2027 is not a leap year; 29.2. rolls forward to 2028.
        self.assertEqual(
            fd.parse_date_token("29.2.", locale="de", today=date(2027, 3, 1)),
            date(2028, 2, 29),
        )

    def test_commitment_with_impossible_date_is_skipped(self) -> None:
        # Conversational capture must not offer (or crash) on a misread.
        parsed = fd.parse_date_commitment(
            "Das Fest ist am 9.28.", locale="de", today=date(2026, 8, 4)
        )
        self.assertIsNone(parsed)


class TestDateParsingAndDue(unittest.TestCase):
    def test_iso_and_de_locale_parsing(self) -> None:
        self.assertEqual(
            fd.parse_date_token("2026-12-24"), date(2026, 12, 24)
        )
        self.assertEqual(
            fd.parse_date_token("24.12.2026", locale="de"), date(2026, 12, 24)
        )
        self.assertEqual(
            fd.parse_date_token(
                "24.12.", locale="de", today=date(2026, 8, 4)
            ),
            date(2026, 12, 24),
        )
        # Day.month. without year after the date has passed → next year
        self.assertEqual(
            fd.parse_date_token(
                "24.12.", locale="de", today=date(2026, 12, 25)
            ),
            date(2027, 12, 24),
        )

    def test_yearly_rollover_next_occurrence(self) -> None:
        entry = {
            "date": "2020-03-15",
            "recurrence": "yearly",
        }
        self.assertEqual(
            fd.next_occurrence(entry, today=date(2026, 8, 4)),
            date(2027, 3, 15),
        )
        self.assertEqual(
            fd.next_occurrence(entry, today=date(2026, 3, 15)),
            date(2026, 3, 15),
        )
        # none recurrence stays on stored date
        once = {"date": "2026-12-24", "recurrence": "none"}
        self.assertEqual(
            fd.next_occurrence(once, today=date(2026, 8, 4)),
            date(2026, 12, 24),
        )

    def test_lead_time_due_computation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fd.add_date(
                tmp,
                title="kita fest",
                when="2026-12-24",
                lead_days=[14, 0],
            )
            fd.add_date(
                tmp,
                title="a member birthday",
                when="2019-03-15",
                recurrence="yearly",
                lead_days=[7],
                birth_year=2019,
            )
            # 14 days before kita fest
            due = fd.due_reminders(tmp, today=date(2026, 12, 10))
            titles = {(d["title"], lead) for d, lead, _occ in due}
            self.assertIn(("kita fest", 14), titles)
            self.assertNotIn(("kita fest", 0), titles)

            # day-of kita fest
            due_day = fd.due_reminders(tmp, today=date(2026, 12, 24))
            titles_day = {(d["title"], lead) for d, lead, _ in due_day}
            self.assertIn(("kita fest", 0), titles_day)

            # yearly: 7 days before next birthday (2027-03-15)
            due_bday = fd.due_reminders(tmp, today=date(2027, 3, 8))
            titles_b = {(d["title"], lead) for d, lead, occ in due_bday}
            self.assertIn(("a member birthday", 7), titles_b)
            occ = next(occ for d, lead, occ in due_bday if d["title"] == "a member birthday")
            self.assertEqual(occ, date(2027, 3, 15))


class TestIdempotentSurfacing(unittest.IsolatedAsyncioTestCase):
    async def test_heartbeat_posts_once_per_done_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("alpha", "beta", "family"):
                Path(tmp, name).mkdir()
            family = Path(tmp) / "family"
            entry = fd.add_date(
                family,
                title="kita fest",
                when="2026-12-24",
                lead_days=[14],
            )
            post = AsyncMock()
            with (
                patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)),
                patch.object(fd, "post_date_reminder", post),
                patch("dates.local_now", return_value=MagicMock(
                    date=lambda: date(2026, 12, 10),
                    hour=10,
                )),
            ):
                first = await fd.run_scheduled_date_reminders(
                    practice_dirs=[family]
                )
                second = await fd.run_scheduled_date_reminders(
                    practice_dirs=[family]
                )

            post.assert_awaited_once()
            self.assertEqual(first, 1)
            self.assertEqual(second, 0)
            # done-map persisted
            key = fd.reminder_done_key(entry["id"], 14, date(2026, 12, 24))
            self.assertIn(key, fd.list_reminders_done(family))


class TestDateRouting(unittest.IsolatedAsyncioTestCase):
    async def test_family_never_surfaces_in_private_and_vice_versa(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("alpha", "beta", "family"):
                Path(tmp, name).mkdir()
            family = Path(tmp) / "family"
            private = Path(tmp) / "alpha"
            fd.add_date(
                family, title="kita fest", when="2026-12-24", lead_days=[14]
            )
            fd.add_date(
                private, title="private appointment", when="2026-12-24", lead_days=[14]
            )

            with patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)):
                self.assertEqual(
                    fd.owning_channel_id_for_practice_dir(family),
                    FAMILY_CHANNEL,
                )
                self.assertEqual(
                    fd.owning_channel_id_for_practice_dir(private),
                    PRIVATE_RIVER,
                )
                self.assertNotEqual(
                    fd.owning_channel_id_for_practice_dir(family),
                    PRIVATE_RIVER,
                )
                self.assertNotEqual(
                    fd.owning_channel_id_for_practice_dir(private),
                    FAMILY_CHANNEL,
                )

            posted_channels: list[int] = []

            async def _capture(channel_id, entry, lead_day, occ, *, locale="en"):
                posted_channels.append(int(channel_id))

            with (
                patch.object(mage, "_MAGE_REGISTRY", _registry(tmp)),
                patch.object(fd, "post_date_reminder", side_effect=_capture),
                patch(
                    "dates.local_now",
                    return_value=MagicMock(date=lambda: date(2026, 12, 10), hour=10),
                ),
            ):
                await fd.run_scheduled_date_reminders(
                    practice_dirs=[family, private]
                )

            self.assertEqual(set(posted_channels), {FAMILY_CHANNEL, PRIVATE_RIVER})
            # family reminder must not land on private river
            self.assertEqual(posted_channels.count(FAMILY_CHANNEL), 1)
            self.assertEqual(posted_channels.count(PRIVATE_RIVER), 1)


class TestDateCommands(unittest.IsolatedAsyncioTestCase):
    async def test_date_capture_and_dates_listing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            message = MagicMock()
            message.channel = MagicMock()
            message.channel.id = PRIVATE_RIVER
            message.author = MagicMock()
            message.reply = AsyncMock()

            frozen = MagicMock(date=lambda: date(2026, 8, 4))
            with (
                patch("mage.get_pd", return_value=tmp),
                patch("dates.locale_for_practice_dir", return_value="de"),
                patch("dates.address_for_capture", return_value="a member"),
                patch("dates.local_now", return_value=frozen),
            ):
                digest = await fd.cmd_date(
                    message, ["24.12.", "kita", "fest"]
                )
                self.assertIn("kita fest", digest.lower())

                listed = fd.list_dates(tmp)
                self.assertEqual(len(listed), 1)
                self.assertEqual(listed[0]["date"], "2026-12-24")
                self.assertEqual(listed[0]["title"], "kita fest")

                digest2 = await fd.cmd_dates(message, [])
                self.assertIn("upcoming", digest2.lower())
                reply_text = " ".join(
                    str(c.args[0]) for c in message.reply.await_args_list if c.args
                ).lower()
                self.assertIn("kita fest", reply_text)

    async def test_date_usage_on_missing_args(self) -> None:
        message = MagicMock()
        message.reply = AsyncMock()
        digest = await fd.cmd_date(message, [])
        self.assertIn("!date", digest)
        self.assertIn("<when>", digest)
        self.assertIn("<what>", digest)


class TestReminderCopy(unittest.TestCase):
    def test_care_language_en_and_de(self) -> None:
        entry = {
            "title": "kita fest",
            "date": "2026-12-24",
            "recurrence": "none",
            "lead_days": [14, 0],
        }
        en = fd.compose_reminder_text(
            entry, lead_day=14, occurrence=date(2026, 12, 24), locale="en"
        )
        self.assertIn("kita fest", en.lower())
        self.assertIn("two weeks", en.lower())
        self.assertNotIn("must", en.lower())
        self.assertNotIn("task", en.lower())

        de = fd.compose_reminder_text(
            entry, lead_day=14, occurrence=date(2026, 12, 24), locale="de"
        )
        self.assertIn("kita fest", de.lower())
        self.assertTrue("wochen" in de.lower() or "14" in de)

    def test_turns_n_when_birth_year_present(self) -> None:
        entry = {
            "title": "a member birthday",
            "date": "2019-03-15",
            "recurrence": "yearly",
            "birth_year": 2019,
            "lead_days": [7],
        }
        text = fd.compose_reminder_text(
            entry, lead_day=7, occurrence=date(2026, 3, 15), locale="en"
        )
        self.assertIn("turns 7", text.lower())


class TestDateConfirmOffer(unittest.TestCase):
    def test_looks_like_date_commitment_de(self) -> None:
        parsed = fd.parse_date_commitment(
            "Am 24.12. ist Kita Fest — bitte erinnern",
            locale="de",
            today=date(2026, 8, 4),
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.when, date(2026, 12, 24))
        self.assertIn("kita", parsed.title.lower())


# 2026-08-06 is a Thursday — the anchor for every relative fixture below.
TODAY = date(2026, 8, 6)


class TestNameFormDates(unittest.TestCase):
    """Dates written the way people write them: month names, not digits."""

    def test_day_first_de(self) -> None:
        for token in ("24. Dezember", "24 Dezember", "24. Dez"):
            with self.subTest(token=token):
                self.assertEqual(
                    fd.parse_date_token(token, locale="de", today=TODAY),
                    date(2026, 12, 24),
                )

    def test_month_first_en(self) -> None:
        for token in ("December 24", "December 24th", "Dec 24"):
            with self.subTest(token=token):
                self.assertEqual(
                    fd.parse_date_token(token, locale="en", today=TODAY),
                    date(2026, 12, 24),
                )

    def test_explicit_year_wins_over_rollover(self) -> None:
        self.assertEqual(
            fd.parse_date_token("24. Dezember 2029", locale="de", today=TODAY),
            date(2029, 12, 24),
        )
        self.assertEqual(
            fd.parse_date_token("December 24, 2029", locale="en", today=TODAY),
            date(2029, 12, 24),
        )

    def test_passed_date_without_year_rolls_forward(self) -> None:
        # Same rule the numeric D.M. form already follows.
        self.assertEqual(
            fd.parse_date_token("3. März", locale="de", today=TODAY),
            date(2027, 3, 3),
        )

    def test_impossible_name_form_refuses(self) -> None:
        with self.assertRaises(fd.DateError):
            fd.parse_date_token("31. Februar", locale="de", today=TODAY)

    def test_every_month_name_parses(self) -> None:
        # Positive control over the whole class, not one literal from it.
        for names in (fd._MONTHS_DE, fd._MONTHS_EN):
            for index, name in enumerate(names, 1):
                with self.subTest(name=name):
                    parsed = fd.parse_date_token(
                        f"1. {name} 2027", locale="de", today=TODAY
                    )
                    self.assertEqual(parsed, date(2027, index, 1))


class TestWeekdayAndRelativeDates(unittest.TestCase):
    def test_bare_weekday_is_next_occurrence(self) -> None:
        self.assertEqual(
            fd.parse_date_token("Samstag", locale="de", today=TODAY),
            date(2026, 8, 8),
        )
        self.assertEqual(
            fd.parse_date_token("Saturday", locale="en", today=TODAY),
            date(2026, 8, 8),
        )

    def test_same_weekday_as_today_means_next_week(self) -> None:
        # Said on a Thursday, "Donnerstag" is the one coming, not today.
        self.assertEqual(
            fd.parse_date_token("Donnerstag", locale="de", today=TODAY),
            date(2026, 8, 13),
        )

    def test_weekday_with_leading_qualifier(self) -> None:
        for token in ("nächsten Samstag", "kommenden Samstag", "next Saturday"):
            with self.subTest(token=token):
                self.assertEqual(
                    fd.parse_date_token(token, locale="de", today=TODAY),
                    date(2026, 8, 8),
                )

    def test_every_weekday_name_parses(self) -> None:
        for names in (fd._WEEKDAYS_DE, fd._WEEKDAYS_EN):
            for index, name in enumerate(names):
                with self.subTest(name=name):
                    parsed = fd.parse_date_token(name, locale="de", today=TODAY)
                    self.assertEqual(parsed.weekday(), index)
                    self.assertGreater(parsed, TODAY)

    def test_relative_words(self) -> None:
        cases = {
            "heute": date(2026, 8, 6),
            "today": date(2026, 8, 6),
            "morgen": date(2026, 8, 7),
            "tomorrow": date(2026, 8, 7),
            "übermorgen": date(2026, 8, 8),
            "nächste Woche": date(2026, 8, 13),
            "next week": date(2026, 8, 13),
            "in 3 Tagen": date(2026, 8, 9),
            "in 3 days": date(2026, 8, 9),
        }
        for token, expected in cases.items():
            with self.subTest(token=token):
                self.assertEqual(
                    fd.parse_date_token(token, locale="de", today=TODAY), expected
                )

    def test_unparseable_token_still_refuses_with_hint(self) -> None:
        with self.assertRaises(fd.DateError) as ctx:
            fd.parse_date_token("irgendwann", locale="de", today=TODAY)
        self.assertIn("24.12.", str(ctx.exception))


class TestConversationalTiers(unittest.TestCase):
    """Specific dates offer on their own; vague ones need a commitment cue.

    A river is full of "morgen" and "Samstag". Offering a Keep on every one
    of them is an interruption, so the loose forms only fire when the member
    also named something to keep.
    """

    def test_month_name_fires_without_a_cue(self) -> None:
        parsed = fd.parse_date_commitment(
            "Wir fahren am 24. Dezember nach Hamburg",
            locale="de",
            today=TODAY,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.when, date(2026, 12, 24))
        self.assertNotIn("dezember", parsed.title.lower())
        self.assertIn("hamburg", parsed.title.lower())

    def test_bare_weekday_does_not_fire(self) -> None:
        self.assertIsNone(
            fd.parse_date_commitment(
                "Am Samstag war es richtig heiß hier",
                locale="de",
                today=TODAY,
            )
        )

    def test_bare_relative_does_not_fire(self) -> None:
        self.assertIsNone(
            fd.parse_date_commitment(
                "Ich gehe morgen noch schnell einkaufen",
                locale="de",
                today=TODAY,
            )
        )

    def test_weekday_with_commitment_cue_fires(self) -> None:
        parsed = fd.parse_date_commitment(
            "Maëls Geburtstagsfeier ist am Samstag",
            locale="de",
            today=TODAY,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.when, date(2026, 8, 8))
        self.assertEqual(parsed.recurrence, "yearly")

    def test_relative_with_reminder_cue_fires(self) -> None:
        parsed = fd.parse_date_commitment(
            "Zahnarzttermin morgen — bitte erinnern",
            locale="de",
            today=TODAY,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.when, date(2026, 8, 7))

    def test_english_cue_path(self) -> None:
        parsed = fd.parse_date_commitment(
            "remind me about the parent evening on Saturday",
            locale="en",
            today=TODAY,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.when, date(2026, 8, 8))

    def test_numeric_form_still_wins_when_both_present(self) -> None:
        # Tier 1 anywhere in the text beats a tier-2 phrase earlier in it.
        parsed = fd.parse_date_commitment(
            "Samstag passt nicht, das Fest ist am 24.12.",
            locale="de",
            today=TODAY,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.when, date(2026, 12, 24))


class TestTypedCommandMultiWordWhen(unittest.IsolatedAsyncioTestCase):
    async def test_multiword_when_keeps_the_rest_as_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = _registry(tmp)
            message = MagicMock()
            message.reply = AsyncMock()
            message.author = MagicMock()
            with patch.object(mage, "_REGISTRY", reg, create=True), patch.object(
                mage, "get_pd", return_value=f"{tmp}/alpha"
            ), patch.object(fd, "locale_for_practice_dir", return_value="de"):
                await fd.cmd_date(message, ["24.", "Dezember", "Kita", "Fest"])

            kept = fd.list_dates(f"{tmp}/alpha")
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["date"][5:], "12-24")
            self.assertEqual(kept[0]["title"], "Kita Fest")

    async def test_weekday_when_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = _registry(tmp)
            message = MagicMock()
            message.reply = AsyncMock()
            message.author = MagicMock()
            with patch.object(mage, "_REGISTRY", reg, create=True), patch.object(
                mage, "get_pd", return_value=f"{tmp}/alpha"
            ), patch.object(fd, "locale_for_practice_dir", return_value="de"):
                await fd.cmd_date(message, ["Samstag", "Kita", "Fest"])

            kept = fd.list_dates(f"{tmp}/alpha")
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["title"], "Kita Fest")
            self.assertEqual(date.fromisoformat(kept[0]["date"]).weekday(), 5)

    async def test_birthday_year_detected_in_name_form(self) -> None:
        # `15. März 2019` must buy the same yearly + age as `15.03.2019`.
        with tempfile.TemporaryDirectory() as tmp:
            reg = _registry(tmp)
            message = MagicMock()
            message.reply = AsyncMock()
            message.author = MagicMock()
            with patch.object(mage, "_REGISTRY", reg, create=True), patch.object(
                mage, "get_pd", return_value=f"{tmp}/alpha"
            ), patch.object(fd, "locale_for_practice_dir", return_value="de"):
                await fd.cmd_date(message, ["15.", "März", "2019", "Geburtstag"])

            kept = fd.list_dates(f"{tmp}/alpha")
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["recurrence"], "yearly")
            self.assertEqual(kept[0]["birth_year"], 2019)

    async def test_weekday_birthday_has_no_birth_year(self) -> None:
        # No year written means no age claim — "turns N" must not be invented.
        with tempfile.TemporaryDirectory() as tmp:
            reg = _registry(tmp)
            message = MagicMock()
            message.reply = AsyncMock()
            message.author = MagicMock()
            with patch.object(mage, "_REGISTRY", reg, create=True), patch.object(
                mage, "get_pd", return_value=f"{tmp}/alpha"
            ), patch.object(fd, "locale_for_practice_dir", return_value="de"):
                await fd.cmd_date(message, ["Samstag", "Geburtstag"])

            kept = fd.list_dates(f"{tmp}/alpha")
            self.assertEqual(kept[0]["recurrence"], "yearly")
            self.assertIsNone(kept[0].get("birth_year"))

    async def test_single_token_when_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = _registry(tmp)
            message = MagicMock()
            message.reply = AsyncMock()
            message.author = MagicMock()
            with patch.object(mage, "_REGISTRY", reg, create=True), patch.object(
                mage, "get_pd", return_value=f"{tmp}/alpha"
            ), patch.object(fd, "locale_for_practice_dir", return_value="de"):
                await fd.cmd_date(message, ["2026-12-24", "Kita", "Fest"])

            kept = fd.list_dates(f"{tmp}/alpha")
            self.assertEqual(kept[0]["date"], "2026-12-24")
            self.assertEqual(kept[0]["title"], "Kita Fest")


if __name__ == "__main__":
    unittest.main()
