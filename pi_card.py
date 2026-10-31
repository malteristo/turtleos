"""`!pi` in the magic room: the version, the model, and an update that asks.

Pi does not update itself. The card reads what is installed. A check names a
newer release. The update runs only after a second press, and only when the
tarball matches the release's own checksum. A wrong checksum leaves the
installed Pi where it is.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path

import ui_kit

BINARY_NAME = "pi-darwin-arm64.tar.gz"
RELEASES = "https://github.com/earendil-works/pi/releases/download"

_TEXT = {
    "en": {
        "title": "Pi",
        "quiet": "The coding agent on this machine. It does not update itself.",
        "version": "Version",
        "installed": "installed",
        "missing": "not installed",
        "missing_line": "Nothing is at the Pi path on this machine.",
        "model": "Model",
        "ready": "ready",
        "unnamed": "unnamed",
        "unnamed_line": "No model is named for it.",
        "model_line": "The local coder it will ride.",
        "check": "Check for an update",
        "current": "This is the current release.",
        "newer": "A newer release is out.",
        "ask": "Update to {version}",
        "confirm": "Update Pi",
        "keep": "Keep this version",
        "elsewhere": "Pi is maintained in #magic.",
        "checksum": "The download did not match the release. Pi was left as it is.",
    },
    "de": {
        "title": "Pi",
        "quiet": "Der Coding-Agent auf diesem Rechner. Er aktualisiert sich nicht selbst.",
        "version": "Version",
        "installed": "installiert",
        "missing": "nicht installiert",
        "missing_line": "Am Pi-Pfad auf diesem Rechner liegt nichts.",
        "model": "Modell",
        "ready": "bereit",
        "unnamed": "ohne Namen",
        "unnamed_line": "Für ihn ist kein Modell genannt.",
        "model_line": "Der lokale Coder, den er reiten wird.",
        "check": "Nach einem Update suchen",
        "current": "Das ist die aktuelle Version.",
        "newer": "Eine neuere Version ist da.",
        "ask": "Auf {version} aktualisieren",
        "confirm": "Pi aktualisieren",
        "keep": "Diese Version behalten",
        "elsewhere": "Pi wird in #magic gepflegt.",
        "checksum": "Der Download stimmt nicht mit der Version überein. Pi blieb, wie es war.",
    },
}


class ChecksumError(Exception):
    """The tarball is not the file the release named."""


def _t(locale: str) -> dict:
    return _TEXT.get(locale) or _TEXT["en"]


def parse_version(text: str) -> str | None:
    token = (text or "").strip().split()[-1] if (text or "").strip() else ""
    token = token.lstrip("v")
    parts = token.split(".")
    if len(parts) >= 2 and all(part.isdigit() for part in parts):
        return token
    return None


def parse_model(text: str) -> str | None:
    try:
        data = json.loads(text or "")
    except json.JSONDecodeError:
        return None
    providers = data.get("providers") if isinstance(data, dict) else None
    if not isinstance(providers, dict):
        return None
    ollama = providers.get("ollama")
    if not isinstance(ollama, dict):
        return None
    models = ollama.get("models")
    if not isinstance(models, list) or not models:
        return None
    first = models[0]
    if isinstance(first, dict) and str(first.get("id") or "").strip():
        return str(first["id"]).strip()
    return None


def version_key(text: str) -> tuple[int, ...]:
    found = parse_version(text) or ""
    return tuple(int(part) for part in found.split(".")) if found else ()


def is_newer(local: str | None, remote: str | None) -> bool:
    left, right = version_key(local or ""), version_key(remote or "")
    return bool(right) and right > left


def asset_sha(sums: str, name: str = BINARY_NAME) -> str | None:
    for line in (sums or "").splitlines():
        bits = line.split()
        if len(bits) == 2 and bits[1] == name and len(bits[0]) == 64:
            return bits[0]
    return None


def _safe_members(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    safe = []
    for member in tar.getmembers():
        parts = Path(member.name).parts
        if not parts or member.name.startswith("/") or ".." in parts:
            raise ChecksumError(member.name)
        safe.append(member)
    return safe


def install_verified(blob: bytes, sums: str, share: Path, link: Path) -> None:
    """Put a verified tarball at `share` and point `link` at its `pi` binary.

    A checksum that does not match raises and leaves `share` and `link` untouched.
    """
    expect = asset_sha(sums)
    got = hashlib.sha256(blob).hexdigest()
    if not expect or got != expect:
        raise ChecksumError(got)
    import io
    import tempfile

    import shutil

    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        members = _safe_members(tar)
        staging = Path(tempfile.mkdtemp(prefix="pi-"))
        try:
            tar.extractall(staging, members=members)
            if not (staging / "pi" / "pi").is_file():
                raise ChecksumError("no pi/pi in the archive")
            share.parent.mkdir(parents=True, exist_ok=True)
            backup = share.with_name(share.name + ".previous")
            if backup.exists():
                shutil.rmtree(backup)
            if share.exists():
                share.rename(backup)
            try:
                (staging / "pi").rename(share)
            except Exception:
                if backup.exists() and not share.exists():
                    backup.rename(share)
                raise
            if backup.exists():
                shutil.rmtree(backup)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(share / "pi")


def surface(
    *,
    version: str | None,
    model: str | None,
    latest: str | None = None,
    asking: bool = False,
    locale: str = "en",
    on_check=None,
    on_ask=None,
    on_confirm=None,
    on_keep=None,
):
    """The card. `latest` is set after a check. `asking` is the second step of an update."""
    t = _t(locale)
    rows = []
    if version:
        rows.append(ui_kit.Row("Version", t["installed"], "on", extra=version))
    else:
        rows.append(ui_kit.Row("Version", t["missing"], "broken", line=t["missing_line"]))
    if model:
        rows.append(ui_kit.Row(t["model"], t["ready"], "on", extra=model, line=t["model_line"]))
    else:
        rows.append(ui_kit.Row(t["model"], t["unnamed"], "needs", line=t["unnamed_line"]))
    acts: list[ui_kit.Act] = []
    danger = None
    quiet = t["quiet"]
    if asking and latest and on_confirm and on_keep:
        quiet = t["newer"]
        acts.append(ui_kit.Act(t["keep"], "pi:keep", on_keep))
        danger = ui_kit.Act(t["confirm"], "pi:confirm", on_confirm, style="danger", confirms=True)
    elif latest and is_newer(version, latest) and on_ask:
        quiet = t["newer"]
        label = t["ask"].format(version=parse_version(latest) or latest)
        danger = ui_kit.Act(label, "pi:ask", on_ask, style="danger", asks=True)
    elif latest and version and not is_newer(version, latest):
        quiet = t["current"]
    elif on_check and version:
        acts.append(ui_kit.Act(t["check"], "pi:check", on_check, style="primary"))
    return ui_kit.build(
        [ui_kit.Card(title=t["title"], quiet=quiet, rows=tuple(rows), acts=tuple(acts), danger=danger)]
    )


def maintained_here(name: str | None) -> bool:
    return name == "magic"


def fetch_text(url: str) -> str:
    import urllib.request

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "turtleos-pi", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - the release URL is fixed by the caller
        return response.read().decode()


def read_installed(binary: Path | None = None, models: Path | None = None) -> tuple[str | None, str | None]:
    binary = binary or Path.home() / ".local" / "bin" / "pi"
    models = models or Path.home() / ".pi" / "agent" / "models.json"
    version = None
    if binary.exists():
        import subprocess

        done = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=15)
        version = parse_version((done.stdout or "") + (done.stderr or ""))
    model = parse_model(models.read_text(encoding="utf-8")) if models.is_file() else None
    return version, model


def reply_view(version: str | None, model: str | None, *, locale: str = "en", install=install_verified):
    """The card the channel posts. Check and update edit it in place."""
    home = Path.home()
    link = home / ".local" / "bin" / "pi"
    latest_url = "https://api.github.com/repos/earendil-works/pi/releases/latest"

    def show(latest: str | None = None, asking: bool = False):
        return surface(
            version=version,
            model=model,
            latest=latest,
            asking=asking,
            locale=locale,
            on_check=lambda interaction: on_check(interaction),
            on_ask=lambda interaction, pin=None: on_ask(interaction, pin or latest or ""),
            on_confirm=lambda interaction, pin=None: on_confirm(interaction, pin or ""),
            on_keep=lambda interaction: on_keep(interaction),
        )

    async def on_check(interaction):
        import asyncio

        body = await asyncio.to_thread(fetch_text, latest_url)
        latest = parse_version(json.loads(body).get("tag_name") or "")
        await interaction.response.edit_message(
            view=surface(
                version=version,
                model=model,
                latest=latest,
                locale=locale,
                on_ask=lambda press, pin=latest: on_ask(press, pin),
                on_keep=on_keep,
                on_confirm=lambda press, pin=latest: on_confirm(press, pin),
            )
        )

    async def on_ask(interaction, pin: str):
        await interaction.response.edit_message(
            view=surface(
                version=version,
                model=model,
                latest=pin,
                asking=True,
                locale=locale,
                on_keep=on_keep,
                on_confirm=lambda press, found=pin: on_confirm(press, found),
            )
        )

    async def on_keep(interaction):
        await interaction.response.edit_message(view=show())

    async def on_confirm(interaction, pin: str):
        import asyncio

        tag = parse_version(pin) or ""
        base = f"{RELEASES}/v{tag}"
        try:
            sums, blob = await asyncio.gather(
                asyncio.to_thread(fetch_text, f"{base}/SHA256SUMS"),
                asyncio.to_thread(_fetch_bytes, f"{base}/{BINARY_NAME}"),
            )
            await asyncio.to_thread(install, blob, sums, home / ".local" / "share" / f"pi-{tag}", link)
        except ChecksumError:
            await interaction.response.send_message(_t(locale)["checksum"], ephemeral=True)
            return
        fresh, still = read_installed(link, home / ".pi" / "agent" / "models.json")
        await interaction.response.edit_message(view=show_fresh(fresh or tag, still))

    def show_fresh(fresh: str, still: str | None):
        return surface(version=fresh, model=still or model, latest=fresh, locale=locale, on_check=on_check)

    return show()


def _fetch_bytes(url: str) -> bytes:
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "turtleos-pi"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - release asset URL
        return response.read()
