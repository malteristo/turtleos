# House speaker

**Date:** 2026-10-21
**Status:** Destination sanctioned 2026-10-21 and lived that day. **Trial 2026-10-24:** voice from the house speaker lands in one eddy for the local day, named for that day. A sentence carries the time it was said. At the next local midnight, and on the next sentence if the process was down, yesterday is archived and today opens. A triple press does not open an eddy. It is reserved for a later spirit session. A separate conversation is an eddy he opens himself. Google keyboard transcripts and Discord voice messages are not this door. Calls wait. The setup wizard is not built. The device is carried. A battery pack may power it. How long a pack lasts is his measurement. The apartment's Wi-Fi is the limit. The day eddy does not change with the room. **2026-10-25:** the microphone closes between turns. Okay Nabu or one press starts a sentence. A spoken reply that is waiting for an answer lets the next sentence come with neither. A finished answer needs Okay Nabu or one press again. The eddy continues either way. A listening window after every reply, and a wake word of his own, wait.
**Spec:** TURTLE_SPEC §3 (channels). The day eddy is the voice strategy on trial. One press continues today. Three presses do not open another.
**Companions:** [home-turtle.md](home-turtle.md)

Four artifacts first (`docs/development.md` §12). No mechanism in the press release.

---

## Read this first

The press release below is the destination. The house does not do all of it yet. Read this section before changing the speaker, and change this section in the same sitting that makes a line true.

**Live, 2026-10-25.** The device is the Home Assistant Voice Preview Edition. Okay Nabu, or one press, starts a sentence. faster-whisper is the ear. Piper is the mouth. Ollama Conversation, model name `home`, is the messenger, aimed at the door on the Mini. Local command handling stays off. The instruction on that messenger is one plain sentence, with no braces. The hardware mute switch cuts the microphones. A spoken reply that ends in a question lets the next sentence come without Okay Nabu or a press. While a reply is still being written, the microphone is closed.

The sentence lands in the home channel, in the eddy named The speaker is connected, opened 2026-10-21. The house keeps using that eddy. The home channel answers with the local model. The speaker reads the whole reply, because the house never asks for the line `The talk`. Home Assistant's catalogue of other devices is not sent to the turtle.

**Written, not on the house.** One eddy for the local day, the time on each sentence, the talk line, a waiting talk ending in a question mark, and a heard sentence treated as heard. Those land together, and landing them restarts the house. The laptop and the Mini are different trees. Do not lay one over the other.

**Abilities.** Lived: Okay Nabu or one press, Piper speaking, the hardware mute, and answering a question without starting again. Waiting: the volume dial, the light when the button is held and turned, stopping speech with the center button, a triple press reserved for a later spirit session, the light ring, Hey Jarvis or Hey Mycroft as a second wake word, timers, the word stop, the headphone jack, and the lines in the paragraph above. Left alone: the Home Assistant catalogue, a wake word trained from scratch, and a listening window after every reply.

A speaker practice chooses one waiting ability and lives it. The hardware gestures are in Nabu Casa's "Using the device." This page is the house.

---

## 1. Press release

You have a speaker in the house. You talk to it.

What you say shows up in your home channel, in today's voice eddy. If today does not have one yet, one opens, named for the day. You can pick the phone up and read the whole day, and you can answer there too. Another eddy is one you open yourself.

The speaker says the reply. It does not read the longer writing above that reply. The longer writing stays where you can look at it.

Okay Nabu, or one press, talks into today. When the speaker asks you something, you answer. When the answer is finished, the next thing you want to say starts again with Okay Nabu or one press. The conversation on the phone continues either way. Three presses do not start another eddy. The wheel does not speak. Mute means the wake word is off.

The voice stays in the house.

---

## 2. Happy path

