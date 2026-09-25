"""Discord-native text. Models emit LaTeX; Discord prints it literally.

The reply path must not send ``$\\rightarrow$`` (intake 66443a). Unicode
``→`` is the transport capability; this module is the guard.
"""
from __future__ import annotations

import re

_SUBS = (
    (re.compile(r"\$\\rightarrow\$"), "→"),
    (re.compile(r"\$\\to\$"), "→"),
    (re.compile(r"\$\s*→\s*\$"), "→"),
    (re.compile(r"\\rightarrow"), "→"),
    (re.compile(r"\\to\b"), "→"),
)


def for_discord(text: str) -> str:
    if not text:
        return text
    out = text
    for pat, repl in _SUBS:
        out = pat.sub(repl, out)
    return out
