# Design Note: Craft Eddy Temperature (Hearth pulse)

**Opened:** 2026-08-11  
**Status:** Design open — first slice specified; implement after living verify of write path  
**Seed:** Mage, same morning — annealing distribution of craft across Hearth → Forge/Anvil; want visible temperature + next step per craft-turtle eddy without opening every thread  
**Backlog:** `2026-08-11-craft-eddy-temperature-in-hearth`  
**Depends on:** [design-craft-channel.md](design-craft-channel.md); prepared-eddy recommend-close (`2026-08-10-prepared-eddy-target-recommends-close`); pulse engine (TURTLE_SPEC §11.2); workspace Live state on prepared surfaces  
**Dogfood first:** Operator `#craft-turtle`

---

## Tension

Craft work now anneals in dedicated craft-turtle eddies (Hearth), then moves to Forge or Anvil when there is enough heat to act. Three eddies can be live the same morning. The Mage cannot see, from the craft channel alone, which are hot, which are ready for Forge processing, and what each one's next step is — without opening every thread.

The thermodynamics are already named in Magic lore (`on_emotional_annealing.md`, `on_substrate_resonance.md`: Hearth heats → Forge shapes → Anvil implements). What is missing is a **glanceable instrument** on the Hearth surface itself.

Prepared-eddy recommend-close is one temperature reading (*ready to cool*). This note generalizes that to all craft eddies.

---

## Desired experience

From `#craft-turtle` (parent), without entering a thread, the Mage sees each open craft eddy with:

1. **Name** (and link)
2. **Temperature** — a small closed vocabulary (below)
3. **Next step** — one line: whose move, what kind (anneal more / bring to Forge / wait on external / ready to cool)

Opening an eddy still does the deep work. The parent only answers: *where is the heat, and what should I do next?*

---

## Temperature vocabulary (proposed lock)

| Temp | Means | Typical next step |
|------|--------|-------------------|
| **hot** | Recent Mage turns; Live state or conversation still moving | Stay in eddy — keep annealing |
| **warm** | Heat present but idle > quiet window; open questions remain | Glance Live state; one more Hearth pass or hold |
| **ready** | Enough context to act on Forge/Anvil — or prepared good-outcome met | Bring to Forge / confirm `!dissolve` (prepared) |
| **cooling** | Determination written / Mage said done; harvest or archive pending | Spirit harvest or Mage archive |
| **cold** | No Mage turns in a long window; no ready signal | Re-heat, park, or close |

"Enough heat ≈ context readiness to act" is the Mage's own gloss — **ready** is that state, not a model confidence score.

---

## What temperature is *not*

- Not a second backlog (no duplicate of `craft/development.md`)
- Not clippy ranking ("you should work on X") — availability of signal, not persuasion
- Not a new inference call on every glance — derive from artifacts already written
- Not auto-dissolve — recommend / surface only; Mage confirms

---

## Derivation (first slice — no new model)

Read, don't invent:

| Signal | Source |
|--------|--------|
| Last Mage activity | Discord thread last practitioner message time |
| Live state fullness | Prepared workspace `## Live state` — Settled vs Still open |
| Good-outcome proximity | Prepared surface "good outcome" / determination section; sidecar `disposition` |
| Explicit next step | Last Turtle line that names a question or owed move; else "open Live state" |

Compose temperature with deterministic rules (idle thresholds + Live-state emptiness + disposition). Next-step line prefers an explicit sentence already in Live state or the last Turtle question; otherwise a template from the temp bucket.

**Prepared eddies:** `disposition: ready` ⇒ **cooling** (or **ready** until confirm — prefer **ready** with next step "confirm close"); recommend-close noticer feeds this row rather than a separate chrome.

---

## Surface (first slice)

**`!craft`** (or a craft-parent pulse embed refreshed on idle / on eddy open-close) listing open craft eddies as rows:

`🔥 hot · ux research · next: answer MX desired-state question`  
`🟠 ready · hai facilitation · next: wait Kate / or Forge when access lands`

Pin optional; do not spam the parent on every turn — refresh on cadence or on command.

Reuse pulse-engine texture vocabulary where it already fits; do not fork a second classifier.

---

## Out of scope (this note)

