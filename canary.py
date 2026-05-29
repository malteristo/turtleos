#!/usr/bin/env python3
"""
canary.py — mechanical health check for the Turtle substrate.
Exits 0 if green, 1 otherwise. Alerts to river on non-green.
"""
import importlib.util
import os
import json
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ALERT_CHANNEL = os.environ.get("CANARY_ALERT_CHANNEL") or os.environ.get("DISCORD_CHANNEL_DIALOGUE", "")
SPIRIT_OPS = str(Path.home() / "turtleos" / "spirit_ops.py")
VENV_PY = str(Path.home() / "turtleos" / "venv" / "bin" / "python3")

if Path(VENV_PY).exists() and Path(sys.executable).resolve() != Path(VENV_PY).resolve():
    os.execv(VENV_PY, [VENV_PY, *sys.argv])
DISCORD_LOG = Path.home() / "turtleos" / "logs" / "discord.log"
STATE_PATH = Path.home() / "turtleos" / "canary_state.json"
TRIAGE_FALLBACK_STATE_PATH = Path.home() / "turtleos" / "canary_triage_fallback_state.json"
LIVESYNC_LABELS = [label.strip() for label in os.environ.get("CANARY_LIVESYNC_LABELS", "").split(",") if label.strip()]
LIVESYNC_ERR_PATHS = [Path(path.strip()) for path in os.environ.get("CANARY_LIVESYNC_ERR_PATHS", "").split(",") if path.strip()]
LIVESYNC_ERR_RECENT_SECONDS = 10 * 60
SOURCE_MODULES = [
    "discord_bot.py",
    "commands.py",
    "pulse.py",
    "canary.py",
    "sessions.py",
    "eddy_spawn.py",
    "intake_server.py",
    "capabilities.py",
    "shell_harness.py",
    "tos_tools.py",
    "tool_result.py",
    "runtime/update.py",
]



def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 255, "", str(e)


