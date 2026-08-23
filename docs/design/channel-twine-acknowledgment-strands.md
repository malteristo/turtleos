# Channel Twine: Acknowledgment Strands & the Permalink Index

> **Companion:** [channel-twine-and-communal-memory.md](channel-twine-and-communal-memory.md) — that charter establishes the governance (authority, crossing law, perspective, custody). This document is its first concrete strand: the thinnest possible channel twine for a live shared space, as the charter's closing line requests.
>
> **Companion:** [continuity-engine-and-substrate.md](continuity-engine-and-substrate.md) — this is Slice 3 (sediment-as-retrieval-policy) instantiated at channel scale, with a narrower store than the general case.

**Status:** Draft v1 — design chapter, pre-implementation. No implementation is sanctioned by this document.
**Date:** 2026-07-28
**Spec trace:** TURTLE_SPEC §6.4 (sediment deferred), §8.4 (checkpoint), §15.4–15.6 (multi-practitioner topologies), §16 (practice state), §20 (proposal pattern)
**Origin:** Family-channel dogfood 2026-07-19 → 07-27; operator dialogue on Anvil 2026-07-28

---

## 1. The problem, stated from the dogfood

Nine days of continuous use of a live shared space (two members, high emotional load) produced ~18 eddies and ~35 checkpoint notes, and retained **nothing usable**. Each conversation restarted from raw feeling. Three architectural facts explain it completely:

| Layer | State today | Consequence |
|---|---|---|
| **Discord transcript** | Durable, complete, permalinkable — and **unindexed** | Ground truth that is reachable ([`discord_ref_read.py`](../../discord_ref_read.py), on an explicit pasted link) but not *findable*. In practice: not ground truth. |
| **Eddy notes** | Written at checkpoint, **never read back** — [`story_notes.py`](../../story_notes.py) reads state surfaces and intention files, *"never other eddies' transcripts"* | A write-only residue layer. Grows monotonically, informs nothing. |
| **Sediment** | Not built — [`continuity_engine.py`](../../continuity_engine.py): *"Not yet: stale demotion, conversational-offer narrowing, sediment, externals"* | No durable cross-eddy retrieval exists at any scale. |

The alive layer holds five headers with no stale demotion. That is the entire memory of a shared space.

**Restating it as a design brief:** the transcript is already the ground truth and needs no replacement. What is missing is the *pointer layer* between the transcript and the residue — and a policy for which pointers are worth keeping.

## 2. The core stance: index, do not copy

> **An entry holds a permalink, a date, an author, and one plain line. It holds no transcript.**

This is not a storage optimization. It is the safety property that makes shared memory viable in a conflicted space:

- **An index cannot be quoted out of context, because it contains no text to quote.** Using an entry requires returning to the thread where all members were present. Portable decontextualized testimony — the documented failure mode of the prior corpus regime — is structurally unavailable.
- **Deletion semantics are inherited, not designed.** Remove the message, the link dies, the entry self-invalidates. No separate forgetting mechanism.
- **Storage is trivial** and the store is human-readable, which matters for a governance surface members may be shown.

Charter §4's non-goals hold unchanged: no psychographic modeling, no implicit river mining, no majority-overwrites-memory, no engagement mechanics.

## 3. Strand A — Acknowledgments

### 3.1 Why this strand first

An acknowledgment is a member's account **of their own conduct**. That makes it the one class of shared memory with no provenance hazard:

- Charter §3.3.3 requires a member's account *of another* be held as attributed perception, never fact. An acknowledgment is exempt by construction — the author and the subject are the same person.
- It is the highest-value tier for a member who needs a written anchor, and simultaneously the tier with the lowest weaponization risk.
- Charter §3.4's asymmetry trap (the host's account quietly becoming canonical) cannot operate on it: nobody can enter anything about anyone else.

### 3.2 The rule that carries the strand

> **Self-attribution only. A member may mark their own acknowledgment. No member may enter a concession on another member's behalf — not by proposal, not by paraphrase, not by the witness's inference on their behalf.**

Turtle may *offer* an entry to the person who spoke. Turtle may never offer "A acknowledged X" to B, and never write an acknowledgment without that member's sanction (charter §3.1 — Turtle proposes, members sanction).

### 3.3 Store

`<channel practice root>/state/acknowledgments.yaml`

```yaml
schema_version: 1
entries:
  - id: ack-2026-07-27-01
    author: <member id>              # must equal the speaker; enforced, not conventional
    date: 2026-07-27
    permalink: https://discord.com/channels/<guild>/<thread>/<message>
    line: "<one plain line, in the author's own words where possible>"
    sanctioned_at: 2026-07-27T22:41:00+02:00
    source_state: live | unreachable  # set by the deletion watcher (§5)
```

`line` is a label for finding the thing, not a substitute for it. Where the author's own phrasing is available it is used verbatim; where it is paraphrase, that is marked — provenance discipline (`c1952b4`) applies to the store as much as to dialogue.

### 3.4 Offer behaviour

1. Turtle notices, in an eddy, that a member has named something about their own conduct or confirmed a contested fact.
2. **Not while hot.** Acute state → no offer (kernel rule: sleep gate; `character/conduct.md` heavy-moments rule). The offer waits for calm.
3. It offers in plain language, in the water, to the speaker: *"that sounded like you naming something — want me to mark where you said it?"*
4. Accept → entry written. Decline or silence → nothing. No re-ask on the same utterance.
5. **Vocabulary firewall** (CE §4): no internal terms reach the channel. Never "acknowledgment strand," never "twine," never "ledger" unless the members have adopted that word themselves.

