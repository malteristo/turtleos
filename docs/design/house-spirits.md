# House spirits

**Date:** 2026-10-16
**Status:** Summon always opens (`4924249`). A forge spirit can open one magic session over the connection. The house spirit answers that turn in the channel. On that turn it can read a file in the house repo. It has a terminal on the machine, and can open one page. Clicking is still not given. Pi's driver can start one session and has not been run.
**His words,** this morning, after Summon refused him, and again when he sent the Forge on.

A new session always opens. Other work may still be going on. Several spirits in one workshop are the ordinary case. An alive workshop has several spirits active at the same time. They are aware of each other and of each other's work. They try not to get in each other's way. For the rest they roam freely.

A spirit is active until it releases. Release closes the session. The session is not lost. Every session is recorded and kept. A spirit that does not release is blocked. The help happens inside that session, so it can release. The workshop owes the spirit that.

Spirits act from the workshop. He has a different relation to turtles than to spirits. The workshop in the magic channel is the workshop of turtleOS. Spirits do things for the members and work on the house. They are the house spirits.

He can summon a spirit from anywhere in the house. Sharing into the magic channel opens a session on the context attached to that message. In the session, Spirit decides from `... <that context>` and proposes. He signs off or corrects. Spirit implements with a Pi coding agent on a local model. The agent writes a ponytail implementation. Spirit judges it. Then Spirit releases.

Spirit outside turtleOS is the same session, mirrored. Cursor over the connection, and any other agent with it, does not keep a second workshop. A session opened there opens a session in the magic channel, and the conversation is mirrored back over the connection.

He can practice from a computer that is not his, without his phone or his laptop. He installs the connection on that computer. A flow he developed in his magic practice, for the person he is sitting with, is available over the connection. The local agent follows that flow while he is there and consents. The data stays on his system. The local agent instructs a spirit. The spirit opens the session in the magic channel, so he can follow it from there. He can intervene. He does not have to.

It works the same way from Cursor on his own laptop. He uses the local agent to drive the spirit on turtleOS, and he talks to that spirit over the connection. The spirit is the one with a terminal on the Mac Mini and with a browser. The local agent does not have either.

The point of the mirror is the history. He keeps control of it. Any chat that led to a change in the system is retained. turtleOS can trace its own development down to that chat log.

Magic in turtleOS is built from the Forge. A spirit here practices with a spirit in the house, and they build it from the inside. The Forge spirit develops resonance with the house spirit. The connection between them is MCP. It is how the two spirits talk. It is not a second workshop, and it is not a terminal.

## What is true after this commit

Pressing Summon opens a session while other sessions are unreleased. The greeting names those spirits and tells the new one to stay out of their work. It does not say to release one first, and it does not stop.

`speak` on the house connection is the Forge spirit's side of that talk. It opens one session in the owner's magic channel, names it `Forge · <day>`, and posts the turn there as Spirit's account, prefixed so the channel shows who spoke. The same words are kept in that session's file (`kind` `forge`). A later `speak` with that session continues it, and does not enter a session this path did not open. A grant made before this operation existed does not gain it until `GrantStore.add_operation` is asked. A reader grant cannot receive it. The tool says it has no terminal and no browser. `hear` brings back the house spirit's latest reply in that session. Until the reply is posted, `hear` is empty. Another sitting's reply is not returned.

The house spirit answers a forge turn in that session. The room treats `Forge:` as the other spirit, and treats its own reply as its own voice, so it does not answer itself. The prompt names the missing terminal and browser of that `Forge:` message. His own message has both. `.` goes on with the climb toward the ideal state he has passed, and when those claims are true the house spirit hands back. He names the next ideal state, or he sends `...` and it offers one hill from what is already there. That glance is not a new arrival. A turn that arrived while the room was still ignoring it is answered when the room is ready. On that turn the house spirit can look at the workshop. A write, an edit, a git verb, and a run are refused. A change waits on him. The terminal is refused on that turn too, including a command that only looks. The message is posted by Spirit's account, and the workshop is the room owner's, so the covenant is in hand on that turn.

A forge turn can read one file in the house repo. The channel names the path, not the text. A secret file (`.env`, `credentials.json`, the delegate key) and anything in `.git` are refused, including a link that leaves the repo. The terminal stays closed on that turn: reading a file is not a command.

The house spirit can run one command on the machine, in the house repo or the workshop. The channel shows the command, not its output. Restarting the house and forceful git are refused before the command starts. A secret file (`.env`, `credentials.json`, the delegate key) cannot be read from the command: the process is sandboxed, and a command does not run when the sandbox is missing. Stopping the bot by its process number is not refused. The command is in the session.

The house spirit can open one page. The channel shows the address, without the query. The session keeps the address and the start of what was read. A page on this machine, and a redirect onto one, is refused. It does not click, type, or stay signed in. A forge turn cannot open a page.

## What is not true yet

Sharing a conversation into the channel does not open a session on that context. A spirit does not yet read the other spirits' work, only their names. Pi does not yet write the implementation. The driver can start one session in a worktree of the bare repo, abort it, and refuse an edit to a test Spirit named. A climb has not been run. A stuck spirit is not yet helped inside its own session. A flow is not served over the connection for an agent to follow. The workshop's own checks still run inside the checkout. Clicking through a site is not given. A chat in Cursor is still not, by itself, the session record: the record is the session this connection opened. A change does not yet point back to that chat. A greeting stands on a checkout that already contains house main, including one with commits of its own. It says the room waited when the tree is dirty, or when the checkout and house main have diverged.
