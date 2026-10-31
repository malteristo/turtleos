# Names audit — every word a practitioner meets

**Date:** 2026-10-14
**Status:** Draft for him to react to. Nothing is renamed by this document.
**His rule (2026-10-14):** naming on turtleOS is deliberate. No command or function name is chosen arbitrarily; it is the shortest, most descriptive version of the name. Where Discord or an agent standard already has a word, the burden of proof is on turtleOS's own.

## How to read the table

One row per word a person sees on a surface (buttons, cards, replies, commands). *Standard word* is what Discord or the agent world calls the same thing. *What is lost* is what a person would no longer be told by the word. *Lean* is a position, not a decision.

| Word | What it names | Standard word | What is lost by switching | Lean |
|------|---------------|---------------|---------------------------|------|
| **eddy** | A Discord thread with Turtle in it, plus the memory and five states (live, resting, kept, sealed, gone) that Discord does not give a thread | thread | That it has a lifecycle. A plain thread has none | Weak case. The lifecycle is carried by the states, not by the noun. Run the rename as an experiment, not by taste |
| **river** | Two things: a person's main channel, and the small agent that executes acts | channel (the place), assistant or agent (the doer) | Nothing; the double meaning is a defect | Split: the place should be a plain word, the agent keeps its name |
| **flow** | A markdown prompt program a person starts | skill, workflow | That a person starts it, rather than Turtle reaching for it | Becomes a skill with `invoke: person`. See [procedures-and-doors](procedures-and-doors.md) |
| **act** | One platform operation behind a button | action | Nothing | `action` is the standard word and as short in use. Internal first |
| **checkpoint** | Save the state and write the note | save, snapshot | The idea of a resumable point | Keep: it is the established word in agent work |
| **release** | Checkpoint, then clear history | end, close, reset | That a checkpoint happens first | Describe by effect on the card: "Close the session" already does |
| **dissolve** | Archive the eddy and write the chronicle line | close, archive | That the eddy's contents are folded into memory | The card's own sentence ("archive this eddy") says what it does; the verb is the odd one |
| **spark** | Drop a line into an eddy's note | note | Nothing I can see | Weakest name on the card; check whether anyone uses it |
| **pin** | Keep a plan or message where it can be found | pin | Nothing | Keep: Discord's own word |
| **share** | Send an eddy to a person's home or a shared room | forward, send | Nothing | Keep |
| **home** | A member's own channel | DM, inbox | That Turtle is there too | Keep until a person says otherwise |
| **`...` and `.`** | Show me where we are / go on | none | Everything: this is the product | Keep |

## What would settle it

- **Who meets the word.** The six words on the `!` card are the ones to settle first; internal names (act, river-the-agent) can change without a person noticing.
- **A person's own word.** The first members have used some of these for weeks. What they say instead of "eddy" is better evidence than either Discord's word or ours.
- **One change at a time.** A rename touches the bar, the card, the prompts, the specs and the PR/FAQs. Rename one word, live with it, then decide the next.

## Not decided here

Whether to rename anything. This table is the board; he decides.
