# MCP access point — turtleOS reachable from any AI client

**Status:** Draft 2026-09-24 · design before code
**Spec reference:** TURTLE_SPEC §15.5 (multi-practitioner data flow), §3.2.1 (health), §20 (self-development)
**Builds on:** `docs/native-harness.md` (capability registry, policy gate, audit), `docs/chapters/design-health-record.md` (subject owns record meaning), `docs/chapters/design-hosted-river.md` (no report to the operator)
**Reference implementation studied:** gbrain remote MCP (§9)

---

## 1. What this is

turtleOS today is reached through Discord. This document adds a second front door: an **MCP server** that any MCP-capable AI client can connect to — a member's Cursor on their own laptop with whatever model they choose, the operator's Forge, Claude Desktop, a phone app on the tailnet, and later cloud agents.

**Why it matters: personal context management.** A person accumulates and curates their context on turtleOS — conversations, notes, a health picture — by practising with it. Any AI agent they grant MCP access can then work with that context, for whatever they are doing at the moment. The person decides what is exposed, to which agent, for how long, and sees every access in their own root. No skill file, no export, no copy: connect to the server and it explains itself (§2, `initialize.instructions`, `turtleos://brief`).

It is an access point for the platform, not a feature for one member or one practice. Practices built on turtleOS (for instance `docs/design/co-created-practice.md`) may use it; it does not know about them.

## 2. Principle

**A sovereign system explains itself and protects its integrity.**

- *Explains itself.* A connected agent needs nothing but the connection: `initialize` returns instructions that say what turtleOS is, whose context this is, how to use every tool offered, and what the connection cannot do; every resource and tool carries a description. Enforced: `SelfDescriptionTests` fails if a listed tool is not named in the instructions or anything listed lacks a description. A client does not discover turtleOS by scanning files. The server authors an honest account of what this connection may reach, what is live there and what needs attention (`turtleos://brief`), and a machine-readable account of the connection's own authority (`turtleos://capabilities`). The brief is honest when things are broken.
- *Protects its integrity.* Every grant is least-privilege, every call is audited where the data's owner can see it, and River watches the access point: expired or unused grants, refused calls, publish drift, a listener that should not exist.

## 3. Roles — the split gbrain does not need and turtleOS does

gbrain has one owner: whoever runs the server owns the brain. turtleOS hosts several members on one machine, so two roles that coincide there are separate here.

| Role | Holds | Can | Cannot |
|---|---|---|---|
| **Host operator** | the host, the service, the owner credential for the *service* | publish / unpublish, see which grants exist and their health, revoke any grant in an emergency | read any member's content; approve access to a member's sources |
| **Source owner** | a practice root (registry `mage`), or a health instance where they are `subject` | approve, narrow, revoke grants to their own sources; see their audit | grant access to anyone else's source |
| **Client principal** | one grant | the operations the grant names, on the sources it names | widen itself; administer; see that out-of-scope sources exist |

