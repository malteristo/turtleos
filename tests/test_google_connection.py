"""One Google sign-in per person: begin, finish, refresh, forget. No network."""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

sys.modules.setdefault("discord", MagicMock())
sys.modules.setdefault("discord.ext", MagicMock())
sys.modules.setdefault("discord.ui", MagicMock())

import google_connection as gc

CAL = list(gc.SERVICE_SCOPES["calendar"])
REFRESH = "PLANTED_REFRESH_SECRET"
ACCESS = "PLANTED_ACCESS_SECRET"
CODE = "PLANTED_AUTH_CODE"


def _id_token(email: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"email": email}).encode()).rstrip(b"=").decode()
    return f"x.{body}.y"


class FakeHttp:
    def __init__(self, answers: list[dict]) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, dict]] = []

    def post_form(self, url: str, data: dict) -> dict:
        self.calls.append((url, dict(data)))
        return self.answers.pop(0) if self.answers else {}


def granted(scopes=None, **extra) -> dict:
    return {
        "refresh_token": REFRESH,
        "access_token": ACCESS,
        "expires_in": 3600,
        "scope": " ".join(scopes if scopes is not None else ["openid", "email", *CAL]),
        "id_token": _id_token("ada@example.com"),
        **extra,
    }


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.house = self.base / "house"
        self.house.mkdir()
        self.root = self.base / "ada"
        self.root.mkdir()
        env = patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "csecret", "GOOGLE_REDIRECT_URI": "https://house.example/connect/google/callback"})
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def begin(self, now=1000.0, services=("calendar",)) -> tuple[str, str]:
        url = gc.begin(person="ada", root=self.root, house=self.house, channel_id=7, services=list(services), now=now)
        return url, parse_qs(urlparse(url).query)["state"][0]

    def signed_in(self) -> None:
        _url, state = self.begin()
        gc.complete(self.house, state, CODE, FakeHttp([granted()]), now=1001.0)


class BeginTests(Base):
    def test_the_link_asks_for_what_was_picked_and_proves_itself(self) -> None:
        url, state = self.begin()
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["client_id"], ["cid"])
        self.assertEqual(query["redirect_uri"], ["https://house.example/connect/google/callback"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["access_type"], ["offline"])
        asked = set(query["scope"][0].split())
        self.assertEqual(asked, {"openid", "email", *CAL})
        self.assertNotIn("csecret", url)
        self.assertGreater(len(state), 30)

    def test_it_refuses_without_the_houses_app(self) -> None:
        with patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}):
            self.assertFalse(gc.configured())
            with self.assertRaises(gc.SigninError):
                self.begin()
        self.assertTrue(gc.configured(), "positive control")
        with patch.dict(os.environ, {"GOOGLE_REDIRECT_URI": ""}):
            self.assertFalse(gc.configured(), "no registered return address, no sign-in")

    def test_an_unknown_service_is_not_asked_for(self) -> None:
        with self.assertRaises(gc.SigninError):
            self.begin(services=("mail",))

    def test_the_pending_record_is_private_and_old_ones_go(self) -> None:
        self.begin(now=1000.0)
        path = gc.pending_path(self.house)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.begin(now=1000.0 + gc.PENDING_TTL + 5)
        self.assertEqual(len(json.loads(path.read_text())), 1)


