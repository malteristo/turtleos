"""Every offer the runtime can make: its kind, its label, and whether it is counted.

Slice 3 of the transport abstraction. Slice 2 moved *one* offer's judgement out of
a Discord UI module (`runtime/link_offers.py` decides what a link is and what the
button may be called). This does the same for the rest, because the labels were
spread across six modules with no list of them anywhere — which is how the
codebase ended up unable to answer two questions it needed:

* **What offers exist?** `offer_ledger.KINDS` was hand-maintained and its own
  comment records getting this wrong once already: `turtle_save` and
  `turtle_checkpoint` were missing while sitting *ahead* of `save` and
  `checkpoint` in the turn handler, so the two kinds that had never fired in
  eight weeks were also the two the instrument could not see. A hand-kept list
  beside the thing it describes is a list that drifts. `KINDS` now derives from
  `counted_kinds()`.

* **What is this offer called?** Each view spelled its own label, so a surface
  without buttons had nothing to fold into prose, and the one localized offer
  (`date_keep`, German) kept its translation inside a Discord view. Neither the
  wording nor the language is a platform concern.

**Counted is not the same as offered.** Three surfaces post real offers that no
ledger row has ever described — see `UNCOUNTED`. That is stated here rather than
quietly omitted, because this package's whole argument is that a gap you can see
is worth more than a number you cannot check.

No transport import, by design — see `tests/test_transport_boundary.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from runtime.messages import Action

DEFAULT_LOCALE = "en"


@dataclass(frozen=True)
class OfferSpec:
    """One offer kind. `labels` is keyed by locale; `en` is required."""

    kind: str
    labels: Mapping[str, str]
    description: str = ""
    # False when the offer ledger has no row for this kind. Always paired with a
    # reason in `UNCOUNTED` — an uncounted offer is a measurement gap, and an
    # unexplained one is indistinguishable from an oversight.
    counted: bool = True
    # The label depends on the content, not the kind (a video's offer is not an
    # article's), so the registry declares the delegate instead of a string.
    dynamic_label_from: str = ""
    payload: Mapping[str, str] = field(default_factory=dict)

    def label(self, locale: str = DEFAULT_LOCALE) -> str:
        if self.dynamic_label_from:
            raise ValueError(
                f"{self.kind} chooses its label from content — call "
                f"{self.dynamic_label_from} instead of asking the registry"
            )
        return self.labels.get(locale) or self.labels[DEFAULT_LOCALE]


_SPECS: tuple[OfferSpec, ...] = (
    OfferSpec(
        kind="save",
        labels={"en": "Save to library"},
        description="Optional — **save this link** to your practice library.",
    ),
    OfferSpec(
        kind="checkpoint",
        labels={"en": "Checkpoint"},
        description="Optional — **checkpoint** this thread when you are ready.",
    ),
    OfferSpec(
        kind="turtle_save",
        labels={"en": "Save to library"},
        description="Optional — **save this link** to your practice library.",
    ),
    OfferSpec(
        kind="turtle_checkpoint",
        labels={"en": "Checkpoint"},
        description="Optional — **checkpoint** this thread when you are ready.",
    ),
    OfferSpec(
        kind="home_plan",
        labels={"en": "Keep as working plan"},
    ),
    OfferSpec(
        # The only localized offer today. The translation lived in `dates.py`
        # beside a Discord button; a second transport would have had to find it.
        kind="date_keep",
        labels={"en": "Keep this date", "de": "Datum merken"},
    ),
    OfferSpec(
        kind="themes_keep",
        labels={"en": "Keep these"},
    ),
    OfferSpec(
        kind="flow_intake",
        labels={"en": "Prepare"},
        counted=False,
    ),
    OfferSpec(
        kind="flow_rename",
        labels={"en": "Rename thread"},
        counted=False,
    ),
    OfferSpec(
        kind="link_read",
        labels={"en": "Read links"},
        dynamic_label_from="runtime.link_offers.action_for_urls",
    ),
    OfferSpec(
        # Counted, and this one has to be. It is the entry gate to autonomous
        # craft sessions, so its take rate is the measurement that says whether
        # the noticer reads conversations the way the practitioner does. The
        # flag path it replaces fired once in five days and nothing counted
        # that either — which is why nobody noticed it had stopped.
        kind="eddy_ready",
        labels={"en": "Yes — that's the target"},
        description="Optional — confirm this eddy is ready to become work.",
    ),
)

REGISTRY: Mapping[str, OfferSpec] = {spec.kind: spec for spec in _SPECS}

# Why each uncounted kind is uncounted. Every one of these is a real offer a
# practitioner sees, so each line is a measurement the practice does not have —
# and the reason has to survive reading, because "we never got to it" and "we
# decided against it" are different states that look identical in a list.
#
# `themes_keep` and `link_read` were here and are now counted (2026-08-14). What
# remains is deliberate.
UNCOUNTED: Mapping[str, str] = {
    "flow_intake": (
        "Deliberate, and the reason changed today. Since the Skip button went, "
        "**talking is the designed way past intake** — so an ignored Prepare is the "
        "expected path, not a misread moment, and `no answer` in the ratios table "
        "means the opposite there than everywhere else. Counting it would make one "
        "row of that table lie about what its column means. The Prepare-uptake "
        "question is real and answerable separately, against flow eddies rather "
        "than against offers."
    ),
    "flow_rename": (
        "Cosmetic — a suggested thread title. Nothing downstream changes on the "
        "answer, so there is no decision a take rate would inform. Listed so it "
        "reads as decided rather than forgotten."
    ),
}


def spec(kind: str) -> OfferSpec:
    try:
        return REGISTRY[kind]
    except KeyError:
        raise KeyError(
            f"unknown offer kind {kind!r} — declare it in runtime/offers.py so the "
            "ledger and the label live in one place"
        ) from None


def label_for(kind: str, locale: str = DEFAULT_LOCALE) -> str:
    return spec(kind).label(locale)


def description_for(kind: str) -> str:
    return spec(kind).description


def accept_action(
    kind: str,
    *,
    locale: str = DEFAULT_LOCALE,
    payload: Mapping[str, str] | None = None,
) -> Action:
    """The affordance that accepts this offer, named by the runtime."""
    resolved = spec(kind)
    merged = dict(resolved.payload)
    if payload:
        merged.update(payload)
    merged.setdefault("kind", kind)
    return Action(key=kind, label=resolved.label(locale), payload=merged)


def counted_kinds() -> tuple[str, ...]:
    """Kinds the offer ledger has rows for. `offer_ledger.KINDS` derives from this."""
    return tuple(sorted(k for k, s in REGISTRY.items() if s.counted))


def uncounted_kinds() -> tuple[str, ...]:
    return tuple(sorted(k for k, s in REGISTRY.items() if not s.counted))
