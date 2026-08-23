# Self-Heal Registry

**Canonical law:** `TURTLE_SPEC.md` §20.4. **Implementation:** `self_heal.py` (`HEAL_REGISTRY`).

Operator default: only registry-listed checks may auto-heal. All other recovery is inspect → propose → dyad craft.

## Registry

| Canary check | Healable | Action | On failure |
|--------------|----------|--------|------------|
| `ollama` | **Yes** | `restart_ollama()` | Alert Mage |
| `loops` | No | — | Alert Mage (bot restart is dyad action) |
| `practice_freshness` | No | — | Alert Mage (topology-aware practice state freshness) |
| `file_io` | No | — | Alert Mage (filesystem intervention) |
| `discord` | No | — | Alert Mage (connection unhealthy) |

## Invocation

1. **Health canary (INT-027):** `background.py` → `check_and_heal(check_name)` before Discord alert.
2. **On-demand:** `full_diagnostic()` and `!diagnose` — read-only status; no ad-hoc restarts.

## Adding a heal path

Requires **both**:

1. Amendment to `TURTLE_SPEC.md` §20.4 table
2. Matching `HealEntry` in `self_heal.py`

## Retired (do not re-add without explicit resurrection)

- LiveSync bridge / tunnel restart
- CouchDB restart

## Dyad-only (never auto-heal)

- `git pull` / commit / deploy
- `com.turtle.discord` / `com.turtle.river` restart
- Caddy restart
- Shell source edits
