#!/usr/bin/env python3
"""Create, list and revoke MCP access grants.

``create`` previews by default: it prints the grant it would make and makes
nothing. ``--yes`` makes it. The credential is never printed; it is written
once to ``--credentials-out`` (created 0600, refused if the file exists) as a
client config snippet, and only its hash is kept.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mcp_access.grants import GrantStore  # noqa: E402
from mcp_access.operations import PROFILES, snapshot_for  # noqa: E402
from mcp_access.registry import load_registry, owned_sources  # noqa: E402

CONTENT_FREE = "operator-health"


def plan(owner: str, profile: str, wanted: list[str], registry: dict) -> list[str]:
    if profile not in PROFILES:
        raise SystemExit(f"unknown profile {profile!r}; known: {', '.join(PROFILES)}")
    if profile == CONTENT_FREE:
        if wanted:
            raise SystemExit(f"{CONTENT_FREE} reaches no sources; drop --source")
        return []
    owned = [s.id for s in owned_sources(owner, registry)]
    if not owned:
        raise SystemExit(f"{owner!r} owns no sources in the registry")
    if not wanted:
        return owned
    foreign = [s for s in wanted if s not in owned]
    if foreign:
        raise SystemExit(f"{owner!r} does not own: {', '.join(foreign)}")
    return wanted


def write_credentials(path: Path, url: str, token: str) -> None:
    snippet = {"mcpServers": {"turtleos": {"url": url, "headers": {"Authorization": f"Bearer {token}"}}}}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(snippet, f, indent=2)
        f.write("\n")


def cmd_create(args, store: GrantStore) -> int:
    sources = plan(args.owner, args.profile, args.source or [], load_registry())
    preview = {
        "principal": args.principal,
        "owner": args.owner,
        "profile": args.profile,
        "sources": sources,
        "operations": snapshot_for(args.profile),
        "ttl_days": args.ttl_days,
    }
    print(json.dumps(preview, indent=2))
    if not args.yes:
        print("preview only — nothing created. Re-run with --yes --credentials-out PATH.")
        return 0
    if not args.credentials_out:
        raise SystemExit("--yes needs --credentials-out: the credential is never printed")
    out = Path(os.path.expanduser(args.credentials_out))
    if out.exists():
        raise SystemExit(f"{out} exists; refusing to overwrite")
    grant, token = store.create(
        principal=args.principal,
        owner=args.owner,
        sources=sources,
        profile=args.profile,
        ttl_days=args.ttl_days,
    )
    try:
        write_credentials(out, args.url, token)
    except OSError:
        store.revoke(grant.id, if_revision=grant.revision)
        raise
    print(f"created {grant.id} (revision {grant.revision}); credential written to {out}")
    return 0


def cmd_list(_args, store: GrantStore) -> int:
    print(json.dumps([g.public() for g in store.all()], indent=2))
    return 0


def cmd_revoke(args, store: GrantStore) -> int:
    grant = store.revoke(args.grant, if_revision=args.revision)
    if grant is None:
        current = store.get(args.grant)
        where = f"current revision is {current.revision}" if current else "no such grant"
        raise SystemExit(f"not revoked: {where}")
    print(f"revoked {grant.id} (revision {grant.revision})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--owner", required=True)
    c.add_argument("--principal", required=True, help="who connects, e.g. 'laptop cursor'")
    c.add_argument("--profile", default="reader")
    c.add_argument("--source", action="append")
    c.add_argument("--ttl-days", type=int, default=30)
    c.add_argument("--url", default=os.environ.get("TURTLE_MCP_URL", "https://HOST.TAILNET.ts.net:8443/mcp"))
    c.add_argument("--credentials-out")
    c.add_argument("--yes", action="store_true")
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("grant")
    r.add_argument("--revision", type=int, required=True)
    args = p.parse_args(argv)
    store = GrantStore()
    return {"create": cmd_create, "list": cmd_list, "revoke": cmd_revoke}[args.cmd](args, store)


if __name__ == "__main__":
    raise SystemExit(main())
