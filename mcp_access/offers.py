"""Connection offers: the owner's press opens a short pickup window.

The host operator can offer a connection; only the source owner can press it,
in their own river. The press makes the offer ready; the grant and its
credential do not exist until a pickup from the owner's own tailnet identity
inside that window, and the credential goes to that client only — it is never
shown in a channel. Offers live in the owner's own root, beside the audit.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.atomic_io import atomic_write_text, file_lock
from mcp_access.grants import DEFAULT_TTL_DAYS, Grant, GrantStore
from mcp_access.operations import snapshot_for

OFFERS_REL = Path("state") / "mcp_offers.json"
OFFER_TTL_DAYS = 7
PENDING = "pending"
READY = "ready"
ACCEPTED = "accepted"
PICKUP_MINUTES = 15


class OfferError(Exception):
    pass


@dataclass
class Offer:
    id: str
    owner: str
    principal: str
    sources: list[str]
    profile: str
    url: str
    created: str
    expires: str
    status: str = PENDING
    channel_id: int | None = None
    message_id: int | None = None
    grant: str | None = None
    ready_until: str | None = None
    grant_expires: str | None = None
    announced: bool = False

    def pickup_open(self, now: datetime | None = None) -> bool:
        return (
            self.status == READY
            and self.ready_until is not None
            and (now or datetime.now(timezone.utc)) < datetime.fromisoformat(self.ready_until)
        )

    def expired(self, now: datetime | None = None) -> bool:
        return (now or datetime.now(timezone.utc)) >= datetime.fromisoformat(self.expires)


def _path(root: Path) -> Path:
    return Path(root) / OFFERS_REL


def _read(root: Path) -> dict[str, Offer]:
    p = _path(root)
    if not p.is_file():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8") or "{}")
    return {k: Offer(**v) for k, v in raw.items()}


def _write(root: Path, offers: dict[str, Offer]) -> None:
    atomic_write_text(_path(root), json.dumps({k: asdict(v) for k, v in offers.items()}, indent=2))


def all_offers(root: Path) -> list[Offer]:
    return list(_read(root).values())


def create(root: Path, *, owner: str, principal: str, sources: list[str], profile: str, url: str) -> Offer:
    if not Path(root).is_dir():
        raise OfferError(f"owner root missing: {root}")
    now = datetime.now(timezone.utc)
    offer = Offer(
        id="o_" + secrets.token_hex(6),
        owner=owner,
        principal=principal,
        sources=list(sources),
        profile=profile,
        url=url,
        created=now.isoformat(),
        expires=(now + timedelta(days=OFFER_TTL_DAYS)).isoformat(),
    )
    with file_lock(_path(root)):
        offers = _read(root)
        offers[offer.id] = offer
        _write(root, offers)
    return offer


def to_post(root: Path) -> list[Offer]:
    return [o for o in _read(root).values() if o.status == PENDING and o.message_id is None and not o.expired()]


def posted_pending(root: Path) -> list[Offer]:
    return [o for o in _read(root).values() if o.status in (PENDING, READY) and o.message_id is not None]


def to_announce(root: Path) -> list[Offer]:
    return [o for o in _read(root).values() if o.status == ACCEPTED and not o.announced and o.message_id is not None]


def mark_announced(root: Path, offer_id: str) -> None:
    with file_lock(_path(root)):
        offers = _read(root)
        if offer_id in offers:
            offers[offer_id].announced = True
            _write(root, offers)


def mark_ready(root: Path, offer_id: str) -> Offer:
    """The owner's press. Opens (or reopens) the pickup window; creates nothing."""
    with file_lock(_path(root)):
        offers = _read(root)
        offer = offers.get(offer_id)
        if offer is None:
            raise OfferError("This offer no longer exists.")
        if offer.status not in (PENDING, READY):
            raise OfferError("This connection was already made. Ask for a new one if you need it again.")
        if offer.expired():
            raise OfferError("This offer expired. Ask for a new one.")
        offer.status = READY
        offer.ready_until = (datetime.now(timezone.utc) + timedelta(minutes=PICKUP_MINUTES)).isoformat()
        _write(root, offers)
    return offer


def pickup(root: Path, store: GrantStore) -> tuple[Offer, Grant, str]:
    """Create the grant for the offer whose window is open. The credential is returned once."""
    with file_lock(_path(root)):
        offers = _read(root)
        open_ = sorted((o for o in offers.values() if o.pickup_open() and not o.expired()),
                       key=lambda o: o.ready_until or "", reverse=True)
        if not open_:
            raise OfferError("nothing to pick up")
        offer = open_[0]
        grant, token = store.create(
            principal=offer.principal,
            owner=offer.owner,
            sources=offer.sources,
            profile=offer.profile,
            ttl_days=DEFAULT_TTL_DAYS,
        )
        offer.status = ACCEPTED
        offer.grant = grant.id
        offer.grant_expires = grant.expires
        _write(root, offers)
    return offer, grant, token


def mark_posted(root: Path, offer_id: str, *, channel_id: int, message_id: int) -> None:
    with file_lock(_path(root)):
        offers = _read(root)
        if offer_id in offers:
            offers[offer_id].channel_id = int(channel_id)
            offers[offer_id].message_id = int(message_id)
            _write(root, offers)


def server_entry(url: str, token: str) -> dict:
    return {"url": url, "headers": {"Authorization": f"Bearer {token}"}}


def base_url(url: str) -> str:
    return url[: -len("/mcp")] if url.endswith("/mcp") else url


def describe(offer: Offer) -> list[str]:
    reach = ", ".join(offer.sources) or "nothing"
    ops = snapshot_for(offer.profile)
    can = "read and search" if "search" in ops else "report on itself"
    return [
        f"**For:** {offer.principal}",
        f"**Reaches:** {reach} — it can {can}, and cannot write.",
        f"**Lasts:** {DEFAULT_TTL_DAYS} days from when you connect.",
    ]