Consent to a grant is given by the **source owner**, in their own river (the turtleOS equivalent of gbrain's owner consent page). A shared room's grant needs every member whose room it is, recorded next to the grant.

## 4. Decisions

| # | Question | Decision | Why |
|---|---|---|---|
| D1 | Publishing | Server binds `127.0.0.1` only. `tailscale serve` terminates HTTPS on the host's MagicDNS name and forwards. Public reach (`tailscale funnel`) is a separate explicit switch, off, for cloud agents only | gbrain's shape; nothing listens on a routable address; Tailscale ACLs gate reach |
| D2 | Unit of access | A **grant**: one client principal × a set of sources × a profile. One grant per client installation; shared credentials are one principal | gbrain: profile grants authority; the source list confines it |
| D3 | Profiles | `reader` (read + search), `writer` (reader + governed writes), `operator-health` (host health only, no content). No `full` | Least privilege; the host operator's profile carries no content by construction |
| D4 | Surface vs authority | The visible tool list follows the profile; a wider surface never adds authority | gbrain: "full surface does not bypass a grant" |
| D5 | Operation snapshot | A grant records the operation names at grant time. A server upgrade does not widen existing grants; widening is an explicit regrant the owner approves | gbrain; stops silent scope creep across deploys |
| D6 | Sources | A source is a practice root or a health instance. The candidate list for a member is derived from the registry (`mage`, health `subject`); the grant names which of them it covers | Ownership already lives in the registry; a second list would drift |
| D7 | Shared rooms | Expressible from v1 as a source kind with a consent list; **not granted in v1** | "Add them later" must be one grant, not a redesign |
| D8 | Connection methods | v1: **machine handoff** — a bearer credential revealed once in the source owner's river, installed in the client's MCP config, 30-day expiry, renewal in the river. Later: native OAuth/PKCE with consent in the river | Cursor accepts a URL + header today; OAuth is the better lifecycle and comes second, as gbrain distinguishes the two paths |
| D9 | Tailnet identity | Record the Tailscale identity headers `tailscale serve` adds on first use; a later call from a different tailnet identity is refused | A copied credential off-tailnet or on another person's device fails. **Verify** the headers on the host's Tailscale version before relying on them (O1) |
| D10 | Writes | Only through capabilities that already exist and are already governed: health `governed_record` (subject authority, provenance), eddy-note-shaped practice notes. New write kinds arrive as native capabilities first | The access point is a new mouth on old hands |
| D11 | Out of scope | Refused as `not_found`, indistinguishable from nonexistent | gbrain `sources_remove`; existence is information |
| D12 | Audit | `{ts, grant, principal, capability, source, decision}` appended in the **source's own root**; the host keeps only counts per grant | The owner sees who touched their context; the operator sees that a grant is used, not what it read |
| D13 | Lifecycle | Distinct `invalidate` (tokens), `revoke` (keep record + audit), `delete` (registration gone, audit kept); every change previews first and applies against a revision | gbrain `ADMIN.md`; a lost response is not proof nothing changed |
| D14 | Publish tool | `scripts/mcp_expose.py` — `check` (default, changes nothing), `apply`, `remove`; named checks; a receipt without secrets; fail-closed when `tailscale serve status` cannot be read; refuses a port carrying another handler or Funnel. Publishes on **HTTPS :8443**, never :443 | gbrain's expose steps. :443 on the reference host already carries Funnel for the artifact reader; a Funnel request has no tailnet identity, so D9 cannot hold on a Funnel port |
| D15 | Runtime | Own launchd service `com.turtle.mcp`; `restart.sh` kickstarts it when loaded, behind the same deploy guard (tested) | A server crash must not take the bots down |
| D16 | Brief | Live-computed per call from the runtime's own readers; carries an integrity block (grant expiry, refused calls since last brief, stale sync) | Snapshots are one more writer nobody reads |
| D17 | Verification bar | "Registered", "configured", "server checks pass" and "observed in the actual client" are four different results, reported separately | gbrain's evidence rule; presence is not function |
| O1 | Tailscale identity headers present and unspoofable through `serve` on this host | **resolved 2026-09-24** — from the Tailscale source (1.102): `serve` deletes client-sent `Tailscale-User-*` and sets them for user-owned nodes; sets `X-Forwarded-For` to the tailnet source address; both empty for tagged nodes and Funnel. Binding = login + address; missing identity is refused | D9 rests on it. Holds only because the backend is loopback (D1) |
| O2 | Resource granularity for eddy notes (whole notes vs. search-only) | **open** | First real session's evidence |
| O3 | Rate limits, body cap | **open** | Adopt gbrain's defaults when the server exists |
| O4 | Funnel for cloud agents | **open, off** | No cloud client asked yet |

## 5. Surface (v1)

**Resources**
- `turtleos://capabilities` — this connection's effective grant: principal, profile, sources, operation snapshot, expiry, revision.
- `turtleos://brief` — sources in scope and their last activity; recent eddy titles; health picture summary where the principal's owner is subject; the integrity block (D16).
- `turtleos://room/<source>/notes` — eddy notes (O2).
- `turtleos://health/<source>/picture`, `turtleos://health/<source>/record` — subject only.

**Tools**
- `search(query, source?)`, `read(ref)` — scope-checked.
- `save_health_observation`, `recap_health_visit` — existing governed capabilities, principal as actor.
- `note(text, source)` — practice note in the owner's root, eddy-note shape, `source: mcp`.

## 6. What this is not

- **Not the MCP client layer.** `mcp-layer-design-draft.md` (operator workshop intake) designs turtleOS *calling* external MCP servers. Both directions sit behind the same control plane (`native-harness.md` § Capability).
- **Not model selection.** The client's model is the client's business.
- **Not an operator read path.** No profile gives the host operator content (D3); a test enumerates the capability registry so a new capability is covered by default.
- **Not a practice.** It serves any practice and encodes none.

## 7. Enforcement owed (same change as the code)

- **Listener** — the server refuses to start on any bind other than loopback; test runs the check against `0.0.0.0` and a tailnet address.
- **Scope boundary** — per capability, a request against a source outside the grant is refused as `not_found`; *positive control:* a planted file in the out-of-scope source is readable by its owner's grant.
- **No operator content path** — every capability in the registry refuses `operator-health` against a content resource.
- **Snapshot** — after adding a capability to the registry, an existing grant does not see it until regranted.
- **Tailnet identity** — the same credential with a different identity header is refused; with its own identity it passes.
- **Honest brief** — with a missing source root, the brief says unavailable (and audit does not recreate the root); with a refused call planted, the integrity block counts it. The host has no sync on the source side, so "stale sync" is not a state here.
- **Audit location** — audit lines land in the source's root; none in the operator's root.
- **Publish tool** — `mcp_expose.py` fails by name (not "not exposed") when `tailscale serve status` returns non-JSON; refuses Funnel, :443, a foreign handler, an unhealthy backend.

Implemented in `tests/test_mcp_access.py`; each guard has a positive control, and the scope, identity and path-confinement guards were mutation-checked (disable the guard → the suite fails). The protocol is hand-rolled JSON-RPC on aiohttp (no SDK on the host); conformance was checked once with the official Python SDK client (2.2) against a local server.

## 8. Slices

| # | Target condition | Verified by |
|---|---|---|
| 1 | `com.turtle.mcp` on loopback, published by `mcp_expose.py`; one reader grant; `capabilities` + `brief` answer in a real Cursor | §7 listener, publish tool; observed call in the client (D17). **Code + server checks done 2026-09-24; not yet installed or observed** |
| 2 | Read + search over the grant's sources; source-owner consent + credential reveal in their river | §7 scope boundary, no operator path, audit location. **Read + search done; consent + reveal in the river not built** — until then `mcp_grant.py` writes the credential to a 0600 file |
| 3 | Writer profile: governed health writes + `note` | governed-record tests extended to principal-as-actor; snapshot test |
| 4 | Lifecycle (invalidate / revoke / delete, revisions) + River integrity watch | §7 honest brief; revoke observed in the client |
| 5 | Native OAuth/PKCE with consent in the river | D17 observed in the client |

## 9. Reference: gbrain remote MCP

Studied 2026-09-24: `docs/guides/remote-mcp.md`, `docs/guides/hosted-harness-access.md`, `docs/mcp/ADMIN.md`, `SECURITY.md` in `github.com/garrytan/gbrain`.

| gbrain | Here |
|---|---|
| Loopback bind; `tailscale serve` terminates TLS; `--funnel` explicit for cloud agents | **Adopted** (D1, O4) |
| `gbrain mcp expose`: named checks, dry-run, consent, receipt without secrets, `--status` finds leftovers, `--remove` touches only its own handler, fail-closed on unreadable Tailscale state | **Adopted** as `mcp_expose.py` (D14) |
| Grant = profile (authority) × source; surface selects visible tools, never authority | **Adopted** (D2–D4) |
| Operation snapshot per grant; upgrades don't widen | **Adopted** (D5) |
| `gbrain://capabilities` describes the connection's authority and never upgrades it | **Adopted** (`turtleos://capabilities`) |
| Native OAuth/PKCE vs private machine handoff as distinct paths | **Adopted, order reversed for v1** (D8): machine handoff first, because Cursor takes a header today and consent lives in Discord |
| Owner = host admin = data owner; owner dashboard and login links | **Adapted** — split into host operator and source owner; consent in the owner's river (§3) |
| DCR off by default, every self-registration waits for approval | **Adopted in spirit**: no self-registration at all in v1 |
| Out-of-scope source answers `not_found` | **Adopted** (D11) |
| invalidate / revoke / delete with preview + revision | **Adopted** (D13) |
| Four-step evidence: registered ≠ configured ≠ server-verified ≠ observed in the harness; synthetic round trip with cleanup | **Adopted** (D17) |
| Audit table on the host | **Adapted** — audit in the source's root; host holds counts only (D12) |
| Delegation, spending caps, shared skills | **Not adopted** — no need yet |
