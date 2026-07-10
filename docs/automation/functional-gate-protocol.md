# Functional Gate Protocol

**Status:** Active (2026-06-26)  
**Frames:** Distributed cognition supporting distributed software craft on turtleOS.

Spirit closes the **functional gate** before the Mage dogfoods practice UX. The Mage does not discover broken plumbing in Discord.

---

## Division of labor

| Layer | Owner | Method |
|-------|-------|--------|
| **Spirit gate** | Spirit (Forge + Mini) | `unittest`, `shake_*.py` offline, `SHAKE_LIVE=1` live on Mini |
| **Mage gate** | Mage (async) | Screenshot + felt-sense in Forge; acceptance scenarios marked UX-only |

Standing rule from `cast_shake.md`: Spirit owns technical functioning and integration. Mage owns user experience — tone, pacing, whether they would reach for it again.

---

## After every turtleOS deploy chapter

Spirit runs on Mac Mini (or Forge SSH):

```bash
cd ~/turtleos && git pull origin main
# restart services if runtime Python changed (dyad approval for active use)

# Offline suite (always)
~/turtleos/venv/bin/python3 -m unittest discover -s tests -q
~/turtleos/venv/bin/python3 scripts/shake_river.py
~/turtleos/venv/bin/python3 scripts/shake_flow.py navigator
~/turtleos/venv/bin/python3 scripts/shake_eddy_bar.py
~/turtleos/venv/bin/python3 scripts/shake_link_read.py
~/turtleos/venv/bin/python3 scripts/shake_lifecycle.py
~/turtleos/venv/bin/python3 scripts/shake_discord_ref.py

# Live suite (Mini) — run subset by **changed surface**, not full matrix every deploy

| If you touched… | Add live shake |
|-----------------|----------------|
| Flow runner / Navigator / in-eddy flows | `shake_flow.py navigator --live` |
| Eddy bar / spawn / rename | `shake_eddy_bar.py --live` |
| Link read / content fetch | `shake_link_read.py --live` |
| Discord permalink self-feed | `shake_discord_ref.py --live` |
| Lifecycle checkpoint/release | `shake_lifecycle.py --live` |
| Share eddy | `shake_share_eddy.py` (offline) + Mage S1 dogfood on Mini (`--live` not implemented) |
| Hosted river onboarding | `shake_hosted_river.py --live` |
| River acts / classification only | `shake_river.py` (offline usually enough) |

**Full shake inventory** (not exhaustive of every future script — check `scripts/shake_*.py`):

- `shake_river.py` — River parse/prompt/routing
- `shake_flow.py` — per-flow (navigator default)
- `shake_eddy_bar.py` — eddy spawn + bar
- `shake_link_read.py` — H-rows / X2
- `shake_lifecycle.py` — R4/R5
- `shake_discord_ref.py` — D2/D2b
- `shake_share_eddy.py` — S1+
- `shake_hosted_river.py` — O-rows
- `shake_spawn_eddy.py` — helper for live flow shake (not standalone gate)
- `shake_report.py` — aggregates `test-runs/shake-*-latest.json`

River noise during development is acceptable; scope live runs to what the chapter touched plus a **smoke** (`navigator --live`) when unsure.

~/turtleos/venv/bin/python3 canary.py
~/turtleos/venv/bin/python3 scripts/shake_report.py --strict
```

Shortcut: `./scripts/shake_after_deploy.sh` (offline) and `SHAKE_LIVE=1 ./scripts/shake_after_deploy.sh` (partial live — extend script as suite grows).

**Mini ops (Layer 1+2, sanctioned 2026-06-26):** `./scripts/ops_runner.sh` or `python scripts/ops_runner.py` — full offline suite + canary + update drift + Spirit Ops Report to `desk/craft/automation-reports/latest.md`. Local qwen summary on FAIL only. Scheduled via `docs/install/com.turtle.ops-gate.plist.example`. See `docs/automation/registry.md`.

**Dashboard:**

```bash
python scripts/shake_report.py          # markdown for Forge / briefing
python scripts/shake_report.py --json   # machine-readable
```

Verdict artifacts: `test-runs/shake-*-latest.json`. Report: `test-runs/shake-report-latest.json` (written when using `--write` if added).

---

## Mage notification

**Clarification (2026-06-26):** Option **1A** is Spirit running live shake via **Forge SSH during a deploy chapter** — not async automation pinging the Mage. Gate **fail** feedback goes to **Spirit on Forge** for fix-and-retest; the Mage is not in the functional-test loop.

Only after `shake_report.py --strict` passes (functional gate **pass**):

Post to **Forge** (briefing or chapter close) — not `#craft-turtle`:

```
Functional gate CLOSED — [chapter name]
Mage UX only: J1, D2, H1 feel — screenshot + felt-sense when convenient
```

`#craft-turtle` is **Mage intake** for practice frictions discovered during your own use (forwards, screenshots, short reports) — triaged for a **future** Forge session. It is not the Spirit gate feedback channel.

If gate **fail**: Spirit fixes on Forge, re-runs suite, does not ask Mage to verify plumbing.

---

## Mage ideation (non-technical input)

Chapter intent template (Mage → Spirit translation):

```markdown
## Chapter intent
- Friction / wish: …
- Who: (you / hosted practitioner / generic Pop 2)
- Feel when done: …
- Priority tier: (optional — Spirit maps to priority-stack.md)
```

Spirit produces: chapter doc, spec § trace, acceptance rows, implementation slice, shake mapping.

---

## Compounding

- Shake fail → fix → tighten offline assertion (`cast_shake.md` compounding).
- Mage UX dogfood → proposal only when insight is durable.
- Chapter harvest → `docs/learnings.md` + acceptance README status.

---

## Open decisions (dyad — not yet sanctioned)

| # | Decision | Options | Default if silent |
|---|----------|---------|-------------------|
| 1 | **Live shake trigger** | Forge SSH after each deploy · Cursor Automation on `main` push · Mini hook offline-only | Forge SSH (today) |
| 2 | **Mage ping surface** | Forge only · `#craft-turtle` · briefing Lessons | Forge + craft channel on fail |
| 3 | **Live suite scope** | Full live every deploy · changed-surface only | Changed-surface + navigator smoke |
| 4 | **`shake_report --strict` in CI** | turtleos unittest job · manual only | Manual at deploy |

Sanction updates this table; Spirit operates on sanctioned row until Mage redirects.
