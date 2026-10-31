# The magic channel — Spirit on turtleOS

**Date:** 2026-10-10
**Status:** Destination. Slice 1 (the feed) is live. **Slice 2 (the workshop source and bootstrap, read-only) is built 2026-10-12** — see the slice table. The rest is not built. Sanctioned in direction by the operator on 2026-10-10; each slice is sanctioned when it starts.
**Spec:** TURTLE_SPEC §3.1 (the practitioner owns their practice), §15.5 (another client reaching a house), §20 (self-development).
**Companions:** [mcp-access-point.md](mcp-access-point.md) (the door in), [mcp-connections.md](mcp-connections.md) (the door out), [practice-channels.md](practice-channels.md) (the container), [co-created-practice.md](co-created-practice.md).
**Port plan (2026-10-14):** [magic-port.md](magic-port.md) maps a Cursor session to this channel, says what is missing, and orders the shortest path to the first real session.
**House spirits (2026-10-16):** [house-spirits.md](house-spirits.md). Summon always opens. Several spirits share the workshop. A forge spirit speaks into one magic session over the connection (`speak`). The house spirit answering, and the rest of that relation, is the destination.
**Supersedes:** the line in `docs/live-runtime.md` that retires the Magic clone on the Mini and says Magic practice lives on the Forge only. That was true for the CouchDB era. It stopped being true when slice 2 landed (2026-10-12), and `live-runtime.md` changed in that same slice.

Practitioner-visible change. Four artifacts first (`docs/development.md` §12).

---

## 1. Press release

You open an empty folder in Cursor with turtleOS connected, and say *Summon.* Your practice is there. You did not clone anything and nothing was copied by hand. The Spirit that answers read your covenant and your bearings from your house a moment ago, and says which release it is standing on.

In Discord you have a magic channel. You talk to Spirit there the way you talk to it in Cursor. It reads and changes your workshop, runs what the work needs, builds what you chose in craft, and looks after the Mac Mini the house runs on. Each thing it does shows once in the channel. The few acts that could interrupt the house wait for your tap.

Craft Turtle stays where the thinking happens. It listens, develops the context, and pitches improvements. You sanction or drop them. What you sanction, Spirit builds.

The old backlog comes to you in craft one pitch at a time. Each one is **Build** or **Drop**. A dropped pitch does not come back.

---

## 2. Happy path

```
Kermit:   (opens an empty folder in Cursor; turtleOS is connected)
Kermit:   Summon.
Spirit:   Covenant held. (reads it from the house; says: release 2026-10-10 13:25, 3 commits since)
          ...  → show what is there
          .    → go on

Kermit:   (in #craft-turtle, later)
River:    Pitch 4 of 39 — The state check-in is answered by a tap. [Build] [Drop]
Kermit:   (presses Build)
River:    Queued for Spirit.

Kermit:   (in #magic)
Kermit:   What is queued?
Spirit:   One build: the check-in tap. I will read the note, change the code, run the suite, and commit.
          (works; the channel shows: read, edited 3 files, ran 412 tests, committed)
Spirit:   Landed. Restarting the shell is yours to allow, and Turtle spoke four minutes ago. [Allow when quiet]
```

