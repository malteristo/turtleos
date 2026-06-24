# Flows and River intake

> **Target UX (2026-06-23):** In-eddy flow library + Turtle bootstrap — see **[flow-library-journeys.md](flow-library-journeys.md)**.  
> The sections below describe **legacy** bar flow menu + River modal intake (retired from shell).

Flows are prompt programs loaded when `context_type` / `flow_id` is set (historically from bar flow menu; now from in-eddy picker). Flow front matter governs reads/writes under `state/`.

**See also:** [eddy-entry.md](eddy-entry.md) · [journeys.md](journeys.md) · [link-reading.md](link-reading.md) (URLs in eddy dialogue)

---

## Flow menu (bar) — retired

Lists only **installed** flows — `.md` files under `practice/flows/` or `template/flows/`. Template ships **Navigator**, **Thread**, **Companion**, **Feedback**; practitioners see whatever is installed under their practice root.

**Two entry paths (legacy):** flows **without** `intake` in front matter vs flows **with** `intake` declared (Navigator). Intake makes a flow feel like a **program** (contract → prepare → handoff), not a dressed-up prompt.

---

## Intake-free flow eddy (Shelter) — archived

| Step | What the practitioner should see |
|------|----------------------------------|
| Pick flow from bar | Thread titled **flow name** (e.g. `Shelter`), not generic `new eddy` |
| Enter thread | **One River orientation embed** — what this flow is, whether a checkpoint file exists |
| First message | Practitioner speaks; River adds Turtle; thread may rename to topic |
| First Turtle reply | Flow voice + compact presence tag (shell-injected) |

**Target:** blank eddy + Turtle identity (Layer 1); Shelter removed from ship set.

---

## River intake (flows with `intake` front matter — legacy modal)

**Why:** A menu + checkpoint file is not enough — practitioners still experience “talk to the model with a system prompt.” River intake separated **preparation** (River) from **dialogue** (Turtle) and made the handoff legible on the timeline.

| Step | What the practitioner should see |
|------|----------------------------------|
| Pick flow from bar | Thread titled **flow name** (e.g. `Navigator`) |
| Enter thread | **Orientation embed** — entry contract, checkpoint hint, **[Prepare]** and (if `skippable`) **[Skip — I'll talk]** |
| Prepare | Discord **modal** (text fields only, ≤5) → **summary embed** with **[Edit]** + **[Begin with Turtle]** — **return visits prefill** from prior intake file (`state/notes/{flow}-intake.md`) |
| Begin | `river changed the channel name: {topic}` (from intake) → `river added turtle` (system line) → **Turtle speaks first** |
| Skip | Short embed: first message will bring Turtle in (classic path) |

**Target (shipped):** Turtle conversational bootstrap — no modal; intake captured in dialogue or from prior file. See `flow_bootstrap.py`.

**Split-bot rule:** River **cannot** call Turtle dialogue. After **Begin**, River writes a handoff file under `thread-state/intake-handoff/{thread_id}.json`; Turtle’s watcher picks it up and posts the opening. Do **not** auto-open on modal submit alone — **Begin** must remain explicit so `river added turtle` + Turtle’s reply stay legible.

**Intake artifact:** Field values write to the path in front matter (e.g. `state/notes/navigator-intake.md`) and load into Turtle’s prompt. Flow conduct must **not** re-ask captured fields (see `template/flows/navigator.md` CRITICAL block).

**Dogfood notes:**

- **Stale buttons after bot restart:** Discord persistent views die on restart; Prepare/Begin on old embeds fail silently. Dogfood on a **fresh flow eddy** after deploy.
- **Modals are text-only:** selects and rich controls belong on embeds/buttons, not inside the modal.
- **Re-Prepare updates in place:** Edit on the green summary reopens the modal and updates that embed in place (one Begin target); `navigator-intake.md` always holds the latest capture.

River does **preparation**, not dialogue — orientation and intake embeds are allowed exceptions to “acts not words” (setup only, silent, no chatbot tone).

**Implementation (legacy):** `flow_intake_handler.py` (Prepare/Skip/Begin, modal, summary, **rename on Begin**); `flow_intake_opening.py` (handoff shim); `flow_runner.py` (`intake` front matter); `flow_bootstrap.py` (target path).
