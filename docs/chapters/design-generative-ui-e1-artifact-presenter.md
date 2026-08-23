# Design: Generative UI E1 — Artifact presenter

**Status:** Shipped + dogfood complete (2026-06-29) — Mini at `3e89b2f`  
**Experience (read first):** [generative-ui-e1-experience.md](../ux/generative-ui-e1-experience.md)  
**Parent:** Magic `desk/proposals/2026-06-29-generative-ui.md`  
**Spec trace:** TURTLE_SPEC §11.5–11.5.5, §9.6  
**Tier:** Controlled generative UI (rules pick kit blocks; no LLM layout)

---

## Goal

Replace static markdown catalog screens for artifact browsing with **intent-composed Discord surfaces** — reusing the seneschal/River act path practitioners already trust.

**One sentence:** `!artifacts` answers *why are you looking?* not *here is every shelf*.

---

## Non-goals (E1)

- LLM-chosen layout
- Browser SPA home / Level 1 generated HTML
- Generative search result layouts (E2 candidate)
- TURTLE_SPEC §11.5.6 amendment (after dogfood)
- Renaming shelves or changing allowlist

---

## Architecture

### New module: `artifact_presenter.py`

Single entry point:

```python
def compose_artifact_surface(
    intent: ArtifactIntent,
    *,
    mage_type: str | None = None,
    practice_dir: str | None = None,
) -> ArtifactSurface:
    ...
```

**`ArtifactIntent`** (enum or tagged union):

| Intent | Trigger |
|--------|---------|
| `browse_default` | `!artifacts` with no args |
| `browse_shelf` | `!artifacts <shelf>` |
| `browse_all` | `!artifacts --all` (operator/shakedown) |
| `post_checkpoint` | After `!checkpoint` / `!release` when Tier-1 write occurred |

**`ArtifactSurface`** (render package):

| Field | Purpose |
|-------|---------|
| `content` | Optional markdown body (embed description or compact `-#` line) |
| `embed` | Optional `discord.Embed` spec (title, fields, footer) |
| `view` | Optional `discord.ui.View` with Open / Export acts |
| `template_id` | Telemetry string e.g. `recent_cross_shelf`, `shelf_listing`, `operator_catalog` |

**Renderer** in `cmd_practice_io.py` (and checkpoint path in `cmd_sessions.py`):

1. `surface = compose_artifact_surface(intent, ...)`
2. `await message.reply(content=..., embed=..., view=..., mention_author=False)`

River integration deferred to E1.1 — same composer, different caller.

### Data: recent cross-shelf

New helper in `artifact_viewer.py` (or presenter):

```python
def list_recent_artifacts(*, limit: int = 8, mage_type: str | None = None) -> list[RecentArtifact]:
    # mtime across iter_artifact_files(); include shelf label + display name
```

Prefer **filesystem mtime** for E1 (matches pulse spirit; no new persistence). Optional: weight sessions/notes higher in E1.1.

### UI kit (E1 blocks)

| Block | Use |
|-------|-----|
| Embed title | `Recent` / `{Shelf title}` / `Practice artifacts` |
| Embed fields | Up to 8 items: `display · shelf` (no command syntax) |
| Open button | Label: truncated filename; act: open browser read path (same as `!read` success path) |
| Export button | Secondary; only on shelf listing rows if room (max 3 buttons per row — prefer Open-only on recent view) |
| String select | When recent items > 3 and ≤ 25: options = paths; one row |
| Footer | `Search: !search · All shelves: !artifacts --all` (practitioner); operator footer may omit |

**Open act execution:** Reuse River act machinery — register `!read <path>` in contextual allowlist OR dedicated `artifact:open:{path_hash}` custom_id handler that calls existing read/browser embed logic from `cmd_read`.

**Pattern 6 fallback:** If recent list empty → current `format_shelf_menu` but **omit empty shelves** and **strip command-as-primary copy** from item lines (keep footer hints).

---

## Intent rules (E1)

### `browse_default`

1. Load recent artifacts (limit 8, non-empty paths only).
2. If **≥1 recent**:
   - Embed: title **Recent**, fields or description listing items with shelf names.
   - View: Open buttons for top 3 **or** select menu if 4–8 (Discord constraint).
   - Footer: browse/search hints; no per-line `` `!read` ``.
3. If **no recent**:
   - Fallback embed: non-empty shelves only (count > 0), shelf names as fields with blurb — **no** `` `!artifacts sessions` `` in every line; optional `[Browse sessions]` button per shelf if ≤3 non-empty shelves.
4. Never show empty shelves in default view.

### `browse_shelf`

1. Same listing as today but:
   - Item lines: human display name only in embed/list.
   - View: up to 3 Open buttons for first items **or** select for 4+.
   - Remove `` `!read` / `!export` `` from markdown lines.
2. Export remains available via select secondary action or second row in E1.1 if needed.

### `browse_all`

1. **Preserve today's behavior** for Spirit/shakedown: full `format_shelf_menu` including empty shelves and command hints.
2. Trigger: `--all` flag only (first arg).