- Building the ellipsis contextual menu (`…`)
- Auto-opening Forge sessions
- Scoring "quality of annealing"
- Family-river temperature (different habitat)

---

## Recognition tests

1. Three open craft eddies → parent/`!craft` shows three rows with temp + next step without Spirit on Forge.
2. Prepared eddy hitting good-outcome → row reads **ready** / recommend close; Mage still confirms.
3. Stale eddy with empty Live state and no Mage turns past cold threshold → **cold**, not **ready**.
4. No Ollama call required to render the list (deterministic read).

---

## Lifecycle in the practice (Spirit-created vs Mage-created)

Eddies are **thinking places**. They start on a topic; digressions are normal. Lifecycle is how heat becomes durable without forcing the Mage to leave the heat.

### Shared phases (both origins)

| Phase | Mage sees | Spirit / Turtle does |
|-------|-----------|----------------------|
| **heating** | New or freshly active thread | Open context; for Spirit-created, present prepared surface |
| **annealing** | Conversation + Live state moving | Update Live state / working memory; offer digression harvest without derailing topic |
| **ready** | Temp row says ready; next step names Forge/Anvil or cool | Write **handoff packet** (tried / decided / open / files / next act) |
| **cooling** | Confirm dissolve / archive | Harvest packet → workshop (bright, backlog, `desk/craft/handoffs/`); prepared `disposition` advances |
| **cooled** | Thread gone or aged quiet | No further Hearth work unless Mage reopens |

Temperature (`!craft` / pulse) is the **glance** representation of phase. It is not a second backlog.

### Spirit-created (prepared)

- **Open:** Spirit opens with surface + "what good outcome looks like"; Mage works in his own time.
- **Linger rule:** Prefer **appear → serve → recommend close**. They should not accumulate as permanent furniture once the target is met (`2026-08-10-prepared-eddy-target-recommends-close`).
- **Ready:** Good-outcome met **or** Mage declares enough heat → Turtle proposes ready; Mage confirms.
- **Close:** Recommend dissolve → existing ready/harvest path; Spirit reads Live state + handoff at `. craft` / chapter start.

### Mage-created (organic)

- **Open:** Mage starts a thread when thinking needs a place — no prepared surface required.
- **Linger rule:** Stay until Mage is done (or cold long enough that `!craft` marks cold and offers park/cool). Spin-off is optional when a digression becomes its own topic.
- **Ready:** Enough context to act on Forge/Anvil (same gloss as temperature **ready**) → handoff packet even without a prepared surface (first slice: Turtle writes `craft/handoffs/<id>-….md` or a `## Handoff` block Turtle + Spirit share).
- **Promote (optional):** Mid-flight, an organic eddy can gain a prepared-style workspace if heat will return across days — not required for handoff.

### Digression harvest (focus without loss)

Sanctioned 2026-08-11: keep the eddy on-topic **without losing** inspired asides.

- Mid-turn offer (Mage confirm only): **capture aside → boom** · **spin off eddy** · (later) route to a named destination.
- Cool-time optional candidate list — still confirm; never silent-route into bright.
- Field proof: Wohngruppe thesis inside architecture eddy → bright § Scaling; backlog `2026-08-11-eddy-digression-harvest`.

### Three representations, one state

1. **Glance** — Discord parent / `!craft`: name · temp · next step (all open craft eddies).
2. **Working memory** — prepared `## Live state`; Mage eddies: handoff section when ready.
3. **Chronicle** — workshop harvest: bright / backlog / `desk/craft/handoffs/` / moves.

### Raised flag → craft session intake (proposed lock)

**Yes — integrate the handoff check into craft practice.** The ad-hoc 2026-08-11 check becomes a standing instrument: when an eddy is **ready** (e.g. written proposal / handoff packet) or hits a **significant milestone**, Turtle **raises a flag** on the Hearth. That flag means: *this eddy carries context that should enter the next `. craft`.*

Spirit at craft arrival then does not re-survey fifteen threads. It reads the **flagged set** first, forms a session approach, and only then opens depth.

#### Two flag kinds (do not collapse)

| Flag | Means | Spirit's default move |
|------|--------|------------------------|
| **ready** | Enough context to act on Forge/Anvil — packet exists (tried / decided / open / files / next act) | Candidate for this session's work queue |
| **milestone** | Significant progress, but not yet actionable (e.g. survey half-done, waiting external, proposal draft still soft) | Orient / maybe return to Hearth — do **not** treat as implement-now |

