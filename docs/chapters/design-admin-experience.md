# Design: Admin (host) experience

**Date:** 2026-07-28  
**Status:** Implemented (this chapter)  
**Spec:** TURTLE_SPEC §15  
**Harvest:** a third practitioner onboarding post-mortem (learnings 2026-07-25) + admin UX redesign

## Problem

Host commands grew as an inventory (`onboard`, `river-key`, registry prune, …) while the product job is simple: invite people to private rivers, run shared spaces, keep the house healthy. Legacy `!admin onboard` and post-claim rename to `#<name>-dialogue` taught the wrong model — guests identify “their river” by name (`#river-<name>`).

## Decisions

1. **Channel identity:** Hosted rivers are `#river-<name>` from provision through claim and forever. No `*-dialogue` rename on claim.
2. **Primary command:** `!admin invite` (alias `river-key`). `onboard` deprecated (redirect only).
3. **Already-on-server guests:** `invite … --member @member` pre-grants claim-room view and prefers a Discord deep link.
4. **Help by jobs:** People & rivers · Spaces · Health · Advanced (progressive disclosure).
5. **Live coherence:** `!admin rivers sync-names [--confirm]` — idempotent Discord + registry alignment; operator-timed, not auto on boot.

## Command map

| Job | Command |
|-----|---------|
| Invite someone | `!admin invite <name> <emoji> [en\|de] [--member …]` |
| List rivers | `!admin rivers` |
| Open claim room for a member | `!admin rivers admit <name> @member` |
| Fix names | `!admin rivers sync-names [--confirm]` |

**Invite auto-admit (2026-07-28):** Provision stores `invite_code` / `invite_uses` on the unclaimed-river row. On `on_member_join`, if that invite’s use count increased, Turtle grants claim-room view/send automatically (no Discord UI).
| Shared rooms | `!admin space …` |
| Pulse / members / audit | `!admin status` · `members` · `audit` |
| Diagnose | `!admin doctor` |
| Power tools | `!admin advanced` → channels, registry prune |

## Modules

- `commands.py` — `cmd_admin` router
- `admin_experience.py` — help text, rivers list/sync, doctor
- `river_keys.py` — provision, claim, `hosted_river_channel_name`, `--member` grant

## Out of scope

Web admin console; renaming operator home `#river`; deleting `onboard` handler body (already redirect-only).

## Verification

- Unit: `tests/test_admin_experience.py`, `tests/test_river_keys.py`
- Shake: `scripts/shake_hosted_river.py` (invite help, no dialogue rename law)
- Live: `!admin` · `!admin rivers` · `!admin rivers sync-names` then `--confirm` when quiet