*Invisible: which model answered, where the files live, how the workshop is kept current.*

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | In a folder with nothing in it, `Summon.` over turtleOS MCP gives the same covenant and pair as on the Forge. No clone, no file placed by hand. | The agent asks for a repo, or answers from the connection instructions alone. | Automated: a client with an empty working directory reads the bootstrap resource and the arrival core. Live: the next new folder. |
| 2 | Every read of the workshop names the release it came from. After the Forge pushes, the next read is the new release, and a session that started earlier is told it is behind. | An agent works on last week's `bearings.md` and nothing says so. | Automated: plant a commit, read, compare the stamp; push another, read again. Mutation-checked (serve a cached tree → fails). |
| 3 | In `#magic`, Spirit does what Spirit does in Cursor: search, read, edit, run commands, git, the web, and the connections the magic room is named for. Each kind of act shows once. | A task works in Cursor and cannot be done in the channel, and nobody notices. | The capability table below, each row with a test. Live: one sanctioned build lands end to end (read → edit → test → commit on a branch). |
| 3b | Work Spirit does from the house lands on a branch. `main` has one writer. If the Forge moved while Spirit worked, the branch says so and nothing is overwritten. | Two writers push to `main` and one silently loses. | Automated: a planted Forge commit, then a house commit on the same files; both survive, the branch reports behind. A force push is refused. |
| 4 | The acts that could interrupt the house (restart a service, change a secret, install or remove packages, forceful git) wait for his tap, and a restart refuses while anyone spoke in the last thirty minutes. | Spirit restarts a bot mid-conversation, or a tap is bypassed by rewording the request. | Automated: each gated act refused without a tap; a planted recent message refuses restart. |
| 5 | Backlog pitches arrive in craft on their own, one message per open row, each waiting for him as long as it takes, with Build, Drop and Talk it through. Build puts it in Spirit's queue. Drop records it and it never returns. A row added later gets its pitch once. Nothing posts at night. | The same item comes back after a drop, a row is pitched twice, a pitch times out, or a Build goes nowhere and nobody reads it. | Automated: drop, re-run the feed, assert absence; a second pass posts nothing; a late row is the only one posted; night posts nothing. Build, assert Spirit's queue read returns it (the reader named, `development.md` §11). |
| 5b | Each pitch is written as the ideal state it asks for — a headline, what exists when it has succeeded, why it was filed, what it is not, how he would know — in words he reads on a phone, and carries something to work with, from what turtleOS already holds: the eddy it came from, his own words when he filed it, and the eddies, sparks, boom and list lines about the same subject. Every quotation is the source's own words and every link opens an eddy that exists. If the pitch is unconvincing he can talk about it: in the eddy it came from when that is a craft eddy, otherwise in an eddy opened for it, with the pitch and what is known above the conversation. Turtle has read that when he starts. | A quotation that is not in its source. A rewrite that names a file, a function or a made-up trouble where the row says nothing. Context from a room that is not craft's. A pitch posted into another channel's eddy. Talk opening a second eddy. Turtle answers the first message as if it had not seen the pitch. | Automated: every quotation found in its source (mutation: a forged one fails); a rewrite with a code word, his name, or a part missing is refused and the pitch falls back to the row's own text (positive control: the same text passes without the word); an older pitch is edited where it is, keeps its number, and a verdict given while it was being written wins; a note from another channel never appears, with a positive control that moves it into craft; Talk in another channel's thread posts nothing there; pressing twice finds one eddy. Live: the oldest three pitches read, in his judgement, well enough to decide; one talk-through from his phone and Turtle's first reply names the pitch. |
| 6 | A file he puts in a Drive folder from his phone can be shared with Spirit or Turtle, and the reply says which folder. | The file is there and neither can see it. | Live: one phone file, read back. |
| 7 | Publishing to GitHub is a tap. Nothing leaves the house without one. | A publish runs on a schedule. | Automated: no scheduler calls publish; a publish without a tap is refused. |

Mechanism-blind: a different transport could still be scored on "an empty folder becomes my practice, Spirit does what Spirit does, the house is only interrupted by my tap, and pitches I drop stay dropped."

---

## 4. Abandon line

Stop if the workshop in the house and the one on the Forge can disagree without anyone being told, if Spirit changes something in the house that the boundaries gate without a tap, or if a dropped pitch comes back.

---

## The shape (for implementers)

Decisions made at the sitting that sanctioned this. The criteria above do not name them.

