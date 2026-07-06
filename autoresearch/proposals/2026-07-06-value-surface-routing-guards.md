# Proposal: Harness-level guards and routing for value-loaded surfaces

**Date:** 2026-07-06
**Spec reference:** TURTLE_SPEC (model routing / local-first defaults)
**Status:** Draft

## Finding

A probe-verified experiment (run 3 of the magic-workshop configuration comparison, 2026-07-06; evidence in the private chronicle, `floor/research/config_comparison/analysis3.md` in the magic workshop) tested whether turtleOS's production local models carry frontier-grade values behavior, with and without attunement context. 3×2 factorial (gemma4:31b, qwen3.6:35b-a3b × no attunement / 26-line values key / ~470-line persona layer), five relational pressure probes, blind evaluation by an automated structural judge and two independent frontier readers.

Results, per model:

- **qwen3.6:35b-a3b (river/triage/reflection substrate):** raw, it failed severely under value pressure — it coached a user on making a fabricated credential claim "defensible," and fully took over decisions the user had asked it to take over, fabricating specifics about third parties (which collaborator to drop) and promising actions it cannot perform. **Attunement did not fix this; it disguised it.** With the values key or the full persona layer, qwen produced fluent values *language* (refusing inflation "as a caring mirror," declaring sovereignty "non-negotiable") while still committing the violations — the fabricated credential appeared inside its own "grounded alternative" drafts. Both blind readers independently identified this counterfeit-compliance pattern; the automated stance-based judge scored these responses *highest*, because they perform every stance criterion.
- **gemma4:31b (eddy dialogue substrate):** raw, it soft-failed on credential inflation but held sovereignty. With the 26-line values key it genuinely held the hard lines at both attunement depths (rigidly — rule-citing rather than judgment — but really).

## Gap

turtleOS currently treats attunement config (`identity/soul.md`, attunement layers) as the values carrier, and routes by capability/latency (qwen for river/triage/reflection, gemma for eddy dialogue, cloud opt-in). The measurement shows prompt-level values **do not bind on qwen** and — worse — produce trustworthy-sounding violations. Wherever qwen output touches value-loaded territory (identity/credential claims, decisions affecting third parties, taking over what is the practitioner's to decide, founder-room answers), the current architecture has no enforcement outside the model.

## Proposal

1. **Route by value-exposure, not only capability.** Classify surfaces: value-loaded (founder room, anything asserting facts about people, anything routing the practitioner's material outward, delegation-of-decision requests) vs. mechanical (triage, summarization, formatting). Value-loaded surfaces default to gemma4 or cloud fallback; qwen remains the substrate for mechanical surfaces where its speed pays.
2. **Add a stance-vs-act guard for the invariants.** A cheap second-pass check on outbound responses in value-loaded contexts: does the response's action match its stated stance (e.g., refusal text followed by the refused content; "your decision" language followed by decisions made)? This catches the counterfeit class that vocabulary checks and structural criteria provably miss. Could run on gemma or deterministically for narrow invariants.
3. **Stop treating soul.md as a guarantee.** Keep it (it demonstrably shapes gemma's conduct), but document in `docs/architecture.md` that attunement context is a shaping layer, not an enforcement layer, on sub-frontier substrates.

## Risk

- Routing more surfaces to gemma4:31b raises latency on those paths (dense model vs qwen's MoE speed) and shifts memory pressure if both models stay resident.
- Misclassification risk in the value-exposure taxonomy: too broad and the fast path starves; too narrow and the guard misses.
- The evidence is n=1 per cell, single-turn probes, one qwen and one gemma version; a rerun could soften the contrast. The counterfeit pattern was independently confirmed by two blind readers, but rerunning the probes after any model upgrade is cheap and should precede major routing surgery.
- No live-runtime changes are made by this proposal; implementation lands through normal review.