def format_age(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h"
    return f"{hours // 24}d"


def check_couchdb():
    rc, out, _ = run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:5984/"])
    if rc == 0 and out.strip() == "401":
        return "green", "HTTP 401 (auth required = responding)"
    return "red", f"unexpected response: rc={rc} body={out!r}"


def check_tailscale_serve():
    """Functional check: does the Tailscale-proxied URL respond like local CouchDB?
    More robust than `tailscale serve status` which requires GUI in some contexts."""
    rc, out, _ = run([
        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
        "--max-time", "5",
        "https://turtles-mac-mini.tail433a7d.ts.net/",
    ])
    if rc == 0 and out.strip() == "401":
        return "green", "proxied URL returns HTTP 401 (serve configured correctly)"
    return "red", f"proxied URL unexpected: rc={rc} code={out!r}"


def check_launchd_label(label):
    rc, out, _ = run(["launchctl", "list", label])
    if rc == 0:
        for line in out.splitlines():
            if line.strip().startswith('"PID"'):
                pid_val = line.split("=")[1].strip().rstrip(";").strip()
                if pid_val.isdigit() and int(pid_val) > 0:
                    return "green", f"PID {pid_val}"
        return "red", "no live PID in plist state"
    return "red", f"label not loaded (rc={rc})"


def check_bridge_err_clean(path):
    if not path.exists():
        return "green", "no errors (file absent)"
    try:
        lines = path.read_text(errors="replace").splitlines()
        tail = "\n".join(lines[-200:])
    except Exception as e:
        return "yellow", f"read failed: {e}"
    bad_patterns = ["Method not implemented", "Uncaught (in promise)"]
    hits = [p for p in bad_patterns if p in tail]
    if hits:
        age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
        if age > LIVESYNC_ERR_RECENT_SECONDS:
            return "green", f"stale error ignored (mtime {format_age(age)} ago)"
        return "red", f"found: {', '.join(hits)}"
    return "green", "clean"


def check_ollama():
    rc, out, _ = run(["curl", "-s", "http://localhost:11434/api/tags"])
    if rc == 0 and out.startswith("{"):
        return "green", "models available"
    return "red", f"not reachable (rc={rc})"


def check_source_deployable():
    failures = []
    for rel in SOURCE_MODULES:
        path = Path(__file__).parent / rel
        if not path.exists():
            failures.append(f"{rel}: missing")
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as e:
            detail = str(e).splitlines()[-1]
            failures.append(f"{rel}: {detail[:120]}")
        except Exception as e:
            failures.append(f"{rel}: {type(e).__name__}: {e}")
    if failures:
        return "red", "; ".join(failures[:3])
    return "green", f"{len(SOURCE_MODULES)} modules compile"


def _load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_behavior_smoke():
    try:
        base = Path(__file__).parent
        pulse = _load_module_from_path("canary_pulse_smoke", base / "pulse.py")
        pulse_data = pulse.scan_pulse()
        title, body = pulse.compose_river_entry(pulse_data)
        if not title or not body.strip():
            return "red", "river entry composer returned empty output"
        signals = pulse.compose_interoception(pulse_data, prev_pulse=None)
        if not isinstance(signals, list):
            return "red", "interoception composer did not return a list"
    except Exception as e:
        return "red", f"pulse smoke failed: {type(e).__name__}: {e}"

    try:
        bot = _load_module_from_path("canary_discord_bot_smoke", base / "discord_bot.py")
        actions = bot._extract_contextual_actions('Try `!thread "canary smoke" --model local --attunement semi`.')
        if not actions or actions[0][1] != '!thread "canary smoke" --model local --attunement semi':
            return "red", "contextual action extraction failed"

        class Snapshot:
            created_at = None
            type = "default"
            content = "forwarded smoke"
            embeds = []
            attachments = []

        class Message:
            content = ""
            message_snapshots = [Snapshot()]

        visible, forwarded = bot._visible_message_content(Message())
        if "forwarded smoke" not in visible or "forwarded smoke" not in forwarded:
            return "red", "forwarded snapshot extraction failed"
    except SystemExit as e:
        return "red", f"discord_bot smoke exited: {e}"
    except Exception as e:
        return "red", f"discord_bot smoke failed: {type(e).__name__}: {e}"

    return "green", "pulse + contextual action + forwarded snapshot smoke passed"


def check_tool_smoke():
    try:
        base = Path(__file__).parent
        tools = _load_module_from_path("canary_tos_tools_smoke", base / "tos_tools.py")

        checks = [
            ("list", tools.execute_tos_tool("list_practice_files", {"directory": ""})),
            ("shell_pwd", tools.execute_tos_tool("run_turtleos_shell", {
                "command": "pwd",
                "reason": "canary tool smoke",
            })),
            ("shell_search", tools.execute_tos_tool("run_turtleos_shell", {
                "command": "rg -n execute_tos_tool tos_tools.py",
                "reason": "canary safe search smoke",
            })),
            ("capability_index", tools.execute_tos_tool("list_turtle_capabilities", {})),
        ]
    except Exception as e:
        return "red", f"tool smoke raised: {type(e).__name__}: {e}"

    failures = []
    for name, result in checks:
        lower = (result or "").lower()
        if "toolresult[" in lower or "shell command failed" in lower or "shell command blocked" in lower:
            failures.append(f"{name}: {result[:160]}")
    if failures:
        return "yellow", "; ".join(failures[:2])
    return "green", "list + shell pwd + safe search tools passed"



def check_topology_drift():
    try:
        mage = _load_module_from_path("canary_mage_topology", Path(__file__).with_name("mage.py"))
        topology = mage.get_topology()
        practice = Path(topology["practice_dir"]).expanduser()
        runtime = Path(topology["runtime_dir"]).expanduser()
    except Exception as e:
        return "red", f"topology resolution failed: {type(e).__name__}: {e}"

    if not practice.exists():
        return "red", f"practice_dir missing: {practice}"
    if not runtime.exists():
        return "yellow", f"runtime_dir missing: {runtime}"

    if practice.resolve() == runtime.resolve():
        return "green", f"tOS-only topology: practice/runtime share {practice}"

    duplicate_dirs = []
    for rel in ("proposals", "sessions", "boom.md", "boom/bright.md", "intentions"):
        if (practice / rel).exists() and (runtime / rel).exists():
            duplicate_dirs.append(rel)
    if duplicate_dirs:
        return "yellow", f"duplicate practice artifacts in runtime_dir: {', '.join(duplicate_dirs[:5])}"
    return "green", f"practice={practice}; runtime={runtime}"

def check_triage_fallback_count():
    """Detect new triage fallbacks since the previous canary run."""
    if not DISCORD_LOG.exists():
        return "yellow", "discord.log missing"
    try:
        stat = DISCORD_LOG.stat()
        state = json.loads(TRIAGE_FALLBACK_STATE_PATH.read_text()) if TRIAGE_FALLBACK_STATE_PATH.exists() else {}
    except Exception as e:
        return "yellow", f"state read failed: {e}"

    previous_size = int(state.get("size", 0))
    if previous_size <= 0 or previous_size > stat.st_size:
        TRIAGE_FALLBACK_STATE_PATH.write_text(json.dumps({"size": stat.st_size}) + "\n")
        return "green", "baseline recorded for triage fallback monitoring"

    try:
        with DISCORD_LOG.open("rb") as f:
            f.seek(previous_size)
            chunk = f.read().decode(errors="replace")
    except Exception as e:
        return "yellow", f"log read failed: {e}"

    fallbacks = chunk.count("Triage failed (ReadTimeout), using heuristic fallback")
    TRIAGE_FALLBACK_STATE_PATH.write_text(json.dumps({"size": stat.st_size}) + "\n")
    if fallbacks == 0:
        return "green", "0 new fallbacks since last canary"
    if fallbacks <= 3:
        return "yellow", f"{fallbacks} new fallbacks since last canary (intermittent)"
    return "red", f"{fallbacks} new fallbacks since last canary (recurring — INT-024 regression?)"


CHECKS = [
    ("infra", "couchdb_reachable", check_couchdb, "high"),
    ("infra", "tailscale_serve", check_tailscale_serve, "high"),
    ("infra", "discord_bot_alive", lambda: check_launchd_label("com.turtle.discord"), "high"),
    ("models", "ollama_reachable", check_ollama, "high"),
    ("models", "triage_fallback_count", check_triage_fallback_count, "medium"),
    ("source", "source_deployable", check_source_deployable, "high"),
    ("behavior", "behavior_smoke", check_behavior_smoke, "high"),
    ("tools", "tool_smoke", check_tool_smoke, "medium"),
    ("topology", "topology_drift", check_topology_drift, "medium"),
]

for idx, label in enumerate(LIVESYNC_LABELS, start=1):
    CHECKS.insert(2, ("infra", f"livesync_label_{idx}", lambda label=label: check_launchd_label(label), "high"))

for idx, path in enumerate(LIVESYNC_ERR_PATHS, start=1):
    CHECKS.insert(3, ("infra", f"livesync_err_clean_{idx}", lambda path=path: check_bridge_err_clean(path), "medium"))


def active_signature(results):
    return [
        {"layer": r["layer"], "name": r["name"], "status": r["status"]}
        for r in results
        if r["status"] != "green"
    ]


def layer_summary(results):
    layers = []
    for layer in dict.fromkeys(r["layer"] for r in results):
        statuses = [r["status"] for r in results if r["layer"] == layer]
        if "red" in statuses:
            status = "red"
        elif "yellow" in statuses:
            status = "yellow"
        else:
            status = "green"
        layers.append(f"{layer}:{status}")
    return " · ".join(layers)


def load_state():
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def main():
    results = []
    has_red = False
    has_yellow = False
    for layer, name, fn, weight in CHECKS:
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = "red", f"check raised: {e}"
        results.append({"layer": layer, "name": name, "status": status, "detail": detail, "weight": weight})
        if status == "red" and weight == "high":
            has_red = True
        elif status == "red":
            has_yellow = True
        elif status == "yellow":
            has_yellow = True

    overall = "red" if has_red else ("yellow" if has_yellow else "green")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    emoji = {"green": "\U0001F7E2", "yellow": "\U0001F7E1", "red": "\U0001F534"}[overall]
    green_count = sum(1 for r in results if r["status"] == "green")
    summary = layer_summary(results)
    print(f"{emoji} canary {timestamp} — overall {overall} ({green_count}/{len(results)} green) — {summary}")
    for r in results:
        if r["status"] != "green":
            print(f"  {r['status']}: {r['layer']}/{r['name']} — {r['detail']}")

    report = {"timestamp": timestamp, "overall": overall, "checks": results}
    history_path = Path("/tmp/canary-history.jsonl")
    with history_path.open("a") as f:
        f.write(json.dumps(report) + "\n")

    previous_state = load_state()
    signature = active_signature(results)
    previous_signature = previous_state.get("signature")

    should_alert = False
    alert_msg = None

    if overall == "green":
        if previous_signature:
            should_alert = True
            alert_msg = f"\u2705 canary {timestamp} — green; cleared previous degraded state"
            try:
                STATE_PATH.unlink()
            except FileNotFoundError:
                pass
    elif signature != previous_signature:
        should_alert = True
        alert_lines = [f"{emoji} canary {timestamp} — {overall} — {summary}"]
        for r in results:
            if r["status"] != "green":
                alert_lines.append(f"  {r['status']}: {r['layer']}/{r['name']} — {r['detail']}")
        alert_msg = "\n".join(alert_lines)
        save_state({"first_seen": previous_state.get("first_seen", timestamp), "last_seen": timestamp, "signature": signature})
    else:
        save_state({**previous_state, "last_seen": timestamp, "signature": signature})
        print("Discord alert suppressed: degraded signature unchanged")

    if should_alert and alert_msg and ALERT_CHANNEL:
        run([VENV_PY, SPIRIT_OPS, "send", ALERT_CHANNEL, alert_msg], timeout=30)
    elif should_alert and alert_msg:
        print("Discord alert skipped: CANARY_ALERT_CHANNEL/DISCORD_CHANNEL_DIALOGUE not configured")

    sys.exit(0 if overall == "green" else 1)


if __name__ == "__main__":
    main()
