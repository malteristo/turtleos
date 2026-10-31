"""MCP JSON-RPC methods over one authenticated grant.

Every request is answered for one grant and the sources it still owns. An
out-of-scope source and a nonexistent one produce the same answer.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from mcp_access import audit, content, receipts, workshop
from mcp_access.grants import Grant, GrantStore
from mcp_access.operations import OPERATIONS, ROOM_OPERATIONS, WORKSHOP_OPERATIONS
from mcp_access.registry import KIND_WORKSHOP, Source

SUPPORTED_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")
SERVER_INFO = {"name": "turtleos", "version": "0.1"}
INTRO = (
    "turtleOS holds personal context that its owner accumulates and curates by "
    "practising with it: conversation notes from their rooms and, where they are "
    "the subject, a health picture and the documents behind it. The owner granted this connection; treat what "
    "you read as theirs, use it for what they are asking you now, and do not "
    "repeat it elsewhere without them."
)


def _tool_use(name: str, ops: set[str]) -> str:
    rooms = bool(ROOM_OPERATIONS & ops)
    shop = bool(WORKSHOP_OPERATIONS & ops)
    if name == "search":
        if rooms and shop:
            return (
                "`search(query, source?)` finds notes, health-picture and document passages, and in a workshop "
                "the first matching line of each file; it returns refs."
            )
        if shop:
            return "`search(query, source?)` finds the first matching line of each workshop file; it returns refs and names the release."
        return "`search(query, source?)` finds notes, health-picture and document passages; it returns refs."
    if name == "speak":
        return (
            "`speak(text, session?)` is how a forge spirit talks to a house spirit. "
            "It opens a magic session, or continues one this connection opened, and the house keeps the turn. "
            "`hear(session)` brings back the house spirit's latest reply in that session. "
            "It cannot change files. It has no terminal and no browser."
        )
    if name == "hear":
        return (
            "`hear(session)` brings back the house spirit's latest reply in a session this connection opened. "
            "It is empty until that reply is posted. It has no terminal and no browser."
        )
    if shop and not rooms:
        return "`read(ref)` opens a workshop ref from search, from a folder listing, or the bootstrap, and names the release it read."
    return "`read(ref)` opens a ref from search or a resource URI."


def _tool_description(name: str, ops: set[str]) -> str:
    rooms = bool(ROOM_OPERATIONS & ops)
    shop = bool(WORKSHOP_OPERATIONS & ops)
    if name == "search":
        if rooms and shop:
            return "Search this connection's conversation notes, health picture, documents and workshop files. Returns refs to read."
        if shop:
            return "Search this connection's workshop files at their current release. Returns refs to read."
        return TOOLS["search"]["description"]
    if name == "speak":
        return TOOLS["speak"]["description"]
    if name == "hear":
        return TOOLS["hear"]["description"]
    if shop and not rooms:
        return "Read a turtleos:// workshop ref returned by search, listed in resources, or named by the bootstrap."
    return TOOLS["read"]["description"]

WORKSHOP_INTRO = (
    "turtleOS serves a practice workshop for its owner: the repository their practice keeps, read at its "
    "current release. The owner granted this connection; treat what you read as theirs, use it for what "
    "they are asking you now, and do not repeat it elsewhere without them."
)

NOT_FOUND = -32002
INVALID_PARAMS = -32602
METHOD_NOT_FOUND = -32601
INVALID_REQUEST = -32600
FORBIDDEN = -32001


class Refusal(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Session:
    grant: Grant
    sources: list[Source]
    store: GrantStore
    refused: bool = field(default=False)
    owner_root: Path | None = None
    locale: str = "en"
    mcp_session: str = ""

    def __post_init__(self) -> None:
        # A grant sees only the kinds of source its operations can use. Without
        # this, a reader grant made after workshops existed would list one it
        # cannot open, and a workshop grant would list rooms it cannot read.
        ops = set(self.grant.operations)
        self.sources = [
            s
            for s in self.sources
            if (ops & WORKSHOP_OPERATIONS if s.kind == KIND_WORKSHOP else ops & ROOM_OPERATIONS)
        ]

    def _source(self, sid: str, *, workshop_kind: bool = False) -> Source:
        for s in self.sources:
            if s.id == sid and (s.kind == KIND_WORKSHOP) == workshop_kind:
                return s
        raise Refusal(NOT_FOUND, "not found")

    def _require(self, operation: str, sources: list[Source] = ()) -> None:
        if operation in self.grant.operations:
            return
        for s in sources:
            audit.append(
                s.audit_dir,
                grant=self.grant.id,
                principal=self.grant.principal,
                operation=operation,
                decision="refused",
            )
        raise Refusal(FORBIDDEN, f"operation not permitted: {operation}")

    def _remember_client(self, params: dict) -> None:
        info = params.get("clientInfo")
        if not isinstance(info, dict):
            return
        name = " ".join(str(info.get("name") or "").split())[:80]
        version = " ".join(str(info.get("version") or "").split())[:40]
        if not name:
            return
        if not self.mcp_session:
            self.mcp_session = secrets.token_hex(16)
        fresh = self.store.remember_mcp_client(self.grant.id, self.mcp_session, name, version or None)
        if fresh is not None:
            self.grant = fresh

    def _caller(self) -> dict:
        # The grant's own client_name is whoever initialized last. A read is
        # attributed only to the session that introduced itself on this request.
        name, version = "", ""
        row = ((self.grant.extra or {}).get("mcp_clients") or {}).get(self.mcp_session)
        if isinstance(row, dict):
            name, version = str(row.get("name") or ""), str(row.get("version") or "")
        return {
            "principal": self.grant.principal or "",
            "client_name": name,
            "client_version": version,
        }

    def _audit(self, operation: str, sources: list[Source]) -> None:
        for s in sources:
            audit.append(
                s.audit_dir,
                grant=self.grant.id,
                principal=self.grant.principal,
                operation=operation,
                decision="allowed",
            )

    def handle(self, message: dict) -> dict | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return _error(None, INVALID_REQUEST, "invalid request")
        method = message.get("method")
        mid = message.get("id")
        if mid is None:
            return None
        params = message.get("params") or {}
        try:
            result = self._dispatch(method, params)
        except Refusal as r:
            self.refused = True
            return _error(mid, r.code, r.message)
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def _dispatch(self, method: str, params: dict):
        if method == "initialize":
            self._remember_client(params)
            asked = str(params.get("protocolVersion") or "")
            version = asked if asked in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            caps: dict = {}
            if self._resource_ops():
                caps["resources"] = {"listChanged": False}
            if self._tool_names():
                caps["tools"] = {"listChanged": False}
            return {
                "protocolVersion": version,
                "capabilities": caps,
                "serverInfo": SERVER_INFO,
                "instructions": self.instructions(),
            }
        if method == "ping":
            return {}
        if method == "resources/list":
            return {"resources": self._resources()}
        if method == "resources/templates/list":
            templates = []
            if "read_note" in self.grant.operations:
                templates.append(
                    {
                        "uriTemplate": "turtleos://room/{source}/note/{id}",
                        "name": "conversation note",
                        "mimeType": "text/markdown",
                        "description": "One conversation note; ids come from the room's notes list.",
                    }
                )
            if "read_document" in self.grant.operations:
                templates.append(
                    {
                        "uriTemplate": "turtleos://documents/{source}/{id}",
                        "name": "document",
                        "mimeType": "text/markdown",
                        "description": "One stored document's extracted text, page by page; ids come from the source's documents list.",
                    }
                )
            if "workshop_read" in self.grant.operations and any(s.kind == KIND_WORKSHOP for s in self.sources):
                templates.append(
                    {
                        "uriTemplate": "turtleos://workshop/{source}/file/{path}",
                        "name": "workshop file",
                        "mimeType": "text/markdown",
                        "description": "One file of a workshop at its current release; the answer names the release. Paths come from the bootstrap, a folder listing or a search.",
                    }
                )
                templates.append(
                    {
                        "uriTemplate": "turtleos://workshop/{source}/tree/{dir}",
                        "name": "workshop folder",
                        "mimeType": "application/json",
                        "description": "The entries directly under one workshop folder at its current release (leave {dir} out for the top).",
                    }
                )
            return {"resourceTemplates": templates}
        if method == "resources/read":
            uri = str(params.get("uri") or "")
            text, mime = self._read_uri(uri)
            return {"contents": [{"uri": uri, "mimeType": mime, "text": text}]}
        if method == "tools/list":
            return {"tools": [self._tool(n) for n in self._tool_names()]}
        if method == "tools/call":
            return self._call_tool(str(params.get("name") or ""), params.get("arguments") or {})
        raise Refusal(METHOD_NOT_FOUND, f"method not found: {method}")

    def instructions(self) -> str:
        ops = set(self.grant.operations)
        workshop_only = bool(WORKSHOP_OPERATIONS & ops) and not (ROOM_OPERATIONS & ops)
        parts = [WORKSHOP_INTRO if workshop_only else INTRO, ""]
        if self.sources:
            label = {"subject": "health", KIND_WORKSHOP: "workshop"}
            listed = ", ".join(f"{s.id} ({label.get(s.kind, 'room')})" for s in self.sources)
            parts.append(f"This connection reaches: {listed}. Nothing else exists for it.")
        else:
            parts.append("This connection reaches no personal context; it can report on its own grant only.")
        if self.grant.profile == "house":
            from mcp_access.reveal import opening_sentence

            parts.append(opening_sentence(self.sources, self.locale))
        if "brief" in self.grant.operations and not workshop_only:
            parts.append(
                "Start with turtleos://brief — turtleOS's own account of what is here, "
                "what is recent, and whether anything is wrong."
            )
        for s in self.sources:
            if s.kind == KIND_WORKSHOP and "workshop_read" in ops:
                parts.append(
                    f"`{s.id}` is a workshop: a practice repository, read at its current release and never from a copy. "
                    f"Begin with turtleos://workshop/{s.id}/bootstrap; it says how to read and what the practice asks first. "
                    "Every workshop answer names the release it came from and says when you are behind it. "
                    "If the person asks you to summon, to practise, or to continue their practice, the bootstrap is "
                    "what they mean: read it before replying and do what it says, even in a folder with no files."
                )
        parts.extend(_tool_use(n, ops) for n in self._tool_names())
        writes = any(OPERATIONS[o].write for o in self.grant.operations if o in OPERATIONS)
        tail = "turtleos://capabilities states this grant exactly. "
        if "spirit_speak" in ops:
            tail += (
                "speak is the one write on this connection: it opens or continues a magic session "
                "and the house keeps the turn. hear brings the house spirit's reply back. "
                "It cannot change files. It has no terminal and no browser. "
            )
        elif not writes:
            tail += "This connection cannot write. "
        tail += "It cannot see anyone else's context."
        parts.append(tail)
        return "\n".join(parts)

    def _tool(self, name: str) -> dict:
        ops = TOOL_OPERATIONS[name]
        writes = any(OPERATIONS[o].write for o in ops)
        return {
            **TOOLS[name],
            "description": _tool_description(name, set(self.grant.operations)),
            "annotations": {
                "readOnlyHint": not writes,
                "destructiveHint": False,
                "idempotentHint": not writes,
                "openWorldHint": name == "speak",
            },
        }

    def _resource_ops(self) -> list[str]:
        return [
            o
            for o in ("capabilities", "brief", "list_notes", "read_health_picture", "list_documents", "workshop_read")
            if o in self.grant.operations
        ]

    def _tool_names(self) -> list[str]:
        names = []
        if {"search", "workshop_search"} & set(self.grant.operations):
            names.append("search")
        if {"read_note", "read_health_picture", "read_document", "workshop_read"} & set(self.grant.operations):
            names.append("read")
        if "spirit_speak" in self.grant.operations:
            names.append("speak")
            names.append("hear")
        return names

    def _resources(self) -> list[dict]:
        ops = set(self.grant.operations)
        out = []
        if "capabilities" in ops:
            out.append(_res("turtleos://capabilities", "capabilities", "application/json",
                            "This connection's grant: owner, sources, operations, expiry."))
        if "brief" in ops:
            out.append(_res("turtleos://brief", "brief", "text/markdown",
                            "Read first: what this connection reaches, recent activity, integrity."))
        for s in self.sources:
            if s.kind == KIND_WORKSHOP:
                if "workshop_read" in ops:
                    out.append(_res(workshop.refs(s, "bootstrap"), f"{s.id} bootstrap", "text/markdown",
                                    "Read first: how to read this workshop with no clone, and what the practice asks of a session that begins here."))
                    out.append(_res(workshop.refs(s, "tree"), f"{s.id} top folder", "application/json",
                                    "The top-level entries of this workshop at its current release."))
                continue
            if "list_notes" in ops:
                out.append(_res(f"turtleos://room/{s.id}/notes", f"{s.id} notes", "application/json",
                                f"Conversation notes in {s.id}, newest first; open one with read."))
            if "read_health_picture" in ops and s.kind == "subject":
                out.append(_res(f"turtleos://health/{s.id}/picture", f"{s.id} health picture", "text/markdown",
                                "The owner's current health picture, as turtleOS holds it."))
            if "list_documents" in ops and content.list_documents(s):
                out.append(_res(f"turtleos://documents/{s.id}", f"{s.id} documents", "application/json",
                                f"Documents stored in {s.id} (letters, reports), newest first; open one with read."))
        return out

    def _read_uri(self, uri: str) -> tuple[str, str]:
        if uri == "turtleos://capabilities":
            self._require("capabilities")
            return json.dumps(self._capabilities(), indent=2), "application/json"
        if uri == "turtleos://brief":
            self._require("brief", self.sources)
            self._audit("brief", self.sources)
            text = content.brief(
                self.sources,
                expires=self.grant.expires,
                refused_since_brief=self.grant.refused_since_brief,
                documents="list_documents" in self.grant.operations,
                workshop_ops="workshop_read" in self.grant.operations,
            )
            self.store.update(self.grant.id, refused_since_brief=0)
            return text, "text/markdown"
        query = ""
        if "?" in uri:
            uri, _, query = uri.partition("?")
        parts = uri.removeprefix("turtleos://").split("/") if uri.startswith("turtleos://") else []
        if len(parts) >= 3 and parts[0] == "workshop":
            return self._read_workshop(self._source(parts[1], workshop_kind=True), parts[2], "/".join(parts[3:]), query)
        if len(parts) == 3 and parts[0] == "room" and parts[2] == "notes":
            s = self._source(parts[1])
            self._require("list_notes", [s])
            self._audit("list_notes", [s])
            return json.dumps(content.list_notes(s), indent=2, ensure_ascii=False), "application/json"
        if len(parts) == 4 and parts[0] == "room" and parts[2] == "note":
            s = self._source(parts[1])
            self._require("read_note", [s])
            text = content.read_note(s, parts[3])
            if text is None:
                raise Refusal(NOT_FOUND, "not found")
            self._audit("read_note", [s])
            receipts.for_note(
                self.owner_root,
                note_id=parts[3],
                title=content.latest_title(text),
                locale=self.locale,
                **self._caller(),
            )
            return text, "text/markdown"
        if len(parts) == 3 and parts[0] == "health" and parts[2] == "picture":
            s = self._source(parts[1])
            self._require("read_health_picture", [s])
            text = content.read_health_picture(s)
            if text is None:
                raise Refusal(NOT_FOUND, "not found")
            self._audit("read_health_picture", [s])
            receipts.for_health(self.owner_root, locale=self.locale, **self._caller())
            return text, "text/markdown"
        if len(parts) == 2 and parts[0] == "documents":
            s = self._source(parts[1])
            self._require("list_documents", [s])
            self._audit("list_documents", [s])
            return json.dumps(content.list_documents(s), indent=2, ensure_ascii=False), "application/json"
        if len(parts) == 3 and parts[0] == "documents":
            s = self._source(parts[1])
            self._require("read_document", [s])
            text = content.read_document(s, parts[2])
            if text is None:
                raise Refusal(NOT_FOUND, "not found")
            self._audit("read_document", [s])
            receipts.for_letter(
                self.owner_root,
                doc_id=parts[2],
                filename=content.document_filename(s, parts[2]),
                locale=self.locale,
                **self._caller(),
            )
            return text, "text/markdown"
        raise Refusal(NOT_FOUND, "not found")

    def _capabilities(self) -> dict:
        g = self.grant
        return {
            "grant": g.id,
            "principal": g.principal,
            "owner": g.owner,
            "profile": g.profile,
            "operations": g.operations,
            "sources": [{"id": s.id, "kind": s.kind} for s in self.sources],
            "expires": g.expires,
            "revision": g.revision,
        }

    def _started(self, source: Source) -> str | None:
        return ((self.grant.extra or {}).get("workshop_started") or {}).get(source.id)

    def _mark_started(self, source: Source, release: workshop.Release) -> None:
        """Remember the release this client last began from, on the grant (a grant is one client installation).

        Decided, not skipped: two sessions in one installation share this one
        marker, so a second session's bootstrap resets what the first is
        compared against. A ref carrying ``?since=`` is exact for each session
        and takes precedence; the marker covers a client that drops it.
        """
        extra = dict(self.grant.extra or {})
        marks = dict(extra.get("workshop_started") or {})
        marks[source.id] = release.sha
        extra["workshop_started"] = marks
        self.grant.extra = extra
        self.store.update(self.grant.id, extra=extra)

    def _behind(self, source: Source, release: workshop.Release, query: str) -> dict | None:
        since = ""
        for part in query.split("&"):
            if part.startswith("since="):
                since = part[len("since="):]
        since = since or self._started(source) or ""
        if not since:
            return None
        return workshop.behind(source, since, release)

    def _read_workshop(self, source: Source, kind: str, path: str, query: str) -> tuple[str, str]:
        self._require("workshop_read", [source])
        release = workshop.head(source)
        if release is None:
            raise Refusal(NOT_FOUND, "this workshop is unavailable on the host")
        behind = self._behind(source, release, query) if kind != "bootstrap" else None
        stay = f"?since={release.short}"
        if kind == "bootstrap" and not path:
            text = workshop.bootstrap_text(source, release)
            self._mark_started(source, release)
        elif kind == "file" and path:
            body = workshop.read_file(source, release, path)
            if body is None:
                raise Refusal(NOT_FOUND, "not found")
            text = workshop.header(release, path=path, behind_note=behind) + "\n\n" + body
        elif kind == "tree":
            entries = workshop.list_tree(source, release, path)
            if entries is None:
                raise Refusal(NOT_FOUND, "not found")
            for e in entries:
                e["ref"] = workshop.refs(source, "tree" if e["type"] == "dir" else "file", e["path"]) + stay
            self._audit("workshop_read", [source])
            doc = {"release": release.line(), "path": path, "entries": entries}
            if behind is not None:
                doc["behind"] = behind
            return json.dumps(doc, indent=2, ensure_ascii=False), "application/json"
        else:
            raise Refusal(NOT_FOUND, "not found")
        self._audit("workshop_read", [source])
        receipts.for_workshop(self.owner_root, locale=self.locale, **self._caller())
        return text, "text/markdown"

    def _search_workshops(self, shops: list[Source], query: str) -> list[dict]:
        out = []
        for s in shops:
            release = workshop.head(s)
            if release is None:
                continue
            behind = self._behind(s, release, "")
            for h in workshop.search(s, release, query):
                out.append(
                    {
                        "ref": workshop.refs(s, "file", h["path"]) + f"?since={release.short}",
                        "title": h["path"],
                        "last": release.committed,
                        "snippet": f"line {h['line']}: {h['text']}",
                        "release": release.short,
                        **({"behind": behind} if behind is not None else {}),
                    }
                )
        return out

    def _call_tool(self, name: str, args: dict) -> dict:
        if name not in self._tool_names():
            raise Refusal(NOT_FOUND, "not found")
        if name == "search":
            wanted = args.get("source")
            pool = [self._source(str(wanted), workshop_kind=_is_workshop_id(self.sources, str(wanted)))] if wanted else self.sources
            rooms = [s for s in pool if s.kind != KIND_WORKSHOP]
            shops = [s for s in pool if s.kind == KIND_WORKSHOP]
            query = str(args.get("query") or "")
            hits: list[dict] = []
            if rooms:
                self._require("search", rooms)
                hits.extend(content.search(rooms, query, documents="read_document" in self.grant.operations))
                self._audit("search", rooms)
                receipts.for_search(self.owner_root, hits, locale=self.locale, **self._caller())
            if shops:
                self._require("workshop_search", shops)
                found = self._search_workshops(shops, query)
                hits.extend(found)
                self._audit("workshop_search", shops)
                if found:
                    receipts.for_workshop(self.owner_root, locale=self.locale, **self._caller())
            hits.sort(key=lambda h: h["last"] or "", reverse=True)
            return _text(json.dumps(hits[:20], indent=2, ensure_ascii=False))
        if name == "speak":
            self._require("spirit_speak")
            from spirit_link import deliver_live

            session = str(args.get("session") or "").strip() or None
            result = deliver_live(self.grant.owner, str(args.get("text") or ""), session)
            if not result.get("ok"):
                return {
                    "content": [{"type": "text", "text": str(result.get("error") or "could not speak")}],
                    "isError": True,
                }
            return _text(json.dumps(result, ensure_ascii=False))
        if name == "hear":
            self._require("spirit_speak")
            from spirit_link import hear_live

            result = hear_live(self.grant.owner, str(args.get("session") or "").strip() or None)
            if not result.get("ok"):
                return {
                    "content": [{"type": "text", "text": str(result.get("error") or "could not hear")}],
                    "isError": True,
                }
            return _text(json.dumps(result, ensure_ascii=False))
        ref = str(args.get("ref") or "")
        try:
            text, _ = self._read_uri(ref)
        except Refusal as r:
            if r.code == NOT_FOUND:
                self.refused = True
                return {"content": [{"type": "text", "text": "not found"}], "isError": True}
            raise
        return _text(text)


TOOLS = {
    "search": {
        "name": "search",
        "description": "Search this connection's conversation notes, health picture and documents. Returns refs to read.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "source": {"type": "string", "description": "Optional source id from turtleos://capabilities"},
            },
            "required": ["query"],
        },
    },
    "read": {
        "name": "read",
        "description": "Read a turtleos:// ref returned by search or listed in resources.",
        "inputSchema": {
            "type": "object",
            "properties": {"ref": {"type": "string"}},
            "required": ["ref"],
        },
    },
    "speak": {
        "name": "speak",
        "description": (
            "Speak as the forge spirit to the house spirit. Opens one magic session, or continues "
            "one this connection opened, and the house keeps the turn. No terminal and no browser."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "What the forge spirit says."},
                "session": {
                    "type": "string",
                    "description": "A session this connection already opened. Omit to open one.",
                },
            },
            "required": ["text"],
        },
    },
    "hear": {
        "name": "hear",
        "description": (
            "Bring back the house spirit's latest reply in a session this connection opened. "
            "Empty until that reply is posted. No terminal and no browser."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session": {
                    "type": "string",
                    "description": "A session this connection already opened.",
                },
            },
            "required": ["session"],
        },
    },
}


TOOL_OPERATIONS = {
    "search": ("search",),
    "read": ("read_note", "read_health_picture", "list_notes", "list_documents", "read_document", "brief", "capabilities"),
    "speak": ("spirit_speak",),
    "hear": ("spirit_speak",),
}


def _is_workshop_id(sources: list[Source], sid: str) -> bool:
    return any(s.id == sid and s.kind == KIND_WORKSHOP for s in sources)


def _res(uri: str, name: str, mime: str, description: str) -> dict:
    return {"uri": uri, "name": name, "mimeType": mime, "description": description}


def _text(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}