## 4. Strand B — Held disagreement

Charter §3.1: *"member A remembers it this way; member B that way" is a recordable state, not an error to resolve.* Same store shape, two permalinks, no verdict.

```yaml
  - id: div-2026-07-27-01
    date: 2026-07-27
    positions:
      - author: <member a>
        permalink: <...>
        line: "<A's account, attributed>"
      - author: <member b>
        permalink: <...>
        line: "<B's account, attributed>"
    recurrences: [2026-07-26, 2026-07-27]
```

**Two design notes.**

*Held ≠ parked.* Parking files a divergence as permanently unresolvable — which reads as relief to a member who experiences the past as emotionally inert, and as erasure to a member for whom it is live. Holding makes both accounts **findable from both sides** and asserts nothing about resolvability. The difference is not cosmetic; it is the difference between a judgment and a retrieval property.

*Recurrence is the signal.* A divergence surfacing three times in four days is a repair-rate finding, not a fact dispute. `recurrences` exists so the witness can notice slowing repair — the standing job the charter assigns it — without re-litigating content.

## 5. Deletion witnessing (required, not optional)

Charter §3.1 forbids silent rewrites of shared memory. **Discord message deletion is a silent rewrite** — and if the transcript is ground truth, deletion hands any single member a unilateral memory-hole over the between.

Requirement: a dead reference renders as *"referenced content no longer reachable"* with its date and author intact. It never vanishes and is never garbage-collected.

Hook: [`discord_reconcile.py`](../../discord_reconcile.py) already surfaces `reconcile_thread_delete` and lock/archive transitions via `runtime/adapters/lifecycle`. Archive is **not** deletion (archived threads stay readable and must not be marked unreachable). Message-level deletion needs a `on_raw_message_delete` path; thread deletion invalidates every entry pointing into it.

This is the charter's "witnessed trace that it occurred rather than a silent gap" (§3.4), applied one layer down.

## 6. Retrieval — the sediment policy, narrowed

Once A and B exist, retrieval is a pointer offer, never an injection:

- Topic recurs in the channel → Turtle offers *"you landed on something adjacent on the 27th"* + link.
- **Pointer only.** Content is never injected from the store into the prompt; the member opens the thread or does not.
- Never holistic. Relevance-gated, per CE §5.3.
- Charter §5.2's open question is the whole ergonomic risk: too eager nags, too shy never accrues. **Only live tuning decides this**, and it is the reason implementation is not sanctioned here.

## 7. What this deliberately does not do

- **No third strand for agreements yet.** Convergences are rarer, harder to detect, and need both members' sanction. Ship A and B; let agreement detection follow real data.
- **No crossing law implementation.** Charter §3.2 stands unimplemented; this strand is channel-local only. Nothing crosses to or from any private river.
- **No shared-space inference layer.** Detection runs where the eddy already runs.
- **No member-facing concept.** Members never learn there is a store. They see occasional plain-language offers and can always say no.

## 8. Slices

| Slice | Content | Acceptance |
|---|---|---|
| **1** | `acknowledgments.yaml`, self-attribution enforcement, offer path, sanction confirm | A member is offered an entry for something they said; declining leaves no trace; another member cannot produce an entry about them |
| **2** | Held-disagreement entries + recurrence counter | A divergence surfacing twice is recorded once with two dates, both positions attributed |
| **3** | Deletion witnessing | Deleting a referenced message renders the entry unreachable-but-present; archiving does not |
| **4** | Relevance-gated pointer offers | A recurring topic surfaces a prior pointer; holistic context is unchanged |
| **5** | Rendered view (the "ledger") | A member can ask what has been marked and receive an attributed, permalinked list |

Slice 1 alone is a complete, useful product. Slices 2–3 make it safe. Slice 4 is where the ergonomic risk lives and should be gated on live observation.

## 9. Open questions

1. **Detection quality.** Can a reflection-class model reliably distinguish *"I did that"* from *"I understand that you feel that"*? A false positive is an offer to mark something the member does not consider an acknowledgment — mildly bad. A systematic bias toward offering one member more than the other is **charter §3.4 territory** and must be measured, not assumed.
2. **`line` phrasing.** Author's verbatim words, or a witness paraphrase? Verbatim is safer for provenance and worse for findability. Probably: verbatim where a clean short utterance exists, marked paraphrase otherwise.
3. **Message vs thread granularity.** Message permalinks are precise but require capturing the message id at offer time; thread permalinks always work but land the reader in a long conversation. Start message-level, degrade to thread.
4. **Who may read the rendered view?** Any member, presumably — but a view of one's own acknowledgments and a view of the whole store are different objects, and one of them is closer to a case file. Slice 5 should not ship without this settled.
5. **Operator visibility.** Charter §6 residual: how an operator action on the store is shown to members. The store is a governance surface; an operator edit to it is a claim about meaning, not custody.

---

*The charter said: pick the smallest live shared space and give it the thinnest possible channel twine — witness notes plus member-sanctioned corrections — before any crossing law is implemented. This is that, narrowed further: no notes at all, only pointers to what people said about themselves.*
