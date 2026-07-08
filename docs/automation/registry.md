# Mini-hosted ops automation registry

**Status:** Active (2026-06-26)  
**Layers:** Layer 1 script ops (zero tokens) + Layer 2 qwen summary on FAIL only.

Spirit harvests reports from `desk/craft/automation-reports/latest.md` at `. craft` on Forge.

**Native topology (2026-06+):** Mini writes reports to `{practice_root}/state/notes/automation-reports/` (not a git checkout). `ops_harvest_sync` skips when no `~/workshop` clone exists. Forge pulls via Magic `scripts/sync_practice_root.sh pull`.

---

## Philosophy

| Principle | Rule |
|-----------|------|
| Scripts own truth | Pass/fail from `shake_report`, `canary`, unittest — never LLM |
| Local LLM optional | `ops_summarize.py` runs only when `ops_overall != pass` |
| River quiet | Ops reports go to workshop desk files, not `#craft-turtle` |
| Forge harvest | After each run, `ops_harvest_sync.py` commits report markdown to workshop `origin` |
| Canary alerts | Existing `canary.py` river alert on RED/degraded signature only |
| Forge fixes | FAIL → Spirit on Forge; Mage not in plumbing loop |

---

## Jobs

| Job ID | Trigger | Command | Output |
|--------|---------|---------|--------|
| `ops-gate` | Manual / default | `python scripts/ops_runner.py` | Full offline suite + report |
| `scheduled` | launchd daily 04:15 | `ops_runner.py --job scheduled` | Same as ops-gate |
| `post-merge` | git hook after pull | `ops_runner.py --job post-merge` | Same; hook ignores exit code |
| `quick` | Manual | `ops_runner.py --mode quick` | Canary + shake_report refresh only |

---

## Artifacts

| Path | What |
|------|------|
| `{practice_root}/state/notes/automation-reports/latest.md` | Spirit Ops Report (Forge harvest via `sync_practice_root.sh pull`) |
| `{practice_root}/state/notes/automation-reports/YYYY-MM-DD-HHMM-{job}.md` | Dated archive |
| `~/turtleos/test-runs/ops-report-latest.json` | Machine bundle |
| `~/turtleos/test-runs/shake-report-latest.json` | Shake dashboard JSON |
| `~/turtleos/logs/ops-gate.log` | launchd log |

Report directory resolves via `mage_registry.yaml` practice_dir when available.

### Harvest sync (Forge)

After `write_ops_artifacts`, `ops_runner.py` calls `ops_harvest_sync.sync_ops_harvest()` unless `--no-harvest-sync`:

1. Stage only `desk/craft/automation-reports/latest.md` and the dated archive from this run.
2. Commit: `ops harvest: {job} {ops_overall}`
3. Push workshop `origin` (turtle bare → Forge `git pull turtle main`)

Harvest sync failure does **not** change `ops_overall` exit code — ops truth stays script-owned; sync status appears in bundle `harvest_sync` and stdout.

---

## Install (Mini)

```bash
cd ~/turtleos
# Daily scheduled gate
cp docs/install/com.turtle.ops-gate.plist.example ~/Library/LaunchAgents/com.turtle.ops-gate.plist
# Edit paths if username != turtle
launchctl load ~/Library/LaunchAgents/com.turtle.ops-gate.plist

# Optional: ops gate after git pull
cp docs/install/git-post-merge-ops.example.sh .git/hooks/post-merge
chmod +x .git/hooks/post-merge
```

Manual smoke:

```bash
cd ~/turtleos && ./venv/bin/python3 scripts/ops_runner.py --json
```

---

## vs Cursor Cloud Agents

| Work | Mini ops (this) | Cursor Automation |
|------|-----------------|-------------------|
| Offline shake suite | **Default** | Optional backup |
| Token cost | **0** (qwen only on FAIL) | Cloud agent billing |
| Live Discord shake | Forge SSH chapter | Possible but costly |
| Pre-merge PR gate | Not this job | Good fit if needed |

---

## Related

- `docs/automation/functional-gate-protocol.md` — Spirit functional gate
- `scripts/shake_after_deploy.sh` — deploy chapter shortcut (subset of ops_runner suite)
- `docs/automation/cursor-shake-after-push.md` — optional cloud backup
