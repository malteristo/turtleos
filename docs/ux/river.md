# River UX patterns

**Principles:** [principles.md](principles.md) · **Journeys:** [journeys.md](journeys.md) · **Flow library:** [flow-library-journeys.md](flow-library-journeys.md)  
**Destination:** [design-river-bar-floor.md](../chapters/design-river-bar-floor.md)

---

## Standing eddy bar (reconciled floor)

**Purpose:** Launch pad — “start a conversation,” not a river console.

**Principle:** One persistent affordance at the **bottom** of the river timeline. Eddies and acts accumulate above it; the control is a **floor fixture**, not a message that races every act.

**Face:**

```
… practitioner drops …
… Discord thread cards / river acts …
[ 🌀 new eddy ]  [ more ▾ ]   ← always last message
```

**more** (select on the bar): `artifacts` · `help`.

- **new eddy** — materialize blank eddy (unchanged).
- **artifacts** — public Recent browse as today; reconcile is **held** until the browse sequence ends.
- **help** — ephemeral Commands card (no timeline litter).

**Flow choice is in-eddy, not on the bar.** Practitioners load a flow via the in-thread library or **`!flows`** inside an eddy. **`!flows`** in the parent river redirects to open an eddy first.

### Placement law (reconcile)

The harness does **not** eagerly delete/repost the tracked bar after every timeline tick. It **reconciles the floor**:

1. Debounce after activity (~1–2s quiet; coalesces during bursts).
2. Scan recent history for orphan bar messages; delete them.
3. Post exactly one fresh bar last (unless `bar_hold` is active).
4. Safety net: on River ready + slow periodic sweep.

**Multi-step hold:** Known sequences (e.g. artifacts browse) pause reconcile until complete, then one settle. The bar must not insert itself between related acts.

**Implementation:** `river_handler.py` — `RiverEddyBarView`, `reconcile_river_bar_floor`, `post_river_eddy_bar`. Debounce/hold: `bar_anchor.py`. Unified hook: `bar_anchor.ensure_channel_bars` (schedules debounce on river channels).

**State:** `thread-state/river/eddy_bar.json` maps channel id → bar message id.

**Retired:** standing-bar **`flow menu`** / `RiverFlowPickerView` (2026-06-20). Peer buttons for artifacts/help on the face (2026-07-16 — demoted under **more**).

---

## River classification acts (per message)

The River model classifies each practitioner message into acts. **Parent channel** acts today:

| Act | When | Rendered as |
|-----|------|-------------|
| `acknowledge` | Thin input (hi, emoji) | Often suppressed in render — low signal |
| `offer_flow_menu` | Practitioner asks about flows / programs on **this message** | Reply with flow buttons on **that message** |
| `offer_flow` | One flow clearly named | Reply with “Open {flow}” button on **that message** |
| `show_threads` | Practitioner asks to see threads / eddies (optionally a window) | Glance embed + Open link per named eddy |
| `show_waiting` | Practitioner asks what is waiting / where the heat is | Only ready / proposed / waiting rows. Whose move. Not an inventory. |
| `show_channel_menu` | Practitioner asks to change the channel or see its controls | Buttons from the primitive’s `parent_controls` |
| `file_intake` | Craft drop that is not a display request | Same gather/register as before — chosen, not the only mouth |
| `error` | Degraded / parse failure | Red embed in channel |

**Spoken displays.** Ordinary language in the parent channel can ask for a display. “show me threads from the last 5 days” does not go through `!threads`. River **sees** the craft drop (it is not stolen by intake). A display request draws the glance plus an Open link; anything else in craft files intake. The harness runs the same collectors the bang commands use. River still does not write prose.

**Not emitted in parent channel:** `offer_eddy`, `revise_offer` — materialize is the standing bar’s job.

**Implementation:** `river_display.parse_display_request`, `classify_river_acts`, `finalize_parent_river_acts`, `render_acts`; prompt in `template/character/river_prompt.md`.

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
