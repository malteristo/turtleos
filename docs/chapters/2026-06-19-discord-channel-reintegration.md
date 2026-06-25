# Chapter: Discord Channel Re-integration

**Date:** 2026-06-19  
**Status:** Complete — hosted river chapter closed; friend claim test pending

## Problem

After the v1 platform reorientation (`attunement: native`), satellite Discord channels were untouched. Hosted river design chapter executed end-to-end.

## Shipped

### Founding retired
- Removed from `mage_registry.yaml` on Mac Mini

### Hosted river (full chapter)
- Slices 0–4 — see `docs/chapters/design-hosted-river.md`
- TURTLE_SPEC §15 (hosted-river, unclaimed-river, onboarding, river keys)
- `scripts/shake_hosted_river.py`
- `docs/operations/hosted-river-boundaries.md`
- UX journey: claim + practitioner eddy path

## Other design chapters (not this arc)

| Chapter | Doc |
|---------|-----|
| Craft channel | `design-craft-channel.md` |
| Family shared river | `design-family-shared-river.md` |
| Share eddy (thinking together) | `design-share-eddy.md` — §15.6; Slice 1 practitioner first |

## Verify

```bash
cd ~/turtleos && python3 -m pytest tests/test_river_keys.py tests/test_hosted_river_onboarding.py tests/test_practitioner_readiness.py tests/test_native_prompts.py -q
python3 scripts/shake_hosted_river.py --live   # on Mini
```

## Pending operator dogfood

- Friend claim via `!admin river-key`
- Nesrine eddy when she returns

