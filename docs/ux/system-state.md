# System-state presentation

**Status:** Living — first reader is `!threads` (2026-09-16).  
**Principles:** [principles.md](principles.md) · **Five names:** [eddy-lifecycle-bar.md](eddy-lifecycle-bar.md)

System state is a glance, not an inventory. The practitioner should see *what is in play* in a few seconds. A dump of every row the registry knows is the founding defect.

## Rules

1. **One question per view.** `!threads` answers “which eddies here, and what can wait?” It does not also show model, attunement, type, or ids.
2. **Attention order.** Live, then kept, then sealed, then resting, then gone. Counts in the title follow that order. Empty states stay off the surface.
3. **One modifier that changes the next act.** On this view that is age, plus `ready` if an eddy is flagged. No second taxonomy (type emoji) and no leftover chrome (`unconfigured`, raw ids).
4. **Counts are complete; lists may collapse.** The title always names every occupied state. The body lists live / kept / sealed (sidebar recency, a dozen names, then how many were left out). Resting and gone are a count until `!threads --all`.
5. **One order.** Live names walk the same way Discord's thread sidebar does (`last_message_id`). We do not invent a second sort, and we cannot usefully change the sidebar.

A list that cannot be read at a glance is not a list. A list Discord will not post is also not a list — the body still has to fit.

## First reader

| Surface | Glance | Inventory |
|---------|--------|-----------|
| `!threads` | Title counts + embed fields. Parked states say `parked` / `closed`. | `!threads --all` names resting and gone, still capped. |
| Spoken to River (`show me threads…`) | Same glance, sidebar order. One list in the embed; one row of name-only jump links for the top five. | Channel menu is a different act (`show_channel_menu`). |
| Spoken waiting (`what's waiting`, `where's the heat`) | Only rows waiting for a session or a word. Whose move. | The full temperature table stays off this surface. |
| Turtle packet | One line: live count in the last 5 days. | `survey_eddies` (five-state, days, this parent). Do not inject the list. |

Later status surfaces (diagnose, house picture, awareness for a human) inherit these rules. Turtle’s internal awareness line may keep machine fields — that is a prompt, not a practitioner table.

## Enforcement

`tests/test_eddy_five_state.py` — glance collapses resting, title is attention-order, default collect lines have no `unconfigured` and no `id:`. This file must keep the rule names above or the dest test fails.
