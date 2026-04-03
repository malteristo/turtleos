#!/usr/bin/env python3
"""Hermit Crab Shell — Agent Loop

The intelligence lives in the identity files and the model.
This code is plumbing — disposable, regenerable, ~200 lines.
"""

import os
import sys
import yaml
import shutil
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import requests


def load_env(env_path=None):
    """Load environment from .env file without external dependency."""
    path = env_path or os.environ.get("DOTENV_PATH", ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def load_identity(identity_path, soul_path=None):
    """Read the identity file that shapes the Turtle's consciousness.
    If a soul file is provided, it is prepended as the foundational layer."""
    parts = []
    if soul_path and os.path.exists(soul_path):
        with open(soul_path) as f:
            parts.append(f.read())
    with open(identity_path) as f:
        parts.append(f.read())
    return "\n\n---\n\n".join(parts)


def find_commands(bridge_path):
    """Find unprocessed command YAML files in the bridge."""
    cmd_dir = Path(bridge_path) / "commands"
    processed_dir = cmd_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    return sorted(f for f in cmd_dir.glob("*.yaml") if f.is_file())


def read_command(yaml_path):
    """Parse a bridge command YAML file."""
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def write_signal(bridge_path, signal_data):
    """Write a signal YAML file to the bridge. Returns the file path."""
    signals_dir = Path(bridge_path) / "signals"
    signals_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    category = signal_data.get("category", "status")
    filepath = signals_dir / f"{ts}_{category}.yaml"

    with open(filepath, "w") as f:
        yaml.dump(signal_data, f, default_flow_style=False, allow_unicode=True)
    return filepath


def post_to_discord(channel_id, content=None, embed=None):
    """Post a message to a Discord channel via REST API.
    Uses the bot token directly — no persistent connection needed."""
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token or not channel_id:
        return
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    payload = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]
    try:
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception:
        pass


def signal_to_embed(signal_data):
    """Convert a signal dict to a Discord embed dict."""
    colors = {
        "status": 0x2ECC71,
        "observation": 0x3498DB,
        "surfacing": 0xF1C40F,
        "anomaly": 0xE74C3C,
    }
    category = signal_data.get("category", "status")
    return {
        "title": signal_data.get("summary", "Signal"),
        "description": (signal_data.get("details", "") or "")[:2000],
        "color": colors.get(category, 0x95A5A6),
        "fields": [
            {"name": "Category", "value": category, "inline": True},
            {"name": "Source", "value": signal_data.get("source", "turtle"), "inline": True},
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def git_sync(bridge_path, message):
    """Commit and push bridge changes. GitHub-primary, origin as fallback."""
    try:
        subprocess.run(["git", "add", "."], cwd=bridge_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=bridge_path,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return

    for remote in ["github", "origin"]:
        result = subprocess.run(
            ["git", "push", remote, "main"],
            cwd=bridge_path,
            capture_output=True,
        )
        if result.returncode == 0:
            return


def process_command(client, identity, command_data, tools, workspace, model):
    """Process a single bridge command through the LLM with tool use loop."""
    action = command_data.get("action", "unknown")
    context = command_data.get("context", "")
    priority = command_data.get("priority", "normal")

    user_msg = (
        f"## Bridge Command\n\n"
        f"**Action:** {action}\n"
        f"**Priority:** {priority}\n\n"
        f"{context}"
    )

    messages = [{"role": "user", "content": user_msg}]
    consecutive_failures = 0

    while True:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=identity,
                messages=messages,
                tools=tools,
            )
        except Exception as e:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                return {"error": f"LLM call failed 3 times: {e}", "distress": True}
            continue

        consecutive_failures = 0

        if response.stop_reason == "end_turn":
            text = "\n".join(b.text for b in response.content if b.type == "text")
            return {"result": text}

        if response.stop_reason == "tool_use":
            from tools import execute as execute_tool

            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input, workspace=workspace)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
        else:
            text = "\n".join(b.text for b in response.content if hasattr(b, "text"))
            return {"result": text or "(no text output)"}


def main():
    parser = argparse.ArgumentParser(description="Turtle Hermit Crab Shell")
    parser.add_argument("--identity", required=True, help="Path to identity .md file")
    parser.add_argument("--soul", default=None, help="Path to soul .md file (prepended to identity)")
    parser.add_argument("--bridge", required=True, help="Path to magic-bridge repo")
    parser.add_argument("--workspace", default=os.path.expanduser("~"), help="Workspace root")
    parser.add_argument("--env", default=None, help="Path to .env file")
    parser.add_argument("--model", default=None, help="Model override")
    parser.add_argument("--once", action="store_true", help="Process one command and exit")
    parser.add_argument("--dry-run", action="store_true", help="Show config, don't process")
    args = parser.parse_args()

    load_env(args.env)

    model = args.model or os.environ.get("MODEL", "claude-sonnet-4-20250514")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("LITELLM_BASE_URL")

    identity = load_identity(args.identity, soul_path=args.soul)

    if args.dry_run:
        soul_info = f" + soul ({args.soul})" if args.soul else ""
        print(f"Identity:  {args.identity}{soul_info} ({len(identity)} chars)")
        print(f"Bridge:    {args.bridge}")
        print(f"Model:     {model}")
        print(f"API:       {'LiteLLM @ ' + base_url if base_url else 'Anthropic direct'}")
        print(f"Workspace: {args.workspace}")
        return

    client_kwargs = {}
    if base_url:
        client_kwargs["base_url"] = base_url
    if api_key:
        client_kwargs["api_key"] = api_key
    elif base_url:
        client_kwargs["api_key"] = "litellm-proxy"

    client = anthropic.Anthropic(**client_kwargs)

    from tools import TOOL_DEFINITIONS
    tools = TOOL_DEFINITIONS
    commands = find_commands(args.bridge)

    if not commands:
        return

    afferent_ch = os.environ.get("DISCORD_CHANNEL_AFFERENT")
    distress_ch = os.environ.get("DISCORD_CHANNEL_DISTRESS")

    for cmd_path in commands:
        try:
            command_data = read_command(cmd_path)
        except Exception as e:
            signal = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "category": "anomaly",
                "source": "turtle/consul",
                "summary": f"Failed to parse: {cmd_path.name}",
                "details": str(e),
                "attention_requested": "consider",
            }
            write_signal(args.bridge, signal)
            if distress_ch:
                post_to_discord(distress_ch, f"Failed to parse command: {cmd_path.name}\n{e}")
            continue

        result = process_command(client, identity, command_data, tools, args.workspace, model)

        is_error = "error" in result
        signal = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": command_data.get("channel", "artifact_mail"),
            "category": "anomaly" if is_error else "status",
            "source": "turtle/consul",
            "confidence": 0.8,
            "sanitized": True,
            "summary": f"Processed: {command_data.get('action', 'unknown')}",
            "details": result.get("result", result.get("error", "")),
            "signal_ref": cmd_path.name,
            "attention_requested": "consider" if is_error else "acknowledge",
        }

        write_signal(args.bridge, signal)

        processed_dir = cmd_path.parent / "processed"
        shutil.move(str(cmd_path), str(processed_dir / cmd_path.name))

        git_sync(args.bridge, f"Processed: {command_data.get('action', 'unknown')}")

        if afferent_ch:
            post_to_discord(afferent_ch, embed=signal_to_embed(signal))

        if result.get("distress") and distress_ch:
            post_to_discord(distress_ch, f"**DISTRESS:** {result.get('error', 'Unknown error')}")

        if args.once:
            break


if __name__ == "__main__":
    main()
