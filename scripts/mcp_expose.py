#!/usr/bin/env python3
"""Publish the MCP access point on the tailnet — and only the tailnet.

``check`` (default) runs the named checks and changes nothing. ``apply`` runs
them, publishes only if every one passes, re-reads the config to confirm, and
writes a receipt. ``remove`` unpublishes. Any failure exits non-zero and names
the check.

The MCP port must not carry Funnel: Funnel requests arrive without tailnet
identity, and the server's credential binding depends on that identity.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mcp_access.grants import state_dir  # noqa: E402
from mcp_access.server import DEFAULT_PORT  # noqa: E402

HTTPS_PORT = 8443
MAC_APP_CLI = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def backend_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def evaluate(serve: dict, host: str, https_port: int, backend: str, health_ok: bool) -> list[Check]:
    key = f"{host}:{https_port}"
    web = (serve.get("Web") or {}).get(key) or {}
    handlers = web.get("Handlers") or {}
    ours = {"/": {"Proxy": backend}}
    funnel = bool((serve.get("AllowFunnel") or {}).get(key))
    return [
        Check("not_the_funnel_port", https_port != 443, f"https port {https_port}"),
        Check("backend_healthy_on_loopback", health_ok, f"{backend}/health"),
        Check(
            "port_free_or_ours",
            not handlers or handlers == ours,
            "free" if not handlers else json.dumps(handlers),
        ),
        Check("funnel_off", not funnel, f"AllowFunnel[{key}]={funnel}"),
    ]


def published(serve: dict, host: str, https_port: int, backend: str) -> bool:
    key = f"{host}:{https_port}"
    handlers = ((serve.get("Web") or {}).get(key) or {}).get("Handlers") or {}
    funnel = bool((serve.get("AllowFunnel") or {}).get(key))
    return handlers == {"/": {"Proxy": backend}} and not funnel


def _cli() -> str:
    found = shutil.which("tailscale")
    if found:
        return found
    if os.path.exists(MAC_APP_CLI):
        return MAC_APP_CLI
    raise SystemExit("check tailscale_cli: not found")


def _json(*args: str) -> dict:
    try:
        out = subprocess.run([_cli(), *args, "--json"], check=True, capture_output=True, text=True)
        data = json.loads(out.stdout or "{}")
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"FAIL tailscale_{args[0]}_readable: {type(exc).__name__}")
    if not isinstance(data, dict):
        raise SystemExit(f"FAIL tailscale_{args[0]}_readable: not an object")
    return data


def _host() -> str:
    return str(_json("status").get("Self", {}).get("DNSName", "")).rstrip(".")


def _health(backend: str) -> bool:
    try:
        with urllib.request.urlopen(f"{backend}/health", timeout=3) as r:
            return r.status == 200 and json.loads(r.read()).get("status") == "ok"
    except (OSError, ValueError):
        return False


def _report(checks: list[Check]) -> bool:
    for c in checks:
        print(f"{'ok  ' if c.ok else 'FAIL'} {c.name}: {c.detail}")
    return all(c.ok for c in checks)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("action", nargs="?", default="check", choices=["check", "apply", "remove"])
    p.add_argument("--https-port", type=int, default=HTTPS_PORT)
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help="loopback backend port")
    args = p.parse_args(argv)
    backend = backend_url(args.port)
    host = _host()
    if not host:
        print("FAIL tailnet_host: tailscale reports no DNS name")
        return 1

    if args.action == "remove":
        subprocess.run([_cli(), "serve", f"--https={args.https_port}", "off"], check=True)
        print(f"removed https://{host}:{args.https_port}")
        return 0

    checks = evaluate(_json("serve", "status"), host, args.https_port, backend, _health(backend))
    if not _report(checks):
        return 1
    if args.action == "check":
        print("check only — nothing changed.")
        return 0

    subprocess.run(
        [_cli(), "serve", "--bg", f"--https={args.https_port}", backend], check=True, capture_output=True
    )
    after = _json("serve", "status")
    if not published(after, host, args.https_port, backend):
        print("FAIL post_apply: serve config does not match; run `remove` and inspect")
        return 1
    url = f"https://{host}:{args.https_port}/mcp"
    receipt = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "backend": backend,
        "checks": [c.__dict__ for c in checks],
    }
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "expose_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"published {url} (tailnet only); receipt in {d / 'expose_receipt.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
