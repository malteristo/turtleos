# FAQ — for the person who installs it

This is for a household administrator: the member who puts turtleOS on a machine they own and invites the rest of the household. You do not need to be a developer. If you use Claude Code, Codex, Cursor, or a similar helper, hand them [docs/install/SKILL.md](../install/SKILL.md) and walk the Discord steps they cannot finish alone.

---

## What is turtleOS?

A family-friendly AI that runs on a machine you own and lives in a Discord server you own. Each member gets a private river. The household can also have one shared room. Turtle talks in **eddies** (threads), not in the main channel.

## Do I need to be a programmer?

No. You need a machine you can leave running, a Discord account, and about an afternoon. The recommended path is to let an AI helper follow the install skill. The Discord developer portal still needs you: creating the bot, copying the token, inviting it to your server.

## What do I need?

- A Mac or Linux machine that can run a local conversation model (roughly a ~30B-class model, or a smaller one you accept)
- Python 3.11+, Git, [Ollama](https://ollama.ai)
- A Discord account and a **private** Discord server you own
- No cloud API key for the default path

## How do I know install worked?

The bot is online in your river. A **`new eddy`** bar sits at the bottom. You click it, send a message, and Turtle replies in the thread. That is first success for **you**. It is not yet a household.

Details: [onboarding.md](onboarding.md).

## How do I add another adult?

They need their own Discord account, and they join **your** server. In your river:

```
!admin
!admin invite morgan 🌿 en --member @Morgan
```

They open the link, claim their river, and talk to Turtle there. You remain the host on that channel (you can see it exists; stay out of their threads). `!admin rivers` lists who has a river. `!admin doctor` checks the house. The bot needs **Administrator** on the server or the invite fails.

## How do we get a room we share?

After the people who will be in it have rivers (or at least Discord accounts on the server):

```
!admin space create family --members @You @Morgan --context family --policy members_only
```

A message there is a family conversation, not a copy into one private river.

## Does every member need a Discord account?

Yes. turtleOS binds a river to a Discord identity. An unclaimed or guest session is a new person every time they come back — it is not a household member.

**Children.** Discord’s minimum age depends on where you live. In Germany (and the EU) it is **16**. Younger children cannot join, and turtleOS does not offer a guest workaround. Their absence is the honest picture, not a failed install. A private river for someone under 18 is also not a designed path; do not invent one.

## Where does our data live?

Notes, dates, and practice files live on **your machine**, under each member’s practice root. With local models, inference stays there too.

**Discord still carries the messages.** The transport is Discord, so the words in rivers and eddies are stored by Discord like any other server you run. If that is unacceptable for your household, this is not the tool yet.

## Will it talk in the family room when it should stay quiet?

It is built to read the register before it offers anything, and to fail closed when that check cannot run. It is a witness, not a referee. It will still get moments wrong; the project measures those failures rather than claiming they cannot happen.

## Can I use a cloud model instead of Ollama?

Yes, as an opt-in after first success. The default path does not need an API key.

## How do I update?

You pull the public tree you cloned and restart when the house is quiet. The person who installed it is still a member — updates are ordinary house care, not a special operator species.

## What is Magic, and do I need it?

[Magic](https://github.com/malteristo/magic) is a practice framework that can author flows for turtleOS. You do not need it to install or to live with turtleOS. Do not load it to “understand” the product.

## What if something fails?

`!admin doctor` first. Then the troubleshooting table in [docs/install/SKILL.md](../install/SKILL.md). If you are testing as a first-timer, write down what you tried and what the public instructions did not say — that is the useful report.

---

*Install law: [TURTLE_SPEC.md](../../TURTLE_SPEC.md) §13. Household / hosted rivers: §15. Stance: [family-care-operating-model.md](../design/family-care-operating-model.md).*
