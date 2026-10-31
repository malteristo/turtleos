# Your connections, in the rooms that are yours — destination

**Date:** 2026-09-28
**Status:** Destination. X in craft, and the chat list, are live as of 2026-10-06. Further MCP practice waits.
**Spec:** TURTLE_SPEC §3.1 (the practitioner owns their practice), §15.5 (another client reaching a house).
**Refined 2026-10-14:** a room is a ceiling and a per-person switch, not only a hard-coded name. See [channel-connections.md](channel-connections.md). "No grid" still holds: the switch is offered in the room, and the card shows where each service answers.
**Companions:** [mcp-access-point.md](mcp-access-point.md) (this house as a guest door), [own-channel-model.md](own-channel-model.md) (a room follows its person).

Practitioner-visible change. Four artifacts first (`docs/development.md` §12).

---

## 1. Press release

You sign in to a service once. Your home channel and your health channel both know that sign-in. You do not set it up again for the second room.

A service the whole house shares is simply there. A service that is yours is yours alone. The person you share a room with has their own sign-in, and a question of yours does not use it.

When you ask in a room you share, the reply says whose sign-in it used and which service. Asking there means the room hears the answer.

If some of your context lives in another house, you can ask for it from here. The reply says which house it read, and it brings back only what that house allows you.

The house you are standing in already holds your context. You do not connect to it in order to see what it already has.

The person who runs the machine can tell whether a connection is healthy and can cut one off. They cannot see your secret, and they cannot see what was fetched.

---

## 2. Happy path

```
Sam, in her home channel:

Sam: !mcp
Turtle: (only Sam sees this)
        Coming in — clients that can read your context here
          Cursor on Sam's laptop — ready, last used yesterday
        Going out — services this house can call for you
          Calendar — yours, ready
          Search — the house's, ready
        Test, pause, or remove one. A new personal service asks you to sign in.

Sam, later, in her health channel:

Sam: What is on my calendar tomorrow?
Turtle: [Calendar — Sam's]
        Tomorrow is clear until 15:00.

Sam, in the family room, where her partner also has a calendar:

Sam: What is on my calendar tomorrow?
Turtle: [Calendar — Sam's]
        Tomorrow is clear until 15:00.

Partner: And mine?
Turtle: [Calendar — Partner's]
        Yours has the morning blocked.

Sam: What did I write down in the other house about the trip?
Turtle: [The other house — Sam's notes there]
        One note, from March: …
```

The partner never sees Sam's list. Sam never sees the partner's secret. A question from the partner does not come back with Sam's calendar.

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | A person signs in to a personal service once. A question in their home channel and a question in their health channel both use that same sign-in. | The second room asks them to sign in again, or the two rooms diverge after a few days. | Automated: one stored sign-in resolves for two rooms that person owns. Live: the first time a second room of theirs uses it. |
| 2 | Another person's sign-in is not used and not shown. In a shared room, each asker's question uses only their own. | Her question returns his calendar, or his list shows her connection. | Automated: two members, one shared room, cross-use refused and the other list absent. Mutation-checked. |
| 3 | A reply that used a connection says whose it was and which service. A reply in a shared room is how the room learns that. | A shared-room answer arrives with no name, or names the service and uses the other person's sign-in anyway. | Automated: the visible reply carries the name; the other sign-in is not called. |
| 4 | Someone helping in a health channel cannot use the subject's connections there, and cannot use their own there. | Support's question reads the subject's calendar, or support's own calendar answers inside that room. | Automated: support refused both ways; the subject still can. |
| 5 | Context asked from another house is only what that house allows this person, and the reply names the house. | A narrowed allowance there still returns the wider set here, or the reply could be this house's notes. | Automated: a fixture allowance returns only its scope; the reply names the other house. |
| 6 | This house's own context still answers when the guest door is down. | Stopping the guest door blinds a question about notes that are already on this machine. | Automated: guest door stopped, resident read still returns a planted note. |
| 7 | The person who runs the machine sees every connection's health and can cut one off, and does not see the secret or what it fetched. | A new kind of connection is missing from that view, or a planted fetch shows up in it. | Automated: enumerate connections; planted content absent. Mutation-checked. |
| 8 | A secret typed while connecting never appears in the channel. | The channel history contains the secret. | Automated: the channel transcript fixture has no secret field. Live: the first real sign-in, read back from the channel. |

---

## 4. Abandon line

Stop if a person must sign in twice for two rooms they own, if one person's question uses another person's sign-in, or if this house cannot read its own context unless the guest door is up.

---

## The shape (for implementers)

Decisions from the sitting that sanctioned this. The criteria above do not name them, so a different shape can still pass.

