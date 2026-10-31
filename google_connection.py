"""One Google sign-in per person, held by the house.

A person approves once in the browser. The house keeps the refresh secret in its
own file (0600, never read by a card, never posted to a channel) and a second
file that names the person and their account and holds no secret. Every room that
is theirs uses the same sign-in; whether a room may use it is `room_connections`.

The network is injected (`Http`) so every path runs on a fixture. A pending
sign-in is a record in the house directory, so whichever process receives the
browser's return can finish it, whichever process started it. See
docs/design/channel-connections.md.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"

BASE_SCOPES = ("openid", "email")
SERVICE_SCOPES: dict[str, tuple[str, ...]] = {
    "calendar": (
        "https://www.googleapis.com/auth/calendar.events.readonly",
        "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    ),
}

PENDING_TTL = 10 * 60
ACCOUNT_NAME = "google-account.json"
TOKEN_NAME = "google-token.json"
PENDING_NAME = "google-pending.json"
_ACCOUNT_KEYS = frozenset({"person", "account", "services"})
_TOKEN_KEYS = frozenset({"person", "refresh_token", "access_token", "expires_at"})
_EARLY = 60  # refresh a minute before the token lapses


class SigninError(Exception):
    """Carries words a person can read. Never the code, the secret, or Google's body."""


class NeedsSignin(Exception):
    """The stored sign-in no longer works. The person is asked once, in plain words."""


class Http(Protocol):
    def post_form(self, url: str, data: dict) -> dict: ...


class UrlHttp:
    """The real network. A non-2xx answer raises with the status only."""

    def post_form(self, url: str, data: dict) -> dict:
        body = urllib.parse.urlencode(data).encode()
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed https hosts
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except Exception:
                payload = {}
            return {"error": str(payload.get("error") or f"http_{exc.code}")}


@dataclass(frozen=True)
class Client:
    client_id: str
    client_secret: str
    redirect_uri: str


def client() -> Client | None:
    """The house's registered app. None until the operator has put it on the machine."""
    cid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    redirect = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
    # No default address: it is this house's own, and lives in its .env, not in the source.
    if not cid or not secret or not redirect:
        return None
    return Client(cid, secret, redirect)


def configured() -> bool:
    return client() is not None


def _state_dir(root: Path) -> Path:
    return root / "state"


def _write_private(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def account_path(root: Path) -> Path:
    return _state_dir(root) / ACCOUNT_NAME


def token_path(root: Path) -> Path:
    return _state_dir(root) / TOKEN_NAME


def pending_path(house: Path) -> Path:
    return house / PENDING_NAME


def signed_in(person: str, root: Path | None) -> dict | None:
    """{account, services} for this person, or None. A file with any other field is refused."""
    if not person or root is None:
        return None
    data = _read_json(account_path(root))
    if not data or set(data) != _ACCOUNT_KEYS or data.get("person") != person:
        return None
    services = data.get("services")
    if not isinstance(services, list) or not all(isinstance(s, str) for s in services):
        return None
    account = str(data.get("account") or "").strip()
    return {"account": account, "services": sorted(set(services) & set(SERVICE_SCOPES))} if account else None


def scopes_for(services: list[str] | tuple[str, ...]) -> list[str]:
    wanted = list(BASE_SCOPES)
    for name in services:
        wanted.extend(SERVICE_SCOPES[name])
    return wanted


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def begin(
    *,
    person: str,
    root: Path,
    house: Path,
    channel_id,
    services: list[str],
    now: float | None = None,
) -> str:
    """The one link a person opens. The record that lets us finish it stays here."""
    app = client()
    if app is None:
        raise SigninError("Google is not set up on this house yet.")
    person = (person or "").strip()
    chosen = [name for name in services if name in SERVICE_SCOPES]
    if not person or not chosen:
        raise SigninError("A sign-in needs a person and a service.")
    now = time.time() if now is None else now
    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce()
    path = pending_path(house)
    pending = _read_json(path) or {}
    pending = {k: v for k, v in pending.items() if isinstance(v, dict) and v.get("expires", 0) > now}
    pending[state] = {
        "person": person,
        "root": str(root),
        "channel": str(channel_id) if channel_id is not None else "",
        "services": chosen,
        "verifier": verifier,
        "expires": now + PENDING_TTL,
    }
    _write_private(path, pending)
    query = {
        "client_id": app.client_id,
        "redirect_uri": app.redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes_for(chosen)),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(query)}"


