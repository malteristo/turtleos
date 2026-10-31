"""Sparks named in an eddy note, and the act that develops or drops one.

A spark starts open. The only acts are developed and dropped. Sparks that
share a topic are read together; a shape for that topic cites every spark
in it, not one thin line.
"""

from __future__ import annotations

import re

import yaml

from story_entries import _ENTRY_FRONT_RE, parse_eddy_file_entries

ACTS = ("developed", "dropped")


class SparkActError(ValueError):
    """The act was not develop or drop, or the spark is not in the note."""


def slug(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return text or "spark"


def parse_spark_lines(body: str) -> list[dict]:
    """Lines from the note writer: `- name | topic`, or `none`."""
    sparks: list[dict] = []
    seen: set[str] = set()
    for raw in (body or "").splitlines():
        line = raw.strip().lstrip("-").strip()
        if not line or line.lower() in ("none", "none."):
            continue
        if "|" in line:
            name, topic = (part.strip() for part in line.split("|", 1))
        else:
            name, topic = line, ""
        if not name:
            continue
        base = slug(name)
        spark_id = base
        n = 2
        while spark_id in seen:
            spark_id = f"{base}-{n}"
            n += 1
        seen.add(spark_id)
        sparks.append(
            {
                "id": spark_id,
                "name": name,
                "topic": topic or "unspecified",
                "status": "open",
            }
        )
    return sparks


def sparks_from_front(front: dict) -> list[dict]:
    raw = front.get("sparks") or []
    if not isinstance(raw, list):
        return []
    sparks: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        spark_id = str(item.get("id") or slug(name)).strip()
        if not spark_id or not name:
            continue
        status = str(item.get("status") or "open").strip()
        if status not in ("open", *ACTS):
            status = "open"
        sparks.append(
            {
                "id": spark_id,
                "name": name,
                "topic": str(item.get("topic") or "unspecified").strip() or "unspecified",
                "status": status,
            }
        )
    return sparks


def apply_spark_act(content: str, spark_id: str, status: str) -> str:
    """Set one spark to developed or dropped. Any other status is refused."""
    if status not in ACTS:
        raise SparkActError("a spark is developed or dropped")
    matches = list(_ENTRY_FRONT_RE.finditer(content))
    for match in reversed(matches):
        try:
            front = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue
        if not isinstance(front, dict):
            continue
        sparks = front.get("sparks")
        if not isinstance(sparks, list):
            continue
        hit = False
        for spark in sparks:
            if isinstance(spark, dict) and str(spark.get("id")) == spark_id:
                spark["status"] = status
                hit = True
        if not hit:
            continue
        dumped = yaml.safe_dump(
            front, sort_keys=False, allow_unicode=True
        ).strip()
        return (
            content[: match.start()]
            + f"---\n{dumped}\n---\n\n"
            + content[match.end() :]
        )
    raise SparkActError(f"no spark {spark_id}")


def sparks_by_topic(entries) -> dict[str, list[dict]]:
    """Every spark under its topic, across notes. Each item keeps its eddy body."""
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        sparks = getattr(entry, "sparks", None) or []
        for spark in sparks:
            topic = str(spark.get("topic") or "unspecified")
            grouped.setdefault(topic, []).append(
                {
                    **spark,
                    "eddy": getattr(entry, "title", ""),
                    "contribution": getattr(entry, "body", ""),
                }
            )
    return grouped


def cites_the_topic(topic_sparks: list[dict], cited_ids: set[str] | list[str]) -> bool:
    """A shape for a topic cites every spark in it.

    One spark is the whole topic. Two sparks cited as one line is the thin line.
    """
    ids = {str(spark.get("id")) for spark in topic_sparks if spark.get("id")}
    cited = {str(item) for item in cited_ids}
    if not ids:
        return False
    return cited == ids


def load_sparks(content: str) -> list[dict]:
    found: list[dict] = []
    for front, _body in parse_eddy_file_entries(content):
        found.extend(sparks_from_front(front))
    return found
