"""turtleOS practice file I/O — read, write, search, list practice files.

Pure file operations with no dependencies on other bot modules
(except mage.get_pd() for directory resolution).
"""

import os
import re
from urllib.parse import quote

from mage import get_pd, get_mage_key, get_runtime_dir
from state import (
    ARTIFACT_READ_TOKEN,
    OBSIDIAN_VAULT,
    PRACTICE_WEB_BASE,
    MAX_BRIGHT_CHARS,
    MAX_INTENTION_LINES,
)


# ─── Core File Operations ────────────────────────────────────────

def read_safe(path):
    try:
        with open(path) as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return ""


def read_header(path, max_lines=20):
    try:
        with open(path) as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line)
            return "".join(lines)
    except (FileNotFoundError, PermissionError):
        return ""


# ─── Text Utilities ──────────────────────────────────────────────

def count_items(text):
    if not text.strip():
        return 0
    bullets = sum(1 for line in text.strip().split("\n")
                  if line.strip().startswith("- "))
    if bullets > 0:
        return bullets
    blocks = [b.strip() for b in text.strip().split("---") if b.strip() and not b.strip().startswith("*")]
    return len(blocks) if blocks else 0


def truncate(text, limit=2000):
    if len(text) <= limit:
        return text
    return text[:limit - 20] + "\n\n*...truncated*"


def artifact_read_url(rel_path: str) -> str | None:
    """HTTPS browser URL for an allowlisted artifact when ``PRACTICE_WEB_BASE`` is set."""
    rel = rel_path.strip()
    if not rel.endswith(".md"):
        rel += ".md"
    if not PRACTICE_WEB_BASE:
        return None
    mage_key = get_mage_key()
    url = f"{PRACTICE_WEB_BASE.rstrip('/')}/{mage_key}/{quote(rel)}"
    if ARTIFACT_READ_TOKEN:
        url = f"{url}?t={quote(ARTIFACT_READ_TOKEN, safe='')}"
    return url


def obsidian_link(filename):
    """Generate a tappable link for a practice file.
    Prefers web link (works in Discord's in-app browser) with obsidian:// fallback."""
    name = filename.replace(".md", "")
    web_url = artifact_read_url(filename)
    if web_url:
        return web_url
    return f"[{filename}](obsidian://open?vault={quote(OBSIDIAN_VAULT)}&file={quote(name)})"


def artifact_display_name(filename: str) -> str:
    base = filename.replace("\\", "/").rstrip("/").split("/")[-1]
    return base.replace(".md", "").replace("-", " ").replace("_", " ")


def summarize_bright(text, limit=1500):
    if not text or not text.strip():
        return "(bright empty)"
    lines = text.strip().split("\n")
    summary_lines = []
    items_in_section = 0
    max_items = 5
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("# "):
            summary_lines.append(stripped)
            items_in_section = 0
        elif stripped.startswith("### "):
            summary_lines.append(stripped)
            items_in_section = 0
        elif (stripped.startswith("- ") or (stripped.startswith("**") and not stripped.startswith("***"))) and items_in_section < max_items:
            summary_lines.append(stripped[:140])
            items_in_section += 1
        elif items_in_section == max_items:
            summary_lines.append("  *(more items...)*")
            items_in_section += 1
    result = "\n".join(summary_lines)
    return result[:limit] if len(result) > limit else result


def extract_section(content, section_name):
    """Extract a markdown section by heading name (case-insensitive)."""
    lines = content.split("\n")
    target = section_name.lower().strip()
    start = None
    start_level = 0
    for i, line in enumerate(lines):
        heading_match = re.match(r'^(#{1,6})\s+(.+)', line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip().lower()
            if start is None and target in title:
                start = i
                start_level = level
            elif start is not None and level <= start_level:
                return "\n".join(lines[start:i]).strip()
    if start is not None:
        return "\n".join(lines[start:]).strip()
    return None


def list_headings(content):
    """List all markdown headings in a file."""
    headings = []
    for line in content.split("\n"):
        m = re.match(r'^(#{1,6})\s+(.+)', line)
        if m:
            headings.append(m.group(2).strip())
    return ", ".join(headings[:15]) if headings else "(no headings)"


def load_intentions_list():
    idir = os.path.join(get_pd(), "intentions")
    if not os.path.isdir(idir):
        return []
    return [f.replace(".md", "").replace("-", " ").replace("_", " ")
            for f in sorted(os.listdir(idir)) if f.endswith(".md")]


# ─── File Access Checks ─────────────────────────────────────────

def is_readable(filename):
    """True if filename is an allowlisted practice artifact (TURTLE_SPEC §11.5.1)."""
    from artifact_viewer import is_artifact_readable

    return is_artifact_readable(filename)


def is_writable(filename):
    """Any .md file within the practice directory is writable."""
    if ".." in filename or filename.startswith("/"):
        return False
    return filename.endswith(".md")


# ─── Age Utilities ───────────────────────────────────────────────

def file_age_hours(path):
    """Return file age in hours, or float('inf') if missing."""
    from datetime import datetime
    try:
        return (datetime.now().timestamp() - os.path.getmtime(path)) / 3600
    except (FileNotFoundError, OSError):
        return float("inf")


def format_age(hours):
    """Human-readable age from hours."""
    if hours == float("inf"):
        return "∞"
    if hours < 1:
        return f"{int(hours * 60)}m"
    if hours < 24:
        return f"{int(hours)}h"
    return f"{int(hours / 24)}d"


# ─── Thread State I/O ────────────────────────────────────────────

def get_thread_state_dir():
    return os.path.join(get_runtime_dir(), "thread-state")


def read_thread_state(thread_name: str) -> str:
    """Read a thread card if it exists. Returns empty string if not found."""
    safe_name = re.sub(r'[^\w\-]', '_', thread_name.lower())
    path = os.path.join(get_thread_state_dir(), f"{safe_name}.md")
    content = read_safe(path)
    return content.strip()[:1400] if content.strip() else ""
