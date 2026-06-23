# Practitioner journeys

End-to-end walkthroughs. Detail lives in topic docs — these are the composed paths.

**Index:** [README.md](README.md)

---

## Target UX (2026-06-20) — not yet shipped

**Onboarding (generic):** personal AI on Discord — install, open an eddy, talk. Flows optional for structured use; Navigator as a **sample flow** when exploring. Full copy:

→ **[onboarding.md](onboarding.md)**

**Journeys (flows + bootstrap):**

→ **[flow-library-journeys.md](flow-library-journeys.md)**

**Quick paths (target):**

```
Layer 1 — daily use (default)
  [new eddy] → enter → first message → river added turtle → dialogue
  (flow picker visible; ignoring it is fine)

Layer 2 — try a flow (optional)
  [new eddy] → flow library → Navigator (or other)
  → river added turtle → Turtle bootstrap → guided dialogue → checkpoint

Return — Navigator with prior checkpoint
  [new eddy] → Navigator → bootstrap reads last commit → continue

Lens — load flow mid-conversation (future)
  … talking … → flow library → load flow
  → bootstrap from thread history → no auto-rename → optional [Rename thread]
```

River bar target: **`[ 🌀 new eddy ]` only** (no `flow menu`). Shelter retired; blank eddy is Layer 1.

---

## Legacy journeys (current shell)

The running bot still uses river-bar flow menu and River modal intake for Navigator. Use these for dogfood and shakedown until the in-eddy flow library chapter ships.

### Open blank eddy from bar

```
River timeline: … → click [new eddy]
  → bar gone → thread card "new eddy" appears
  → fresh bar below
  → enter thread → first message
  → thread renames → river added turtle → reply
  → lifecycle bar appears at thread bottom (Checkpoint · Release · Dissolve)
```

→ [eddy-entry.md](eddy-entry.md) · [eddy-lifecycle-bar.md](eddy-lifecycle-bar.md)

### Open intake-free flow eddy from bar (Shelter) — retiring

```
Click [flow menu] → select Shelter
  → thread card titled "Shelter" (not "new eddy")
  → enter thread → River orientation embed (what flow is, checkpoint status)
  → first message → river added turtle → Turtle reply in flow voice
  → lifecycle bar at thread bottom after first message
  → 15 min idle → flow checkpoint + session note (if thresholds met)
```

**Target:** remove Shelter from ship set; use Journey 1 (blank eddy) instead.

→ [flows-and-intake.md](flows-and-intake.md)

### Open intake flow eddy from bar (Navigator) — superseded by target

```
Click [flow menu] → select Navigator
  → thread titled "Navigator"
  → orientation embed: entry contract + [Prepare] [Skip — I'll talk]
  → Prepare → modal (intention, territory) → summary embed + [Edit] [Begin with Turtle]
  → Begin → thread renames from intake → river added turtle → Turtle opening
  → dialogue continues → lifecycle bar after first post-intake message
  → checkpoint on idle / bar / !checkpoint / !release
```

**Target:** in-eddy flow library + Turtle bootstrap — see [flow-library-journeys.md](flow-library-journeys.md).

→ [flows-and-intake.md](flows-and-intake.md)

---

## Hosted river claim

Operator provisions with `!admin river-key <name> <emoji> [de|en]` and sends the channel invite privately.

```
Guest opens invite → private claim room (pinned instructions)
  → sends river key emoji as single message
  → bind + channel rename + permissions lock
  → onboarding embed (Fluss / Wirbel or EN equivalent)
  → eddy bar at bottom
Guest opens eddy from bar → first message → river added turtle → Turtle reply (practitioner voice)
```

Operator river stays separate; hosted content must not appear in operator proposals verbatim.

→ `docs/operations/hosted-river-boundaries.md` · `docs/chapters/design-hosted-river.md`

**Target onboarding copy for guests:** generic Layer 1 — see [onboarding.md](onboarding.md); optional Navigator mention at end.

---

## Drop text in river (no eddy yet)

```
Practitioner posts in river
  → River acts (ack / flow offer / error only)
  → bar moves to bottom
  → practitioner uses bar or contextual button when ready
```

**Target:** no standing flow offers on river messages; use bar → eddy → flow library.

→ [river.md](river.md)

---

## Drop URL in eddy

### URL-primary (auto-read)

```
Practitioner: https://example.com/article — what's the argument?
  → Reading… embed (silent)
  → typing during fetch
  → Read embed: host · 8,000 / 29,830 in context · box/intake/… if spilled
  → Turtle reply grounded in excerpt (no fetch prose in voice)
```

Thread title stays River-owned (no link-read rename fight in split-bot).

→ [link-reading.md](link-reading.md)

### Incidental link (long message)

```
Practitioner: long paragraph … and also this article https://…
  → Turtle reply to the message (no fetch yet)
  → Link detected · [Read article] [Skip]
  → (Read) fetch + Read embed + second Turtle turn with extract
```

→ [link-reading.md](link-reading.md)

---

## Explicit release

```
Practitioner: !release
  → checkpoint runs (if thresholds met)
  → history cleared
  → release embed
  → chronicle line on checkpoint
```

→ [sessions.md](sessions.md)
