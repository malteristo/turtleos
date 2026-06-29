# turtleOS Architecture — Mac Mini Instance (2026-06-29)

> **Product law:** [`ARCHITECTURE.md`](../ARCHITECTURE.md), [`TURTLE_SPEC.md`](../TURTLE_SPEC.md)  
> **Spec → code:** [`traceability-matrix.md`](traceability-matrix.md)

This document describes **what runs on the operator Mac Mini** after the native-practice-root migration.

---

## Process Architecture

| Service | launchd label | Role |
|---------|---------------|------|
| **Turtle** | `com.turtle.discord` | Dialogue in eddies — native attunement |
| **River** | `com.turtle.river` | Acts in parent channels (checkpoint, flows, share) |
| **Ollama** | (system) | Local inference (River + Turtle models) |
| **Caddy** | `com.turtle.caddy` | HTTPS (Tailscale) |
| **Caffeinate** | `com.turtle.caffeinate` | Keep Mini awake |
| **Canary** | `com.turtle.canary` | Mechanical health checks |
| **Ops gate** | `com.turtle.ops-gate` | Automation gate |

**Retired:** CouchDB, LiveSync bridge/tunnel, `~/workshop/` Magic clone on disk.

---

## Filesystem Layout

```
/Users/turtle/
├── turtleos/                 # Platform — bots, registry, template, identity
├── repos/
│   └── magic.git             # Bare repo — Forge pushes full Magic workshop (host only)
└── workshops/
    ├── kermit/               # Operator native practice + runtime (colocated)
    ├── nesrine/              # Hosted practitioner
    ├── lukas/                # Hosted practitioner
    ├── family/               # Shared space
    └── .archived/            # Metabolized workshops (Discord archived / legacy)
```

### Operator (Kermit) — native topology

```
~/workshops/kermit/
├── character/          # Turtle attunement (template + custom)
├── flows/              # Navigator, Companion, …
├── chronicle/          # Deep event log
├── state/notes/        # Flow checkpoints (navigator-last.md, …)
├── sessions/           # Turtle checkpoint writes → sync to Forge desk/sessions/
├── proposals/          # Turtle proposals → sync to Forge desk/proposals/
├── thread-state/       # Eddy continuity
├── native-runtime/     # Task queue + audit
└── share/, signals/, … # Runtime surfaces
```

**No** `~/workshop/` clone. **No** Magic `library/`, `system/`, `floor/` on Mini.  
Magic practice (boom, intentions, summoning) lives on the **Forge** only.  
Turtle outputs flow **Mini → Forge** via `scripts/sync_practice_root.sh pull`.

### Registry routing

`mage_registry.yaml` maps Discord channel → `practice_dir` + `runtime_dir`.  
For Kermit both are `~/workshops/kermit`. Spaces (`family`) use `~/workshops/family/`.

---

## Sync with Forge

| Direction | Mechanism |
|-----------|-----------|
| Forge → Mini (framework) | `git push turtle main` → `~/repos/magic.git` (bare; not checked out) |
| Mini → Forge (Turtle outputs) | `scripts/sync_practice_root.sh pull` + `check_turtle_state.py` |

Watched paths: `sessions/`, `proposals/`, `state/notes/navigator-*.md` — not boom or briefings.

---

## Archive metabolism

When a Discord space is archived, move `~/workshops/<space>/` → `~/workshops/.archived/<space>-<date>/`.
