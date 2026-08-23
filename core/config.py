"""Configuration that is read, never called — the part of `state` with no client in it.

**Why this module exists, and why it holds so little.** `mage.get_pd()` is the
most-imported function in the codebase (34 importers) and it resolves the
practice directory. On 2026-08-15 it was transport-coupled, and the reason was
four levels down and one line wide:

    get_pd
      -> _resolve_primary_practice_dir
        -> _infer_primary_workshop_dir     # fallback: registry is empty
          -> _resolve_dialogue_channel_id  # reads state.CHANNELS
            -> state                        # holds the Discord client

`_infer_primary_workshop_dir` runs only when `mage_registry.yaml` is missing, and
it wants the dialogue channel id purely as a **tiebreaker** when scoring
candidate workshop directories. So the whole practice-directory resolution
path — imported everywhere, called on every turn — depended on the transport
layer because of a scoring hint in a fallback.

`CHANNELS` is a dict of environment-derived ids. Nothing about it needs a client;
it lived in `state.py` because that is where configuration accumulated. Moved
here, the chain above becomes transport-free end to end, with no behavioural
change of any kind — the same dict, read from a module that cannot import a
transport.

**What belongs here:** values, read at import, derived from the environment.
**What does not:** anything that resolves an id into a live object. `get_channel`
stays in `state.py`, because turning an id into a channel needs the client, and
that is the actual boundary.
"""

from __future__ import annotations

import os

# Named Discord channels, by id, from the environment. An id is a value; the
# channel it names is not, which is why `state.get_channel` is elsewhere.
CHANNELS = {
    "dialogue": os.environ.get("DISCORD_CHANNEL_DIALOGUE"),
}