class CompleteTests(Base):
    def test_a_good_return_leaves_a_secret_file_and_a_plain_one(self) -> None:
        _url, state = self.begin()
        http = FakeHttp([granted()])
        done = gc.complete(self.house, state, CODE, http, now=1001.0)
        self.assertEqual((done.person, done.account, done.services, done.channel), ("ada", "ada@example.com", ["calendar"], "7"))
        self.assertEqual(http.calls[0][1]["code"], CODE)
        self.assertIn("code_verifier", http.calls[0][1])
        token = json.loads(gc.token_path(self.root).read_text())
        self.assertEqual(token["refresh_token"], REFRESH)
        self.assertEqual(gc.token_path(self.root).stat().st_mode & 0o777, 0o600)
        plain = gc.account_path(self.root).read_text()
        for secret in (REFRESH, ACCESS, CODE, "csecret"):
            self.assertNotIn(secret, plain, "the file a card reads holds no secret")
        self.assertEqual(gc.signed_in("ada", self.root), {"account": "ada@example.com", "services": ["calendar"]})

    def test_a_sign_in_is_single_use(self) -> None:
        _url, state = self.begin()
        gc.complete(self.house, state, CODE, FakeHttp([granted()]), now=1001.0)
        with self.assertRaises(gc.SigninError):
            gc.complete(self.house, state, CODE, FakeHttp([granted()]), now=1002.0)

    def test_a_late_or_unknown_return_is_refused_and_leaves_nothing(self) -> None:
        _url, state = self.begin(now=1000.0)
        for bad, when in ((state, 1000.0 + gc.PENDING_TTL + 1), ("not-a-state", 1001.0), ("", 1001.0)):
            with self.assertRaises(gc.SigninError):
                gc.complete(self.house, bad, CODE, FakeHttp([granted()]), now=when)
        self.assertIsNone(gc.signed_in("ada", self.root))
        self.assertFalse(gc.token_path(self.root).exists())

    def test_a_refusal_in_the_browser_or_a_narrower_grant_is_not_a_sign_in(self) -> None:
        _url, state = self.begin()
        with self.assertRaises(gc.SigninError):
            gc.complete(self.house, state, "", FakeHttp([]), now=1001.0)  # the person said no: no code
        _url, state = self.begin()
        with self.assertRaises(gc.SigninError):
            gc.complete(self.house, state, CODE, FakeHttp([granted(scopes=["openid", "email"])]), now=1001.0)
        _url, state = self.begin()
        with self.assertRaises(gc.SigninError):
            gc.complete(self.house, state, CODE, FakeHttp([{"error": "invalid_grant"}]), now=1001.0)
        self.assertIsNone(gc.signed_in("ada", self.root))

    def test_the_words_never_carry_google_or_the_code(self) -> None:
        _url, state = self.begin()
        try:
            gc.complete(self.house, state, CODE, FakeHttp([{"error": "PLANTED_GOOGLE_BODY"}]), now=1001.0)
        except gc.SigninError as exc:
            for text in ("PLANTED_GOOGLE_BODY", CODE, REFRESH):
                self.assertNotIn(text, str(exc))
        else:
            self.fail("expected a refusal")


class AccessTests(Base):
    def test_a_fresh_token_is_used_without_asking_google(self) -> None:
        self.signed_in()
        http = FakeHttp([])
        self.assertEqual(gc.access_token("ada", self.root, http, now=1100.0), ACCESS)
        self.assertEqual(http.calls, [])

    def test_a_stale_token_is_refreshed_and_kept(self) -> None:
        self.signed_in()
        http = FakeHttp([{"access_token": "NEW", "expires_in": 3600}])
        self.assertEqual(gc.access_token("ada", self.root, http, now=1001.0 + 4000), "NEW")
        self.assertEqual(http.calls[0][1]["refresh_token"], REFRESH)
        self.assertEqual(gc.access_token("ada", self.root, FakeHttp([]), now=1001.0 + 4100), "NEW")

    def test_a_revoked_sign_in_asks_the_person_again(self) -> None:
        self.signed_in()
        with self.assertRaises(gc.NeedsSignin):
            gc.access_token("ada", self.root, FakeHttp([{"error": "invalid_grant"}]), now=1001.0 + 4000)
        with self.assertRaises(gc.SigninError):  # not the same as revoked: Google just did not answer
            gc.access_token("ada", self.root, FakeHttp([{"error": "temporarily_unavailable"}]), now=1001.0 + 4000)

    def test_another_person_and_an_odd_file_have_no_sign_in(self) -> None:
        self.signed_in()
        with self.assertRaises(gc.NeedsSignin):
            gc.access_token("bea", self.root, FakeHttp([]), now=1100.0)
        data = json.loads(gc.token_path(self.root).read_text())
        data["extra"] = "x"
        gc.token_path(self.root).write_text(json.dumps(data))
        with self.assertRaises(gc.NeedsSignin):
            gc.access_token("ada", self.root, FakeHttp([]), now=1100.0)

    def test_an_account_file_with_a_secret_field_is_refused(self) -> None:
        self.signed_in()
        data = json.loads(gc.account_path(self.root).read_text())
        data["refresh_token"] = REFRESH
        gc.account_path(self.root).write_text(json.dumps(data))
        self.assertIsNone(gc.signed_in("ada", self.root))


class DisconnectTests(Base):
    def test_forgetting_removes_both_files_and_asks_google_to_drop_it(self) -> None:
        self.signed_in()
        http = FakeHttp([{}])
        self.assertTrue(gc.disconnect("ada", self.root, http))
        self.assertFalse(gc.token_path(self.root).exists())
        self.assertIsNone(gc.signed_in("ada", self.root))
        self.assertEqual(http.calls[0], (gc.REVOKE_URL, {"token": REFRESH}))
        self.assertFalse(gc.disconnect("ada", self.root, FakeHttp([])), "nothing left to remove")


if __name__ == "__main__":
    unittest.main()