Temperature **ready** and flag **ready** should converge: raising ready **writes or refreshes the handoff packet**. A flag without a packet is chrome without payload — refuse the raise until the packet exists (Turtle can draft; Mage confirms).

#### Who raises

- Turtle **proposes** (Live state / good-outcome / "I've written the spec").
- Mage **confirms** (or raises explicitly: "flag this" / button later).
- Prepared `disposition: ready` already is a raise — fold into the same glance row.

#### What Mage sees on the Hearth

Same `!craft` / pulse row, plus a visible mark — e.g. `🚩 ready` or `◇ milestone` — not a separate channel. Cold/hot/warm still describe heat; the flag describes **craft-session relevance**.

#### What Spirit does at `. craft` (session shape)

1. **Intake flagged eddies** (ready first, then milestones) — read packets, not full thread history unless needed.
2. **Propose a session plan** (decision-surface): which ready items this session, order, which stay Hearth, which cool; cost and recommendation.
3. **Orchestrate execution** per item:
   - Spirit does it (judgment, design, governance, cross-eddy coherence).
   - Sub-spirits (e.g. Grok agents) for **parallel, packet-bounded** implement slices when the approach says so.
   - Return to Hearth when the packet is still soft (milestone, not ready).
4. Mage accepts / rejects / amends the plan — then work proceeds.

Sub-agents are an **execution option after the plan**, not the arrival step. Arrival stays one Spirit mind assessing the flagged set. Deploy / service disruption still hits the ordinary sanction list — sub-agents do not bypass it.

#### Improvements on the Mage's sketch

1. **Packet is the unit of raise** — flag = pointer; packet = content. Prevents "ready" that still requires rediscovery.
2. **Milestone ≠ ready** — keeps inspired progress visible without flooding the implement queue.
3. **Arrival reads flags, not all eddies** — scales when craft-turtle has many threads; temperature remains the ambient glance.
4. **Session plan before sub-agents** — Spirit chooses approach; parallelism is a tool, not the default.
5. **Wire into `cast_arrival.md` `. craft`** (pending flow amend): after prepared-eddies / moves, add *flagged craft eddies* (pull script or Mini sidecar list). Exact wording to propose when first slice ships.
6. **Clear the flag on harvest** — when Spirit folds a ready eddy into shipped work or cools it, lower the flag so the next arrival is not haunted.

#### Recognition tests

1. Mage confirms ready on markdown-first → Hearth row shows 🚩; `. craft` lists it in flagged intake before backlog skim.
2. Architecture hits "spec written" → ready raise + packet; mid-survey progress alone → milestone at most.
3. Fifteen open eddies, two flagged → Spirit's first deep reads are those two packets.
4. Flag raised with empty handoff section → system refuses or Turtle is forced to draft before the mark sticks.

---

## Living control — handoff check 2026-08-11

Full table: `magic/desk/craft/handoffs/2026-08-11-craft-eddy-handoff-check.md`.

**Ready now:** markdown-first (Forge confirm one-line); context-window / ellipsis / design-evals / craft-practice-evolution (cool or Forge-session, little Hearth left).  
**More heat / wait:** architecture (hot — finish transport spec then handoff); hai (warm — external wait); ux-research (warm — two opens); muse-glimmer (warm→park).  
**Cold:** several Mage threads ~2–4d idle — digression-pass then cool (echo-chamber is the high-value one).

---

## Open questions

1. Idle thresholds for hot→warm→cold — start with 2h / 24h / 7d and tune from dogfood?
2. Is **ready** Mage-declared only, or may Turtle propose it from Live state + good-outcome text? **Answered 2026-08-11:** Turtle may propose; Mage confirms before cooling.
3. Does the craft digest on Mini (`craft/development.md`) also gain a Temperature section, or is Discord the only glance surface?
4. For Mage-created eddies without a surface file: is the first handoff artifact a Discord-posted packet, a `craft/handoffs/` file, or both (message for Mage, file for Spirit)?
5. Milestone vocabulary — free text one-liner on the row, or a tiny closed set (surveyed / waiting-external / proposal-draft)?

---

## Recommendation

