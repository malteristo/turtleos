# Practice artifacts — curated shelves

**Status:** Shipped v1 (2026-06-29) — `!artifacts` + allowlisted `!read` / `!ls` / `!search`.  
**Canonical law:** [TURTLE_SPEC.md](../../TURTLE_SPEC.md) §11.5  
**Chapter seed:** Magic `floor/drafts/file-access-on-turtleos-chapter-seed.md`

---

## What this is

Practitioners build up **practice artifacts** — sessions, flow notes, saved links — on their machine. They should **feel ownership** without learning paths, YAML, or runtime layout.

**Artifact** = practitioner-owned material turtleOS lets you see (stored as markdown on disk). It is not "every file on the computer" — not proposals, logs, runtime JSON, or host tooling.

The artifact viewer is **shelves of your practice** — not a filesystem tree, not Magic desk sync.

---

## Shelves (v1 target)

| Shelf | What it shows | Source (operator doc only) |
|-------|---------------|----------------------------|
| **Sessions** | Checkpoint and session notes | `sessions/` |
| **Notes** | Flow outcomes (Navigator, Companion, …) | `state/notes/` |
| **Archives** | Dissolved thread captures | `thread-archive/` |
| **Chronicle** | Human-readable practice timeline | `chronicle/surface.md` |
| **Saved links** | URLs you saved or fetched | `link-resonance/` + fetch cache (summary UI) |
| **Intake** | Your pasted captures | `box/intake/` |

Hosted practitioners with portable surface files also see shelves backed by `boom.md`, `bright.md`, `compass.md`, etc. — still as **named shelves**, not filenames in a tree.

**Not artifacts (hidden):** proposals, runtime JSON, dialogue logs, signals, share metadata, other people's practice, anything under `~/turtleos/`.

**Proposals:** Host diagnostics only — never shown to hosted practitioners.

---

## How you open it

**Today:** `!artifacts` for shelves; `!read`, `!ls`, `!search` scoped to the same allowlist.

**Target v1.1:** **Artifacts** on the eddy lifecycle bar (after you have something saved, or after your first checkpoint).

We do **not** pop up browsers unprompted. After checkpoint, a single line like "Saved to Sessions — try `!artifacts`" is enough.

Layer 1 users who only chat may never open Artifacts. That is fine.

---

## What you can do

| Action | Supported |
|--------|-----------|
| Browse and read | Yes |
| Search your corpus | Yes |
| Change content | Ask Turtle in the eddy (or complete a flow) — not edit markdown directly |
| Export an artifact | Yes — `.md` attachment in Discord (v1) |
| Delete artifacts | No — use dissolve/archive on eddies |

Sharing practice with someone else: use **`!share`** to open a shared eddy, not "send this artifact."

---

## Operator vs practitioner

| Role | Extra access |
|------|----------------|
| **Hosted practitioner** | Tier 1 shelves on their practice root only |
| **Operator (native root)** | Same shelves + optional operator-only material (proposals, craft reports) |
| **Shared space member** | Shelves on the **space** root; never another member's private artifacts |

---

## Design intent

- **Sovereignty:** Your artifacts live on your machine (or your hosted root). Export proves it.
- **No sysadmin cosplay:** Paths like `thread-state/registry.yaml` are implementation details.
- **One mental model:** Viewer, web read (future), and `!read`/`!ls` share the same allowlist once shipped.

---

## Implementation (when built)

| Piece | Location |
|-------|----------|
| Allowlist enforcement | `practice_io.is_readable`, `artifact_viewer.py` |
| `!artifacts` command | `cmd_practice_io.py`, `commands.py` |
| Shelf pagination | Discord embeds + `split_message` |
| Bar button | `eddy_lifecycle_bar.py` (v1.1) |
| Shakedown | `scripts/shake_*.py` extension (TBD) |

**Review checklist:** [review-checklist.md](review-checklist.md) — any UX-touching slice updates this doc and §11.5 together.

---

## Rejected

- Full practice-root tree in Discord (`!ls` everywhere) as the **product** experience — power-user escape hatch only, narrowed over time.
- Calling runtime paths "files" in practitioner copy — use **artifacts** for the allowlisted corpus only.
- Practitioners browsing `proposals/` — host diagnostics, not practice.
- Raw `chronicle/deep.jsonl` in viewer — use `surface.md` + jump links.

See also [rejected.md](rejected.md).
