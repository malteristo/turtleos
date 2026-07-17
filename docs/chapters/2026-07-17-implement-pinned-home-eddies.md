# Chapter — Implement: Pinned Home Eddies

**Opened:** 2026-07-17  
**Status:** Implementing — claimed-by: forge-craft 2026-07-17T18:29:09Z  
**Design law:** [design-pinned-home-eddies.md](design-pinned-home-eddies.md)  
**Spec touch:** TURTLE_SPEC §5.3, §8 (cool), §11.5  
**Dogfood:** Operator river first  
**Claim:** When executing, write `claimed-by: <session> <UTC>` at top of this file’s Status line (or adjacent `2026-07-17-implement-pinned-home-eddies.claim`) before coding — see magic craft backlog claim-marker item.

---

## Mission (one sentence)

Ship Discord-honest **working plans**: 1:1 home eddy ↔ Tier-1 artifact, discovered via a **river pin card** (`Continue` / `Open` / `Stop pinning`), with sticky cool and re-entry attunement — without inventing a side-panel.

## Cognition altitude (already decided — do not re-open)

All product forks are locked in the design chapter. AFK Spirit **implements**; does not redesign. If Discord API or code reality blocks a lock, write a **blocker note** in this file and stop that slice — do not invent a sidebar.

## Honesty constraint (word-action)

UI copy, Turtle prompts, help text, and learnings: **river pin + home eddy + file** only. Never “side-panel,” “shelf beside chat,” or “live sidebar sync.”

---

## Slice map

| Slice | Deliverable | Primary modules | Risk | Gate |
|-------|-------------|-----------------|------|------|
| **0** | Registry + paths | new `home_plans.py`; `state/home_plans.yaml` under practice root | Low | unit |
| **1** | Ensure artifact on disk | `home_plans.py` + Notes shelf allowlist | Low | unit |
| **2** | River pin card + buttons | new `home_plan_ui.py` (or under `river_handler`); River posts/pins | Med | unit + live |
| **3** | `!pin` product path + offer confirm | `commands.py` `cmd_pin`; view callback | Med | unit + live |
| **4** | Sticky cool | `sessions.cool_eddy_from_auto_archive` + registry flag | Med | unit |
| **5** | Attunement packet | dialogue context inject on home-eddy turns / Continue | Med | unit |
| **6** | Quiet perform write helper | small patch API + Turtle-visible instruction | Low–Med | unit |
| **7** | Spec, UX docs, matrix, shake, deploy notes | `TURTLE_SPEC`, `docs/ux/*`, `scripts/shake_home_plans.py` | Low | `spirit_verify` + shake |

**Out of this chapter:** portable any-eddy load; auto-classifier “this is a working doc” (Turtle/River **offer button** or explicit `!pin` is enough); story untouched nudges; hosted-river fanout; multi-doc homes.

---

## Data model (Slice 0)

Practice-root file: `state/home_plans.yaml`

```yaml
version: 1
plans:
  - id: <uuid or slug>
    title: "Workout plan"
    artifact_path: "state/notes/workout-plan.md"   # Tier-1 Notes shelf
    home_eddy_id: 1527...                          # Discord thread snowflake
    river_channel_id: 1479...
    river_pin_message_id: 1528...                  # pinned card message
    created_at: ISO8601
    updated_at: ISO8601
    sticky: true
```

API sketch (`home_plans.py`):

- `list_plans(practice_dir) -> list`
- `get_by_eddy(practice_dir, eddy_id) -> plan | None`
- `get_by_artifact(practice_dir, path) -> plan | None`
- `bind_home(...) -> plan` — 1:1 enforce (refuse second primary on same eddy; refuse two homes for same artifact)
- `set_pin_message(...)`, `clear_plan(...)` / `stop_pinning(...)`
- `is_sticky_eddy(eddy_id) -> bool`

Thread registry: optional mirror flag on eddy record if one exists; YAML is source of truth for day one.

---

## Slice 1 — Artifact ensure

- On bind: if no file, write markdown skeleton under `state/notes/<slug>.md` (title + body from source message or placeholder).
- If practitioner/Turtle already wrote content in chat, prefer saving that body (from replied-to message content) over empty skeleton.
- Must pass `artifact_viewer.is_artifact_readable` / Notes shelf.

---

## Slice 2 — River pin card

River bot posts embed (or short content) on the **practice river**:

- Title = plan title  
- Description = optional `Updated <date>`  
- Buttons: **Continue** (link button to `thread.jump_url` or bot ack that opens/unarchives thread), **Open** (artifact presenter / `PRACTICE_WEB_BASE` read URL — reuse `artifact_presenter` patterns), **Stop pinning** (confirm → unpin + clear binding; keep file by default)

Then `await card.pin()`.

Idempotent refresh: if pin message missing/deleted, re-post and update YAML.

**Continue behavior day one:** prefer Discord jump URL into existing thread; if thread archived, unarchive (bot needs manage threads) then jump. Do not spawn a second eddy.

---

## Slice 3 — `!pin` product path

Redesign `cmd_pin` in [commands.py](../../commands.py):

