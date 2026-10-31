# Which connection answers in which room — the board

**Date:** 2026-10-14
**Status:** Sanctioned 2026-10-14 (board, order, Google on the ordinary APIs). Built and deployed 2026-10-14, inert until a Google client is on the Mini: the ceiling and switch (slice 1), the sign-in core, the return page and Calendar's read tools (slice 2). The `!mcp` Google card (connect, a switch per room, disconnect) is built the same day. Not built: the in-room "turn it on here?" offer, Gmail, Drive, the calendar write. The four artifacts (press release, happy path, criteria, abandon line) follow once the board is sanctioned (`docs/development.md` §12).
**Spec:** TURTLE_SPEC §3.1, §15.5.
**Companions:** [mcp-connections.md](mcp-connections.md) (the person owns the sign-in; the first service, X), [magic-channel.md](magic-channel.md) (slice 5 names Drive, GitHub, Gmail, Calendar), [calendar-suggestions.md](calendar-suggestions.md).

## What changes against mcp-connections.md

That document says *there is no grid of connections granted to channels*, and that a room is only ever a ceiling (`ANSWERS_IN = "craft"`, for X). His ask on 2026-10-14 is a switch per channel. Both hold if there are two layers and the second is never shown as a grid:

- **The sign-in is the person's.** Once per person per provider. Unchanged.
- **The room decides where it answers.** The house sets a ceiling for each kind of room. The person switches a service on inside that ceiling, one room at a time. A service is on in a room only when both agree.

## 1. Press release

You sign in to Google once. Then your rooms decide what answers where. Calendar answers in your home. Calendar, mail and files answer in craft. Your health rooms and the rooms you share with others never do. If you ask for something in a room where it is off, Turtle says so in one line and offers a button to turn it on, where that room is allowed to have it.

Turtle reads. It does not write by itself. A date it offers goes on your calendar when you press one button. A mail it helps with is a draft. Sending is yours.

## 2. Happy path

```
Kermit, in home:   !mcp
River (only he sees):
        What your house uses for you
        Google — not connected          [ Connect Google ]

        (he presses; a private reply carries one link; he approves once in the browser)

River:  Google — connected: Calendar, Gmail, Drive
        Calendar   answers in: Home       [ Change rooms ]
        Gmail      answers in: nowhere yet
        Drive      answers in: nowhere yet

Kermit, in craft:  What did the shop write me about the invoice?
Turtle: Gmail isn't on in this room. Turn it on here?   [ Turn on Gmail here ]

Kermit, in my-health:  What is on my calendar Friday?
Turtle: Not in this room.                                (no button)
```

*Invisible: the client id, the secret, the scopes, the tool names, the room's ceiling, the word "grant".*

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | A service answers in a room only when the house allows it there and he switched it on there. | A room the house forbids answers, or a switch he never pressed is on. | Automated: every room type against every service, both layers; a planted service answers only where both agree. Mutation: drop either layer and a case fails. |
| 2 | Health and shared rooms never list a service and refuse a call to one. | A health or shared room offers a tool, or a direct call returns data. | Automated: the tool list for each such room is empty; a called tool is refused. Positive control: the same tool is listed in a room that allows it. |
| 3 | One Google sign-in serves every room that is his. | A second room asks him to sign in again. | Automated: one stored sign-in resolves for two rooms. |
| 4 | The room's choice survives a restart and shows the same on the card and in the room. | The card says on, the room says off. | Automated: write, reload, read in both places. |
| 5 | A write is a button he presses. Turtle has no tool that writes by itself, and none that sends mail. | A write or a send route appears in a tool list, or runs without a press. | Automated: write and send tools absent from every list and refused if called. Positive control: they exist in the server's own list. |
| 6 | No secret appears in a channel, in a file the card reads, or in the log. | A token is in a transcript. | Automated: a planted secret is absent from the channel fixture, the card text and the log line. Live: the first real sign-in, read back from the channel. |
| 7 | A newly signed-in service is on in his home only. | It is on in craft the moment he signs in. | Automated: a fresh sign-in resolves on in home, off elsewhere. |

## 4. Abandon line

Stop if a service answers in a room the ceiling forbids, if a secret appears in a channel, if a person has to sign in twice for the same provider, or if Turtle can send mail.

## The board

Rooms as they are in `mage_registry.yaml` on 2026-10-14. *Look* is reading. *Act* is a write, and an act is always one button the person presses; Turtle never writes by itself.

| Room | Ceiling | Proposed on now | Why |
|---|---|---|---|
| Home (Kermit) | Calendar, Gmail, Drive | **Calendar**: look, and act through the date button | A date said in words already becomes an offer there (`keep_date`). The button should write the calendar he connected. This is the room `calendar-suggestions.md` names. |
| Craft | Everything he signs in to | **Calendar, Gmail, Drive** look; **X** (live). Act: Gmail drafts only | He named it. Mail and files are material for what is built. |
| Magic (not yet a room) | Calendar, Gmail, Drive, GitHub | The same three, when the room exists | Slice 5 of `magic-channel.md`. It is the room that acts, so its acts are the gated ones. |
| Home (every other member) | Same ceiling as his home | **Nothing until the member signs in.** Offered once, in their own words | Their sign-in, their choice. The offer is the same card. |
| My health (Kermit, solo) | None | None | Health picture is the most protected thing here. A calendar holding appointments is the reason to revisit, not now. |
| Health (shared) | None | None | Two people's rooms. |
| Family, Community, Quest | None | None | Shared rooms. The design rule already says the asker's own sign-in, named in the reply, one yes per person per room. That is later, and it needs a room to ask for it first. |
| Spirit (test room) | Whatever is being tried | Off. Switched on while a thing is verified, then off | The switch is exactly what that room needs. |
| Crypto (not yet a room) | Market data | Its own, when it exists | A house service, no personal sign-in. |

