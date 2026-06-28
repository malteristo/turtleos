# Design Chapter: Admin Space Provisioning

**Opened:** 2026-06-27  
**Status:** Implemented — S1–S4  
**Spec trace:** TURTLE_SPEC §15.4 (operator provisioning), §15.6 (Share eddy space targets)  
**Sanctioned proposal:** Magic `desk/proposals/2026-06-27-admin-space-provisioning.md`  
**First dogfood:** `lukas_play` sandbox (S5 substitute — guest sharer outside channel)

---

## Tension

Shared-river spaces (Family, play sandboxes, future cohort channels) require coordinated setup across Discord permissions, `mage_registry.yaml` (`spaces` + `channels`), and a minimal workshop root. Manual edits don't scale and drift from `!admin audit`.

Hosted provisioning already uses blessed operator commands (`!admin onboard`, `!admin river-key`). Shared spaces lacked the equivalent.

---

## Design intent

| Principle | Meaning |
|-----------|---------|
| **Operator-only** | Primary operator gate — same as river-key |
| **Registry-first** | Discord channel alone is insufficient; space + shared-river bind written atomically |
| **Privacy default** | Members-only Discord view; `--open` is explicit opt-in |
| **Share policy separate** | `share_policy` controls Share picker, not Discord membership |
| **Archive, don't delete** | Close marks registry `archived`; channel locked / moved to Archived category |
| **Registered mages only** | Every `--members` entry must exist in `mages.*` |

---

## Command surface

```
!admin space create <space-key> [--members @user ...] [--open] [--policy all_practitioners|members_only] [--context family|shared] [--channel name]

!admin space close <space-key> [--confirm] [--dissolve-eddies]

!admin space list

!admin space sync <space-key>
```

### Examples

```bash
# Kermit + Lukas sandbox; Nesrine can share in without channel membership
!admin space create lukas_play --members @kermit @lukas --policy all_practitioners

# Family-like closed space
!admin space create family_trip --members @kermit @nesrine --policy members_only --context family

# Archive when done
!admin space close lukas_play --confirm
```

---

## Registry shape

```yaml
spaces:
  lukas_play:
    practice_dir: ~/workshops/lukas_play
    runtime_dir: ~/workshops/lukas_play
    members: [kermit, lukas]
    share_policy: all_practitioners

channels:
  "CHANNEL_ID":
    mage: lukas_play
    type: shared-river
    default_context: shared
    description: Shared practice space (lukas_play)
```

On close:

```yaml
channels:
  "CHANNEL_ID":
    mage: lukas_play
    type: shared-river
    archived: true
    archived_at: "2026-06-27T12:00:00+00:00"
```

Archived channels are skipped by river harness iteration, Share picker resolution, and shared-river permission sync.

---

## Implementation

| Module | Role |
|--------|------|
| `space_provisioning.py` | Parse args, resolve members, create/close/list/sync |
| `commands.py` | `!admin space` router |
| `mage.py` | `is_channel_archived()`; sync skips archived |
| `river_handler.py` | `_iter_river_channels` skips archived |
| `share_eddy.py` | `shared_river_channel_for_space` skips archived |

Create flow: Discord channel → registry write → `reload_mage_registry()` → `ensure_space_channel_access()` → eddy bar deploy.

Rollback: delete Discord channel if registry write fails after channel creation.

---

## Acceptance (operator dogfood)

1. `!admin space create test_sandbox --members @kermit @<hosted> --policy members_only`
2. Both members materialize eddy; third practitioner cannot view channel
3. Share picker: third party does not see space (`members_only`)
4. With `--policy all_practitioners`: third party sees space in picker, still no Discord view
5. `!admin space close test_sandbox --confirm`: channel locked; no new river acts
6. `!admin audit`: no orphan entries

---

## Deferred

- Self-service practitioner space requests
- Auto-orientation embed (use `shared-river-orientation` flow)
- Hard delete / registry row removal
- Children's partial membership

---

## Related

- [design-family-shared-river.md](design-family-shared-river.md) — shared-river harness law
- [design-share-eddy.md](design-share-eddy.md) — space share targets
- [docs/ux/journeys.md](../ux/journeys.md) — operator journey section
