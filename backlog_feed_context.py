"""What a backlog pitch brings with it — the material he can work with.

A pitch that is only a row of the backlog is a title and a paragraph written weeks
ago, and he cannot judge it from that. He asked for each pitch to carry what
turtleOS already knows about it, and **only that**: the eddy it came from, the
sparks that touch it, the lines in his boom and his own list that touch it. Every
quotation here is a substring of a file, and every link points at an eddy that
exists. Nothing is written by a model, because a summary he cannot check against a
source is the thing he would have to distrust.

**The craft lane.** Only eddies of the craft channel are read, shown or linked.
His practice root holds eddy notes from rooms that are not craft's (a private
channel is in there, and the origin of one backlog row is a health thread). A
backlog pitch is not a reason for those to surface in craft. The check is the
thread registry's parent channel; a note whose thread the registry does not place
under craft is absent, not guessed at. ``tests/test_backlog_feed_context.py`` plants
a note in another channel that matches the row word for word, and asserts it never
appears.

**How "touches" is decided — two steps, and the first is not enough.** Words
the row shares with a candidate, weighted by rarity, produce a *shortlist*. That
alone was tried against the live backlog on 2026-10-10 and shows him noise: rows
matched eddies on "chapter", "produced" and "named". Shared vocabulary is not
shared subject. So a judge (a small model call, `backlog_feed_judge.py`) reads the
row and the shortlist and keeps only what is about the same subject, and it
leaves out when in doubt. The judge picks; it writes nothing. What he reads is
still the source's own words, and when the judge is unavailable the pitch shows
the origin eddy (which is not a guess) and no related material, never the raw
shortlist.

No Discord import, by design: a pitch is composed in a process that has none to
spare, and the tests read real files.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from story_entries import EDDIES_SUBDIR, parse_eddy_file_entries

REGISTRY_REL = Path("thread-state") / "registry.yaml"
INTAKE_REL = Path("craft") / "intake"

BOOM_PATH = "desk/boom.md"
ALTBACKLOG_PATH = "box/altbacklog.md"

# The shortlist is deliberately loose: shared rare words only decide what a judge
# gets to read, never what he is shown (see `shortlist`).
MIN_SHARED = 2
RARE_FRACTION = 0.08  # a word in more than this share of the documents is not distinctive...
RARE_FLOOR = 6  # ...unless the whole corpus is small: up to this many documents is always rare
SHORTLIST = {"eddy": 6, "spark": 4, "boom": 4, "alt": 3, "doc": 4}
DOC_MIN_SHARED = 3  # a design note is long and shares words by accident; ask for more
DOC_SECTION_MIN = 120  # a heading with a line under it is not a passage worth quoting
MAX_KEPT = 4
QUOTE_CHARS = 260

_STOP = frozenset(
    """
    about above after again against also although always another because been before being
    between both cannot could does doing done down during each either else even ever every
    from further have having here into itself just like made make many more most much must
    need needs never only other over same should since some such than that their them then
    there these they this those through under until upon very want wants well were what when
    where whether which while will with within without would your yours
    aber auch dass dies diese dieser dieses doch eine einem einen einer eines euch haben hier
    ihre kann mehr noch nicht oder sein sind über und viel wenn werden wird wir wollen
    harvested pickup shipped target dest original filed registered backlog row item
    """.split()
)

_ID_TOKEN = re.compile(r"\b[0-9a-f]{6,}\b|\b\d{4}-\d{2}-\d{2}\b")
_WORD = re.compile(r"[a-zäöüß][a-zäöüß0-9\-]{3,}")
_THREAD_ID = re.compile(r"\b(\d{17,20})\b")
_INTAKE_ORIGIN = (
    re.compile(r"channel_id=(\d{15,20})"),
    re.compile(r"channel=(\d{15,20})"),
    re.compile(r"Channel ID:\*\*\s*`(\d{15,20})`"),
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


# ── words ───────────────────────────────────────────────────────


def _stem(word: str) -> str:
    for suffix, repl, keep in (("ies", "y", 3), ("ing", "", 4), ("es", "", 4), ("s", "", 4)):
        if word.endswith(suffix) and len(word) - len(suffix) >= keep:
            return word[: -len(suffix)] + repl
    return word


def words(text: str) -> set[str]:
    """The distinctive words of a text: lower-cased, stemmed, stop words and ids dropped."""
    clean = _ID_TOKEN.sub(" ", (text or "").lower())
    return {_stem(w) for w in _WORD.findall(clean) if w not in _STOP}


def quote_of(text: str, limit: int = QUOTE_CHARS) -> str:
    """The first sentences of ``text``, verbatim apart from whitespace, within ``limit``."""
    flat = " ".join((text or "").split())
    if len(flat) <= limit:
        return flat
    out = ""
    for sentence in _SENTENCE.split(flat):
        if out and len(out) + 1 + len(sentence) > limit:
            break
        out = f"{out} {sentence}".strip()
        if len(out) >= limit:
            break
    if len(out) > limit:
        out = out[: limit - 1].rstrip() + "…"
    return out


# ── what it returns ─────────────────────────────────────────────


@dataclass(frozen=True)
class Source:
    """One thing turtleOS already holds that touches the row."""

    kind: str  # "origin" | "said" | "eddy" | "spark" | "boom" | "alt" | "doc"
    label: str
    quote: str
    thread: str | None = None  # a craft eddy this came from, when there is one
    shared: tuple[str, ...] = ()


@dataclass(frozen=True)
class Context:
    origin_candidates: tuple[str, ...] = ()
    origin: Source | None = None
    related: tuple[Source, ...] = ()
    said: Source | None = None  # his own words, from the intake the row was harvested from

    @property
    def empty(self) -> bool:
        return self.origin is None and not self.related and self.said is None

    @property
    def origin_thread(self) -> str | None:
        return self.origin.thread if self.origin else None


# ── the material, read once ─────────────────────────────────────


@dataclass
class _Doc:
    source: Source
    words: frozenset[str]
    corpus_text: str = ""


@dataclass
class Corpus:
    """Everything a pitch can draw on, read once per burst of pitches."""

    root: Path
    craft_threads: dict[str, str] = field(default_factory=dict)
    notes: dict[str, _Doc] = field(default_factory=dict)  # thread id -> its latest note
    docs: list[_Doc] = field(default_factory=list)
    # turtleOS's own design notes, by section. Kept apart from `docs` so their
    # vocabulary does not move what counts as a rare word among his own writing.
    refs: list[_Doc] = field(default_factory=list)
    df: dict[str, int] = field(default_factory=dict)

    def weight(self, word: str) -> float:
        n = max(len(self.docs), 1)
        return math.log((n + 1) / (self.df.get(word, 0) + 1))

    def is_rare(self, word: str) -> bool:
        return self.df.get(word, 0) <= max(RARE_FLOOR, RARE_FRACTION * len(self.docs))


def craft_threads(root: str | Path, parent_id) -> dict[str, str]:
    """``{thread id: name}`` of the eddies the registry places under the craft channel."""
    path = Path(root) / REGISTRY_REL
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    out: dict[str, str] = {}
    for tid, meta in (data.get("threads") or {}).items():
        if isinstance(meta, dict) and str(meta.get("parent_channel_id")) == str(parent_id):
            out[str(tid)] = str(meta.get("name") or "")
    return out


def _split_blocks(text: str) -> list[str]:
    blocks: list[list[str]] = [[]]
    for line in (text or "").splitlines():
        if line.strip() == "---":
            blocks.append([])
        else:
            blocks[-1].append(line)
    return ["\n".join(b).strip() for b in blocks if "\n".join(b).strip()]


_BOOM_DATE = re.compile(r"\*?(\d{4}-\d{2}-\d{2})")


def _flat(text: str) -> str:
    """A markdown table as plain lines: the quote is read in a message, not rendered."""
    lines = []
    for line in text.splitlines():
        if re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line) and "-" in line:
            continue
        if line.lstrip().startswith("|"):
            line = " · ".join(cell.strip() for cell in line.strip().strip("|").split("|") if cell.strip())
        lines.append(line)
    return "\n".join(lines).replace("**", "").replace("`", "")


def _best_paragraph(block: str, item_words: set[str]) -> str:
    block = _flat(block)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", block) if p.strip()]
    plain = [p for p in paragraphs if not p.startswith(("*", "#", ">"))] or paragraphs
    return max(plain, key=lambda p: len(words(p) & item_words), default=block)


def load_corpus(
    root: str | Path,
    parent_id,
    *,
    boom_text: str | None = None,
    altbacklog_text: str | None = None,
    design_notes: dict[str, str] | None = None,
) -> Corpus:
    """Read the craft eddy notes, their sparks, the boom and his list.

    ``boom_text`` and ``altbacklog_text`` are given in by the caller, who knows where
    the workshop is read from (the bare repository's head). None means not available,
    and the pitch simply has less to bring.
    """
    root = Path(root)
    corpus = Corpus(root=root, craft_threads=craft_threads(root, parent_id))
    eddies_dir = root / EDDIES_SUBDIR
    if eddies_dir.is_dir():
        for path in sorted(eddies_dir.glob("*.md")):
            tid = path.name.split("-", 1)[0]
            if tid not in corpus.craft_threads:
                continue
            try:
                entries = parse_eddy_file_entries(path.read_text(encoding="utf-8"))
            except OSError:
                continue
            if not entries:
                continue
            entries.sort(key=lambda e: str(e[0].get("timestamp") or ""))
            front, body = entries[-1]
            title = str(front.get("title") or corpus.craft_threads[tid]).strip()
            text = " ".join([title, *[b for _, b in entries[-2:]], *map(str, front.get("proposed-themes") or [])])
            note = _Doc(Source("eddy", title, quote_of(body), tid), frozenset(words(text)), corpus_text=body)
            corpus.notes[tid] = note
            corpus.docs.append(note)
            sparks: dict[str, dict] = {}
            for f, _ in entries:
                for spark in f.get("sparks") or []:
                    if isinstance(spark, dict) and spark.get("name"):
                        sparks[str(spark.get("id") or spark["name"])] = spark
            for spark in sparks.values():
                if str(spark.get("status") or "open") != "open":
                    continue
                name, topic = str(spark["name"]).strip(), str(spark.get("topic") or "").strip()
                quote = f"{name} — {topic}" if topic and topic != "unspecified" else name
                corpus.docs.append(_Doc(Source("spark", f"spark in “{title}”", quote, tid), frozenset(words(quote)), quote))
    for block in _split_blocks(boom_text or ""):
        date = _BOOM_DATE.search(block)
        label = f"boom {date.group(1)}" if date else "boom"
        corpus.docs.append(_Doc(Source("boom", label, ""), frozenset(words(block)), block))
    for line in (altbacklog_text or "").splitlines():
        line = line.strip()
        if line.startswith("- ") and len(line) > 4:
            corpus.docs.append(
                _Doc(Source("alt", "your list", quote_of(line[2:].strip())), frozenset(words(line)), line[2:].strip())
            )
    for name, text in sorted((design_notes or {}).items()):
        corpus.refs.extend(_sections(name, text))
    for doc in corpus.docs:
        for w in doc.words:
            corpus.df[w] = corpus.df.get(w, 0) + 1
    return corpus


DESIGN_DIRS = ("docs/ux", "docs/design", "docs/chapters")


def read_design_notes(repo_dir: str | Path) -> dict[str, str]:
    """``{file name: text}`` of turtleOS's design notes in this checkout. Missing
    folders give nothing; a pitch then has less to bring, which it says."""
    out: dict[str, str] = {}
    for rel in DESIGN_DIRS:
        folder = Path(repo_dir) / rel
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            try:
                out[path.name] = path.read_text(encoding="utf-8")
            except OSError:
                continue
    return out


def _sections(name: str, text: str) -> list[_Doc]:
    """A design note cut at its headings, one passage each."""
    title = name
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in (text or "").splitlines():
        if line.startswith("# ") and title == name:
            title = line[2:].strip() or name
        elif line.startswith("#"):
            sections.append((line.lstrip("#").strip(), []))
        else:
            sections[-1][1].append(line)
    out = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if len(body) < DOC_SECTION_MIN:
            continue
        label = f"turtleOS design · {title}" + (f" › {heading}" if heading else "")
        out.append(_Doc(Source("doc", label, ""), frozenset(words(f"{heading} {body}")), body))
    return out


# ── one row's context ───────────────────────────────────────────


def origin_candidates(root: str | Path, item_id: str, body: str) -> tuple[str, ...]:
    """Discord thread ids the row points at: where its intake says it came from,
    then ids written in the row. Unverified; whether one is a craft eddy is for
    the caller (the registry here, Discord on a press)."""
    found: list[str] = []
    intake = Path(root) / INTAKE_REL / f"{item_id}.md"
    try:
        text = intake.read_text(encoding="utf-8")
    except OSError:
        text = ""
    for pattern in _INTAKE_ORIGIN:
        for match in pattern.finditer(text):
            if match.group(1) not in found:
                found.append(match.group(1))
    for match in _THREAD_ID.finditer(body or ""):
        if match.group(1) not in found:
            found.append(match.group(1))
    return tuple(found)


_MAGE_REPORT = re.compile(r"^## Mage report\s*\n(?P<text>.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)


def said_for(root: str | Path, item_id: str) -> Source | None:
    """His own words when the row was filed, from the craft intake it was harvested
    from. Rows filed by hand on the Forge have no intake, and say nothing here."""
    try:
        text = (Path(root) / INTAKE_REL / f"{item_id}.md").read_text(encoding="utf-8")
    except OSError:
        return None
    match = _MAGE_REPORT.search(text)
    said = " ".join(match.group("text").split()) if match else ""
    return Source("said", "your words when you filed it", quote_of(said, 320)) if said else None


def _row_words(title: str, body: str) -> set[str]:
    return words(f"{title} {body}")


@dataclass(frozen=True)
class Candidate:
    key: str
    source: Source
    text: str  # what the judge reads


@dataclass(frozen=True)
class Shortlist:
    origin_candidates: tuple[str, ...]
    origin: Source | None
    candidates: tuple[Candidate, ...]
    said: Source | None = None


def shortlist(corpus: Corpus, item_id: str, title: str, body: str) -> Shortlist:
    """The origin eddy (if the row names one that is a craft eddy) and the loosely
    related material a judge may keep from. The origin is not a guess; the rest is."""
    candidates = origin_candidates(corpus.root, item_id, body)
    origin = None
    for tid in candidates:
        note = corpus.notes.get(tid)
        if note is not None:
            origin = Source("origin", note.source.label, note.source.quote, tid)
            break
        if tid in corpus.craft_threads:
            origin = Source("origin", corpus.craft_threads[tid], "", tid)
            break
    item_words = _row_words(title, body)
    scored: list[tuple[float, _Doc, tuple[str, ...]]] = []
    for doc in corpus.docs:
        if origin is not None and doc.source.thread == origin.thread:
            continue  # it is already shown as the origin
        shared = {w for w in item_words & doc.words if corpus.is_rare(w)}
        if len(shared) >= MIN_SHARED:
            ordered = tuple(sorted(shared, key=lambda w: -corpus.weight(w)))
            scored.append((sum(corpus.weight(w) for w in shared), doc, ordered))
    for doc in corpus.refs:
        shared = {w for w in item_words & doc.words if corpus.is_rare(w) or corpus.df.get(w, 0) == 0}
        if len(shared) >= DOC_MIN_SHARED:
            ordered = tuple(sorted(shared, key=lambda w: -corpus.weight(w)))
            scored.append((sum(corpus.weight(w) for w in shared), doc, ordered))
    scored.sort(key=lambda t: -t[0])
    taken = {k: 0 for k in SHORTLIST}
    out: list[Candidate] = []
    for _score, doc, shared in scored:
        kind = doc.source.kind
        if taken[kind] >= SHORTLIST[kind]:
            continue
        taken[kind] += 1
        quote = doc.source.quote
        if kind in ("boom", "doc"):
            quote = quote_of(_best_paragraph(doc.corpus_text, item_words))
        source = Source(kind, doc.source.label, quote, doc.source.thread, shared[:4])
        text = f"{source.label}: {quote}" if kind in ("eddy", "spark", "doc") else quote
        out.append(Candidate(f"c{len(out) + 1}", source, text))
    return Shortlist(candidates, origin, tuple(out), said_for(corpus.root, item_id))


def decide(short: Shortlist, keep: Iterable[str]) -> Context:
    """The context once a judge has chosen. Keys not on the shortlist are ignored,
    so a judge cannot add anything that is not a source."""
    wanted = {str(k) for k in keep}
    kept = [c.source for c in short.candidates if c.key in wanted][:MAX_KEPT]
    order = {"eddy": 0, "spark": 1, "boom": 2, "alt": 3, "doc": 4}
    kept.sort(key=lambda s: order[s.kind])
    return Context(short.origin_candidates, short.origin, tuple(kept), short.said)


# ── words he reads ──────────────────────────────────────────────


def jump_url(guild_id, thread_id) -> str:
    return f"https://discord.com/channels/{guild_id}/{thread_id}"


def compose_context(context: Context, guild_id, *, limit: int = 1800) -> str:
    """The part of a pitch that is not the row: what turtleOS already holds.
    Whole entries are dropped from the end to fit ``limit``, never cut in half."""
    titles = {"eddy": "Eddies that touch it", "spark": "Sparks", "boom": "In your boom", "alt": "On your list", "doc": "In the turtleOS design notes"}
    parts: list[str] = []
    if context.origin is not None:
        o = context.origin
        head = f"**Where it came from** — [{o.label}]({jump_url(guild_id, o.thread)})"
        parts.append(head + (f"\n> {o.quote}" if o.quote else ""))
    if context.said is not None:
        parts.append(f"**Your words when you filed it**\n> {context.said.quote}")
    for kind in ("eddy", "spark", "boom", "alt", "doc"):
        group = [s for s in context.related if s.kind == kind]
        if not group:
            continue
        entries = [f"**{titles[kind]}**"]
        for s in group:
            if kind == "alt":
                line = f"- {s.quote}"
            else:
                label = f"[{s.label}]({jump_url(guild_id, s.thread)})" if s.thread else s.label
                line = f"- {label}: {s.quote}"
            entries.append(line)
        parts.append("\n".join(entries))
    while parts and len("\n\n".join(parts)) > limit:
        parts.pop()
    return "\n\n".join(parts)


NOTHING_YET = "*Nothing in your eddies, sparks or boom touches this yet.*"


def compose_embed(context: Context, guild_id, as_filed: str, *, filed_chars: int = 450) -> str:
    """The embed under a pitch: what turtleOS holds about it, then the row as it was
    filed, so the rewrite above can be checked against what it was written from."""
    known = compose_context(context, guild_id, limit=2000)
    parts = [known or NOTHING_YET]
    filed = quote_of(as_filed, filed_chars)
    if filed:
        parts.append(f"**The row as filed**\n> {filed}")
    return "\n\n".join(parts)


def in_sources(context: Context, texts: Iterable[str]) -> bool:
    """True when every quotation in ``context`` is found in one of ``texts``.
    The check the tests use, kept here so the claim and its check move together."""
    flat = [" ".join(t.split()) for t in texts]
    for s in (*([context.origin] if context.origin else []), *([context.said] if context.said else []), *context.related):
        quote = s.quote.rstrip("…").strip()
        if quote and not any(quote in t for t in flat):
            return False
    return True