```
Alex is at home. The speaker is in the room. Today's voice eddy is already open in the home channel.

Alex:    (Okay Nabu, then) What should I do with the rest of the afternoon?
Speaker: (asks one question, and nothing above it)
Alex:    (answers, without pressing and without the wake word)
Speaker: (says a finished answer)
Alex:    (stays quiet. Nothing new is written)
Alex:    (one press, then) And the evening?
Speaker: (says the reply, and nothing above it)
Alex:    (picks up the phone, opens that same eddy, reads the sentences, the times, and the replies)

Alex:    (later, one press) Did the morning actually get done?
Speaker: (says the reply)
Alex:    (the phone shows both sentences in the same eddy)

Alex:    (three presses, then a sentence)
Speaker: (says the reply in today's eddy. No second eddy appears)

Alex:    (the next day, one press) Morning.
Speaker: (says the reply)
Alex:    (yesterday's eddy is closed. Today's is a new one)

Alex:    (turns the wheel)
Speaker: (says nothing)

Alex:    (mutes)
Speaker: (says nothing, and a sentence spoken at it does not appear in the home channel)
```

*Invisible: how a press is counted, how the reply is chosen, how sound is made. A different path that left Alex in the same place would still pass.*

---

## 3. Success criteria

| # | Experience | Can fail in week three | Re-run |
|---|------------|------------------------|--------|
| 1 | A sentence that is not a house command is answered out loud, and that sentence is visible in the home channel. | The speaker says it could not understand, or the home channel has no sentence to read. | Say a sentence that is not a house command. Look at the home channel. |
| 2 | When the reply has a longer writing and a talk, the speaker says the talk and does not say the longer writing. | A phrase that was only in the longer writing is spoken. | A planted reply with a phrase only above the talk. The speaker does not say that phrase. |
| 3 | Voice from the speaker through one local day lands in one eddy, named for that day. The next day is a new eddy, and the previous one is closed. A triple press does not open an eddy. | A sentence after midnight continues yesterday, or a triple press starts a new eddy. | Two sentences on one day, then one after midnight. The phone shows two eddies. A triple press leaves the count at one. |
| 4 | The wheel does not speak. Mute keeps a sentence out of the home channel. | A turn of the wheel produces a reply, or a sentence spoken while muted appears. | Turn the wheel once. Mute, speak, unmute. |
| 5 | The voice is not sent out of the house. | A sentence is answered by a service outside the house. | The same sentence, with the house offline from the outside. It still answers, or it says it cannot. It does not leave. |
| 6 | A spoken question can be answered with no tap and no wake word. A finished answer needs Okay Nabu or one press. The eddy continues either way. | A finished answer leaves the microphone open, or a question requires a new tap. | Get a question, and answer without tapping. After a finished answer, stay quiet, then say Okay Nabu and speak again. Both sentences are in the same eddy. |

Mechanism-blind: another speaker could still be scored on *the sentence is readable, only the talk is spoken, one press continues, three presses start fresh, the wheel is silent, mute keeps the sentence out, and the voice stays in the house.*

---

## 4. Abandon line

Stop if the speaker reads the longer writing aloud.

Stop if a sentence you can hear yourself say never appears where you can read it.

Stop if one press and three presses do the same thing for a week and the difference was simply never wired.

Stop if answering means sending the voice out of the house.

---

## This slice

The day eddy is the trial. Okay Nabu and one press send the sentence into today's eddy in the owner's home. A spoken reply that ends waiting for an answer lets the next sentence come with neither. A finished answer needs Okay Nabu or one press again. The microphone is closed while a reply is still being written. A listening window after every reply, and another wake word, are not this start. A triple press is still heard by the door and does not open another eddy. The assistant instructions are plain text. A brace in that setting is rendered by Home Assistant before the sentence reaches the door, and a failure there is spoken as a problem with a template. Yesterday's eddy is archived when the local day changes. The sentence is posted with the time it was said, so the eddy can tell a morning from an afternoon. He opens any other eddy himself.

Until replies carry a talk, the reply itself is what would have been read, so that is what may be spoken. When a talk is present, the writing above it is not spoken, even if the talk is empty. An empty talk is a silence the home channel still holds, and the speaker says that the reply is written there rather than reading the page.