Not proposed: any service with no room that uses it. GitHub is for the magic room. The phone-files Drive folder is a Drive use, not a fourth service.

## How fine

| Level | Who decides | Grain |
|---|---|---|
| Sign-in | The person | Per provider. One Google sign-in covers Gmail, Calendar and Drive. The scopes asked are the ones for the services they picked |
| Ceiling | The house, by kind of room | Per room, per service. Health and shared rooms: none |
| Switch | The person | Per room, per service: **off**, **look**, **look and act** |
| Tool | Nobody | Not exposed. A server's tool list changes without telling anyone. The door sorts a tool as reading or writing (as `_writable` does for X) and refuses what the room's setting does not allow |

An eddy follows its room. It has no switch.

Writes, even when a room allows them:

- **Gmail:** drafts. Never sends. "He sends" is already how mail works here, and the three send routes (`send_message`, `reply`, `forward`) are absent from the list Turtle sees and refused if called.
- **Calendar:** one event on the person's primary calendar, by button. Family and another person's calendar: never.
- **Drive:** none in the first build.

## Where the switch lives

1. **At the moment of need.** In a room where a service is off, Turtle says so in one line and offers the button: *Calendar isn't on in this room. Turn it on here?* Most switches will be pressed this way. A room the ceiling forbids says *not in this room* and offers nothing.
2. **On the `!mcp` card.** Each service row shows where it answers (*Home, Craft*), and a menu of the person's own rooms changes that. Nothing in the card names a grant or an id.

A newly signed-in service is on in the person's home channel only.

## What the house can take over

The sign-in is the hard part, so it is named exactly.

- **Gmail, Calendar and Drive are Google's own hosted servers** (`gmailmcp`, `calendarmcp`, `drivemcp` at `googleapis.com/mcp/v1`). Nothing to run. Cursor's plugins point at the same addresses, but they sign in with Cursor's own app. turtleOS cannot borrow it. It needs its own.
- **One-time, by the person who runs the house (about ten minutes, in Google's console):** create a project, enable the three services, set up the consent screen, make one OAuth client with the house's callback address. The console steps cannot be scripted; everything after them can. The app has to be *published*, not in *testing*. Google confirms a testing app's sign-in lapses after seven days, which for an always-on house is a silent failure. A published app that Google has not verified shows an "unverified app" warning at sign-in and is capped at 100 people over its lifetime. For one household that is fine; the warning is one extra tap.
- **A gate found on 2026-10-14, before building on it:** Google's hosted servers are in a *Developer Preview Program*, and the project behind our client has to be enrolled (a form, a couple of days). One account says the form wants a Workspace-domain address, not a personal Gmail one. The official page says "a Google Workspace account" and does not say whether a personal one counts. Not verified. If it does not count, the same sign-in, switch and door carry Google's ordinary Gmail, Calendar and Drive APIs instead, with tools we write ourselves. That is also stronger for the rule that Turtle cannot send mail: the tool does not exist. Nothing in slices 1 to 3 depends on which it is.
- **Scopes cannot say "no send":** the mail scope that allows drafts (`gmail.compose`) also allows sending. The refusal is the door's, not Google's. Calendar's write needs `calendar.events`; the read-only set Google lists first has no write.
- **Per person, from the chat:** press *Connect Google*, a private reply carries one link, the person approves once in the browser, the house receives the answer, stores the secret in its own store (never in a channel, never in a file the card reads), and the card changes to *Connected: Gmail, Calendar, Drive*. A phone can do it. The callback can sit on the address that is already public through Funnel (Caddy on `:8080`), so a member who is not on the tailnet can finish it.
- **Google's phone-style code entry (device flow) is not available** for mail and calendar scopes, so the browser step cannot be skipped. It can be one tap.
- **The engine is one thing, not one file per service.** X is a hand-built door today (`outgoing_connections.py`, `outgoing_x.py`, a subprocess). The next service should not be a copy. A service becomes a row — name, address, how it signs in, which tools read and which write, what each room's ceiling is — on a shared door that speaks the protocol's own sign-in and refreshes its own tokens. A server that supports the protocol's self-registration needs no console step at all; Google does not, so Google is a row with a client id.

## Build order, if sanctioned

| # | Target condition | Verified by |
|---|---|---|
| 1 *(built)* | The shared door and one row. Ceiling × switch resolves for a room; an off or forbidden room neither lists nor calls | Two rooms, one sign-in; a health room refuses; a planted write tool is absent from the list and refused when called (positive control: it is listed in a room that allows it) |
| 2 *(core built; the button is not)* | Google row, sign-in from the chat, calendar look in home. Needs on the Mini: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` in `.env`, and a Caddy route sending `/connect/*` to the bot's web server (a public path, added with the client, not before) | A sign-in through the callback leaves no secret in the channel transcript; a lapsed token is refreshed; a refused sign-in says so |
| 3 *(the `!mcp` row is built; the in-place offer is not)* | The switch: in-place offer and the `!mcp` row | A press changes the room's state and the card agrees; a shared room cannot be switched on |
| 4 | Gmail and Drive look, Gmail drafts, in craft | Send routes absent and refused; a draft lands in its thread (read `threadId` back) |
| 5 | Calendar act: the date button writes the calendar | The write is on the primary calendar; an ignored class is not offered again |
| 6 | Magic room and GitHub | With slice 5 of the magic channel |

## Not decided

- Whether the other members are offered Google in their homes now or when they ask.
- A shared family calendar: it needs the shared-room rule and its own yes.
- Whether X moves onto the shared door (it works; moving it is for deletability, not behaviour).
