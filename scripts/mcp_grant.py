#!/usr/bin/env python3
"""Offer, create, list and revoke MCP access grants.

``offer`` is the path for anyone but yourself: it writes an offer into the
owner's root, River posts it in their river, and the grant exists only when
they press Connect and their Spirit picks it up from their own Tailscale
account — nobody sees the key. The owner's Tailscale account must be linked
in the registry first (``--tailscale-login`` links it), because a pickup from
an unlinked account can never succeed. ``create`` is for a grant
over your own sources.

``create`` previews by default: it prints the grant it would make and makes
nothing. ``--yes`` makes it. The credential is never printed; it is written
once to ``--credentials-out`` (created 0600, refused if the file exists) as a
client config snippet, and only its hash is kept.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mcp_access import offers  # noqa: E402
from mcp_access.grants import GrantStore, state_dir  # noqa: E402
from mcp_access.operations import PROFILES, snapshot_for  # noqa: E402
from mcp_access.registry import load_registry, member_for_login, owned_sources, registry_path  # noqa: E402

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


def require_self(owner: str, registry: dict) -> None:
    """The host operator is the registry's admin; `create` is theirs, over their own sources."""
    entry = (registry.get("mages") or {}).get(owner) or {}
    if not entry.get("admin"):
        raise SystemExit(
            f"{owner!r} is not the host operator: a credential for someone else's context "
            "must not pass through the operator. Use `offer` — they accept it in their home channel."
        )


def cmd_create(args, store: GrantStore) -> int:
    registry = load_registry()
    require_self(args.owner, registry)
    sources = plan(args.owner, args.profile, args.source or [], registry)
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


def published_url() -> str | None:
    receipt = state_dir() / "expose_receipt.json"
    if receipt.is_file():
        return json.loads(receipt.read_text(encoding="utf-8")).get("url")
    return None


_LOGIN = re.compile(r"^[^\s@:'\"#]+@[^\s@:'\"#]+$")


def link_login(path: Path, member: str, login: str) -> None:
    """Insert ``tailscale_login`` under ``mages.<member>``, keeping the file's comments and order."""
    if not _LOGIN.match(login):
        raise SystemExit(f"not a Tailscale login: {login!r}")
    text = path.read_text(encoding="utf-8")
    registry = load_registry(path)
    owner = member_for_login(registry, login)
    if owner and owner != member:
        raise SystemExit(f"{login} is already linked to {owner!r}")
    entry = (registry.get("mages") or {}).get(member)
    if entry is None:
        raise SystemExit(f"no member {member!r} in {path}")
    if entry.get("tailscale_login"):
        raise SystemExit(f"{member!r} is already linked to {entry['tailscale_login']}; edit the registry to change it")
    lines = text.splitlines(keepends=True)
    in_mages, at = False, None
    for i, line in enumerate(lines):
        if re.match(r"^mages:\s*$", line):
            in_mages = True
        elif in_mages and re.match(r"^\S", line):
            break
        elif in_mages and re.match(rf"^  {re.escape(member)}:\s*$", line):
            at = i
            break
    if at is None:
        raise SystemExit(f"could not find the block for {member!r} under mages: — link it by hand")
    lines.insert(at + 1, f"    tailscale_login: {login}\n")
    new = "".join(lines)
    tmp = path.with_name(path.name + ".linking")
    tmp.write_text(new, encoding="utf-8")
    if member_for_login(load_registry(tmp), login) != member:
        tmp.unlink()
        raise SystemExit("linking did not read back; registry left unchanged")
    os.replace(tmp, path)


def cmd_offer(args, _store: GrantStore) -> int:
    registry = load_registry()
    linked = ((registry.get("mages") or {}).get(args.owner) or {}).get("tailscale_login")
    if not linked and not args.tailscale_login:
        raise SystemExit(
            f"{args.owner!r} has no linked Tailscale account, so a pickup could never succeed. "
            "Re-run with --tailscale-login <their Tailscale login>."
        )
    if linked and args.tailscale_login and linked.casefold() != args.tailscale_login.casefold():
        raise SystemExit(f"{args.owner!r} is linked to {linked}, not {args.tailscale_login}")
    sources = plan(args.owner, args.profile, args.source or [], registry)
    root = next((s.root for s in owned_sources(args.owner, registry) if s.kind == "private"), None)
    if root is None:
        raise SystemExit(f"{args.owner!r} has no private root to hold the offer")
    url = args.url or published_url()
    if not url:
        raise SystemExit("no published URL: run mcp_expose.py apply, or pass --url")
    print(json.dumps({"owner": args.owner, "principal": args.principal, "profile": args.profile,
                      "sources": sources, "url": url, "posts_to": "the owner's river",
                      "tailscale_login": linked or f"{args.tailscale_login} (will be linked)"}, indent=2))
    if not args.yes:
        print("preview only — nothing offered. Re-run with --yes.")
        return 0
    if not linked:
        link_login(registry_path(), args.owner, args.tailscale_login)
        print(f"linked {args.owner!r} to {args.tailscale_login}")
    offer = offers.create(root, owner=args.owner, principal=args.principal, sources=sources,
                          profile=args.profile, url=url)
    print(f"offered {offer.id}; River posts it within a minute. No credential exists until the owner presses Connect and their Spirit picks it up.")
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
    o = sub.add_parser("offer", help="offer a connection the owner accepts in their home channel")
    o.add_argument("--owner", required=True)
    o.add_argument("--principal", required=True)
    o.add_argument("--profile", default="reader")
    o.add_argument("--source", action="append")
    o.add_argument("--url")
    o.add_argument("--tailscale-login", help="link the owner's Tailscale account if it is not linked yet")
    o.add_argument("--yes", action="store_true")
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("grant")
    r.add_argument("--revision", type=int, required=True)
    args = p.parse_args(argv)
    store = GrantStore()
    return {"create": cmd_create, "offer": cmd_offer, "list": cmd_list, "revoke": cmd_revoke}[args.cmd](args, store)


if __name__ == "__main__":
    raise SystemExit(main())
