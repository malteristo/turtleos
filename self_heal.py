"""turtleOS self-healing — restart degraded tools and services.

Provides safe restart primitives for infrastructure components.
Used by the health canary (INT-027) for auto-recovery and by
!diagnose for manual intervention.
"""

import asyncio
import subprocess
import os


SERVICES = {
    "livesync-bridge": "com.turtle.livesync-bridge",
    "livesync-tunnel": "com.turtle.livesync-tunnel",
    "couchdb": "com.turtle.couchdb",
    "caddy": "com.turtle.caddy",
}

OLLAMA_PATH = "/opt/homebrew/bin/ollama"


async def restart_service(name: str) -> tuple[bool, str]:
    """Restart a launchd service by name. Returns (success, detail)."""
    service_id = SERVICES.get(name)
    if not service_id:
        return False, f"Unknown service: {name}. Known: {', '.join(SERVICES.keys())}"

    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            ["launchctl", "kickstart", "-k", f"user/{os.getuid()}/{service_id}"],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0:
            return True, f"Service {name} ({service_id}) restarted"
        else:
            # Try stop + start as fallback
            await asyncio.to_thread(
                subprocess.run,
                ["launchctl", "stop", service_id],
                capture_output=True, timeout=5,
            )
            await asyncio.sleep(2)
            await asyncio.to_thread(
                subprocess.run,
                ["launchctl", "start", service_id],
                capture_output=True, timeout=5,
            )
            return True, f"Service {name} restarted via stop/start"
    except subprocess.TimeoutExpired:
        return False, f"Service restart timed out: {name}"
    except Exception as e:
        return False, f"Service restart failed: {name} — {e}"


async def restart_ollama() -> tuple[bool, str]:
    """Restart Ollama by killing and letting launchd respawn."""
    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            ["pkill", "-f", "ollama"],
            capture_output=True, timeout=5,
        )
        await asyncio.sleep(3)

        # Verify it came back
        import urllib.request
        try:
            resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
            if resp.status == 200:
                return True, "Ollama restarted and responding"
        except Exception:
            pass

        # If it didn't respawn, try starting manually
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


async def check_and_heal(check_name: str) -> tuple[bool, str] | None:
    """Attempt to heal a specific failing check. Returns (healed, detail) or None if not healable."""
    if check_name == "ollama":
        return await restart_ollama()
    elif check_name == "livesync":
        ok1, d1 = await restart_service("livesync-bridge")
        ok2, d2 = await restart_service("livesync-tunnel")
        return (ok1 and ok2, f"{d1}; {d2}")
    elif check_name == "loops":
        # Background loops can only be restarted by restarting the bot
        return None  # Not self-healable without full restart
    elif check_name == "discord":
        return None  # Discord requires full bot restart
    elif check_name == "file_io":
        return None  # Filesystem issues need manual intervention
    return None


async def full_diagnostic() -> list[dict]:
    """Run diagnostic on all services. Returns list of {name, status, pid, detail}."""
    results = []

    for name, service_id in SERVICES.items():
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                ["launchctl", "list"],
                capture_output=True, text=True, timeout=5,
            )
            found = False
            for line in proc.stdout.split("\n"):
                if service_id in line:
                    parts = line.split()
                    pid = parts[0] if parts[0] != "-" else None
                    exit_code = parts[1] if len(parts) > 1 else None
                    status = "running" if pid and pid.isdigit() else "stopped"
                    results.append({
                        "name": name, "status": status,
                        "pid": pid, "detail": f"exit: {exit_code}"
                    })
                    found = True
                    break
            if not found:
                results.append({"name": name, "status": "not registered", "pid": None, "detail": ""})
        except Exception as e:
            results.append({"name": name, "status": "error", "pid": None, "detail": str(e)})

    # Check Ollama
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
