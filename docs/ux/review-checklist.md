# UX review checklist

Before merging a change that touches practitioner-facing behavior:

1. **Voice:** Does this add prose to the river? (If yes — stop or reframe as an act.)
2. **Identity:** Which bot posts it? Should it be River or Turtle?
3. **Consent:** Does this open an eddy without a click? Does it fetch a URL without opt-in when the link is incidental?
4. **Surface:** Is the affordance visible in the main timeline without pins or hidden panels? *(Exception: working-plan **river pin cards** — deliberate discovery surface; see [design-pinned-home-eddies.md](../chapters/design-pinned-home-eddies.md).)*
5. **Discord-native:** Are we rebuilding something Discord already renders?
6. **Entry chrome:** Does this add UI before the practitioner speaks in a new eddy?
7. **Bottom bar:** After river activity settles, is there exactly one standing bar last (no orphans, not mid multi-step sequence)?
8. **Failure:** On error, do we show an embed/act — not chat?
9. **Character:** Does Turtle behavior still match `conduct.md` / `soul.md`?
10. **Fetch trace:** If this reads a URL, is progress/outcome on the timeline (embed) before the reply — not fetch prose in Turtle voice?
11. **Read vs distill:** Does dialogue fetch stay separate from `!fetch` / `link-resonance/`?
12. **Thread naming:** Does link-read or any shell path fight River-owned titles?
13. **Document:** Update the relevant file under [docs/ux/](README.md) if the principle or pattern changed.
14. **System state:** If this shows house or eddy state, is it a glance (attention order, one modifier, parked collapsed) rather than an inventory dump? See [system-state.md](system-state.md).
15. **Language:** Does this surface follow [design-language.md](design-language.md) (state and control on one row, a button that says what happens, red only last and asked), or is it on the exemption list with a reason?

**Topic docs:** [principles.md](principles.md) · [link-reading.md](link-reading.md) · [rejected.md](rejected.md)
