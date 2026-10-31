# One connection, and the card that opens what it shows

**Date:** 2026-10-12
**Status:** Built in the checkout. Not offered, not deployed. The offer is the post in the home channel, and it waits until this is on the Mini.
**Spec:** TURTLE_SPEC §3.1, §15.5.
**Companions:** [mcp-access-point.md](mcp-access-point.md) (D19, the two profiles), [magic-channel.md](magic-channel.md) (the seat).

Practitioner-visible change. Four artifacts first (`docs/development.md` §12).

## The gap it closes

A connection was one profile, and a profile was one family: rooms and health, or the workshop, never both. Picking up the workshop wrote a second entry the client showed under the same name, so an empty-folder summon read the rooms connection and never reached the practice. Closing one thing meant revoking the whole connection.

---

## 1. Press release

You have one connection to your house. After it connects, your home channel lists what it can show: your notes, your health picture, your practice. Each one is open or closed, and you change that whenever you like. Closed means the client cannot see it. Open means the next thing it asks can. You do not connect a second time to add one, and you do not lose the others to close one.

## 2. Happy path

```
River:    A connection to your own context is ready for an AI client.
Kermit:   (presses Connect, then the sentence in Cursor)
River:    Connected — laptop cursor, until 2026-11-11.

          What this connection can show. Open is visible to the client. Closed is not.
          your notes — closed
          your health picture — closed
          your practice — closed
          [Open your notes] [Open your health picture] [Open your practice]

Kermit:   (opens your practice)
River:    your practice — open

Cursor:   (the next read of the practice succeeds; a read of the health picture does not)
```

*Invisible: the grant id, the source id, the profile name, the git verb.*

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | A new connection of this kind shows nothing until he opens it. A thing he has not opened is absent from a read and from a search. | The first request returns his notes, or a closed thing. | Automated: a house grant with nothing open; search for a planted line is empty; open, the line is there; close, it is empty again. The second search is a new request, as the server does. |
| 2 | He can open his notes, his health picture and his practice on the same connection. A rooms-only connection cannot grow a practice. | Opening the practice on the rooms connection succeeds, or the combined connection drops one of the three. | Automated: the combined profile plans all three and starts with none; the rooms profile refuses the practice. Mutation: skip the reach check, the refusal disappears. |
| 3 | The card names the kind of thing. It does not name the grant, the source, or the profile. The same in his other language. | An id appears in the card text, in either language. | Automated: planted ids absent from the English and German card; a label present in each (positive control). The button says the same kind of thing. |
| 4 | Picking up the combined connection writes the one client entry and removes the workshop entry. A workshop-only pickup still uses its own name. | The combined pickup is named as a second entry, or a workshop-only pickup takes the rooms name. | Automated: the connect reply for the combined grant is `turtleos` and lists the workshop entry under `replaces`; the workshop-only reply is unchanged. The connect tool drops a `replaces` entry from the settings file. |
| 5 | What the client is told matches what is open. | The instructions name a practice he has closed. | Automated: with only notes open, the instructions say so and do not say the practice is open; after it is opened, they point at the bootstrap. |

Mechanism-blind: another transport still has to give "one connection, I open and close what it shows, and a closed thing does not leave the house."

## 4. Abandon line

Stop if a thing he has closed can be read or searched by the client, or if the card shows him an identifier he would not say aloud.

---

## The shape (for implementers)

- **`house` is a third profile.** It holds the room operations and the workshop operations. `reader` and `workshop-reader` stay, so a grant made for one family does not widen when this exists. An offer of `house` with no sources named starts with nothing open.
- **Open is the grant's source list.** Closing removes an id. The server already reads the grant on every request, so the next request is the enforcement. A source the profile cannot reach is refused, not dropped quietly.
- **The card is the announcement** of a picked-up offer, on that same message, restored after a restart. Labels come from the kind: notes, health picture, practice.
- **The client name.** A combined grant is `turtleos` and `replaces` the workshop entry. The connect tool removes those keys. A workshop-only grant is still `turtleos-workshop`.
- **Not in this slice:** offering the connection on the live house, revoking the two grants already on the laptop, craft or family as sources (they are not sources yet), consent-before-read of a sensitive file (`workshop-consent.md`).
