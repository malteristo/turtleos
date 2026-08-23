"""Transport-agnostic message value objects.

The seam between a chat platform and the runtime. A transport adapter builds an
``IncomingMessage`` from whatever its platform delivered; the runtime answers
with an ``OutgoingMessage`` and never learns which platform it was talking to.

Shape decided in the craft-turtle architecture eddy of 2026-08-11
(``learning turtleos system architecture basics``), stress-tested against three
transports the Mage named — Discord today, a home speaker, and Matrix/Element
later. Two of those exposed fields Discord alone would never have suggested:

* **Voice** showed which fields are *optional*. A spoken turn has no
  attachments, no reply chain and no mentions, so nothing downstream may assume
  Discord's richness is present.
* **Matrix** showed that identity must be *resolved before* the runtime sees it.
  Matrix is federated, so one person can arrive as ``@name:server-a`` or
  ``@name:server-b``; elsewhere as a Discord snowflake or a voice profile. A
  runtime that maps those itself has to know every platform's ID format — which
  is the coupling, restated.

The invariant that keeps the door open, in the Mage's words *"don't close the
door to switching in the future"*: **the runtime never imports a transport
library.** ``runtime/__init__.py`` has claimed this package is "intentionally
independent of Discord" since it was created and nothing checked;
``tests/test_transport_boundary.py`` now does.

Nothing here decides behaviour. Value objects only — so a transport can be
written and tested without a runtime, and vice versa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# `voice_live` is reserved, not implemented: the home-speaker case is deferred
# until the hardware exists, on the Mage's call, and is named here so the
# interface does not have to be reopened when it arrives.
InputModality = Literal["text", "voice_message", "voice_live"]

MODALITIES: tuple[str, ...] = ("text", "voice_message", "voice_live")

# What the runtime is allowed to ask about a surface. Deliberately *not*
# "which transport is this" — the runtime asking that name is how transport
# knowledge leaks back in. A transport declares what it can do; the runtime
# reads the declaration.
Affordance = Literal["buttons", "voice_out", "attachments", "threads", "edit"]


@dataclass(frozen=True)
class Attachment:
    """A file that came with a message, already fetched by the transport."""

    filename: str
    content_type: str = ""
    text: str = ""
    url: str = ""
    size_bytes: int = 0


@dataclass(frozen=True)
class Action:
    """An affordance offered alongside a reply — a button, where there are buttons.

    The label is the runtime's, because the runtime is what knows whether this
    reply is a transcript or an article. Getting that wrong is a live defect:
    a YouTube link sent with a sentence around it currently offers "Read
    article" instead of "Fetch transcript". A transport with no ``buttons``
    affordance renders these as text or drops them; it does not invent labels.
    """

    key: str
    label: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IncomingMessage:
    """One practitioner turn, normalized.

    ``practitioner_id`` is resolved by the transport and trusted by the runtime.
    ``transport`` is provenance for the audit trail, not a branch condition —
    when behaviour needs to vary, read ``affordances``.
    """

    text: str
    practitioner_id: str
    channel_id: str
    transport: str = "discord"
    thread_id: str | None = None
    message_id: str | None = None
    input_modality: InputModality = "text"
    attachments: tuple[Attachment, ...] = ()
    reply_to_id: str | None = None
    urls: tuple[str, ...] = ()
    is_from_bot: bool = False
    # Where a conversation held somewhere without a thread should be written so
    # the practitioner can pick up a phone and read it. Resolved by the
    # transport before handoff — the home speaker has no eddy selected when the
    # wake word fires, and resolving that is a transport problem.
    mirror_eddy_id: str | None = None
    affordances: frozenset[str] = frozenset({"buttons", "attachments", "threads"})
    raw: Any = None

    def __post_init__(self) -> None:
        if self.input_modality not in MODALITIES:
            raise ValueError(
                f"unknown input_modality {self.input_modality!r} — one of {MODALITIES}"
            )
        if not self.practitioner_id:
            raise ValueError(
                "practitioner_id is required: identity is resolved by the "
                "transport, never inferred inside the runtime"
            )
        if not self.channel_id:
            raise ValueError("channel_id is required")

    @property
    def is_voice(self) -> bool:
        return self.input_modality in ("voice_message", "voice_live")

    @property
    def conversation_id(self) -> str:
        """Where this turn belongs — the thread if there is one, else the channel."""
        return self.thread_id or self.channel_id

    def can(self, affordance: str) -> bool:
        return affordance in self.affordances


@dataclass(frozen=True)
class OutgoingMessage:
    """The runtime's answer, before any platform has rendered it.

    ``speak`` and ``mirror_to_id`` carry the voice matrix the Mage described:
    a spoken turn answers aloud *and* writes the text where it can be read
    later; a Discord voice message answers in text and offers to read itself
    aloud; text answers in text. One reply object, three renderings, no
    transport branch in the runtime.
    """

    text: str
    actions: tuple[Action, ...] = ()
    speak: bool = False
    mirror_to_id: str | None = None
    attachments: tuple[Attachment, ...] = ()
    reply_to_id: str | None = None

    @classmethod
    def answering(
        cls, incoming: IncomingMessage, text: str, *, actions: tuple[Action, ...] = ()
    ) -> "OutgoingMessage":
        """Build the reply whose output mode matches how the turn arrived.

        The rule the eddy settled: voice in, voice out plus a readable mirror;
        a recorded voice message answers in text and offers to be read aloud;
        text answers in text.
        """
        if incoming.input_modality == "voice_live":
            return cls(
                text=text,
                actions=actions,
                speak=True,
                mirror_to_id=incoming.mirror_eddy_id or incoming.conversation_id,
                reply_to_id=incoming.message_id,
            )
        if incoming.input_modality == "voice_message":
            read_aloud = Action(key="read_aloud", label="Read aloud")
            offered = actions if any(a.key == "read_aloud" for a in actions) else (
                actions + (read_aloud,)
            )
            return cls(text=text, actions=offered, reply_to_id=incoming.message_id)
        return cls(text=text, actions=actions, reply_to_id=incoming.message_id)

    def renderable_actions(self, incoming: IncomingMessage) -> tuple[Action, ...]:
        """Actions this surface can actually present.

        A transport without buttons gets none — and the caller is expected to
        fold them into prose rather than drop the capability silently. Offering
        a button a surface cannot post is the craft-turtle act-offer defect:
        six offers queued, none ever shown.
        """
        if incoming.can("buttons"):
            return self.actions
        return ()