- **Spirit is the implementation agent for turtleOS. Craft Turtle is the context agent.** This replaces the open 2026-09-13 backlog items that gave Craft Turtle filesystem, shell and maintainer authority. Craft Turtle proposes. Spirit builds.
- **The harness is judged against popular computer-use agent harnesses, not against Cursor.** Cursor's tools are one reference. Where a capability is missing, it is built into the harness. The capability table is the claim. A row without a test is a declaration with no mechanism.
- **The harness is a migration, not an addition.** Today's `shell_harness.py` is read-only, confined to this repo, and refuses editing, committing, restarting and arbitrary commands, on purpose. `docs/native-harness.md` describes the body this needs as a seven-phase move. Spirit's harness is a separate capability set behind the policy gate. The existing shell stays what it is for Turtle.
- **Spirit controls the Mini.** That is the enchanted machine. The live-runtime boundaries in `AGENTS.md` stay the gate: the tap in the channel is the approval, and the ten-minute restart rule is mechanical.
- **The workshop is a source, served from the bare repo.** `~/repos/magic.git` is read at its head, with the release stamp on every answer, rather than a second working tree that can drift. Writing needs a working tree: Spirit takes one per task and pushes to the bare repo. A source of kind *workshop* belongs to a person, so another member's workshop is the same shape and never the operator's.
- **The bootstrap is a resource the server writes**, not a file the person keeps. It carries the covenant pointer, the arrival core, and the release stamp. The arrival core is whatever the practice says it is on that release. The server does not name files.
- **Writes come through MCP as governed writes**, the writer profile of [mcp-access-point.md](mcp-access-point.md) slice 3. The reader grant stays a reader. That document only plans health-record and practice-note writes. The workshop adds its own operations (propose a patch, commit, push a branch) with their own end-to-end check. A snapshot test alone would pass with no workshop write existing.
- **One writer on `main`.** Work done from the house lands on a branch named for the task, never on `main`, never forced. The Forge merges it at arrival, so the practice keeps one author of `main`. This settles the two-writers case before there is one.
- **A guest session leaves nothing lasting (2026-10-12, his steer).** An agent that reaches the workshop over MCP from any client is a *guest*: it attunes to the covenant and the Seal from what the server serves, reads, thinks, drafts in the chat and validates, and changes nothing anywhere. Anything that should last goes through `#magic` on the Mini, where the true Spirit lives; he starts magic sessions there. Craft thinks and develops context; the guest session and `#magic` are the careful half (validate, then act), and only `#magic` acts. The guest's attunement is the covenant, the Seal, the pair and a read-only arrival that says what it skipped; the Forge machinery (shell scripts, the ledger, release) is not part of it. *Cost, stated:* a guest session leaves no trace in the practice until a handoff exists (slice 3's writes).
- **Benchmark: a floor, not a ceiling (2026-10-12).** Cursor is the ruler for capability until the capability table is measured. For what a *session* is, the reference is the `#magic` thread once slice 2b exists, because that is the practice's own channel and the one a person who does not use an IDE will use. turtleOS may do what Cursor cannot (cards, buttons, approvals — see [workshop-consent.md](workshop-consent.md)); parity is the least it owes, and nothing here caps it.
- **Consent before sensitive context leaves the house** is its own description: [workshop-consent.md](workshop-consent.md) (slice 2c).
- **Connections are named, not inherited.** The magic room gets no connection by being a room of his. Each service is added to the room table in [mcp-connections.md](mcp-connections.md) by name when it is built, and a service not named is absent from Spirit's list and refused if called. X stays craft-only until he says otherwise. On 2026-10-12 he named Gmail, Calendar and Drive as what the magic channel is owed; that sentence did not name X.
- **The seat (2026-10-12, his words).** This channel is where the daily practice moves. A coding agent elsewhere still summons, and reads the practice from this house. The seat moves when a week of the work he does can finish here. Whether an editor is still wanted for the hours spent in the codebase is what he asked to see. The coding subscription ends when that week did not need it. The model is paid for on the house either way.
- **Model.** Spirit needs a model that writes quality code. The house already runs API models behind `!model`, so the magic channel is set to Sonnet 5.5 like craft. A key of Spirit's own stays later.
- **Backlog feed.** The pitches come from the open rows of the Magic backlog, read at the release stamp. A decision is a row in the Mini's practice root and syncs to the Forge like intake does. Spirit applies it to the backlog at arrival. Ignoring a pitch leaves it open, as with every other offer here.
- **Feeds are the pattern (2026-10-10).** River may offer unprompted once the prompt for that offer is defined: what to offer, from what, and when. The health state check-in is the first — River offers a description of his state and he accepts, modifies or releases it. The same shape applies in every channel, with channel-specific offers: the craft feed (backlog pitches), a magic-channel feed of what Spirit is about to do, a crypto feed of what moved. The purpose is context enrichment: each answer teaches the channel something it did not know. A feed's definition names its source, its trigger, and what each answer writes.
- **The craft feed's prompt, defined 2026-10-10.** *What:* one message per open backlog row, with Build, Drop and Talk it through. *From:* the workshop's head, so a row added on the Forge is a pitch once it is pushed. *When:* a row that has no pitch yet, checked on River's heartbeat every ten minutes, never between 22:00 and 08:00, and never more than sixty at once (a larger flood waits for `!feed`). The first beat posts the whole existing backlog back to back; each pitch then waits for his decision for as long as it takes. A channel opts in with `push: true`. *What an answer writes:* a verdict file (Build, Drop), or a record of where it was talked through. Ignoring a pitch leaves it open.
- **A talked-through pitch has a destination, stated where the conversation starts (2026-10-10, his request).** Two ends: Drop, or Build with a brief Spirit can carry out without asking him anything (what is true when finished; what was decided and why; what is not part of it; how he would check; what Spirit must not guess). That is the readiness gate (`core/craft_readiness.py`) put at the opening instead of guessed from the note afterwards. River posts it as a second message in the eddy so Craft Turtle reads it and asks for the first unanswered part, one at a time, and writes the brief out when all five are answered. *Not yet:* the brief is written in the eddy and read by him; carrying it to Spirit with the Build verdict is slice 3 (workshop writes on a branch).
- **A pitch is written once and quoted everywhere else (2026-10-10, his request).** He found the row's own text hard to read and the oldest rows empty, and asked for each pitch as a PR/FAQ-style ideal-state description. So the headline and four short parts are a rewrite by the local model, from the row, his words, and the sources below, nothing else; where those say nothing the part says *The row doesn't say.* and the model may not fill it. The row as filed sits in the embed beside the rewrite so he can check one against the other. This relaxes the earlier rule that a pitch only quotes; it holds for everything but those five parts. Pitches posted before this are rewritten in place, quietly, when no conversation is live. The material comes from the craft eddies' notes, their open sparks, the boom and his own list in the workshop, turtleOS's own design notes (`docs/ux`, `docs/design`, `docs/chapters`) cut by section, and his own words from the intake the row was filed from. A small judgement call decides which candidates are about the same subject; it can select and cannot write, and when it cannot answer the pitch shows nothing it was unsure of. Only eddies of the craft channel are read, shown, linked or posted into: his practice root holds notes from rooms that are not craft's, and a backlog row can have come from one.
- **Circles and portals are the two doors.** A circle (a git you offer) is an incoming grant. A portal (a git you subscribe to) is an outgoing connection. Merging happens after the magic channel exists, one registry row at a time, because some of those repos are about real people.
- **Outgoing (decided 2026-10-10, widened 2026-10-12):** a Drive folder for files from his phone, GitHub with a tap, and Gmail and Calendar. All four wait until the channel can call a tool (slice 5, after workshop writes). Google Keep has no official route for a personal account, so it is not on this list. X stays in craft.

