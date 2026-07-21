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