- **One door, the person who typed.** The list is visible only to them, including in a shared room. Who typed decides whose configuration loads. A room's shared choice is a different command; this one is a person's.
- **Two directions.** Coming in: clients allowed to read this person's context here. That door is [mcp-access-point.md](mcp-access-point.md). Going out: services this house calls. Some are the house's, set up once, no personal secret, available in every room. Some are personal: one sign-in per person per service.
- **A connection belongs to a person, not to a room.** It is available in every room that is theirs (home, health, craft, the eddies under those). An eddy does not keep its own list. There is no grid of connections granted to channels.
- **A shared room uses the asker's connection, on that turn, and names it.** It does not gain a standing copy. Both people's calendars answering either person's question is a later yes: one yes per person per room, shown on each person's list. Not in the first build.
- **Another house is an ordinary personal connection.** This house is a client of that house's guest door, under a grant that house already knows how to give. The call returns that grant's scope. It is not a room of theirs embedded here.
- **This house does not connect to its own guest door.** The resident and the guest call the same operations. The resident calls them directly. A script or a second app on the machine is a guest and uses the guest door. Turtle is the resident.
- **The call carries the question, not the room's history.**
- **Wide rooms.** Asking in a room everyone can see publishes the answer there. The reply names the service and whose connection it was.
- **Leaving.** When a person leaves, their connections leave with them.
- **The operator** sees health and can revoke, for every connection. The operator does not see secrets or fetched content. Same split as the guest door's operator profile.
- **A browser opens only to finish a sign-in** this chat cannot finish. The list, a pause, and a removal stay in the chat, and a key is not typed into the channel. The list shows the check River already made. A page that lists everyone's connections waits until that list no longer fits the chat.
- **Practices are not part of this door.** A practice asks for a capability. The capability uses the person's connection when they have one, and says so when they have not signed in.
- **First outgoing service, when building starts:** a search the person already uses from outside the house. Not a schedule that checks it while they are away. That service is X. It closed in craft on 2026-10-06. The checklist under "What the first service taught" is how the next one starts.

## What the first service taught (X, closed 2026-10-06)

The next outgoing connection starts from this. It does not start from a summary we write of the server's objects.

- The person signs in once. The secret stays in that service's own store. The file here names the person and their account, and nothing else.
- The practice asks. The door offers the connection only where that practice is allowed. For this first service, that room is craft.
- Turtle is shown the server's own tools and descriptions, and the manual `initialize` returns when there is one. A result is the object the server sent.
- What the practice rules out is absent from that list and refused if called. A prompt that says not to is not the grant.
- A value that makes one read return the body is added only on that read. The same field name on another tool is not the same request. The name printed in the tool list may not be the field that carries the body.
- The channel shows the act, once per kind of act. It does not list the calls and it does not show the object. The log records the length. The audit records the person, the service, the operation, and the decision. The text is not copied into a note. To see it again, return to the eddy or ask again.
- An attachment id is not the picture. Sight means the picture is fetched from the picture host and shown to the model for that turn, and not saved. A video arrives as its preview frame.
- A link that leaves the service is offered, not fetched, until the person accepts it.
- Who spoke has to survive a room refresh and the tool's own thread, or the call goes out as no one.
- A planted reply is not the live connection.

He used this in craft: a pasted post, his bookmarks, and articles those bookmarks point at. The picture path is in. He had not looked at a picture again after it landed when the chapter closed.

The chat list is in. `!mcp` posts a button. The list is a table — the connection, what it is, and the result of the check River already made — and only the person who pressed sees it. Pause and remove are on that row. He does not press Test. Pause keeps the sign-in and stops the calls. Remove asks once, then the sign-in record goes and that account's login on the machine is cleared. A new sign-in is still the browser on the machine.

River checks the login on its own. The check is not a reading of posts. A failure waits until the room is quiet, then tries once more. If it still does not answer, River says so in the channel it already uses for house issues, and says again when the login answers.

**2026-10-13, both directions.** `!mcp` had listed only what goes out (X). It now lists what comes in as well, on the same private reply: each program that can read the person's context, when it last asked, which of their notes / health picture / practice it can show (one press opens or closes each), and End, which asks once. Going out names the room a service answers in; for X that is the same value the door enforces (`ANSWERS_IN`), so the label cannot drift from the rule. Only the asker's own connections appear, and only the asker can change them. A change made here also edits the card in the home channel, so the two never disagree. Last used is a time only, never what was read. Not built, on purpose: a Test button for programs, signing in a new service from the chat, and a log of what was read (the receipts already say that).

Closed here on 2026-10-06. The sign-in already on the machine stays. Removing it to sign in again through `!mcp` would drop a working login, and `!mcp` cannot finish a new one. The next sign-in is still the browser on the machine.

Still later, as the next MCP practice, on purpose:

- Any room besides craft. When that opens, the table names the rooms. Craft is the first name. An eddy follows the room it is under and does not get its own switch. A shared room uses the asker's connection and the reply names whose.
- Another member's sign-in, through this same door, after the list is only theirs.
- Email, calendar, and a page of everyone's connections. On 2026-10-12 the magic channel named Gmail, Calendar and Drive as what that channel is owed, built when it can call a tool (`magic-channel.md` slice 5). Drive was already that slice. X stays in craft.

## Deliberately not in the first build

- A standing yes that lets either person in a shared room use both sign-ins.
- A page as the place connections are managed.
- A channel that declares its own wake condition.
- The resident reaching this house's files by calling the guest door.
- Nodes meshing. A later connection between two houses is one published offer, accepted by the person, named, and revocable. Rivers may notice an offer and propose it. They do not open each other's houses or exchange what was not offered. The local chapter comes before any of this.
