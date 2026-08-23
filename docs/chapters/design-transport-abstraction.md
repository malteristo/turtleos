# Design Note: Transport Abstraction

**Opened:** 2026-08-14 (decisions taken 2026-08-11)
**Status:** Slices 1–3 defined and deployed 2026-08-14 — value objects, enforced boundary, link-offer judgement and offer registry in the runtime. **One production path crosses the seam** (the incidental-link offer: `post_link_offer` → `incoming_from_discord` → `link_offer_for` → `discord_render.send_outgoing`), wired later the same day. Three `runtime/` modules and 241 lines still have no production importers, down from five and 466. Every other Discord path still handles raw `discord.Message` objects — the seam is load-bearing on one route, not on the system. See §*What "shipped" did and did not mean*: for several hours this line claimed the value objects were in use when nothing constructed one, and an outside reviewer read the word exactly as intended rather than as true.
**Seed:** Craft-turtle eddy *learning turtleos system architecture basics*, operator + Turtle, 2026-08-11 13:51–14:42. The grilling produced seven decisions and then stalled on *where does a proposal file live*, which is why this note exists three days later instead of that afternoon.
**Backlog:** `2026-08-11-craft-forge-handoff` (this was the hot eddy that check named)
**Depends on:** `runtime/` package (already present); `docs/native-runtime.md` §"Open transport requirements"
**Dogfood first:** operator `#craft-turtle`

---


## What "shipped" did and did not mean

*Added 2026-08-14, hours after the chapter was written, on an independent review.*

This note said "Slices 1–2 shipped." A reviewer with no knowledge of the project
read it, checked, and reported the sharpest finding anybody has made about this
repository:

> "`runtime/messages.py` — the transport-independence seam the project believes
> protects it from Discord lock-in — has **zero production importers** and is
> exercised only by its own (excellent) test, while 40 modules import `discord`
> directly across 757 call sites. The guard is real, the boundary it guards is not
> load-bearing, and the guard's own excellence is what makes the illusion durable."

Verified: `IncomingMessage` and `OutgoingMessage` appear in their own module, this
chapter, and `tests/test_transport_boundary.py`. Nowhere else. **466 lines across
five `runtime/` modules are tested, enforced, and never run.**

**Closed the same day, in part.** The link offer now runs the whole route: the
Discord message becomes an `IncomingMessage`, `runtime.link_offers.link_offer_for`
returns an `OutgoingMessage`, and `discord_render.send_outgoing` renders it as an
embed with a persistent button. It was chosen because its *judgement* already lived
in `runtime/` while its *posting* was hand-rolled Discord — a boundary half-drawn
rather than a new one. `tests/test_runtime_adoption.py` flipped from asserting the
seam was unreachable to asserting which paths reach it, and additionally asserts
that each listed module actually *calls* into the seam, since a name in a comment
would satisfy the weaker check.

What that slice did **not** do: the other ~45 modules that import `discord` are
untouched, and `runtime/events.py`, `policy.py` and `capabilities/` still have no
production importer. "One path" is the honest claim.

Two things surfaced while wiring it that are worth more than the wiring:

- **Moving labels into `Action` blinded a guard.** `tests/test_no_decline_buttons.py`
  reads button label *literals* from the AST. Once an offer's label is written as
  `Action(key=…, label=…)` in `runtime/`, the scanner saw a clean tree while the
  labels it was hunting had moved one file over. The guard now scans `Action`
  constructions in `runtime/` too. This is the failure mode the repo keeps meeting,
  found this time in the act of causing it.
- **Which `discord` a test gets depends on import order.** Nineteen test files
  install a `MagicMock` at import; the venv also has real discord.py 2.7.1. Under the
  mock, `class SomeView(discord.ui.View)` does not define a class at all — the name
  binds to another mock and the class body never runs, so no button, label,
  `custom_id` or callback in that half of the suite was ever executed. That is much
  of why this repo needs AST guards to see its own buttons. `tests/discord_stub.py`
  makes the mocked half constructible and refuses to touch the real library.

