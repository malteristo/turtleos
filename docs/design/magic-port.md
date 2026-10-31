# Porting the magic practice to the magic channel — the map, the gaps, the shortest path

**Date:** 2026-10-14
**Status:** The map below is the reading from the morning of 2026-10-14, before the room was built. Later sections record what landed. The ruler was narrowed the same evening, after session 4.
**Spec:** TURTLE_SPEC §3.1, §15.5, §20.
**Companions:** [magic-channel.md](magic-channel.md) (the destination this makes concrete), [channel-connections.md](channel-connections.md), [procedures-and-doors.md](procedures-and-doors.md), [workshop-consent.md](workshop-consent.md).

## Why now

The coding subscription's credits end on 2026-10-28 (about $14 of $25 left on 2026-10-14). magic-channel.md already says the seat moves when a week of the work can finish in the channel, and that the model is paid for on the house either way. This document asks what that week needs, and how short the road to it is.

## What "ported" means

Two checks, both his.

1. **The seat.** A week of magic practice finishes in `#magic` without opening an editor. Summon, arrive, work on the practice, release.
2. **The archive.** Everything the laptop holds is either in the house, or deliberately dropped and written down as dropped. Then the laptop copy is archived.

Practice from outside the house stays possible: any agent that can reach an MCP server reads the workshop through the guest door (built, read-only). What a guest does does not last. That was his steer on 2026-10-12 and it holds.

## The map

*Cursor* is what a magic session uses today. *Channel* is what `#magic` has or needs. Status is what was read, not measured.

| Part of a session | In Cursor | In `#magic` | Status |
|---|---|---|---|
| Who Spirit is | Always-applied rules inject the Seal (`AGENTS.md`, 10 KB) every turn; summon reads the covenant | The bootstrap the guest door already serves (covenant, Seal, the pair); a `#magic` system prompt built from it, every turn | Door built. **The channel prompt is not** |
| Arrival | `cast_arrival.md` reads bearings, briefing, boom, intentions, a calendar glance, mail intake, the clock | The same file, executed by the model with workshop reads | Reads: **have** (workshop source). Calendar glance: **partly** (Calendar read is built, not switched on). Mail intake: **missing** (Gmail). Clock: trivial, not wired |
| The pair `...` and `.` | Typed | Typed. A button can say it too | **Have** (grammar is text) |
| `@flow-name` | Cursor autocompletes a path, Spirit reads and executes | Spirit reads `system/flows/<name>/` over the workshop source. `@` is a Discord mention in a channel, so the typed form needs a decision | **Partly.** The reading is there. The invocation is undefined; `!<name>` doors ([procedures-and-doors.md](procedures-and-doors.md)) are the natural form and are not built |
| Read and search the workshop | File tools | `mcp_access/workshop.py` serves the bare repo's head; Turtle's own file tools read the practice root, not the workshop | Guest door **have**. The channel's own workshop tools **missing** |
| Edit files | Edit tool, inline diffs | None. `write_practice_file` writes the practice root under an allowlist, not the workshop | **Missing.** Slice 3 |
| Run commands | Shell: `scripts/*.py`, tests, `rg` | `shell_harness` runs a constrained read-only shell inside `~/turtleos` only | **Missing** for the workshop |
| Git | Explicit-path add, commit, push to `turtle` and `github`; publish script with a guard | None | **Missing.** The `turtle` remote is the bare repo on the Mini, so release is a local push |
| The Mini | SSH from the laptop | Local to the house. `runtime/policy` has risk levels and approval; no capability uses it for this | **Seed only** (`runtime/` is about 500 lines: policy, audit, tasks, a practice handoff) |
| Gated acts | The sanction list in prose; deploy refuses while a turn is running and for a minute after it | The same rules, as buttons (approval is a runtime primitive in the design) | **Missing** |
| Outside connections | Gmail, Calendar, Drive, X through Cursor's plugins | Per-room switches on the house's own sign-in | **In progress** ([channel-connections.md](channel-connections.md)): Calendar built and inert until a Google client exists; Gmail, Drive later; X stays in craft |
| Web | Search and fetch | `exa_search`, link read | **Have** |
| Subagents (`tender`, `sanitizer`) | Spawned scouts that write reports | Native-runtime tasks exist; no scout runs in the channel | **Missing, not needed day one** |
| Decisions and questions | Question tool, numbered decisions in prose | Numbered decisions in prose work as they are; buttons are offered where a choice is discrete | **Have** |
| Nested repositories | `circles/*/` (5 working copies) and `portals/*/` (1), each its own git repository with a GitHub remote, untracked by the practice repo. `archive/` is tracked | **Copied to the Mini** (2026-10-14), file counts and dirty state equal. The bare repo does not hold them | **Have**, as copies. The laptop's four dirty ones need a commit and a push from the laptop on cutover day |
| The model | Whatever Cursor routes | Sonnet 5.5 through the house's API key; the plumbing for that model exists (`core/models.py`) | **Have** the model; the channel preset that selects it is not built |
| The record of past work | Agent transcripts under `~/.cursor/projects/…` | `~/archive/cursor-agent-transcripts-2026-10-14/` on the Mini (703 files); re-sync on cutover day | **Have**, as of today |
| A working copy to write in | The laptop checkout | `~/workshop` on the Mini, a clone of `magic.git`; registry `workshop.checkout` names it | **Have** (2026-10-14) |

