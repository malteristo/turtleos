"""MCP access point — the §7 guards of docs/design/mcp-access-point.md.

Each guard has a positive control: the same probe on the allowed side must
succeed, so a guard that can never fire does not pass.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import plistlib
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from mcp_access import operations  # noqa: E402
from mcp_access.audit import AUDIT_REL  # noqa: E402
from mcp_access.grants import GrantStore  # noqa: E402
from mcp_access.protocol import FORBIDDEN, NOT_FOUND, Session  # noqa: E402
from mcp_access.registry import owned_sources, resolve_sources  # noqa: E402
from mcp_access.server import NotLoopback, assert_loopback, build_app  # noqa: E402

OWN = "CANARY-OWN-7f3a"
OTHER = "CANARY-OTHER-91bc"
HEALTH = "CANARY-HEALTH-22de"


def _note(title: str, body: str) -> str:
    return f"---\ntimestamp: 2026-09-20T10:00:00+02:00\ntitle: {title}\n---\n\n{body}\n"


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.state = base / "state"
        roots = {k: base / k for k in ("alice", "alice_health", "bob", "bob_health", "family")}
        for r in roots.values():
            (r / "story" / "eddies").mkdir(parents=True)
        (roots["alice"] / "story/eddies/walk.md").write_text(_note("walk", f"we talked {OWN}"))
        (roots["bob"] / "story/eddies/secret.md").write_text(_note("secret", f"his {OTHER}"))
        (roots["alice_health"] / "health_model.md").write_text(f"picture {HEALTH}")
        (roots["bob_health"] / "health_model.md").write_text(f"picture {OTHER}")
        (roots["family"] / "story/eddies/shared.md").write_text(_note("shared", f"all {OTHER}"))
        self.roots = roots
        self.registry = {
            "mages": {
                "alice": {"practice_dir": str(roots["alice"])},
                "bob": {"practice_dir": str(roots["bob"])},
            },
            "spaces": {
                "health": {"subject": "alice", "practice_dir": str(roots["alice_health"])},
                "health-bob": {"subject": "bob", "practice_dir": str(roots["bob_health"])},
                "family": {"members": ["alice", "bob"], "practice_dir": str(roots["family"])},
            },
        }
        self.store = GrantStore(self.state)

    def grant(self, owner="alice", profile="reader", sources=None):
        ids = sources if sources is not None else [s.id for s in owned_sources(owner, self.registry)]
        return self.store.create(principal="laptop", owner=owner, sources=ids, profile=profile)

    def session(self, grant):
        return Session(grant, resolve_sources(grant.owner, grant.sources, self.registry), self.store)

    def close(self):
        self.tmp.cleanup()


def call(session, method, params=None, mid=1):
    return session.handle({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})


def read(session, uri):
    return call(session, "resources/read", {"uri": uri})


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.close()

    def test_member_owns_own_root_and_subject_spaces_not_shared_rooms(self):
        ids = {s.id for s in owned_sources("alice", self.f.registry)}
        self.assertEqual(ids, {"alice", "health"})

    def test_source_dropped_when_ownership_ends(self):
        g, _ = self.f.grant()
        self.f.registry["spaces"]["health"]["subject"] = "bob"
        self.assertEqual([s.id for s in resolve_sources("alice", g.sources, self.f.registry)], ["alice"])


class ScopeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        g, _ = self.f.grant()
        self.s = self.f.session(g)

    def tearDown(self):
        self.f.close()

    def test_positive_control_own_canaries_are_reachable(self):
        hits = json.loads(call(self.s, "tools/call", {"name": "search", "arguments": {"query": OWN}})["result"]["content"][0]["text"])
        self.assertTrue(hits)
        text = read(self.s, "turtleos://health/health/picture")["result"]["contents"][0]["text"]
        self.assertIn(HEALTH, text)

    def test_planted_foreign_canary_is_unreachable_by_search(self):
        hits = call(self.s, "tools/call", {"name": "search", "arguments": {"query": OTHER}})
        self.assertEqual(json.loads(hits["result"]["content"][0]["text"]), [])

    def test_out_of_scope_answers_exactly_like_nonexistent(self):
        for uri in ("turtleos://room/bob/notes", "turtleos://room/family/notes", "turtleos://health/health-bob/picture"):
            foreign = read(self.s, uri)["error"]
            missing = read(self.s, uri.replace("bob", "nosuch").replace("family", "nosuch"))["error"]
            self.assertEqual(foreign, missing, uri)
            self.assertEqual(foreign["code"], NOT_FOUND)

    def test_note_id_cannot_escape_the_notes_folder(self):
        for nid in ("../../../bob/story/eddies/secret", "..%2Fsecret", ".hidden", ""):
            self.assertIn("error", read(self.s, f"turtleos://room/alice/note/{nid}"), nid)
        self.assertIn(OWN, read(self.s, "turtleos://room/alice/note/walk")["result"]["contents"][0]["text"])

    def test_content_reader_confines_below_the_router(self):
        from mcp_access import content

        alice = next(s for s in self.s.sources if s.id == "alice")
        self.assertIsNone(content.read_note(alice, "../../../bob/story/eddies/secret"))
        self.assertIn(OWN, content.read_note(alice, "walk"))

    def test_search_named_foreign_source_is_not_found(self):
        r = call(self.s, "tools/call", {"name": "search", "arguments": {"query": OTHER, "source": "bob"}})
        self.assertEqual(r["error"]["code"], NOT_FOUND)


class OperatorHasNoContentPathTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.close()

    def test_operator_profile_has_no_content_operations(self):
        ops = operations.snapshot_for("operator-health")
        self.assertFalse([o for o in ops if operations.OPERATIONS[o].content])
        self.assertTrue([o for o in operations.snapshot_for("reader") if operations.OPERATIONS[o].content])

    def test_no_profile_named_full(self):
        self.assertNotIn("full", operations.PROFILES)

    def test_operator_grant_reads_nothing(self):
        g, _ = self.f.grant(owner="alice", profile="operator-health", sources=[])
        s = self.f.session(g)
        self.assertEqual(read(s, "turtleos://brief")["error"]["code"], FORBIDDEN)
        self.assertEqual(read(s, "turtleos://room/alice/notes")["error"]["code"], NOT_FOUND)
        self.assertNotIn("search", [t["name"] for t in call(s, "tools/list")["result"]["tools"]])

    def test_grant_tool_refuses_sources_on_operator_profile(self):
        import mcp_grant

        with self.assertRaises(SystemExit):
            mcp_grant.plan("alice", "operator-health", ["alice"], self.f.registry)
        with self.assertRaises(SystemExit):
            mcp_grant.plan("alice", "reader", ["bob"], self.f.registry)
        self.assertEqual(mcp_grant.plan("alice", "reader", [], self.f.registry), ["alice", "health"])


class SnapshotTests(unittest.TestCase):
    def test_grant_keeps_its_operations_when_the_profile_changes(self):
        f = Fixture()
        try:
            g, _ = f.grant()
            before = list(g.operations)
            original = operations.PROFILES["reader"]
            operations.PROFILES["reader"] = original + ("host_status",)
            try:
                self.assertEqual(f.store.get(g.id).operations, before)
            finally:
                operations.PROFILES["reader"] = original
        finally:
            f.close()


class CredentialStoreTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.close()

    def test_store_keeps_hash_not_token_and_is_private(self):
        g, token = self.f.grant()
        raw = (self.f.state / "grants.json").read_text()
        self.assertNotIn(token, raw)
        self.assertEqual(stat.S_IMODE(os.stat(self.f.state / "grants.json").st_mode), 0o600)
        self.assertEqual(self.f.store.find_by_token(token).id, g.id)
        self.assertIsNone(self.f.store.find_by_token(token + "x"))

    def test_revoke_needs_current_revision(self):
        g, _ = self.f.grant()
        self.assertIsNone(self.f.store.revoke(g.id, if_revision=g.revision + 1))
        self.assertEqual(self.f.store.revoke(g.id, if_revision=g.revision).status, "revoked")

    def test_preview_creates_nothing_and_credential_file_is_0600(self):
        import mcp_grant

        env = {"MAGE_REGISTRY": str(Path(self.f.tmp.name) / "reg.yaml"), "TURTLE_MCP_STATE": str(self.f.state)}
        Path(env["MAGE_REGISTRY"]).write_text(json.dumps(self.f.registry))
        out = Path(self.f.tmp.name) / "creds.json"
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                mcp_grant.main(["create", "--owner", "alice", "--principal", "laptop"])
                self.assertEqual(GrantStore(self.f.state).all(), [])
                with self.assertRaises(SystemExit):
                    mcp_grant.main(["create", "--owner", "alice", "--principal", "laptop", "--yes"])
                mcp_grant.main(["create", "--owner", "alice", "--principal", "laptop", "--yes", "--credentials-out", str(out)])
        finally:
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.assertEqual(len(GrantStore(self.f.state).all()), 1)
        self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o600)
        token = json.loads(out.read_text())["mcpServers"]["turtleos"]["headers"]["Authorization"][7:]
        self.assertIsNotNone(GrantStore(self.f.state).find_by_token(token))
        self.assertNotIn(token, printed.getvalue())


class BriefAndAuditTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        g, _ = self.f.grant()
        self.g = g

    def tearDown(self):
        self.f.close()

    def test_brief_names_a_missing_source(self):
        s = self.f.session(self.g)
        self.assertNotIn("unavailable", read(s, "turtleos://brief")["result"]["contents"][0]["text"])
        for p in sorted(self.f.roots["alice_health"].rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        self.f.roots["alice_health"].rmdir()
        text = read(self.f.session(self.f.store.get(self.g.id)), "turtleos://brief")["result"]["contents"][0]["text"]
        self.assertIn("unavailable", text)
        self.assertFalse(self.f.roots["alice_health"].exists(), "audit must not recreate a missing root")

    def test_brief_reports_refusals_then_resets(self):
        self.f.store.count(self.g.id, refused=True)
        s = self.f.session(self.f.store.get(self.g.id))
        self.assertIn("refused calls since the last brief: 1", read(s, "turtleos://brief")["result"]["contents"][0]["text"])
        s = self.f.session(self.f.store.get(self.g.id))
        self.assertIn("refused calls since the last brief: 0", read(s, "turtleos://brief")["result"]["contents"][0]["text"])

    def test_audit_lands_in_source_root_and_host_holds_no_content(self):
        s = self.f.session(self.g)
        read(s, "turtleos://room/alice/note/walk")
        lines = (self.f.roots["alice"] / AUDIT_REL).read_text().splitlines()
        self.assertEqual(json.loads(lines[-1])["operation"], "read_note")
        self.assertFalse((self.f.roots["alice_health"] / AUDIT_REL).exists())
        for p in self.f.state.rglob("*"):
            if p.is_file():
                self.assertNotIn(OWN, p.read_text(errors="ignore"), p)


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.f = Fixture()
        self.g, self.token = self.f.grant()
        self.client = TestClient(TestServer(build_app(self.f.store, lambda: self.f.registry)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.f.close()

    def _h(self, login="alice@example.com", addr="203.0.113.7", token=None, **extra):
        h = {"Authorization": f"Bearer {token or self.token}", **extra}
        if login:
            h["Tailscale-User-Login"] = login
        if addr:
            h["X-Forwarded-For"] = addr
        return h

    async def _post(self, headers, body=None):
        body = body or {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        return await self.client.post("/mcp", json=body, headers=headers)

    async def test_first_identity_binds_and_another_is_refused(self):
        self.assertEqual((await self._post(self._h())).status, 200)
        self.assertEqual((await self._post(self._h())).status, 200)
        self.assertEqual((await self._post(self._h(login="mallory@example.com"))).status, 403)
        self.assertEqual((await self._post(self._h(addr="203.0.113.9"))).status, 403)
        self.assertEqual(self.f.store.get(self.g.id).refused, 2)

    async def test_missing_tailnet_identity_is_refused(self):
        self.assertEqual((await self._post(self._h(login=None))).status, 403)
        self.assertIsNone(self.f.store.get(self.g.id).bound_login)

    async def test_bad_revoked_expired_credentials_are_401(self):
        self.assertEqual((await self._post(self._h(token="tos_wrong"))).status, 401)
        self.f.store.update(self.g.id, expires="2000-01-01T00:00:00+00:00")
        self.assertEqual((await self._post(self._h())).status, 401)
        self.f.store.update(self.g.id, expires="2999-01-01T00:00:00+00:00")
        self.assertEqual((await self._post(self._h())).status, 200)
        self.f.store.revoke(self.g.id, if_revision=self.g.revision)
        self.assertEqual((await self._post(self._h())).status, 401)

    async def test_browser_origin_is_refused(self):
        self.assertEqual((await self._post(self._h(Origin="https://evil.example"))).status, 403)

    async def test_initialize_and_notification(self):
        r = await self._post(self._h(), {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        body = await r.json()
        self.assertEqual(body["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("tools", body["result"]["capabilities"])
        r = await self._post(self._h(), {"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(r.status, 202)

    async def test_get_is_not_a_stream(self):
        self.assertEqual((await self.client.get("/mcp")).status, 405)


class SelfDescriptionTests(unittest.TestCase):
    """No skill file: the connection alone must tell an agent how to use it."""

    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.close()

    def _surface(self, profile="reader", sources=None):
        g, _ = self.f.grant(profile=profile, sources=sources)
        s = self.f.session(g)
        init = call(s, "initialize", {"protocolVersion": "2025-06-18"})["result"]
        tools = call(s, "tools/list")["result"]["tools"]
        resources = call(s, "resources/list")["result"]["resources"]
        templates = call(s, "resources/templates/list")["result"]["resourceTemplates"]
        return init["instructions"], tools, resources + templates

    def test_every_offered_tool_is_explained_and_everything_described(self):
        text, tools, resources = self._surface()
        self.assertTrue(tools and resources)
        for t in tools:
            self.assertIn(f"`{t['name']}(", text)
            self.assertTrue(t.get("description") and t.get("inputSchema"))
        for r in resources:
            self.assertTrue(r.get("description"), r)
        self.assertIn("turtleos://brief", text)
        for sid in ("alice", "health"):
            self.assertIn(sid, text)

    def test_read_only_tools_say_so_and_the_hint_follows_the_operations(self):
        _, tools, _ = self._surface()
        for t in tools:
            self.assertTrue(t["annotations"]["readOnlyHint"], t["name"])
        original = operations.OPERATIONS["search"]
        operations.OPERATIONS["search"] = operations.Operation("search", content=True, write=True)
        try:
            _, tools, _ = self._surface()
        finally:
            operations.OPERATIONS["search"] = original
        self.assertFalse(next(t for t in tools if t["name"] == "search")["annotations"]["readOnlyHint"])

    def test_instructions_do_not_offer_what_the_grant_lacks(self):
        text, tools, _ = self._surface(profile="operator-health", sources=[])
        self.assertEqual(tools, [])
        self.assertNotIn("search(", text)
        self.assertNotIn("turtleos://brief", text)
        self.assertIn("no personal context", text)

    def test_cannot_write_claim_follows_the_grant(self):
        text, _, _ = self._surface()
        self.assertIn("cannot write", text)
        original = operations.OPERATIONS["search"]
        operations.OPERATIONS["search"] = operations.Operation("search", content=True, write=True)
        try:
            text, _, _ = self._surface()
        finally:
            operations.OPERATIONS["search"] = original
        self.assertNotIn("cannot write", text)


class ListenerAndPublishTests(unittest.TestCase):
    def test_only_loopback_binds(self):
        for host in ("0.0.0.0", "::", "203.0.113.1", "10.0.0.5"):
            with self.assertRaises(NotLoopback):
                assert_loopback(host)
        assert_loopback("127.0.0.1")

    def test_deploy_restarts_the_access_point(self):
        text = (REPO / "restart.sh").read_text()
        self.assertIn("kickstart_label com.turtle.mcp", text)
        plist = plistlib.loads((REPO / "docs/install/com.turtle.mcp.plist.example").read_bytes())
        self.assertEqual(plist["Label"], "com.turtle.mcp")

    def test_service_template_binds_loopback(self):
        plist = plistlib.loads((REPO / "docs/install/com.turtle.mcp.plist.example").read_bytes())
        args = plist["ProgramArguments"]
        assert_loopback(args[args.index("--host") + 1])

    def test_expose_fails_closed(self):
        import mcp_expose

        host, backend = "node.tail.ts.net", "http://127.0.0.1:3141"
        key = f"{host}:8443"

        def failed(serve, port=8443, healthy=True):
            return {c.name for c in mcp_expose.evaluate(serve, host, port, backend, healthy) if not c.ok}

        self.assertEqual(failed({}), set())
        self.assertEqual(failed({"Web": {key: {"Handlers": {"/": {"Proxy": backend}}}}}), set())
        self.assertIn("funnel_off", failed({"AllowFunnel": {key: True}}))
        self.assertIn("port_free_or_ours", failed({"Web": {key: {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8080"}}}}}))
        self.assertIn("not_the_funnel_port", failed({}, port=443))
        self.assertIn("backend_healthy_on_loopback", failed({}, healthy=False))
        ok = {"Web": {key: {"Handlers": {"/": {"Proxy": backend}}}}}
        self.assertTrue(mcp_expose.published(ok, host, 8443, backend))
        self.assertFalse(mcp_expose.published({**ok, "AllowFunnel": {key: True}}, host, 8443, backend))

    def test_expose_fails_by_name_when_serve_status_is_unreadable(self):
        from unittest import mock

        import mcp_expose

        def fake(stdout):
            return mock.Mock(stdout=stdout)

        with mock.patch.object(mcp_expose, "_cli", return_value="tailscale"):
            with mock.patch.object(mcp_expose.subprocess, "run", return_value=fake("not json")):
                with self.assertRaises(SystemExit) as cm:
                    mcp_expose._json("serve", "status")
                self.assertIn("tailscale_serve_readable", str(cm.exception.code))
            with mock.patch.object(mcp_expose.subprocess, "run", return_value=fake('{"TCP": {}}')):
                self.assertEqual(mcp_expose._json("serve", "status"), {"TCP": {}})


class TransportIndependenceTests(unittest.TestCase):
    def test_server_imports_without_discord(self):
        code = "import sys, mcp_server, mcp_access.server, mcp_access.protocol; print('discord' in sys.modules)"
        out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "False")

    def test_positive_control_the_probe_detects_discord(self):
        code = "import sys, discord; print('discord' in sys.modules)"
        out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True)
        if out.returncode != 0:
            self.skipTest("discord not installed in this interpreter")
        self.assertEqual(out.stdout.strip(), "True")


if __name__ == "__main__":
    unittest.main()