Both halves of that are true and they must be held together:

- The boundary guard **is** doing real work. It is a ratchet: it makes the wrong
  import impossible rather than merely discouraged, and its stale-exemption check
  caught an error on its first run. That value does not depend on adoption.
- The boundary is **not yet load-bearing**, because no Discord input crosses it.
  A green boundary test says *the runtime stayed clean*. It does not say *the
  system runs through the runtime*, and this chapter's status line let those read
  as the same sentence.

**This is the repo's own recurring defect, committed by the document describing the
fix for it** — a declaration whose mechanism verifies something adjacent to what a
reader will take it to mean. Recorded in `docs/quality-measures.md`'s
time-to-detection ledger as an instance of *declaration with no mechanism*, and
notable for being the only entry found by an outsider.

**Now measured, not remembered.** `scripts/quality_baseline.py` reports
`runtime_lines_unused_by_production` on every run, and
`tests/test_runtime_adoption.py` records the current figure so it ratchets:
when a production path constructs a value object, that test fails and the number
comes down on purpose. It can only fall by adoption — never by moving a file.

**The milestone this chapter may not claim until it happens:** one production path
— a single command is enough — where a `discord.Message` becomes an
`IncomingMessage`, the logic runs against the value object, and an
`OutgoingMessage` is rendered back. That is what would make the architecture real,
and it is the smallest thing that would.

## Tension

`dispatch_incoming_message(message: discord.Message)` is the seam, and it is not one. Everything downstream receives a Discord object and interrogates it directly. **47 of 93 root modules import `discord`**, and the highest concentrations are the button surfaces — `eddy_lifecycle_bar.py` (32 type references), `eddy_flow_library.py` (25), `cmd_threads.py` (21), `share_delivery.py` (15).

The Mage's constraint is not "make it portable now." Asked whether Matrix support belongs in the architecture today, he answered: *"support doesn't need to be in the architecture now, just don't close the door to switching in the future."* That reduces to exactly one rule, and the eddy found it:

> **The runtime never imports a transport library.**

Two things make this urgent rather than tidy. First, `runtime/__init__.py` has claimed *"This package is intentionally independent of Discord"* since it was created, and **nothing ever checked** — the invariant existed as a docstring. Second, the two features queued behind this note (YouTube transcript fetch, Exa search) are both **affordance** features: a reply plus a labelled button. The button layer is the most transport-coupled code in the repo, so wiring them in before the seam exists means wiring them twice.

---

## What the transports taught

Discord alone would never have produced the right shape. The Mage named two others and each falsified an assumption.

**Voice showed which fields are optional.** A spoken turn has no attachments, no reply chain, no mentions, and no bot-detection question. Anything downstream that assumes Discord's richness breaks. Voice is the harder constraint, not the softer one.

**Matrix showed that identity must be resolved before the runtime sees it.** Matrix is federated: one person arrives as `@name:server-a`, `@name:server-b`, or from a self-hosted homeserver. A runtime that maps platform IDs to practice roots itself must know every platform's ID format — which is the coupling restated one level down. So the transport resolves `practitioner_id` and the runtime trusts it.

**And the modality matrix is a product decision, not a technical one.** The Mage declined to answer "degraded Discord message or separate path?" and described the experience instead:

| Input | Output | Mirror |
|-------|--------|--------|
| Home speaker ("Hey Turtle") | voice over speaker | text → voice eddy |
| Discord voice message (mic button) | text reply | + "read aloud" button |
| Text, any eddy | text reply | — |

The mirroring is the architecturally interesting half: the voice eddy is not an output channel, it is **shared state** between the speaker and a phone picking the conversation up mid-stream. *"Because the conversation is mirrored in the eddy I should be able to pick up the phone at any time to read the entire conversation and if I want even answer on the phone."*

---

## The seven decisions (locked 2026-08-11)