def _email_from(id_token: str) -> str:
    """The account named in the token Google just handed us over TLS. Not a login check."""
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return str(json.loads(base64.urlsafe_b64decode(payload)).get("email") or "").strip()
    except Exception:
        return ""


@dataclass(frozen=True)
class Done:
    person: str
    account: str
    services: list[str]
    channel: str


def complete(house: Path, state: str, code: str, http: Http | None = None, now: float | None = None) -> Done:
    """Finish a sign-in. Single use: the pending record is gone before the exchange."""
    app = client()
    if app is None:
        raise SigninError("Google is not set up on this house yet.")
    http = http or UrlHttp()
    now = time.time() if now is None else now
    path = pending_path(house)
    pending = _read_json(path) or {}
    record = pending.pop(state, None) if state else None
    _write_private(path, pending)
    if not isinstance(record, dict) or record.get("expires", 0) <= now:
        raise SigninError("That sign-in link is no longer good. Start again from the chat.")
    if not code:
        raise SigninError("Google did not approve it.")
    answer = http.post_form(
        TOKEN_URL,
        {
            "client_id": app.client_id,
            "client_secret": app.client_secret,
            "code": code,
            "code_verifier": record["verifier"],
            "grant_type": "authorization_code",
            "redirect_uri": app.redirect_uri,
        },
    )
    refresh = str(answer.get("refresh_token") or "")
    access = str(answer.get("access_token") or "")
    if answer.get("error") or not refresh or not access:
        raise SigninError("Google did not give the house a sign-in. Start again from the chat.")
    granted = set(str(answer.get("scope") or "").split())
    services = [name for name in record["services"] if set(SERVICE_SCOPES[name]) <= granted]
    if not services:
        raise SigninError("Google was not allowed to share what was asked. Start again and approve all of it.")
    account = _email_from(str(answer.get("id_token") or "")) or "your Google account"
    root = Path(record["root"])
    person = record["person"]
    _write_private(
        token_path(root),
        {
            "person": person,
            "refresh_token": refresh,
            "access_token": access,
            "expires_at": now + int(answer.get("expires_in") or 0),
        },
    )
    _write_private(account_path(root), {"person": person, "account": account, "services": sorted(services)})
    return Done(person, account, sorted(services), str(record.get("channel") or ""))


def access_token(person: str, root: Path | None, http: Http | None = None, now: float | None = None) -> str:
    """A working access token for this person, refreshed when due. Raises NeedsSignin."""
    if not person or root is None or signed_in(person, root) is None:
        raise NeedsSignin()
    stored = _read_json(token_path(root))
    if not stored or set(stored) != _TOKEN_KEYS or stored.get("person") != person:
        raise NeedsSignin()
    now = time.time() if now is None else now
    if float(stored.get("expires_at") or 0) - _EARLY > now and stored.get("access_token"):
        return str(stored["access_token"])
    app = client()
    if app is None:
        raise NeedsSignin()
    answer = (http or UrlHttp()).post_form(
        TOKEN_URL,
        {
            "client_id": app.client_id,
            "client_secret": app.client_secret,
            "refresh_token": stored["refresh_token"],
            "grant_type": "refresh_token",
        },
    )
    fresh = str(answer.get("access_token") or "")
    if answer.get("error") or not fresh:
        if answer.get("error") == "invalid_grant":
            raise NeedsSignin()
        raise SigninError("Google did not answer. Try again in a moment.")
    stored["access_token"] = fresh
    stored["expires_at"] = now + int(answer.get("expires_in") or 0)
    _write_private(token_path(root), stored)
    return fresh


def disconnect(person: str, root: Path | None, http: Http | None = None) -> bool:
    """Forget the sign-in here and ask Google to drop it. True when something was removed."""
    if not person or root is None or signed_in(person, root) is None:
        return False
    stored = _read_json(token_path(root)) or {}
    for path in (token_path(root), account_path(root)):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    token = str(stored.get("refresh_token") or "")
    if token:
        try:
            (http or UrlHttp()).post_form(REVOKE_URL, {"token": token})
        except Exception:
            pass  # the local sign-in is gone either way
    return True
