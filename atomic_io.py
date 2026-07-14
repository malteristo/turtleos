"""Shared atomic-write primitive (TURTLE_SPEC §6.5 / §8.4 write path).

Transaction-safe file writes: mkstemp in the target directory + write +
fsync + os.replace. A crash at any point leaves either the previous file
or the new file — never a partial write.

Stdlib-only by design: this module sits at the bottom of the import
graph so any module (thread_registry, dialogue_store, story surfaces)
can depend on it without cycles.

For multi-writer files (River + Turtle), pass ``lock=True`` or wrap a
read-modify-write sequence in ``file_lock(path)`` — an advisory flock
on a ``<path>.lock`` sidecar (the target itself is swapped out by
os.replace, so it cannot carry the lock).
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def file_lock(path: str | os.PathLike) -> Iterator[None]:
    """Exclusive advisory lock scoped to ``path`` (blocks until acquired).

    Locks a ``<path>.lock`` sidecar file, so it stays valid across the
    os.replace swap and works between processes and threads.
    """
    lock_path = Path(f"{path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def atomic_write_text(
    path: str | os.PathLike,
    content: str,
    *,
    encoding: str = "utf-8",
    lock: bool = False,
) -> None:
    """Atomically replace ``path`` with ``content``.

    Parent directories are created if missing. On failure the previous
    file is left intact and the temp file is removed; the exception
    propagates so callers can decide how to report it.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if lock:
        with file_lock(target):
            _write_and_replace(target, content, encoding)
    else:
        _write_and_replace(target, content, encoding)


def atomic_write_json(
    path: str | os.PathLike,
    data,
    *,
    ensure_ascii: bool = False,
    indent: int | str | None = None,
    lock: bool = False,
) -> None:
    """Atomically replace ``path`` with ``data`` serialized as JSON."""
    payload = json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)
    atomic_write_text(path, payload, lock=lock)


def _write_and_replace(target: Path, content: str, encoding: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
