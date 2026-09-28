"""Three-way merge for a registry both bots write (issues/048).

Each process loads ``mage_registry.yaml``, changes its copy, and saves the whole
copy. When the other process wrote in between, saving the copy writes its change
away. ``merge(base, ours, theirs)`` keeps both: ``base`` is what this process
loaded, ``ours`` is its copy now, ``theirs`` is the file on disk.

Where both sides changed the same scalar, ours wins — the caller is acting now.
Where one side removed an entry and the other only edited it, the removal wins: a
stale copy's edit brought back a member's channel row that offboarding had just
removed (2026-09-28).
Lists of plain values (member lists) merge as sets of additions and removals;
other lists are values.
"""

from __future__ import annotations

_MISSING = object()


def _plain_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(v, (str, int, float, bool)) for v in value)


def merge(base, ours, theirs):
    if ours == base:
        return theirs
    if theirs == base or theirs == ours:
        return ours
    if ours is _MISSING or theirs is _MISSING:
        return _MISSING
    if isinstance(ours, dict) and isinstance(theirs, dict):
        b = base if isinstance(base, dict) else {}
        out = {}
        for key in list(theirs) + [k for k in ours if k not in theirs]:
            value = merge(b.get(key, _MISSING), ours.get(key, _MISSING), theirs.get(key, _MISSING))
            if value is not _MISSING:
                out[key] = value
        return out
    if _plain_list(ours) and _plain_list(theirs) and (base is _MISSING or _plain_list(base)):
        b = base if isinstance(base, list) else []
        removed = {v for v in b if v not in ours}
        out = [v for v in theirs if v not in removed]
        out += [v for v in ours if v not in b and v not in out]
        return out
    return ours