Ship derivation + `!craft` list first. Wire prepared recommend-close into the same row. Defer chrome polish and ranking. Answer Q2 as: Turtle may **propose** ready; Mage confirms before cooling.

**Integrate flag into craft practice** as above: ready/milestone raise on Hearth → flagged intake at `. craft` → Spirit session plan → optional sub-agent execute. First living slice can be **manual**: Turtle writes packet + Mage says "flag ready"; Spirit treats `desk/craft/handoffs/*` unread ready files as the flagged set — no new Discord chrome required to dogfood the session shape.

**Next living acts (no code required):** (1) Forge markdown-first packet now; (2) finish architecture anneal → handoff; (3) cold-pass with digression harvest on echo-chamber before mass-cool.

---

## Shipped 2026-08-16 — readiness has a producer, a gate, and a record

**What made this urgent was a measurement, not the design.** The manual slice
above ("no new Discord chrome required to dogfood the session shape") ran for
five days and fired **once**, on the day it was written, for the one eddy Spirit
had prepared itself. Over the same window seven prepared eddies sat at
`disposition: open` while their surfaces were edited days later, and one eddy
closed with *"You agreed that this architecture warrants a formal specification
before the details disperse"* — a readiness declaration in prose that nothing
could read. That is the craft *moves* channel's death written a second time: a
mechanism that waits for the practitioner to perform a separate marking act
records nothing, because the practice happens in the conversation, not beside it.

**Q2 is now enforced rather than agreed.** Turtle proposes; only a human press
makes an eddy ready. `core/craft_readiness.py` holds the states and refuses the
promotion — a proposal cannot become readiness without a press, and work cannot
be planned against a proposal (`mark_acted` requires `ready`).

**Q4 is answered by deleting the question.** Neither a Discord packet nor a
`craft/handoffs/` file. Readiness is a row in the sidecar for *any* craft eddy,
with or without a workspace, which was the defect: the previous lifecycle
required a surface file, so an ordinary Mage-created eddy had no field to be
ready in.

**The target condition is the gate, and it is the whole design.** The Mage's own
definition — *the amount of work Spirit can perform without having to ask for
more input* — is only testable if something states what would be true when the
work is done. `propose` and `confirm` both refuse without one. An eddy that
cannot state a target condition is not a ready eddy missing paperwork; it is an
unfinished conversation, and the honest move is to keep talking.

**Refusal is an artifact.** Spirit evaluates readiness independently at the
arrival and may disagree; `refuse` requires a named gap, which is the next thing
to talk about in the eddy. A refusal with no gap is indistinguishable, from
inside the eddy, from being ignored.

### How it derives

The noticer reads **the eddy note the checkpoint just wrote**, not the
transcript. That honours this chapter's own rule — *derive from artifacts already
written* — and it fails in the right direction: a conversation whose own summary
cannot say what would be finished is a conversation that is not finished. It
also keeps the cost to one bounded call on a paragraph, on a one-slot host,
after an inference has already been spent reading the same conversation.

Everything about it fails closed: model down, timeout, unparseable JSON, missing
key, or a target condition whose vocabulary is not grounded in the note all
return no proposal. The grounding check exists for the one failure that costs
more than silence — a fluent, confident sentence about work the conversation
never discussed — and it carries its own positive control, because a grounding
check that rejected everything would pass every decline test while turning the
noticer off.

### What did not ship, and why

**No modal for editing the wording.** The obvious next feature is a text box to
correct the target condition, and it is the wrong one for this practice: craft
thinking happens by talking in an eddy, usually on a phone. A wrong condition is
corrected by saying so in the thread — the next idle re-proposes and overwrites,
which `propose` permits for exactly this reason. The conversation is the editor.

**No attribution on the confirm.** `craft-turtle` binds to one mage, so there is
no ambiguity about who pressed. Resolving it would have put this module inside
the 54-module dependency cycle; storing a raw Discord id would have put an
unresolvable token in durable state. The field exists in the record if craft ever
becomes shared.

**No temperature render on the parent channel yet** (Q3 stays open). The
vocabulary and its derivation are implemented and tested — `temperature()`,
including the rule that **readiness outranks idleness**, because a confirmed eddy
that went quiet is waiting for a session rather than cooling off, and reporting
it as cold would hide the one actionable row behind the ones that are not. What
is missing is the surface that renders rows, which is a separate slice.