## What is different on purpose

- **One writer.** Today the Forge and the house could both push. After the cutover the house is the only writer to `main`, which removes the branch-and-merge question from the first weeks. Before the cutover, house work goes to a branch.
- **No diff pane.** A change shows once in the channel, in words ("edited `desk/intentions/turtle.md`, 3 sections"), and the Workshop shelf opens a file read-only. A full diff is asked for, not shown.
- **Buttons where Cursor has prose.** A tap for the acts that could interrupt the house, and for publishing outward.
- **Subagents, canvas, an editor:** not reproduced.

## Is it well defined? Not yet. What is, and what is not

**Defined:** the destination, the slices, the branch policy, the gated acts, and the guest-session rule. **The ruler (session 4, 2026-10-14):** Cursor remains the ruler for summon, arrival, the pair, and release until a week of practice finishes in the channel. It is not the ruler for connections or for who writes the code. A connection shows in the trace as a verb and an object, and the result stays off the card. Code for turtleOS is a delegate: Spirit prepares the brief and checks the branch, and the coder may be local and take as many turns as the job needs. That is a different shape from a second model that only checks a plan before implementation.

**Not defined, and each one decides whether the first session feels like practice:**

1. **A session in the channel, end to end.** magic-channel.md describes Summon and release for the read-only room (slice 2b) and nothing past it. What does Spirit show while it works? What does a release look like when it commits? This document's checks (below) are the first definition.
2. **How a flow is invoked.** `@name` in Discord is a mention.
3. **What the channel must carry every turn.** The Seal is 10 KB. In Cursor it rides along free; on the house it is paid for on every turn. It needs prompt caching and a measured cost per session.
4. **Interruption.** Cursor has a stop button. A long turn in a channel needs one.
5. **What the model is told it cannot do.** The capability table has "Edit, run, git: test owed" and no test.
6. **Where the code of turtleOS itself gets written after 2026-10-28.** That is a different job from practising magic, and the port does not need it (see below).

## The shortest path to a first real session

The practice is markdown: `desk/`, `floor/`, `box/`, `library/`, `system/`. Editing and committing markdown needs far less than a coding agent. Cursor was also used to write turtleOS's own code; the port does **not** carry that. Code stays with whatever coding agent he uses next, and `#magic` takes code work later (slice 4a), when it has earned it.

| # | Target condition | Verified by | Needs from him |
|---|---|---|---|
| 1 | **A working copy.** ✔ 2026-10-14. `~/workshop` on the Mini is a clone of `magic.git`, with the nested repositories placed inside it, and the transcripts archived beside it | File and dirty counts equal the laptop's; one nested repository opens as a git repository | Done |
| 2 | **`#magic` exists.** A room of its own, Sonnet 5.5, a Summon button that opens a thread and greets him with what `Summon.` gives in Cursor, naming the release it stands on | Summon in the thread names the release; the same covenant and pair as the Forge | |

