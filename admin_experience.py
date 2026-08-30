"""Host/admin experience helpers — rivers inventory, name sync, doctor.

Used by ``!admin rivers`` / ``doctor`` (TURTLE_SPEC §15 seneschal surface).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import discord

from river_keys import hosted_river_channel_name, save_registry


@dataclass
class RiverRow:
    channel_id: str
    mage_key: str
    ch_type: str
    discord_name: str | None
    registry_name: str | None
    desired_name: str
    claimed: bool
    practice_dir: str | None
    name_drift: bool


@dataclass
class SyncAction:
    channel_id: str
    mage_key: str
    desired_name: str
    discord_rename: bool
    registry_cleanup: bool
    current_discord: str | None
    note: str


def iter_river_rows(registry: dict[str, Any]) -> list[RiverRow]:
    mages = registry.get("mages") or {}
    rows: list[RiverRow] = []
    for channel_id, entry in (registry.get("channels") or {}).items():
        if not isinstance(entry, dict):
            continue
        ch_type = entry.get("type")
        if ch_type not in ("hosted-river", "unclaimed-river"):
            continue
        mage_key = str(entry.get("mage") or "")
        if not mage_key:
            continue
        desired = hosted_river_channel_name(mage_key)
        discord_name = entry.get("discord_name") or entry.get("name")
        registry_name = entry.get("name")
        mage = mages.get(mage_key) or {}
        claimed = bool(mage.get("discord_id")) and ch_type == "hosted-river"
        drift = (
            (str(discord_name).lower() != desired.lower() if discord_name else True)
            or (str(registry_name).lower() != desired.lower() if registry_name else True)
        )
        rows.append(
            RiverRow(
                channel_id=str(channel_id),
                mage_key=mage_key,
                ch_type=str(ch_type),
                discord_name=str(discord_name) if discord_name else None,
                registry_name=str(registry_name) if registry_name else None,
                desired_name=desired,
                claimed=claimed,
                practice_dir=mage.get("practice_dir") or entry.get("practice_dir"),
                name_drift=drift,
            )
        )
    rows.sort(key=lambda r: (0 if r.ch_type == "unclaimed-river" else 1, r.mage_key))
    return rows


def format_rivers_list(rows: list[RiverRow]) -> str:
    if not rows:
        return "**Rivers:** none registered (hosted / unclaimed)."
    lines = ["**Rivers** (hosted + unclaimed)"]
    for row in rows:
        status = "unclaimed" if row.ch_type == "unclaimed-river" else ("claimed" if row.claimed else "hosted")
        shown = row.discord_name or row.registry_name or "?"
        drift = " · ⚠️ name drift" if row.name_drift else ""
        workshop = row.practice_dir or f"~/workshops/{row.mage_key}"
        lines.append(
            f"- `{row.mage_key}` — `#{shown}` ({status}){drift}\n"
            f"  → desired `#{row.desired_name}` · workshop `{workshop}` · id `{row.channel_id}`"
        )
    return "\n".join(lines)


def plan_sync_names(
    registry: dict[str, Any],
    guild: discord.Guild | None,
) -> list[SyncAction]:
    """Plan idempotent sync of Discord + registry names to ``river-<mage>``."""
    actions: list[SyncAction] = []
    for row in iter_river_rows(registry):
        if row.ch_type != "hosted-river":
            # Unclaimed rooms should already be river-*; still allow registry cleanup.
            if not row.name_drift:
                continue
        live_name: str | None = None
        if guild is not None:
            try:
                ch = guild.get_channel(int(row.channel_id))
            except (TypeError, ValueError):
                ch = None
            if ch is not None:
                live_name = getattr(ch, "name", None)
        current = live_name or row.discord_name or row.registry_name
        needs_discord = bool(current and current.lower() != row.desired_name.lower())
        needs_registry = (
            (row.registry_name or "").lower() != row.desired_name.lower()
            or (row.discord_name or "").lower() != row.desired_name.lower()
        )
        if not needs_discord and not needs_registry:
            continue
        if current and current.lower() == row.desired_name.lower():
            needs_discord = False
        note = []
        if needs_discord:
            note.append(f"rename Discord `#{current}` → `#{row.desired_name}`")
        if needs_registry:
            note.append("clean registry name/discord_name")
        actions.append(
            SyncAction(
                channel_id=row.channel_id,
                mage_key=row.mage_key,
                desired_name=row.desired_name,
                discord_rename=needs_discord,
                registry_cleanup=needs_registry,
                current_discord=current,
                note="; ".join(note) or "noop",
            )
        )
    return actions


def format_sync_preview(actions: list[SyncAction]) -> str:
    if not actions:
        return "**Rivers sync-names:** all hosted/unclaimed river names already coherent."
    lines = [
        f"**Rivers sync-names (dry-run):** {len(actions)} change(s)",
        "Re-run with `--confirm` to apply.",
        "",
    ]
    for act in actions:
        lines.append(f"- `{act.mage_key}` (`{act.channel_id}`): {act.note}")
    return "\n".join(lines)


async def apply_sync_names(
    registry: dict[str, Any],
    guild: discord.Guild,
    actions: list[SyncAction],
) -> list[str]:
    """Apply sync plan; returns human-readable result lines."""
    results: list[str] = []
    channels = registry.setdefault("channels", {})
    for act in actions:
        entry = channels.get(act.channel_id)
        if not isinstance(entry, dict):
            results.append(f"- `{act.mage_key}`: skipped (no registry row)")
            continue
        if act.discord_rename:
            try:
                ch = guild.get_channel(int(act.channel_id))
                if ch is None:
                    ch = await guild.fetch_channel(int(act.channel_id))
                await ch.edit(
                    name=act.desired_name,
                    reason="Admin rivers sync-names — #river-<name> law",
                )
                results.append(f"- `{act.mage_key}`: renamed Discord → `#{act.desired_name}`")
            except (discord.HTTPException, discord.NotFound, TypeError, ValueError) as exc:
                results.append(f"- `{act.mage_key}`: Discord rename failed ({exc})")
                # Still try registry cleanup below
        if act.registry_cleanup or act.discord_rename:
            entry["name"] = act.desired_name
            entry["discord_name"] = act.desired_name
            if not act.discord_rename:
                results.append(f"- `{act.mage_key}`: registry name/discord_name → `{act.desired_name}`")
    save_registry(registry)
    return results


def collect_doctor_findings(
    registry: dict[str, Any],
    guild: discord.Guild | None,
) -> list[str]:
    """One-screen admin health lines with suggested next acts."""
    findings: list[str] = []

    if guild is not None:
        humans = [m for m in guild.members if not m.bot]
        if len(guild.members) <= 1 or not humans:
            findings.append(
                "⚠️ Member cache looks empty — enable **Server Members Intent** on River, "
                "then `./restart.sh`. Check with `!admin members`."
            )
        else:
            from roster_sync import compute_roster_drift, format_roster_doctor_lines

            drift = compute_roster_drift(
                registry,
                human_ids=[str(m.id) for m in humans],
            )
            findings.extend(format_roster_doctor_lines(drift))

    from space_provisioning import prune_orphaned_channels

    preview, _ = prune_orphaned_channels(registry, confirm=False)
    if preview:
        findings.append(
            f"⚠️ {len(preview)} orphaned registry channel row(s) — "
            "`!admin registry prune-orphans` then `--confirm`."
        )

    rows = iter_river_rows(registry)
    drifted = [r for r in rows if r.name_drift]
    if drifted:
        findings.append(
            f"⚠️ {len(drifted)} river(s) with name drift — "
            "`!admin rivers sync-names` then `--confirm`."
        )

    from mage import REGISTRY_PATH, admin_discord_ids, registry_relation_issues

    if not admin_discord_ids(registry):
        findings.append(
            f"⚠️ No administrator Discord id in `{REGISTRY_PATH}` — "
            "`!admin invite` will say it requires the primary operator. "
            "Set `discord_id` on the primary mage to your numeric user id "
            "(the file next to the running bot, not a second copy under `~/turtleos/`)."
        )

    relation_issues = registry_relation_issues(registry)
    if relation_issues:
        findings.append(
            f"⚠️ {len(relation_issues)} member(s) without a usable `relation` "
            "(reach defaults to `guest`): " + "; ".join(relation_issues)
        )

    unclaimed = [r for r in rows if r.ch_type == "unclaimed-river"]
    if unclaimed:
        findings.append(
            f"ℹ️ {len(unclaimed)} unclaimed claim room(s): "
            + ", ".join(f"`{r.mage_key}`" for r in unclaimed)
            + " — finish claim or remove when stale."
        )

    if not findings:
        findings.append("✅ No admin issues detected. `!admin rivers` / `!admin audit` for detail.")
    return findings


def format_doctor(findings: list[str]) -> str:
    return "**Admin doctor**\n" + "\n".join(findings)


def admin_help_default() -> str:
    return (
        "**Host commands** — invite people, run spaces, keep healthy.\n"
        "\n"
        "**People & rivers**\n"
        "- `!admin invite <name> <emoji> [en|de] [--member @member|id|username]` — give someone their river\n"
        "- `!admin rivers` — list hosted / unclaimed rivers\n"
        "- `!admin rivers admit <name> <@member|id|username>` — open an existing claim room for a member\n"
        "- `!admin rivers sync-names [--confirm]` — align Discord + registry to `#river-<name>`\n"
        "\n"
        "**Spaces**\n"
        "- `!admin space` — shared rooms (create / list / close / hide / sync)\n"
        "\n"
        "**Health**\n"
        "- `!admin status` — server overview\n"
        "- `!admin members` — who is on the server\n"
        "- `!admin audit` — permission / registry health\n"
        "- `!admin doctor` — one-screen diagnosis + next acts\n"
        "\n"
        "More: `!admin advanced` · alias: `!admin river-key` = `invite`"
    )


def admin_help_advanced() -> str:
    return (
        "**Advanced admin**\n"
        "- `!admin channels` — full channel topology + overwrites\n"
        "- `!admin registry prune-orphans [--confirm]` — compact discord-deleted orphan rows\n"
        "\n"
        "Deprecated (hidden): `!admin onboard` → use `!admin invite` instead."
    )
