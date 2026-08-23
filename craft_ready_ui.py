"""The one surface where an eddy becomes work — and it is a question, not a form.

When a craft eddy goes quiet, the noticer reads the note it just wrote and, if
the conversation named something finishable, this posts what it read back as a
target condition with a single confirm.

**Three deliberate absences.**

*No Skip.* Ignoring the offer is how it is declined — the standing rule since
2026-08-14. There is nothing to press to say no.

*No modal to edit the wording.* The obvious next feature is a text box for
correcting the target condition, and it is the wrong one. The practice this
serves happens by talking in the eddy, usually on a phone; the craft *moves*
channel died proving that a surface asking the practitioner to edit a projected
field records nothing. So a wrong target condition is corrected by saying so in
the thread — the next idle re-proposes and overwrites, which
`craft_readiness.propose` permits for exactly this reason. The conversation is
the editor.

*No auto-confirm.* The noticer proposes; only a human press makes an eddy ready.
A proposal that promoted itself would put the entry gate to autonomous work
under the judgement of a 27b model reading a paragraph.

**Attribution is deliberately not resolved here.** `craft-turtle` is a
single-practitioner channel — the registry binds it to one mage — so there is no
ambiguity about who pressed the button, and the two ways of recording it both
cost more than they are worth: reaching for `continuity_confirm.address_for_user`
puts this module inside the 54-module dependency cycle the layering campaign
exists to shrink, and storing a raw Discord id puts an unresolvable token in
durable state. The field exists in the record; if craft ever becomes a shared
surface, filling it is a decision made then.

**The view is persistent** (`timeout=None`, custom id carries the thread) and is
re-registered at startup from the sidecar's `proposed` rows. A readiness offer
that expired after three minutes would be an offer only someone at their desk
could take, which is the wrong half of this practice.
"""

from __future__ import annotations

from pathlib import Path

import discord

from core.craft_readiness import PROPOSED, ReadinessError, confirm, list_by_state

CUSTOM_ID_PREFIX = "craft:ready:confirm:"


def compose_offer_text(target_condition: str, evidence: str = "") -> str:
    lines = [
        "This sounds like it reached a point where the work could just be done:",
        "",
        f"> {target_condition}",
    ]
    if evidence:
        lines += ["", f"*from your conversation — “{evidence}”*"]
    lines += ["", "If that is the target, say so and I'll bring it to the next craft session."]
    return "\n".join(lines)


class CraftReadyView(discord.ui.View):
    """Confirm — this eddy is work now. Ignoring it leaves the eddy open.

    ``runtime_dir`` is injected rather than resolved. Asking `mage` for it would
    add an edge to the most-imported module in the codebase for a value both
    call sites already hold, and a view that reads global configuration is a
    view that cannot be tested without one.
    """

    def __init__(self, thread_id: int, runtime_dir: str | Path):
        super().__init__(timeout=None)
        self._thread_id = int(thread_id)
        self._runtime_dir = runtime_dir

        from runtime.offers import accept_action

        button = discord.ui.Button(
            label=accept_action("eddy_ready").label,
            custom_id=f"{CUSTOM_ID_PREFIX}{self._thread_id}",
            style=discord.ButtonStyle.primary,
        )
        button.callback = self._on_confirm
        self.add_item(button)

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        if interaction.channel and interaction.channel.id != self._thread_id:
            await interaction.response.send_message("Wrong thread.", ephemeral=True)
            return

        try:
            entry = confirm(self._runtime_dir, self._thread_id, by="practitioner")
        except ReadinessError as exc:
            # The proposal went stale between posting and pressing — say what
            # happened rather than editing the message into a false confirmation.
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        from offer_ledger import record_for_channel

        record_for_channel(self._thread_id, kind="eddy_ready", event="accepted")
        self.stop()
        await interaction.response.edit_message(
            content=(
                "**Ready.** I'll pick this up at the next craft session:\n\n"
                f"> {entry.get('target_condition', '')}"
            ),
            view=None,
        )


async def offer_ready_confirm(
    thread, target_condition: str, evidence: str = "", *, runtime_dir: str | Path
) -> bool:
    """Post the confirm surface into the eddy. True when it was sent."""
    condition = " ".join((target_condition or "").split())
    if not condition:
        return False
    view = CraftReadyView(thread.id, runtime_dir)
    await thread.send(compose_offer_text(condition, " ".join((evidence or "").split())), view=view)

    from offer_ledger import record_for_channel

    record_for_channel(thread.id, kind="eddy_ready", event="offered", detail=condition[:120])
    return True


def rehydrate_ready_views(client, runtime_dir) -> int:
    """Re-register a persistent view for every outstanding proposal. Returns count.

    Without this a restart silently kills every posted offer — the button stays
    on screen and does nothing, which is worse than never having offered.
    """
    count = 0
    for thread_id, _entry in list_by_state(runtime_dir, PROPOSED):
        try:
            client.add_view(CraftReadyView(int(thread_id), runtime_dir))
            count += 1
        except Exception as exc:  # noqa: BLE001 — one bad row must not cost the rest
            print(f"craft ready rehydrate failed for {thread_id}: {type(exc).__name__}: {exc}")
    return count