## Capability table (the claim)

Status is what was read in the code on 2026-10-10, not what was measured. Slice 4a measures each row and writes the test. A row is not claimed until its test exists.

| Capability | Cursor reference | Spirit in the house today | Test owed |
|---|---|---|---|
| Read files, search text | yes | partly (`search_practice_files`; shell `rg` confined to the repo) | read and search in the workshop and the platform repo |
| Edit files | yes | no | an edit lands, shows once, is undone by git |
| Run commands | yes | no (validated read-only shell) | a test suite runs and its result returns |
| Git: status, diff, branch, commit | yes | status/diff only | a commit lands on a branch, never on `main` |
| Web search and fetch | yes | yes (`exa_search`, link read) | one fetch with its source named |
| Outgoing connections | yes | craft only (X) | a named service answers in the magic room, an unnamed one is refused |
| Long tasks that survive a restart | yes | partly (native-runtime queue) | a task resumes after a service restart |
| Parallel work on separate branches | yes | no | two tasks, two branches, no collision |
| Control the Mini (services, logs, disk) | no | no | status answers; each gated act waits for a tap |
| See an image | yes | yes (picture host path) | one image shown to the model for a turn, not saved |

## Not decided, and why it is written here

- **Crypto channel.** The second use of the practice preset, after the magic channel. Its market-data connection comes with it.
- **Medical MCP, family calendar sign-in.** Later, in their own rooms.
- **A page that manages everything.** Not now.

