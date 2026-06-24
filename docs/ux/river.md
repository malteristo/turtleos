# River UX patterns

**Principles:** [principles.md](principles.md) · **Journeys:** [journeys.md](journeys.md) · **Flow library:** [flow-library-journeys.md](flow-library-journeys.md)

---

## Standing eddy bar (bottom anchor)

**Principle:** One persistent affordance at the **bottom** of the river timeline. Eddies accumulate above it; the control always stays last.

**Pattern:**

```
… practitioner drops …
… Discord thread cards for past eddies …
[ 🌀 new eddy ]   ← always last message
```

**On `new eddy` click:**

1. Bar message **deletes**
2. River bot posts a silent anchor message and creates a thread named **`new eddy`**
3. Discord renders the **native thread-list embed**
4. River posts a **compact flow library** embed in the thread (optional programs — user-initiated)
5. Fresh bar posts **below** the new thread card

**Flow choice is in-eddy, not on the bar.** Practitioners load a flow via the in-thread library embed or **`!flows`** inside an eddy. **`!flows`** in the parent river redirects to open an eddy first.

**After any river timeline activity** (practitioner message, Turtle command output, ops embeds, Spirit ops): the harness re-checks that the bar is still the last message; if not, it removes the stale bar and posts a new one at the bottom.

**Implementation:** `river_handler.py` — `RiverEddyBarView`, `ensure_river_eddy_bar`, `ensure_bar_at_bottom`. In-eddy picker: `eddy_flow_library.py`. Unified hook: `bar_anchor.ensure_channel_bars`.

**State:** `thread-state/river/eddy_bar.json` maps channel id → bar message id.

**Retired:** standing-bar **`flow menu`** and `RiverFlowPickerView` on the bar (2026-06-20 flow library chapter).

---

## River classification acts (per message)

The River model classifies each practitioner message into acts. **Parent channel** acts today:

| Act | When | Rendered as |
|-----|------|-------------|
| `acknowledge` | Thin input (hi, emoji) | Often suppressed in render — low signal |
| `offer_flow_menu` | User asks about flows / programs on **this message** | Reply with flow buttons on **that message** |
| `offer_flow` | One flow clearly named | Reply with “Open {flow}” button on **that message** |
| `error` | Degraded / parse failure | Red embed in channel |

**Not emitted in parent channel:** `offer_eddy`, `revise_offer` — materialize is the standing bar’s job.

**Implementation:** `classify_river_acts`, `finalize_parent_river_acts`, `render_acts`; prompt in `template/character/river_prompt.md`.

---

## Contextual flow offers (optional)

When the River model detects flow-browse intent on a **specific message**, it may attach a **contextual** flow menu or single-flow button to that message (spawn thread from the practitioner’s message — still uses Discord thread embed).

This coexists with the standing bar: bar = always available blank eddy; contextual = “you asked about flows in this drop.” In-eddy library = intentional load inside a thread.

---

## Chronicle

Structural events append to practice chronicle (surface + deep). Materialized eddies log with jump URLs so practitioners can walk backward along the river when sidebar threads age out.

**Implementation:** `_append_chronicle` in `river_handler.py`; spec §6.

---

## Errors

River errors are **embed acts**, never apologetic chatbot paragraphs.