| Context | Behavior |
|---------|----------|
| In eddy, no home yet | Bind this eddy + ensure artifact (reply message body if reply; else latest Turtle structured block / ask for title) → Slice 2 card |
| In eddy, already home | Refresh pin card |
| In eddy, home exists for *other* artifact | Refuse; suggest new eddy |
| On river, reply to message | Legacy: pin that message (keep) |
| Offer view `home_plan_confirm` | Same as eddy bind |

**Offer (minimal):** Provide a persistent view / button Turtle or River can attach: “Keep as working plan” → same bind path. Do **not** build an LLM classifier gate in this chapter; prompt/soul one-liner may invite Turtle to offer the button when a plan-like doc appears (honesty: optional, not required for gate).

Help inventory: update `!pin` blurb to working-plan product act.

**Do not** collide with CE theme `!keep` / `cmd_keep`.

---

## Slice 4 — Sticky cool

In `cool_eddy_from_auto_archive` (and any Discord auto-archive entry):

- If `home_plans.is_sticky_eddy(channel_id)`: **skip cool** (preferred day one) — leave thread active / cancel archive if API allows; log `sticky_home_plan_skip_cool`.
- Fallback only if unarchive-cancel impossible: allow cool but **never delete** river pin; Continue must unarchive + restore. Prefer skip.

Dissolve path: if home plan, prompt fate of artifact (keep file default); clear YAML + unpin.

---

## Slice 5 — Attunement packet

When a practitioner message arrives in a home eddy (or on Continue):

- Inject into Turtle context (substrate block or system appendix): plan title, `artifact_path`, artifact body or truncated summary (cap tokens — follow existing CE/summary patterns), pointer to latest eddy note if present.
- Reuse patterns from `continuity_engine.render_substrate_packet` / scope blocks — **do not** dump full Discord history.

---

## Slice 6 — Quiet perform writes

- Helper: `home_plans.patch_artifact(practice_dir, plan_id, new_body | append_note)` with atomic write.
- Surface to Turtle via existing tool path if one writes notes; else document `!pin`-adjacent operator command deferred — **minimum:** Turtle can be instructed that edits go through a small internal tool registered for home eddies only.
- Ack pattern for dialogue: one-line confirmation after successful write (prompt/conduct hint). Full “gym tempo” quality is Mage dogfood, not a unit gate.

If tool registration is too large for AFK, ship helper + unit tests and a **prompt/conduct one-liner**; mark dialogue tool wiring as residual in chapter close.

---

## Slice 7 — Close the chapter

1. Amend `TURTLE_SPEC.md` (§5 working-plan river pins; §8 sticky home eddies; §11.5 home binding).  
2. Update `docs/ux/artifact-access.md` if behavior text needs “how to pin a plan.”  
3. `docs/turtle-talk.md` `!pin` row.  
4. Traceability matrix rows + Action column.  
5. `scripts/shake_home_plans.py` — offline: YAML bind, sticky skip, card payload shape; live (optional): pin → Continue URL present → stop pinning cleans YAML.  
6. `docs/learnings.md` harvest.  
7. Functional gate: `./scripts/spirit_verify.sh`; offline shakes; live subset if Discord touched (`shake_lifecycle` + new shake).  
8. Deploy: restart **both** `com.turtle.discord` and `com.turtle.river` (shared modules). Dyad approval before kickstart.  
9. Mark design chapter Status → Implementing / Shipped.  
10. Magic `desk/craft/backlog.md` — check off or move `[2026-07-17-pinned-home-eddies]` when shipped.

---

## Tests (minimum)

| Test | Asserts |
|------|---------|
| `tests/test_home_plans.py` | bind 1:1; refuse duplicate artifact/eddy; sticky flag; clear |
| `tests/test_cmd_pin_home.py` | eddy bind path (mocked Discord); river legacy pin still works |
| Cool unit | sticky eddy does not `mark_cooled` |
| UI payload | card has Continue + Open + Stop; no full body |

---

## AFK execution order

```text
claim marker → Slice 0 → 1 → 2 → 3 → 4 → 5 → 6 (helper; tool residual OK) → 7
spirit_verify.sh after each slice that adds tests
shake_home_plans offline before deploy
live smoke on operator river after both-bot restart
```

**Do not** expand into portable load or Nesrine fanout in this chapter.

---

## Recognition tests (Mage gate — after Spirit gate)

From design chapter — Spirit does not mark UX done:

1. River pin → Continue → same home eddy (no sidebar archaeology).  
2. Note mid-session lands on artifact file.  
3. Cool policy leaves pin restorable / sticky.  
4. No side-panel language in product copy.

---

## Blocker protocol

If `PIN_MESSAGES`, thread unarchive, or jump URL fails on Mini: document in this file under `## Blockers`, keep slices 0–1 green, pause Discord slices for Mage.

---

## Status

**Shipped 2026-07-17** — dogfood green (pin card, Continue, Open, Stop delete). Split-bot client mends: `c7b0932` / `58d6c3d` / `b869a6c`. Residual Slice 6 quiet write → crystallization chapter.
