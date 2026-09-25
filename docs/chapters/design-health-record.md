# Design: Health Record Primitive

**Date:** 2026-09-07  
**Status:** Implemented platform and synthetic functional gate; natural-use UX remains the member gate.  
**Spec:** TURTLE_SPEC §3.2.1

## Contract

Health is a person-held longitudinal practice, not a medical chatbot. By
default it is **one individual's** private health channel. The **owner**
(registry: `subject`) owns record meaning. They may assign one **support**
person (registry: `steward`) — another server member — if they cannot
perform health-relevant acts themselves. **Only the owner can assign
support** (`assign_health_support`; a non-owner fails). Support may tend
the container and carry delegated acts; they cannot mint the owner's
testimony as if it were theirs. The board names the best current model of
the data. Clinicians remain expert sources and retain legal diagnosis and
treatment authority; they do not own the model.

A second person's health is a **second health instance**, not a second
role on this one. Membership is not ownership. Every instance is design
data for the primitive: unused options, blocked dests, and forked type
strings feed the next change. Clinical content never leaves its root.

Capabilities are primitive options, not per-subject features. Evening
check-in is one: `record/checkin.json` `enabled: true` turns it on for
that instance only. Missing or false stays quiet. `mode` defaults to
`survey` (the five questions). `mode: state` posts a short picture drawn
from today's eddy notes in that root and asks whether it is the current
state. A day with no notes asks one open question and does not read the
board or the record. `ja` stores the draft as confirmed testimony.
`nein, eher …` stores his words, with the draft labelled on the same
event. Anything else, a reply inside an eddy, and a second reply are
conversation. An unused opt-in is product evidence, not a reason to dest
the capability.

Evidence remains layered:

1. immutable source document;
2. machine extraction, including method and OCR confidence;
3. clinician statement or measured result;
4. record-owner testimony;
5. another member's attributed report;
6. Turtle inference with explicit uncertainty;
7. open question.

The corpus is evidence. `record/` is durable working state. `health_model.md`
is a compact current board. A source-derived current statement has a
source/page citation; an inference says that it is an inference.

## Storage

- `documents/sources/<sha256>/original/` — read-only immutable upload.
- `documents/manifests/<source-id>.json` — hash, origin, state, processor,
  extracts and confidence.
- `documents/extracts/<source-id>/page-NNNN.txt` — local page text.
- `documents/.derived/corpus.sqlite3` — deletable FTS5 index.
- `record/proposals/` — pending/decided mutations.
- `record/observations.jsonl`, `questions.jsonl`, `corrections.jsonl` —
  append-only attributed events.
- `record/checkin.json` — opt-in evening check-in (`enabled: true` is the
  mechanism; missing or false means the instance stays quiet). Optional
  `questions` / `flags` replace the default list for that instance only.
  The prompt asks questions, not scale nouns.
- `record/checkin_state.json` — posted/logged dates for that instance only.
- `record/claims.json` and `model_claim_map.json` — confirmed claims and traces.
- `record/changes.jsonl` — visible decision history.
- `artifacts/appointment-prep-*.md` — readable long outputs.

Existing private `labs/`, `visits/`, `notes/`, `genetics/`, `extracts/`, and
document files are registered in place. Migration does not move or rewrite
them.

## Intake and processing

Persistence has a 100 MB ceiling and is separate from prompt-inline limits.
The original is hashed before registration; an exact SHA-256 match is a
duplicate. PDFs and images never enter generic cloud vision. Native PDF text
uses PyMuPDF; scan pages use local Tesseract `deu+eng`. Page count, pixels,
runtime, archive member count, expanded size, compression ratio, and paths are
bounded. Missing processors and low-confidence OCR become visible
`Needs review`/`Failed` states.

ZIP/CSV specialist data may be stored and inventoried. It does not
automatically alter the model. Consumer DNA data is never interpreted here.

## Conversation

Turtle starts from the compact board and has health-only corpus tools:
search, read page, and trace source. Generic practice-file browsing, shell, and
web search are absent from the sensitive surface.

Explicit ordinary-language save requests are consent for the subject's own
observation/question. Source-derived findings and another member's report
remain proposals until the subject confirms. Confirm/reject is a visible
Discord act. Corrections supersede; they never erase.

Supported activities are:

- plain-language lab breakdown grounded in source pages;
- cross-document lexical pattern search;
- attributed symptom/observation ledger;
- unresolved question list;
- visit recap (`recap_health_visit`) that writes observations, attributed
  clinician words, questions, local date-events, and source-derived
  medication/inference lines in one call;
- appointment-preparation artifact;
- opt-in evening check-in (questions you can answer after reading them).

The member sees upload, status, review, conversation and correction—not paths,
commands, OCR, RAG, primitive configuration, or data modelling.
