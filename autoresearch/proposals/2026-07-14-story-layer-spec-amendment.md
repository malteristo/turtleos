# Proposal: TURTLE_SPEC amendment — the Story Layer

**Date:** 2026-07-14
**Spec reference:** TURTLE_SPEC §3.1, §6.4, §8.4, §10.2, §11.4, §11.5, §16
**Status:** Draft — awaiting Mage sanction
**Companion:** `docs/design/story-layer-vision.md` (direction), `docs/design/continuity-engine-and-substrate.md` (CE v4)

## Finding

User research with an early hosted practitioner plus operator marination converged on a unifying product direction: **turtleOS writes the context that tells your story while you live it, and uses that story to help in the moment.** The design chapter (`story-layer-vision.md`) grounds this. Several spec placeholders already point at this direction without naming it: §6.4 Sediment ("design chapter" pending), §11.4 "MV practice surface files" (v1.1 TBD), §16 deferred rows for both.

## Gap

The spec currently frames the product promise (§3.1) as *local AI made accessible* — the door, but not the reason to stay. Cross-eddy memory is deferred with no stated direction; checkpoints (§8.4) capture session notes but no relational description; the flow library (§10.2) has no practice-move flows; the artifacts viewer (§11.5) has no narrative shelf. The platform has no named concept for the narrative surfaces the research asked for.

## Proposal

Amend TURTLE_SPEC (suggested: minor version bump) with:

1. **§3.1 Product Promise** — add the relational sentence:
   > turtleOS is a **relational** practice space: it develops shared context with you over time — writing the context that tells your story while you live it, and applying what it knows to help you in the moment. Your story stays on your hardware.

2. **§6.4 Sediment** — replace "deferred, out of scope" body with a pointer: direction now set by the story-layer design chapter; sediment is the story's long-term retrieval policy (CE Slice 3); still not v1-vanilla, but no longer directionless.

3. **§8.4 Checkpoint writes** — add **eddy note** to the write-target table: at checkpoint, a short relational description of the eddy (content + relation to neighboring eddies), threshold ≥2 exchanges, written to the practitioner's story surfaces under practice root.

4. **New §6.5 (or §11.4 extension): Story surfaces** — define the narrative artifact family: eddy notes, daily notes, period notes (week/month/year), confirmed thread arcs. Each scale reads the scale below it, never raw transcripts. Practitioner-owned Tier-1 artifacts; git-versioned practice root (one repo per practitioner, hosted included). This *answers* the §11.4 "MV practice surface files" design chapter.

5. **§10.2 Flow library** — add **Fresh Eyes** and **Quest** as shipped flows. Quest carries the no-pressure clause as law: reward framing (what tackling it achieves/unblocks/reveals), never urgency framing.

6. **§11.5 Artifact tiers** — add story surfaces to Tier-1 shelves ("Story" shelf).

7. **§12 River Act Catalog** — add contextual life-artifact offer acts (e.g. "add to your dates?"), deferred implementation but named in the catalog schema.

8. **§16 Deferred table** — update rows: Sediment → "design direction set (story layer); implementation Slice 3"; MV practice surface files → "answered by story surfaces"; add "Timing-aware surfacing" and "Life-domain corpora / prefilled forms" as new deferred rows (Act Three).

## Risk

- **Scope creep into v1:** the amendment names direction; only §8.4 eddy notes and §10.2 flows are near-term implementation. Mitigate by marking act structure (design chapter §8) as sequencing guidance, not v1 requirements.
- **Write amplification:** story surfaces multiply writes to shared state before T1 (atomic writes, serialization) lands — the design chapter names T1 as the foundation slab; implementation must sequence behind it or use the same safe-write path.
- **Privacy weight:** story surfaces are the most intimate artifacts the platform holds; §11.5 tier enforcement and §15.5 hosted boundaries become higher-stakes. No new mechanism needed, but review 019/006 (artifact token model, write-allowlist parity) with story paths in scope.
- **Vocabulary discipline:** practitioner-facing language stays plain ("your story", "threads", "quests"); no internal jargon in surfaces (CE v4 acceptance criteria pattern applies).