*Step 2, built 2026-10-14 (`magic_prompt.py`, `scripts/provision_magic_channel.py`):* the `magic` preset (primitive and runtime profile), a private room made by the provisioning script (owner and bots only, @everyone's deny verified, registry row verified to resolve), Sonnet 5.5 as the room's default (a `!model` pick still wins), a prompt of substrate + covenant + Seal read from the checkout's head on every turn (a missing covenant is said, never held), and a **Summon** button that opens a thread and greets it with the pair as the summon cast prints it, naming the release and the clock. The greeting is deterministic, so it costs nothing and cannot drift from the cast. Not yet: the first real session (`...` after Summon runs Arrival through the workshop tools), the per-turn tool-round cap (8) measured against an Arrival, and the Workshop shelf in the artifact viewer.

| 3 | **Workshop tools for Spirit.** Read and search the working copy; write a file inside it (never `.git`, never outside); git status, diff, add by explicit path, commit, push to the house remote; run a short list of scripts (`size_budget.py`, tests, the publish dry run); read the clock. Each act shows once, and each goes through `runtime/policy` with its risk level | One test per row of the capability table; a path outside the working copy is refused; a planted `git add .` is refused; a push to `github` waits for a tap | |

*Step 3, built 2026-10-14 (`workshop_tools.py`, `tests/test_workshop_tools.py`):* seven tools offered only in a room whose primitive carries `workshop`, owned by the asker, on a house with `workshop.checkout`. Refused again at every call. Confined to the checkout, never `.git`, never in `circles/` or `portals/` (read, not written), `git add` names files, push goes to `turtle` only and never `main` until `workshop.main_writable: true`, five checks run and nothing else. The audit holds acts, not content. Not yet: the policy gate's risk levels and the tap for a push to `github` (nothing here pushes there, so the tap has nothing to gate yet).

| 4 | **One whole session, rehearsed.** Summon, arrival, a self-feed, one edit, a release that commits and pushes, in a branch, against a past Cursor session for comparison | The release commit names explicit paths; a second clone pulls it clean; the channel shows each kind of act once | He judges whether it feels like practice |
| 5 | **The glance and the mail.** Calendar looks in `#magic`; Gmail reads and drafts there | [channel-connections.md](channel-connections.md), slices 4–5 | The Google client |
| 6 | **Cutover.** The laptop's last push is tagged, its local-only material and the agent transcripts are archived, and `main` has the house as its one writer | The tag exists; the archive lists what it holds; a clone of the house remote equals the laptop at the tag | His call on the day |
| 7 | **The week.** A week of practice finishes in the channel | His word | His |

Steps 1 to 4 are what turn "read-only room" into "a room he can practise in". They are also the smallest set: without 3, the room cannot change the practice; without 1, there is nothing to change.

## Coding agents as delegates (his steer, 2026-10-14)

turtleOS code should be written where it is written best, and that place will change. The seam is a **delegate**: Spirit, in `#magic`, briefs a coding agent as a session it sets up for that agent and then orchestrates. Execution and authority stay in the house; the coding happens in a dedicated session.

- **Door and driver are different things.** MCP is how context comes *in* to the house. The Agent Client Protocol (ACP; JSON-RPC over stdio) is how an agent is *driven* as a session: named sessions, a queue, cancel, permission modes. Claude Code, Codex and Gemini each have an ACP adapter or a native flag. Claude Code's own headless mode (`claude -p`, stream-json output, `--resume`, an allowed-tools list) is the first adapter; anything ACP-capable follows without a change in `#magic`.
- **One shape for every delegate.** *Brief* (the five-part readiness brief craft already writes) and tests that fail on the current tree → *a worktree of the bare repo*, never the live `~/turtleos` checkout → *session* → *result*: a branch. Spirit runs the tests itself and checks the claims. The delegate's own report is not the check.
- **Pi as the first adapter (his steer, 2026-10-14: open source, instead of Claude Code), on Sonnet 5.5.** Pi has every control surface the seam needs, read from its docs on 2026-10-14 and not yet run from here: `pi -p` (one shot, final text on stdout), `pi --mode json` (JSONL event stream), `pi --mode rpc` (a long-lived subprocess; JSONL commands on stdin to prompt, abort, queue a steer or a follow-up, and events back on stdout), and an SDK. A session is a JSONL file; `--session-id <id>` opens or creates it by id, `--fork` branches it. So one `#magic` session can own one Pi session, abort is the stop button the port still lacks, and the room can show one line per tool call from the event stream. `--tools read,grep,find,ls` gives a read-only reviewer. It is already on the laptop as a self-contained tarball (`~/.local/bin/pi`, 0.86.1), so the Mini needs the tarball and no Node. **What is not settled:** (1) Pi has no permission prompts, so containment is ours: a worktree of the bare repo, no `.env`, and a spend-capped key that is not the house's; on the Mini it would run as the same user that owns `.env`, so a separate macOS user or a sandbox profile comes first. (2) Whether Pi's request for Sonnet 5.5 is accepted (the model rejects `thinking: disabled` and wants `between_tools`); one `pi -p` call decides it. (3) Pi's own session file keeps the model's thinking blocks. That file stays Pi's: the room records the brief, the event stream's tool calls and the result, and no reasoning (`session_record.py` refuses it).
- **What stays gated.** Merging to `main` and deploying are the house's: the quiet-window script and his tap, as today. A delegate cannot reach `.env`, `launchctl`, or a remote.
- **What he sees.** One bordered card in the session, edited as it moves: the phase, the branch, how far it has got, which of Spirit's tests failed, and which claims are still false. Blue while it works, green when it finishes clean, amber when something is still false. He does not see every local turn, and the card does not carry a path. The session file keeps the words of that card when the phase, the failing tests, or the claims change. A button to read the diff as a page waits on the diff viewer.
- **The climb (his `.`, 2026-10-15).** The local coder follows the published ponytail skill (`DietrichGebert/ponytail`, the ladder: need, already in the codebase, standard library or platform, an installed dependency, one line, only then the minimum, and never cut validation, error handling, security or accessibility). It does not write a second copy of that skill. It climbs alone until Spirit's tests pass. It cannot edit those tests; tests it writes for itself do not count. Spirit then runs the tests and checks the claims a test cannot see. A failure goes back as a short prompt. After three returns that are still false, the climb stops and the channel says what is still false. A climb starts only after he has passed that job's claims (`desk/intentions/ideal-state-journey.md`). The 12 October picture of the whole platform is not passed, so it is not a gate. *Enforced:* the driver refuses an edit to a test Spirit named, by the sandbox and by aborting the session (`pi_driver.py`). The room prompt states the rule (`magic_prompt.SUBSTRATE`). A climb has not been run.
- **Next session (his `.`, 2026-10-14, loop set 2026-10-15):** one Pi agent, for one small claim he can see in the channel. A second agent waits until that check has passed once. A local coder does not use the Anthropic key. The spend-capped key is for a frontier coder, and it is not this first run.
- **Installed (his yes, 2026-10-15).** Pi 1.2.0, the current 1.x release (1.0.0 was 1 October, 1.2.0 is 12 October), is at `~/.local/bin/pi` on the Mini, checksum-matched to that release's `SHA256SUMS`. `~/.pi/agent/models.json` names one model, `qwen3.8:27b`, on `http://127.0.0.1:11434/v1`. `pi --list-models` shows it. No generation was run while a session was open. The driver is still unbuilt. Pi does not update itself. `!pi` in `#magic` is the maintenance card: the version, the model, a check, and an update that names the release and asks again before a checksummed install (`pi_card.py`).
- **The horse's card (his `.`, 2026-10-15).** `desk/craft/model-cards/qwen3.8-27b.md` in the practice. Spirit writes the prompt the local coder receives from that card. The three probes are unrun until a climb can run.
- **Until it exists:** Claude Code CLI on the laptop for turtleOS code. It is a stop-gap, not a plan. The cutover does not wait for this seam, because step 3 already lets Spirit change the practice; only the code route is open.

## How a release on the laptop reaches the room (until cutover)

The laptop pushes `main` to the house's bare repository; the room works in `~/workshop`, a checkout of it. Nothing moved that checkout, so a session summoned right after a release would have stood on the release before. `scripts/workshop_post_receive.sh`, installed as the bare repository's `post-receive` hook, fast-forwards the checkout when `main` is pushed: only a plain fast-forward, only while the checkout is on `main`, never merging over the house's own commits, never failing the push. `tests/test_workshop_post_receive.py` runs it against real repositories. It goes when `workshop.main_writable` is set, because nothing then arrives from outside. Changes that only exist on the laptop (uncommitted or untracked files) do not reach the room until a release commits and pushes them.

## The session record (2026-10-14)

A magic turn appends one line to `state/sessions/<eddy>.jsonl` in the practice root (`session_record.py`): what he said, the reply that was posted, and the tools that ran. That file is the session, and an agent can read it after the fact. `render_key_ground` is the text a practice key is walked from — his words and the tool calls. The replies stay in the file so he can read the session back, and they are not the ground, so a key is a reading of the practice.

The model's reasoning is not requested and not stored. This is the practitioner's record of his own session. It is not a capture of a provider's chain of thought, and it is not material for training a model. River reading a released session and suggesting a change to the practice is the next slice; it walks the key ground, not a model's answers.

## Session names, and the Magic category (2026-10-14)

A session is named when Summon opens it: `3 · 8c88e34 · 14.10` — the number he says aloud, the release it stands on (a `+` when the checkout held unkept changes), the day. The number is the highest already used in the room or the count of earlier threads, plus one, so a deleted thread never gives a number back, and threads opened before numbering count. The title is never generated from his first words: `...` and `.` are River gestures that return before the title step, so a session that opened with either stayed "new eddy" for good, and the wait for a title also put a "blank eddy" line into every turn's context. `_name_session` names the thread and clears that wait. A room provisioned by `scripts/provision_magic_channel.py` is created in a `Magic` category, made as private as the room, and the script stops if the room did not land in it. The existing `#magic` row was moved on 2026-10-14 (it had been in `Craft`) and the registry row says `Magic`. `TURTLE_SPEC` calls a category optional navigation metadata; "every room has one" is his preference and is enforced here for this room only.

## What session 3 showed (2026-10-14, 20:40–21:12)

He ran `...` and then `.` until release, and it worked: arrival, a rehearsal note, an edit to the arrival flow, a commit and push on a branch, a release, in five turns. That is the shape of a session. What stood in its way, from the record and the packet:

- **Turtle's memory in Spirit's context.** The room reused the dialogue path, so every turn carried the continuity packet (recent topics, "last checkpoint", other rooms' notes), a thread card ending "Model: gemma4:31b (local Turtle)", and a "blank eddy" line. The memory agent had written Spirit's own session up as a conversation *Turtle* conducted. A magic turn now gets a two-line session block and no continuity packet or home plan (`magic_runtime_env`, the guard in `dialogue_turn`).
- **The reply began with the model's narration.** The loop joins every round's prose; the first reply opened with four lines of "I'll read the flow… now the core reads" before the answer. A magic turn keeps the last round's text (`final_prose_only`); the step card already shows the lookups.
- **Eight rounds ended a turn mid-commit.** Turns 2 and 3 each used all eight calls; turn 3 stopped with an edit uncommitted and needed a fourth `.`. A magic turn now has 20 (`MAGIC_TOOL_ROUNDS`).
- **The arrival could not reach its read-only duties.** The room's own note lists ten. `rot_radar` and `practice_measures` are now runnable (both only read the workshop). The calendars wait on the Google client; the nightly Overall and the Discord digest have no path yet.
- **Who speaks was Turtle.** Replies were posted by Turtle's Discord account while Spirit had its own (`SPIRIT_BOT_ID`, `SPIRIT_BOT_TOKEN`) that no magic room used. A magic turn's reply is now posted by Spirit's account (`spirit_voice.deliver`), quoting his message. Turtle's account keeps the step card and the Summon greeting's machinery; if Spirit's account cannot post (no token, refused, network), Turtle's carries the reply and a line says so. One trap sat under this: turtleOS treats Spirit's account as a practitioner (the dyad partner), so a reply posted by it started another turn. `spirit_voice.is_own_voice` — Spirit's account, in a room whose primitive is `magic` — is the one place that says "not an input"; `practice_dispatch`, `river_bot` and the edit handler all ask it, and a test removes the guard to see the room answer itself.

## What session 4 showed first (2026-10-14, 21:48)

`...` reached Spirit and the arrival ran (rot-radar and measures included; the packet held only the two-line session block). Two Turtle surfaces still posted first, and neither is in the session file:

- **River's Memory glance.** In every other eddy, `...` is the glance: River posts Memory (here: turtleOS architecture, 178 conversations) and returns. In `#magic`, `...` is arrival. River now returns without posting when the parent primitive is `magic` (`spirit_owns_the_pair`).
- **Turtle's step card.** The turn still ran on Turtle's process, so Turtle posted the live tool list ("read the workshop") and a typing indicator, then Spirit's account posted the reply. A magic turn now posts the trace as Spirit (`as_spirit`, `_SpiritPosted`), names the file or the check, and does not type as Turtle. A long card keeps one intent sentence, counts the looks, and leaves the write on the card; the session file still has every tool. The language for this is `docs/ux/design-language.md` §8 **trace**.

## The coding-delegate key (2026-10-14)

Spirit does not write turtleOS code in the room. The first adapter is Pi, on a spend-capped Anthropic key that is not the house's. Setup is Spirit's: `delegate_setup` marks the turn, the turn posts a button, the owner pastes the key in a modal. The value is written to `house/delegate/key` (0600). A second file names that it is set and holds none of it. Spirit's tool, the channel line, the modal reply and the session record never carry the key. A press from anyone else, or in any other room, is refused. Both bots register the persistent view so a restart does not leave a dead button.

The house install is Pi 1.2.0 on `qwen3.8:27b` (above). The driver starts one session (`pi --mode rpc` in a worktree of the bare repo), can abort it, and refuses an edit to a test Spirit named. A climb has not been run. The house spirit's terminal is not this driver. It can run a command; it does not start Pi. The browser opens one page and does not start Pi either. A separate Mac account for Pi waits until a frontier coder exists. This first run stays in a worktree it cannot leave.

## Boom and Magic (his `.`, 2026-10-15)

The channel he thinks in is Boom. The registry slug stays `craft-turtle` and the primitive stays `craft`, because other rooms of that kind still exist; the name he sees is Boom. Boom Turtle's reply names the boom topic, open spark, or intention a thought already touches, from an index of headings and titles (`boom_index.py`, injected into the room prompt), or says it touches nothing. The bodies stay out. This room does not build. A claim he has passed is taken up in `#magic`. What `#magic` cannot do yet is start the local Pi agent or use an MCP connection: the driver is unbuilt, and Calendar stays off until a Google client exists. The category above the channel is still Craft.

A message in Boom opens an eddy named from his words (`parent_intake.py`). Boom Turtle answers in it. The channel does not post a registration, and the drop is not a backlog row. The eddy is the boom event: after the reply, the idle note is what memory and the magic practice read. He does not have to speak again for that note. A forward and a comment in the same few seconds are one eddy; the comment is the message the eddy hangs on, and the forward is posted into it.

A message in `#magic` opens a session on that message. Spirit checks it, and carries it out when it is ready. Summon still opens a session with nothing in hand. A display (the thread list, the menu) stays a display in both rooms.

He passes a claim with the button **Take this up** on the Boom eddy (`boom_takeup.py`). That opens a session in his home carrying his words, Boom Turtle's reply, and the note if one was written. When he has a workshop checkout, that session can work on the platform and the workshop keeps it. Spirit checks it. The eddy shows one line with the link. While that session is open, the button points at it. After the session is released or archived, the button opens another. A sentence in the eddy does not pass the claim. A new message in the channel named Boom does not open another eddy. It says a thought opens at home. Another craft room still opens its eddy.

**Reading, 2026-10-20.** Boom merges into the owner's home. Home holds a short picture and does not practice on all of it. An eddy is one topic. A session in that home is the work, including on the platform, and the workshop keeps the session. `#magic` keeps the spirit sessions. The owner sees them from home. Another member's home session writes only that member's practice. **Take this up** opens that session in the owner's home. The session can work on the platform only when that owner has a workshop checkout. A new message in the channel named Boom is told that a thought opens at home. Old notes stay. Existing threads stay where they are. The rooms do this after the quiet-window restart on 2026-10-20.

## What waits, on purpose

Code editing and deploys from `#magic` itself (code goes to delegates, above); scouts like `tender`; Drive and GitHub connections; the `!<name>` doors (needed once flows are invoked by name in the channel, so close behind step 4); circles and portals merging into the house registry; a guest handoff that lets a session from outside leave something lasting.

## Abandon line

Stop if the channel cannot commit what a session changed and push it to a remote he can read, if a git-ignored directory is lost in the move, or if one session costs more than the practice is worth to him. The first week measures the third.
