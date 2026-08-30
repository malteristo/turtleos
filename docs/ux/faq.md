# FAQ — for the person who installs it

This is for the member who puts turtleOS on a machine they own. You do not need to be a developer. If you use Claude Code, Codex, Cursor, or a similar helper, hand them [docs/install/SKILL.md](../install/SKILL.md) and walk the Discord steps they cannot finish alone.

---

## What is turtleOS?

A place for practices on a machine you own and a Discord server you own. The house has two rooms: a **private** river that is only yours, and a **community** river that is everyone’s. Practices you add sit on top of that. Turtle talks in **eddies** (threads), not in the main channel. Join is membership.

A new install still creates one private river. Community at install is the remaining destination ([practice-channels.md](../design/practice-channels.md)).

## Do I need to be a programmer?

No. You need a machine you can leave running, a Discord account, and about an afternoon. The recommended path is to let an AI helper follow the install skill. The Discord developer portal still needs you: creating the bot, copying the token, inviting it to your server.

## What do I need?

- A Mac or Linux machine that can run a local conversation model (roughly a ~30B-class model, or a smaller one you accept)
- Python 3.11+, Git, [Ollama](https://ollama.ai)
- A Discord account and a **private** Discord server you own
- No cloud API key for the default path

## How do I know install worked?

The bot is online in your river. A **`new eddy`** bar sits at the bottom. You click it, send a message, and Turtle replies in the thread. That is first success: you can talk in your private room. It is not yet the two-room house.

Details: [onboarding.md](onboarding.md).

## How do I add another adult?

They need their own Discord account, and they join **your** server. That join is the admit — they get a private river, and if you already have a shared room they are seated in it. No further command.

`!admin invite` is still there if you want to pre-create a claim room before they arrive. `!admin rivers` lists who has a river. `!admin doctor` reports when Discord membership and turtleOS membership disagree. The bot needs **Administrator** on the server or channel create fails.

## How do we get a room we share?

The destination is that **community** exists at install. Until that ships, create the shared room after the people who will be in it have Discord accounts on the server:

```
!admin space create family --members @you @them --context family --policy members_only
```

A message there is shared. It is not copied into one private river. A relationship practice is a channel you add; it is not the house itself.

## Does every member need a Discord account?

Yes. turtleOS binds a river to a Discord identity. An unclaimed or guest session is a new person every time they come back — they are not a member.

**Children.** Discord’s minimum age depends on where you live. In Germany (and the EU) it is **16**. Younger children cannot join, and turtleOS does not offer a guest workaround. Their absence is the honest picture, not a failed install. A private river for someone under 18 is also not a designed path; do not invent one.

## Where does our data live?

Notes, dates, and practice files live on **your machine**, under each member’s practice root. With local models, inference stays there too.

**Discord still carries the messages.** The transport is Discord, so the words in rivers and eddies are stored by Discord like any other server you run.

## Will it talk in the shared room when it should stay quiet?

It reads the register before it offers anything, and fails closed when that check cannot run. It witnesses. It does not adjudicate. It will still get moments wrong; the project measures those failures rather than claiming they cannot happen.

## Can I use a cloud model instead of Ollama?

Yes, as an opt-in after first success. The default path does not need an API key.

## How do I update?

You pull the public tree you cloned and restart when the house is quiet. The person who installed it is still a member — updates are ordinary house care, not a special operator species.

## What is Magic, and do I need it?

[Magic](https://github.com/malteristo/magic) is a practice framework that can author flows for turtleOS. You do not need it to install or to live with turtleOS. Do not load it to “understand” the product.

## What if something fails?

`!admin doctor` first. Then the troubleshooting table in [docs/install/SKILL.md](../install/SKILL.md). If you are testing as a first-timer, write down what you tried and what the public instructions did not say — that is the useful report.

---

*Install law: [TURTLE_SPEC.md](../../TURTLE_SPEC.md) §13. Hosted rivers and shared rooms: §15. The house: [practice-channels.md](../design/practice-channels.md).*
