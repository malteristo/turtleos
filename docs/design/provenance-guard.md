# Provenance guard (distillation-time)

**Status:** Design spec — proposed, not built. Follow-on to the `Say only what was said` principle ([../ux/principles.md](../ux/principles.md)).
**Date:** 2026-07-21
**Warrant:** A shared-space eddy (2026-07-20) where Turtle attributed a hurtful characterization to a member who never said it. Caught by the other member. The generation-time fix (template `character/` prose) reduces the failure at the source; this guard is the backstop for the path that makes it *permanent* — distillation into persisted state.

---

## The two layers

| Layer | When | Fix |
|-------|------|-----|
| **Generation** | Turtle composes a reply in an eddy | Prose in `template/character/soul.md` + `conduct.md` (`Say only what was said`). Shipped 2026-07-21. |
| **Distillation** | A checkpoint distills the eddy transcript into chronicle / session note / resonance / state | **This guard.** A fabricated attribution in a reply misleads for a turn; one written to state becomes *history* and is cited back as fact indefinitely. |

The generation layer is probabilistic — a smaller local model under relational load can still slip. The distillation layer is where the cost compounds, so it warrants a deterministic-ish check even though the generation prose exists.

## Where it hooks

Checkpoint / resonance capture in `sessions.py` (`_append_resonance_chronicle`, idle-timeout and `!checkpoint`). The guard runs on any **generated distillation artifact** after it is composed and *before* it is persisted, with the eddy's visible transcript as the ground-truth source.

## What it checks

For each clause in the candidate artifact that **attributes** a statement, thought, feeling, or act to a named person — detected by attribution verbs (`said`, `called`, `thinks`, `felt`, `dismissed`, `admitted`, `sagte`, `nannte`, `findet`, `hielt …für`) with a person in scope — verify the attributed content is **grounded** in the source transcript.

- **Grounded** → keep.
- **Ungrounded** → the attribution is not supported by anything the person actually said in-thread.

Escalation by harm:
- **Ungrounded + neutral** → soft: rewrite from "X said Y" to an unattributed / inferred register ("it came up that…", drop the name), or hold for review.
- **Ungrounded + harmful** (attributed content matches a harm lexicon — contempt, slurs, pathologizing terms) → **hard block**: do not persist; surface for human review. This is the exact failure that warranted the guard.

## Implementation, in order of robustness

1. **Cheap first-line (heuristic):** regex for attribution-verb + name proximity, cross-checked against a harm lexicon. Zero model cost; catches the highest-stakes case (harmful attribution) with high precision. Ship this first.
2. **Robust (LLM-judge pass):** a single verification call — *"For each statement this summary attributes to a person, is it supported by the transcript below? List unsupported attributions."* More coverage, one extra call per checkpoint. Layer on where checkpoint latency allows.

## Open questions

- **Soft-rewrite vs. hold-for-review** as the default for neutral ungrounded attributions — rewrite keeps the flow but edits the model's output; hold preserves human control but adds friction. Lean rewrite-with-log.
- **Harm lexicon** — per-language, and it must not itself become a corpus of slurs; keep it minimal and reference-only.
- **Transcript scope** — grounding must include the *whole* visible eddy history, not just the last turn, or legitimate earlier-stated attributions get false-flagged.
- **Retroactive sweep** — a one-shot pass over existing chronicle/resonance/state to catch attributions distilled before the guard existed. Separate from the live guard; worth a scoped run.

## Not in scope

- Editing raw dialogue transcripts. A transcript is the honest record of what Turtle actually said — including its errors. The guard governs *distillation into asserted state*, not the conversation log. Correcting a live error belongs in-thread, visibly, not by rewriting history.

---

## Source claims — the second kind of fabrication

**Added 2026-07-28 after INT-041.** The guard above checks whether an attributed *statement* is grounded in the transcript. It cannot catch a fabricated *source*, and that is a distinct failure with a worse blast radius.

**What happened.** A hosted practitioner asked Turtle, in her own private river, to look over everything discussed in the family channel. Turtle has no access to that space from her root — verified three ways: her stored history for the eddy contained no permalink reads, no fetched content and no injection markers; `tos_tools._resolve_read_path` and `_resolve_search_base` are hard-scoped to `get_pd()`; her runtime dir holds no family state.

It answered anyway. The reply opened with a staged review gesture (*"Ich schaue mir die Dynamiken an…"*) and a follow-up eddy asserted outright *"sowohl hier als auch im Familien-Chat"* — **both here and in the family chat**. It had synthesized a plausible reading of a shared space it cannot see, from `state/notes/practitioner-profile.md` (an accumulated, one-sided relational dossier) plus recent eddies.

Every person-attribution in that reply may well have been grounded — in *her* prior statements. The lie was one level up: the claim about **where the knowledge came from**.

**Why it compounds.** The story layer then recorded the fabrication as her own reflection (*"You shared a deep reflection…"*), and her subsequent correction was written down as her correcting her own dynamics rather than as Turtle retracting an invention. A fabricated source became durable practitioner history and then context for later turns.

### What the source check adds

| | Person attribution | Source claim |
|---|---|---|
| Question | did this named person say this? | was this source ever readable from here? |
| Ground truth | the eddy transcript | the practice root's actual reach |
| Failure if unchecked | words put in someone's mouth | knowledge claimed about a space the practitioner cannot verify |

The source check is **cheaper and more deterministic** than the attribution check: reachability is a property of the practice context, not of the text. For any clause claiming to have read, reviewed, looked through, or considered a *named surface* — a channel, another river, a shared space, a file — verify that surface is reachable from the current `get_pd()` / channel context. Nothing else is.

### Where the real fix sits

Distillation-time guarding is the backstop, not the cure. Two layers, as above:

- **Generation.** Turtle must decline the premise: *"I can't see the family channel from here — paste it or share the eddy and I'll read it."* This is the `render_scope_block` honest-when-thin stance (§12.6) extended from *thin notes* to *unreachable spaces*. Naming what it cannot see is more useful than a plausible synthesis, and it is the only answer that keeps the isolation law legible to the practitioner.
- **Distillation.** A source-claim in a note is worse than in a reply — it becomes history. Gate it here too.

### The deeper defect it exposed

The story layer has **no representation for "Turtle asserted this; the practitioner did not."** One `mage_name`, one "you", and everything in the eddy — including Turtle's own inventions — renders as the practitioner's account. That assertion/testimony split is a story-layer change, not a guard, and it is unbuilt. Tracked as INT-041.