### `post_checkpoint`

1. Replace `checkpoint_artifact_hint()` text-only return with optional `ArtifactSurface`:
   - Compact line: `Saved to Sessions — {filename}`.
   - View: single **[Open]** button when `session_note` or `flow_write` path known.
2. `cmd_sessions.py` sends reply + view after checkpoint success.
3. Seneschal checkpoint offer (`!checkpoint` button) unchanged — this is **post-success** affordance.

---

## Discord constraints (hard)

| Rule | Enforcement |
|------|-------------|
| Max 5 action rows | Recent: 1 row buttons or 1 row select |
| Row = buttons XOR select | Presenter chooses by count |
| `custom_id` ≤ 100 bytes | Hash path + store lookup, or reuse act encoding pattern from `eddy_lifecycle_bar.py` |
| §11.5.5 | Open still browser-first when `PRACTICE_WEB_BASE` set; no full body in chat |
| Practitioner copy | No `` `!read` `` as primary UI; footer hints OK |

---

## Files to touch

| File | Change |
|------|--------|
| `artifact_presenter.py` | **New** — intent → surface |
| `artifact_viewer.py` | `list_recent_artifacts()`; optional `format_shelf_menu(..., include_empty=False)` |
| `cmd_practice_io.py` | `cmd_artifacts` → presenter; parse `--all` |
| `cmd_sessions.py` | Post-checkpoint surface + view |
| `commands.py` | Open act in allowlist if needed |
| `eddy_lifecycle_bar.py` | Optional: shared `OpenArtifactView` if not duplicated |
| `tests/test_artifact_presenter.py` | **New** — intent rules unit tests |
| `tests/test_artifact_viewer.py` | Recent list tests |
| `tests/test_cmd_practice_io.py` | Mock reply asserts embed/view |
| `scripts/shake_artifacts.py` | Update expectations + `--all` live probe |
| `docs/ux/artifact-access.md` | Practitioner-facing behavior (after ship) |

---

## Acceptance criteria

### Practitioner experience

- [x] `!artifacts` with corpus shows **Recent** first; empty shelves hidden.
- [x] Practitioner can open a recent artifact **without typing** `!read`.
- [x] `!artifacts sessions` (etc.) shows shelf content with tap-to-open, not command copy per line.
- [x] Post-checkpoint message includes **[Open]** when a session/note path was written.
- [x] With `PRACTICE_WEB_BASE` set, Open uses browser embed path (same as `!read`).

### Operator / regression

- [x] `!artifacts --all` shows full catalog (today's menu) for shakedown.
- [x] Allowlist denials unchanged (`proposals` for practitioner, etc.).
- [x] `!export`, `!search`, `!read` still work unchanged.

### Automated

- [x] `pytest tests/test_artifact_presenter.py tests/test_artifact_viewer.py tests/test_cmd_practice_io.py` pass.
- [x] `python scripts/shake_artifacts.py` offline pass.
- [x] `python scripts/shake_artifacts.py --live` pass on Mini (Mage dogfood 2026-06-30; re-run before release sign-off).

---

## Shake updates

| Check | Change |
|-------|--------|
| `check_shelf_menu` | Keep for `--all` / `format_shelf_menu(all=True)` |
| New `check_recent_compose` | Unit-test presenter `browse_default` with fixture corpus |
| Live `!artifacts` | Accept **Recent** title OR legacy title during rollout window — then tighten |
| New live `!artifacts --all` | Assert `Practice artifacts` + shelf hints |
| Live deny probe | Unchanged |

---

## Rollout

1. **Implement on Forge** — unit tests green. ✅
2. **Offline shake** — local turtleos repo. ✅
3. **Deploy Mini** — `git pull`, restart river + discord services, live shake. ✅
4. **Mage dogfood** — checkpoint, browse, search, export refinement. ✅ 2026-06-29 / 2026-06-30
5. **Learnings** — `docs/learnings.md`, `docs/ux/generative-ui-e1-experience.md`. ✅
6. **Docs + spec proposal** — `artifact-access.md` ✅; §11.5.6 deferred.

---

## E1.1 (shipped 2026-06-30)

- [x] Post-search Open act row on top hits
- [x] River `present_artifacts` act type → same composer
- [x] Export on second button row (shelf ≤3); select → attachment preview
- [x] Standing river + eddy bars; bar active state during artifact browse
- [ ] `generative-ui-kit.md` doc extraction — deferred

---

## Open decisions (default if Mage silent)

| Question | E1 default |
|----------|------------|
| Operator flag | `--all` on `!artifacts` |
| Recent source | mtime across all Tier-1 artifacts |
| Button vs select threshold | ≤3 buttons; 4–8 select; >8 truncate + “use !search” |
| Checkpoint Open | Only when exact path known from checkpoint write |

---

## Mage gate

**`.`** on this spec → Spirit implements E1 on turtleOS (Forge), runs tests + offline shake, proposes Mini deploy block for Mage copy-paste.

**Redirect** → name what to trim (e.g. defer post-checkpoint Open to E1.1).