### Structural cost

Four new modules and the feature moved **neither** structural ratchet: `mage`
fan-in stayed 63, the cycle stayed 53. That was not free — the first cut of
`craft_ready_ui` reached for `mage.get_runtime_dir` and
`continuity_confirm.address_for_user`, and both ratchets caught it in the same
run. The runtime dir is now injected by the two call sites that already hold it,
and the attribution decision above is the other half. **A view that reads global
configuration is a view that cannot be tested without one** — the layer rule and
the testability argument turned out to be the same argument.

Suite 1,344 → **1,387**.

### Live control, 2026-08-16 — five real eddy notes, and the one that changed the prompt

Unit tests cover the parser and the failure paths; they cannot tell you whether
a 27b model reading a real note proposes something a person would recognise. So
the noticer was run against five notes the practice actually wrote.

**First run:** one correct fire (the terminology eddy, quoting *"You agreed that
this architecture warrants a formal specification before the details disperse"*),
three correct declines, and **one fire that was grounded, fluent, and useless** —
*"Kermit reviews specific files storing relationship history to verify if they
match their intended concept of 'twine'."*

That is a target condition whose **actor is the practitioner**, and it is exactly
what this seam must not produce: a session cannot meet it, because it is the
conversation continuing rather than work waiting. The grounding check could not
catch it — every word came from the note. Nothing in the design would have
surfaced it either; it took running the thing.

**The prompt now demands a state of the world, never an action and never who
performs it,** with the contrast written into it. Second run: the actor-shaped
proposal is gone, the three declines hold, and the true positive still fires —
now as *"a formal specification for the architecture exists"* rather than a verb.
10.5s per note on the Mini.

**What the run also shows, and it is not fixed:** the ambient-River eddy produced
a concrete experiment design that morning and the noticer declined it. It
under-fires. That is the intended direction of the error — a missed proposal
costs one idle cycle, a wrong one costs attention at the moment of choosing what
to work on — but it is a real limit and the take rate on `eddy_ready` is what
will say whether the asymmetry was set too far.

### A measured negative result, 2026-08-16 — showing the noticer how the conversation ended made it worse

Reading the eddies themselves (`scripts/craft_board.py --read`) produced an
obvious-looking correction and it did not survive measurement. Writing it down
so nobody re-tries it blind.

**The hypothesis.** The muse-glimmer eddy closed with Turtle saying *"the Forge
session has enough to start without reconstructing this conversation"* — a
readiness declaration — and the noticer declined it, because the note summarised
a discussion about local models and said nothing about the decision at the end.
So: a note says what a conversation was *about*, readiness is in how it *ended*.
Show the last six turns beneath the note. No extra inference, better input.

**What it actually did**, across the same four real notes:

| eddy | note only | note + ending |
|---|---|---|
| terminology (true positive) | **correct fire** | *lost* |
| muse-glimmer | declined | fires — on *"the proposal is appended to the backlog"*, **which had already happened during the conversation** |
| architecture diagrams | correct decline | correct decline |
| Gary's talk | correct decline | correct decline |

Note-only: **1 correct fire, 3 correct declines, 0 errors.** With the ending:
**0 correct fires, 1 wrong fire, 3 declines.** Softening *weigh the ending most*
to *read both*, and adding *the target must not already be true*, changed
nothing on the second run.

**Two things worth keeping from the failure.** The architecture-diagrams eddy
ends with a question to the Mage and the note-only version already declined it —
so the "waiting on him" case the ending was supposed to fix was **not broken**,
and the fix was solving a problem that had no instance. And the ending's own
failure mode is sharp: shown the last turns, the model proposes *the last thing
that happened* as the target, which for a conversation that ended by doing
something is a target already met.

**Reverted to note-only.** The plumbing went with it — an unused `history`
parameter is exactly the kind of thing this repo deletes. Two rounds of prompt
tuning against four examples is overfitting, and the stopping rule was written
before the second round rather than after it.

**What the run does not settle:** four notes is not a sample. The real
instrument is the `eddy_ready` take rate, and the honest state of the noticer is
*one measured true positive, no measured false positives, and an under-fire rate
nobody knows.*