1. `IncomingMessage` / `OutgoingMessage` value objects, transport-agnostic, defined in core
2. `practitioner_id` resolved by the **transport**, never by the runtime
3. `input_modality` — `text | voice_message | voice_live` (last reserved)
4. `mirror_eddy_id` — optional, reserved for live voice
5. One translator per transport; it is the only code allowed to import that platform's SDK
6. The runtime never imports a transport library — the door-stays-open invariant
7. Matrix, an Element fork, a native client, a home speaker — all future transports, zero runtime changes

**Scope the Mage set:** text and Discord voice messages (with read-aloud) are in scope; the home speaker is deferred until the hardware exists and gets its own channel with a single eddy, *"scoping this to its own discord channel just feels like the safest way to dogfood it."* The reserved fields are named now so the interface does not have to be reopened later.

**Why this widens the audience.** The Mage raised German *Wohngemeinschaften* — student and young-professional shared houses — as a second market beside families. Their needs overlap a family's; what differs is onboarding, because a WG has four people who each configure themselves with no household administrator. Same transport architecture; and running on Matrix without Discord is what makes turtleOS available to groups who will not adopt a proprietary platform.

---

## Slice 1 — shipped 2026-08-14

**`runtime/messages.py`** — `IncomingMessage`, `OutgoingMessage`, `Attachment`, `Action`. Value objects only, no behaviour, so a transport can be written and tested without a runtime and vice versa. Three details earn their place:

- `OutgoingMessage.answering(incoming, text)` encodes the modality matrix in one place. Voice-live speaks and mirrors; a voice message answers in text and offers "Read aloud"; text answers in text. **No transport branch anywhere in the runtime.**
- `affordances` is a declared capability set, and the runtime asks `can("buttons")` — deliberately *not* `transport == "discord"`. Asking a transport's name is how transport knowledge leaks back in.
- `renderable_actions()` returns nothing on a surface without buttons, so an action cannot be offered where it cannot be posted. That failure is live today: six act offers queued into craft-turtle, none ever shown.

**`tests/test_transport_boundary.py`** — the invariant, enforced by AST walk over every module under `runtime/`, with `runtime/adapters/` exempt as the translation layer. The exemption list is itself checked for stale entries, and **caught one on its first run**: `adapters/discord.py` is named for Discord but translates duck-typed (`message: Any` plus `getattr`), so it needed no exemption. A curated exemption list rots; a checked one does not.

1083 tests green.

---

## Migration — incremental, not a big bang

47 modules is not a refactor to attempt in one pass, and `share_eddy.py` / `discord_bot.py` / `eddy_spawn.py` are already named god-modules in `AGENTS.md`. The boundary is now **enforced where it matters** — inside `runtime/` — so migration is a ratchet rather than a project:

1. **Done:** anything new the runtime needs goes behind `IncomingMessage` / `OutgoingMessage`. The guard makes regression impossible rather than unlikely.
2. **Done (slice 2) — the link offer.** `runtime/link_offers.py` decides what a URL is and what the offer may be called; `link_read.py` renders it. This closed three separate operator reports at once, which is the argument for the whole migration in one data point: the YouTube mislabel, the unjudgeable `host (+N more)` description, and the Skip button. All three were the same defect — a runtime judgement made inside a Discord UI module. `content_fetch.detect_platform` now delegates to the same classifier, so the fetcher and the button cannot disagree.
3. **Next:** the rest of the offer surfaces — `home_plan_ui.py`, `eddy_lifecycle_bar.py` (32 Discord type references, the highest in the repo), `share_ui.py`, `continuity_confirm.py`. `Action` + `renderable_actions` replace per-surface `discord.ui.View` construction. Do the Skip-button question first (below), because it decides what these views contain.
4. **Then:** `DiscordTransport` builds `IncomingMessage` in `dialogue_routing.py`, and `dialogue_turn.py` stops seeing `discord.Message`. That is the decision's headline and the largest single slice.
5. **Deferred:** everything command-shaped (`cmd_*.py`, `commands.py`). Commands are inherently platform-flavoured and migrating them buys the least.

