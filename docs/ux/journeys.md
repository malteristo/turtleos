# Practitioner journeys

End-to-end walkthroughs. Detail lives in topic docs — these are the composed paths.

**Index:** [README.md](README.md)

---

## Open blank eddy from bar

```
River timeline: … → click [new eddy]
  → bar gone → thread card "new eddy" appears
  → fresh bar below
  → enter thread → first message
  → thread renames → river added turtle → reply
  → lifecycle bar appears at thread bottom (Checkpoint · Release · Dissolve)
```

→ [eddy-entry.md](eddy-entry.md) · [eddy-lifecycle-bar.md](eddy-lifecycle-bar.md)

---

## Open intake-free flow eddy from bar (Shelter)

```
Click [flow menu] → select Shelter
  → thread card titled "Shelter" (not "new eddy")
  → enter thread → River orientation embed (what flow is, checkpoint status)
  → first message → river added turtle → Turtle reply in flow voice
  → lifecycle bar at thread bottom after first message
  → 15 min idle → flow checkpoint + session note (if thresholds met)
```

→ [flows-and-intake.md](flows-and-intake.md) · [sessions.md](sessions.md) · [eddy-lifecycle-bar.md](eddy-lifecycle-bar.md)

---

## Open intake flow eddy from bar (Navigator)

```
Click [flow menu] → select Navigator
  → thread titled "Navigator"
  → orientation embed: entry contract + [Prepare] [Skip — I'll talk]
  → Prepare → modal (intention, territory) → summary embed + [Edit] [Begin with Turtle]
  → Begin → thread renames from intake → river added turtle → Turtle opening
  → dialogue continues → lifecycle bar after first post-intake message
  → checkpoint on idle / bar / !checkpoint / !release
```

Skip path: orientation → practitioner’s first message → `river added turtle` → normal first-reply flow (no auto-opening).

→ [flows-and-intake.md](flows-and-intake.md) · [eddy-lifecycle-bar.md](eddy-lifecycle-bar.md)

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

---

## Drop text in river (no eddy yet)

```
Practitioner posts in river
  → River acts (ack / flow offer / error only)
  → bar moves to bottom
  → practitioner uses bar or contextual button when ready
```

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
