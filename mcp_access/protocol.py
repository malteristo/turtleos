"""MCP JSON-RPC methods over one authenticated grant.

Every request is answered for one grant and the sources it still owns. An
out-of-scope source and a nonexistent one produce the same answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from mcp_access import audit, content
from mcp_access.grants import Grant, GrantStore
from mcp_access.operations import OPERATIONS
from mcp_access.registry import Source

SUPPORTED_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")
SERVER_INFO = {"name": "turtleos", "version": "0.1"}
INTRO = (
    "turtleOS holds personal context that its owner accumulates and curates by "
    "practising with it: conversation notes from their rooms and, where they are "
    "the subject, a health picture. The owner granted this connection; treat what "
    "you read as theirs, use it for what they are asking you now, and do not "
    "repeat it elsewhere without them."
)
TOOL_USE = {
    "search": "`search(query, source?)` finds notes and health-picture passages; it returns refs.",
    "read": "`read(ref)` opens a ref from search or a resource URI.",
}

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

    def _source(self, sid: str) -> Source:
        for s in self.sources:
            if s.id == sid:
                return s
        raise Refusal(NOT_FOUND, "not found")

    def _require(self, operation: str, sources: list[Source] = ()) -> None:
        if operation in self.grant.operations:
            return
        for s in sources:
            audit.append(
                s.root,
                grant=self.grant.id,
                principal=self.grant.principal,
                operation=operation,
                decision="refused",
            )
        raise Refusal(FORBIDDEN, f"operation not permitted: {operation}")

    def _audit(self, operation: str, sources: list[Source]) -> None:
        for s in sources:
            audit.append(
                s.root,
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
        parts = [INTRO, ""]
        if self.sources:
            listed = ", ".join(f"{s.id} ({'health' if s.kind == 'subject' else 'room'})" for s in self.sources)
            parts.append(f"This connection reaches: {listed}. Nothing else exists for it.")
        else:
            parts.append("This connection reaches no personal context; it can report on its own grant only.")
        if "brief" in self.grant.operations:
            parts.append(
                "Start with turtleos://brief — turtleOS's own account of what is here, "
                "what is recent, and whether anything is wrong."
            )
        parts.extend(TOOL_USE[n] for n in self._tool_names())
        writes = any(OPERATIONS[o].write for o in self.grant.operations if o in OPERATIONS)
        parts.append(
            "turtleos://capabilities states this grant exactly. "
            + ("" if writes else "This connection cannot write. ")
            + "It cannot see anyone else's context."
        )
        return "\n".join(parts)

    def _tool(self, name: str) -> dict:
        ops = TOOL_OPERATIONS[name]
        writes = any(OPERATIONS[o].write for o in ops)
        return {
            **TOOLS[name],
            "annotations": {
                "readOnlyHint": not writes,
                "destructiveHint": False,
                "idempotentHint": not writes,
                "openWorldHint": False,
            },
        }

    def _resource_ops(self) -> list[str]:
        return [
            o
            for o in ("capabilities", "brief", "list_notes", "read_health_picture")
            if o in self.grant.operations
        ]

    def _tool_names(self) -> list[str]:
        names = []
        if "search" in self.grant.operations:
            names.append("search")
        if {"read_note", "read_health_picture"} & set(self.grant.operations):
            names.append("read")
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
            if "list_notes" in ops:
                out.append(_res(f"turtleos://room/{s.id}/notes", f"{s.id} notes", "application/json",
                                f"Conversation notes in {s.id}, newest first; open one with read."))
            if "read_health_picture" in ops and s.kind == "subject":
                out.append(_res(f"turtleos://health/{s.id}/picture", f"{s.id} health picture", "text/markdown",
                                "The owner's current health picture, as turtleOS holds it."))
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
            )
            self.store.update(self.grant.id, refused_since_brief=0)
            return text, "text/markdown"
        parts = uri.removeprefix("turtleos://").split("/") if uri.startswith("turtleos://") else []
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
            return text, "text/markdown"
        if len(parts) == 3 and parts[0] == "health" and parts[2] == "picture":
            s = self._source(parts[1])
            self._require("read_health_picture", [s])
            text = content.read_health_picture(s)
            if text is None:
                raise Refusal(NOT_FOUND, "not found")
            self._audit("read_health_picture", [s])
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

    def _call_tool(self, name: str, args: dict) -> dict:
        if name not in self._tool_names():
            raise Refusal(NOT_FOUND, "not found")
        if name == "search":
            wanted = args.get("source")
            sources = [self._source(str(wanted))] if wanted else self.sources
            self._require("search", sources)
            hits = content.search(sources, str(args.get("query") or ""))
            self._audit("search", sources)
            return _text(json.dumps(hits, indent=2, ensure_ascii=False))
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
        "description": "Search this connection's conversation notes and health picture. Returns refs to read.",
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
}


TOOL_OPERATIONS = {
    "search": ("search",),
    "read": ("read_note", "read_health_picture", "list_notes", "brief", "capabilities"),
}


def _res(uri: str, name: str, mime: str, description: str) -> dict:
    return {"uri": uri, "name": name, "mimeType": mime, "description": description}


def _text(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}