**Do not** move a module to satisfy the count. The guard's exemption list is the honest record of where the boundary actually is; shrinking it is progress, and it should shrink because a module stopped needing Discord, not because the list was edited.

---

## Open

3. **Done (slice 3) — the offer registry.** `runtime/offers.py` declares every offer the runtime can make: its kind, its label (localized), its description, and whether the ledger counts it. Five Discord views and four seneschal construction sites now ask for their label instead of spelling it, so a surface without buttons has something to fold into prose and the product's one translation (`date_keep`, German) is no longer inside a Discord view.

  **The registry is now the source of `offer_ledger.KINDS`.** That list was hand-maintained beside the labels it described, and the ledger's own comment records the failure: `turtle_save` and `turtle_checkpoint` were missing while sitting *ahead* of `save` and `checkpoint` in the turn handler, so the two kinds that had never fired were also the two the instrument could not see. Adding an offer without deciding whether it is measured is no longer possible by omission.

  **What the registry made visible:** four offer surfaces post to practitioners and have **no ledger row at all** — `themes_keep`, `flow_intake`, `flow_rename`, and `link_read`. The last one is the sharpest: it is the offer whose label and auto-fetch behaviour were changed twice in one week on operator reports, with no take-rate row to say whether either change helped. `UNCOUNTED` names each with its reason, because a gap that can be read is worth more than a number that cannot be checked.

- **The Skip button, as a class — settled 2026-08-14, and it unblocked this slice.** The operator's principle carried: *"Ignoring the offer should just be enough."* The argument that generalises it is a measurement one — a decline button manufactures the very event the ledger exists to infer, so `declined` counted how often someone bothered to dismiss a thing rather than how often they wanted it.

  Five views, not the four listed here: the AST guard (`tests/test_no_decline_buttons.py`) found `eddy_flow_library`'s `Keep title`, a decline wearing a positive label with `…:rename:dismiss:…` as its id. **The inventory was wrong twice before the guard was written.**

  Three were pure message edits. `dates.py` held the only `declined` write in the system. `flow_intake_handler`'s was **the only exit from `awaiting_intake`**, a flag eight call sites gate on, with `handle_eddy_first_message` returning before clearing it — so deleting it alone would have frozen any eddy whose practitioner just started typing. The work was moving each click's job onto the silence path (`practitioner_message_ends_intake_wait`), not deleting buttons. A flow with `intake.skippable: false` is untouched: "ignoring is enough" is a rule about **offers**, and a required step is not one.

  **Measurement consequence, accepted knowingly:** non-acceptance is now `offered - accepted` and nothing separates *passed* from *never saw it*. The sequence-based replacement is not built because no per-channel message timestamps reach the nightly report. Removing the decline also promoted an existing hole to load-bearing — `accepted` was recorded for one of six kinds — so `ACCEPT_INSTRUMENTED` now marks the rest `not recorded` rather than printing a false `0%`.
- **Where exa attaches.** Exa returns results the runtime summarizes — an `OutgoingMessage` with actions — so it wants slice 3 rather than a fourth hand-built view. Note that `TOS_TOOLS` is a flat list with **no per-channel filtering**, and the operator scoped exa to craft-turtle explicitly (*"for now I want to integrate it into the craft-turtle channel"*). Global availability would let a family conversation trigger web searches, so tool scoping is a prerequisite, not a v2.
- **Whether `speak` belongs on `OutgoingMessage` or in a capability call.** It is on the message for now because the modality matrix reads cleanly there; if text-to-speech turns out to need its own audit trail, it moves.
- **The home-speaker eddy strategy** — single persistent eddy vs one per wake-word session — is deliberately *not* decided here. The Mage wants to observe how the continuity engine handles several voice eddies over time rather than predict it.
