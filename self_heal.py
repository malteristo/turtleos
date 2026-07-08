"""turtleOS self-healing — pre-defined repair actions only.

Authority model: TURTLE_SPEC.md §20.4. Only registry-listed checks may auto-heal.
Used by the health canary (INT-027) before alerting and by !diagnose for status.
"""

from __future__ import annotations

import asyncio
import subprocess
import os
from dataclasses import dataclass
from typing import Awaitable, Callable

OLLAMA_PATH = "/opt/homebrew/bin/ollama"

# launchd labels for read-only diagnostics (not auto-restart — dyad deploy ritual).
DIAGNOSTIC_SERVICES = {
    "discord": "com.turtle.discord",
    "river": "com.turtle.river",
    "canary": "com.turtle.canary",
    "caddy": "com.turtle.caddy",
}


@dataclass(frozen=True)
class HealEntry:
    healable: bool
    action: str | None = None
    reason: str = ""


# Canonical registry — must match TURTLE_SPEC.md §20.4.
HEAL_REGISTRY: dict[str, HealEntry] = {
    "ollama": HealEntry(healable=True, action="restart_ollama"),
    "loops": HealEntry(
        healable=False,
        reason="Background loops require full bot restart — dyad action",
    ),
    "practice_freshness": HealEntry(
        healable=False,
        reason="Stale boom/compass — practice sync, not infra restart",
    ),
    "file_io": HealEntry(
        healable=False,
        reason="Filesystem intervention required",
    ),
    "discord": HealEntry(
        healable=False,
        reason="Discord connection unhealthy — bot restart is dyad action",
    ),
}


async def restart_ollama() -> tuple[bool, str]:
    """Restart Ollama by killing and letting launchd respawn."""
    try:
        await asyncio.to_thread(
            subprocess.run,
            ["pkill", "-f", "ollama"],
            capture_output=True,
            timeout=5,
        )
        await asyncio.sleep(3)

        import urllib.request

        try:
            resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
            if resp.status == 200:
                return True, "Ollama restarted and responding"
        except Exception:
            pass

        await asyncio.to_thread(
            subprocess.Popen,
            [OLLAMA_PATH, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(5)
        try:
            resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
            if resp.status == 200:
                return True, "Ollama manually started and responding"
        except Exception:
            pass

        return False, "Ollama restart failed — not responding after restart attempts"
    except Exception as e:
        return False, f"Ollama restart failed: {e}"


_ACTIONS: dict[str, Callable[[], Awaitable[tuple[bool, str]]]] = {
    "restart_ollama": restart_ollama,
}


async def check_and_heal(check_name: str) -> tuple[bool, str] | None:
    """Attempt a registry-listed heal. Returns None if check is not healable."""
    entry = HEAL_REGISTRY.get(check_name)
    if entry is None or not entry.healable or not entry.action:
        return None

    action = _ACTIONS.get(entry.action)
    if action is None:
        return None
    return await action()


def registry_summary() -> list[dict[str, str | bool]]:
    """Machine-readable registry for diagnose surfaces."""
    rows: list[dict[str, str | bool]] = []
    for name, entry in HEAL_REGISTRY.items():
        rows.append(
            {
                "check": name,
                "healable": entry.healable,
                "action": entry.action or "",
                "reason": entry.reason,
            }
        )
    return rows


async def full_diagnostic() -> list[dict]:
    """Read-only service and Ollama status. Does not restart anything."""
    results: list[dict] = []

    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        launchctl_out = proc.stdout
    except Exception as e:
        launchctl_out = ""
        results.append({"name": "launchctl", "status": "error", "pid": None, "detail": str(e)})

    for name, service_id in DIAGNOSTIC_SERVICES.items():
        found = False
        for line in launchctl_out.split("\n"):
            if service_id in line:
                parts = line.split()
                pid = parts[0] if parts and parts[0] != "-" else None
                exit_code = parts[1] if len(parts) > 1 else None
                status = "running" if pid and pid.isdigit() else "stopped"
                results.append(
                    {
                        "name": name,
                        "status": status,
                        "pid": pid,
                        "detail": f"{service_id} exit: {exit_code}",
                    }
                )
                found = True
                break
        if not found and launchctl_out:
            results.append(
                {"name": name, "status": "not registered", "pid": None, "detail": service_id}
            )

    try:
        import urllib.request

        resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        if resp.status == 200:
            results.append({"name": "ollama", "status": "running", "pid": None, "detail": "API responding"})
        else:
            results.append({"name": "ollama", "status": "degraded", "pid": None, "detail": f"HTTP {resp.status}"})
    except Exception:
        results.append({"name": "ollama", "status": "down", "pid": None, "detail": "API not responding"})

    return results
