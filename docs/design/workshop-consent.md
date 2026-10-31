# Workshop consent — a tap before sensitive context leaves the house

**Date:** 2026-10-12
**Status:** Destination. Not built. Sanctioned in direction by the operator on 2026-10-12 (his words: share only what he is willing to give the client machine; sensitive context waits for his accept in his home channel; cards in plain text, the technical description under the hood). Each slice is sanctioned when it starts.
**Spec:** TURTLE_SPEC §3.1 (the practitioner owns their practice), §15.5 (another client reaching a house).
**Companions:** [mcp-access-point.md](mcp-access-point.md) (D18 receipts, D19 workshop source), [magic-channel.md](magic-channel.md).

Practitioner-visible change. Four artifacts first (`docs/development.md` §12).

## The gap it closes

Today a `workshop-reader` grant serves any file of the practice repository. The only trace is a receipt after the fact, at most one per ten minutes, worded for engineers ("files of your workshop (the practice repository)"). The practitioner learns what left the house after it left, and the card does not say what kind of thing it was.

---

## 1. Press release

When something connected to your house is about to read the kinds of thing you keep private, your home channel asks first, in your own words: *"Cursor on your laptop wants to read your health notes. Allow once · Not now."* Nothing is sent until you tap. Everything else it reads is summarised afterwards in one plain line: *"Cursor on your laptop read 14 files from your practice. Nothing private."* You always know which client read which kind of thing. How it was done stays in the audit log.

## 2. Happy path

```
Cursor:   (connected, reads the practice's bearings and intentions)
River:    Cursor on your laptop read 9 files from your practice. Nothing private.

Cursor:   (asks for a file the practice marks as health)
Cursor:   "Waiting for the owner to allow this — a card is in their home channel."
River:    Cursor on your laptop wants to read your health notes.   [Allow for this session] [Not now]
Kermit:   (taps Allow)
River:    Allowed: health notes, for this session only.
Cursor:   (the read now succeeds; the session ends or goes idle; the allowance ends with it)
```

*Invisible: the glob that matched, the grant id, the git verb, the audit path.*

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | A read of a file the practice marks sensitive returns no content until he taps Allow. A tap that never comes is a refusal that says why, in words an agent can relay. | The file arrives and the card follows. A reworded path, a symlink, a search hit or a listing leaks the content or a line of it. | Automated: planted sensitive and plain files; read, search, tree, and `?since` each refuse the sensitive one without a tap. Mutation: skip the check on the search path → fails. Positive control: the same read succeeds after an allow. |
| 2 | The practice declares what is sensitive and gives each kind a plain label; the server names no practice file. A practice that declares nothing gets no gate and says so in its own brief. | The server hard-codes a practice path. A declared pattern silently matches nothing. | Automated: the same server, two registries, two behaviours. A declared pattern that matches no file in the release is reported at the grant, not discovered later. |
| 3 | The ask card says, in plain text, which client and which kind of thing. No grant id, path, verb or hash appears on it. | An engineer's sentence reaches the card. | Automated: a copy test over the card text (en and de) refusing identifiers; positive control: the audit record still carries them. |
| 4 | An allowance covers one kind of thing, for one session, and ends with it. Another client, another session, or another kind of thing asks again. | An allowance outlives the session or covers more than it named. | Automated: allow health, read relationships → asks; end session, read health → asks. |
| 5 | Everything else the client read is one plain line afterwards: which client, how many, "nothing private" only when true. | The line says "nothing private" and a private file was read. | Automated: read plain files only, assert the line; read one allowed sensitive file, assert it is named by kind instead. |
| 6 | An ask for a kind he has just refused is not repeated within the session. | A client that is refused asks again every minute and his home channel fills. | Automated: refuse, retry, assert one card. |

Mechanism-blind: another transport still has to give "I am asked before something private leaves, in my words, and I can see afterwards what left."

## 4. Abandon line

Stop if a sensitive file can reach a client without his tap by any route (read, search, listing, a ref's `?since`), or if the card is ever more cryptic than the sentence he would say aloud.

---

## The shape (for implementers)

- **Sensitivity is declared by the practice** in the registry beside the workshop: `mages.<member>.workshop.sensitive: {<label>: [<glob>, …]}`. The label is the plain-language kind shown on the card ("your health notes"). The server holds no practice path.
- **Granularity, my position:** one tap covers one *kind* for one *session*. Per file would make an arrival unusable; per grant would make the tap meaningless. If this turns out too chatty or too loose, the criteria above are where it changes.
- **The ask is a receipt the other way round.** D18 already queues receipts into the owner's private root and River posts them. An ask is the same path with buttons and a verdict file the server reads, the way pitch verdicts work. The session holds the refusal until the verdict arrives or the session ends.
- **Client name** is what the owner named the grant when he offered it. The card does not invent one.
- **The after-the-fact line replaces the current workshop receipt copy** (`receipts.py`, key `workshop`). The reader and audit stay as D19 built them.
- **Not decided:** whether a grant for another person's workshop (a practitioner who is not the operator) defaults to gating everything until the practice declares its kinds. Rec: yes, gate everything until declared. Decided when a second workshop exists.