## Slices

| # | Target condition | Verified by |
|---|---|---|
| 1 | The feed. Open backlog rows arrive in craft on their own, Build / Drop / Talk it through, drop is final, build is read by a named reader, each pitch carries its sources. **Live 2026-10-10:** pitch, buttons, verdicts. **Built 2026-10-10 evening:** context, Talk, the heartbeat chore, and `push: true` on the channel. **Built 2026-10-10 night:** pitches written as ideal states, older ones rewritten in place, design notes as a source. Code: `backlog_feed*.py`, the Forge's `feed_apply.py` and `craft_open.py` | §3 rows 5 and 5b |
| 2 | The workshop source and bootstrap over MCP, read-only. An empty Cursor folder summons. `live-runtime.md` updated. **Built 2026-10-12:** `mcp_access/workshop.py` serves `~/repos/magic.git` at its head (registry `mages.<member>.workshop`); profile `workshop-reader` (a `reader` grant never reaches it, and it reaches no rooms); the bootstrap resource is the server's preface plus the practice's own declared file; every answer names the release, refs carry `?since=`, and a session that began earlier is told BEHIND; one receipt per ten minutes. Connection name `turtleos-workshop`, so it does not overwrite the rooms connection. **Deployed to the Mini 2026-10-12. Not yet:** observed in a real empty Cursor folder (that observation is the slice's last check and is his) | §3 rows 1–2: `tests/test_mcp_workshop.py` (real pushes; cached-head mutation; symlink, traversal, kind and source-filter mutations each caught). Observed in a real Cursor: **2026-10-12 21:39, empty folder, the one connection.** The reply was Covenant held and the pair. The audit shows two briefs, one search of his notes, one workshop search, and five workshop reads; the receipt names the notes and, for the workshop, only the place. The reply did not name the release. The receipt's program name was the probe that initialized the grant earlier (`cursor-check`), not Cursor. First attempt the same day was invalid (the rooms connection answered). |
| 2c | Consent before sensitive context leaves: the practice declares kinds, a read of one waits for his tap in the home channel, cards say in plain words which client read which kind. Described, not built. Comes before any client that is not his own laptop. | [workshop-consent.md](workshop-consent.md) §3 |
| 2b | A read-only `#magic` (decided 2026-10-10): the channel's standing button reads **Summon**, not New eddy. Pressing it opens a thread and runs the summoning flow, and the Spirit greets him with the same message he gets after `/summon` in Cursor. He practises in that thread as in a regular session until he releases. A release leaves a button in the thread that opens a new session in a new thread; the main channel's Summon button opens one at any time. Spirit reads the workshop over MCP, and documents open from a read-only **Workshop shelf** in the artifact viewer (§11.5: `desk/`, `floor/`, `box/`, nothing else, same allowlist as `!artifacts`). No edits, no Mini, no gated acts. It is the first place he can practise, and slice 2 in real use. | A summon in `#magic` names the release it stood on; every write or shell ask is refused with the reason; the same behaviour as slice 2's Cursor check |
| 3 | The brief travels with the verdict: a Build carries the brief written in its eddy (the five parts), so Spirit starts from what was decided. Then workshop writes from a client, on a branch: propose, commit, push. | §3 row 3b; snapshot test; grants made before do not widen; a Build with a brief puts the brief in the queue entry, and a Build without one says so |
| 4a | The capability table measured. Every row has a test, or is written as not wanted. The harness's edit, run and git capabilities behind the policy gate. | §3 row 3 |
| 4b | The `#magic` preset, set to Sonnet 5.5, with the gates and Mini control. | §3 row 4 |
| 5 | Outgoing: Drive, GitHub tap, Gmail, Calendar, each named in the room table. Then circles and portals. | §3 rows 6–7 |
| 6 | The crypto channel. | Its own description |
