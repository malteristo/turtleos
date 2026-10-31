"""The workshop as an MCP source — design/magic-channel.md §3 rows 1–2.

Real git, real pushes: a work repo pushes to a bare repo, and the source is
served from the bare repo. Each guard has a positive control, and the two that
matter most (the release follows the pushes; nothing is followed out of the
tree) carry a mutation the same check must catch.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from mcp_access import receipts, workshop  # noqa: E402
from mcp_access.audit import AUDIT_REL  # noqa: E402
from mcp_access.grants import GrantStore  # noqa: E402
from mcp_access.protocol import NOT_FOUND, Session  # noqa: E402
from mcp_access.registry import KIND_WORKSHOP, owned_sources, private_root, resolve_sources  # noqa: E402
from mcp_access.server import build_app  # noqa: E402

SHOP_CANARY = "CANARY-SHOP-5c1e"
ROOM_CANARY = "CANARY-ROOM-0a77"
OUTSIDE_CANARY = "CANARY-OUTSIDE-d4f2"
BOOTSTRAP = "system/bootstrap.md"
BOOT_BODY = "Summon: read the covenant, then AGENTS.md. THE-PRACTICES-OWN-WORDS"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, capture_output=True, text=True, check=True)
    return done.stdout


def _note(title: str, body: str) -> str:
    return f"---\ntimestamp: 2026-09-20T10:00:00+02:00\ntitle: {title}\n---\n\n{body}\n"


class Shop:
    """A work repo, a bare repo it pushes to, a practice root, and a registry that names them."""

    def __init__(self, *, bootstrap: str | None = BOOTSTRAP):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.base = base
        self.work = base / "work"
        self.bare = base / "bare.git"
        self.root = base / "alice"
        self.state = base / "state"
        (self.root / "story" / "eddies").mkdir(parents=True)
        (self.root / "story/eddies/walk.md").write_text(_note("walk", f"we talked {ROOM_CANARY}"))
        (base / "outside.txt").write_text(f"{OUTSIDE_CANARY}\n")
        self.work.mkdir()
        git(self.work, "init", "-q", "-b", "main")
        (self.work / "system").mkdir()
        (self.work / "system/bootstrap.md").write_text(BOOT_BODY + "\n")
        (self.work / "desk/intentions").mkdir(parents=True)
        (self.work / "desk/intentions/bearings.md").write_text(f"# Bearings\n\nToward {SHOP_CANARY}\n")
        (self.work / "README.md").write_text("top\n")
        (self.work / "blob.bin").write_bytes(b"\x00\x01\x02binary")
        os.symlink(base / "outside.txt", self.work / "link.md")
        os.symlink("desk", self.work / "linkdir")
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", "first release")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.bare)], env=GIT_ENV, check=True)
        git(self.work, "remote", "add", "turtle", str(self.bare))
        git(self.work, "push", "-q", "turtle", "main")
        shop = {"repo": str(self.bare)}
        if bootstrap is not None:
            shop["bootstrap"] = bootstrap
        self.registry = {
            "mages": {"alice": {"practice_dir": str(self.root), "admin": True, "discord_id": "111", "workshop": shop}}
        }
        self.store = GrantStore(self.state)

    def push(self, subject: str, path: str = "README.md", text: str | None = None) -> str:
        (self.work / path).write_text(text if text is not None else subject + "\n")
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", subject)
        git(self.work, "push", "-q", "turtle", "main")
        return git(self.work, "rev-parse", "HEAD").strip()

    def grant(self, profile="workshop-reader"):
        from mcp_access.registry import owned_sources as owned

        ids = [s.id for s in owned("alice", self.registry) if (s.kind == KIND_WORKSHOP) == (profile == "workshop-reader")]
        return self.store.create(principal="laptop", owner="alice", sources=ids, profile=profile)[0]

    def session(self, grant):
        grant = self.store.get(grant.id)  # a fresh read, as the server does on every request
        return Session(
            grant,
            resolve_sources(grant.owner, grant.sources, self.registry),
            self.store,
            owner_root=private_root(grant.owner, self.registry),
            locale="en",
        )

    def source(self):
        return next(s for s in owned_sources("alice", self.registry) if s.kind == KIND_WORKSHOP)

    def close(self):
        self.tmp.cleanup()


def call(session, method, params=None, mid=1):
    return session.handle({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})


def read(session, uri):
    return call(session, "resources/read", {"uri": uri})


def text_of(reply) -> str:
    return reply["result"]["contents"][0]["text"]


def tool(session, name, **args):
    return call(session, "tools/call", {"name": name, "arguments": args})


def tool_text(reply) -> str:
    return reply["result"]["content"][0]["text"]


def file_ref(path: str, since: str = "") -> str:
    return f"turtleos://workshop/alice-workshop/file/{path}" + (f"?since={since}" if since else "")


class Base(unittest.TestCase):
    def setUp(self):
        self.shop = Shop()
        self.g = self.shop.grant()

    def tearDown(self):
        self.shop.close()

    def s(self):
        return self.shop.session(self.g)


class OwnershipAndReachTests(Base):
    def test_the_workshop_is_a_source_the_owner_has_when_the_registry_names_it(self):
        src = self.shop.source()
        self.assertEqual((src.id, src.kind), ("alice-workshop", KIND_WORKSHOP))
        self.assertEqual(src.audit_dir, self.shop.root, "audit lines belong in the owner's root, not a bare repo")
        self.assertEqual(src.bootstrap, BOOTSTRAP)
        bare = dict(self.shop.registry)
        bare["mages"] = {"alice": {"practice_dir": str(self.shop.root)}}
        self.assertEqual([s.kind for s in owned_sources("alice", bare)], ["private"])

    def test_positive_control_the_workshop_profile_reads_the_workshop(self):
        reply = read(self.s(), file_ref("desk/intentions/bearings.md"))
        self.assertIn(SHOP_CANARY, text_of(reply))

    def test_a_reader_grant_never_reaches_the_workshop(self):
        # a reader grant made with the workshop named explicitly, as a hand-edited store might hold it
        g = self.shop.store.create(
            principal="laptop", owner="alice", sources=["alice-workshop", "alice"], profile="reader"
        )[0]
        s = self.shop.session(g)
        self.assertEqual([x.id for x in s.sources], ["alice"], "the session drops a source its operations cannot use")
        self.assertIn("error", read(s, file_ref("desk/intentions/bearings.md")))
        hits = json.loads(tool_text(tool(s, "search", query=SHOP_CANARY)))
        self.assertEqual(hits, [])
        named = tool(s, "search", query=SHOP_CANARY, source="alice-workshop")
        self.assertEqual(named["error"]["code"], NOT_FOUND)

    def test_a_grant_made_before_workshops_existed_does_not_widen_when_the_profile_does(self):
        from mcp_access import operations

        old = self.shop.store.create(
            principal="laptop", owner="alice", sources=["alice-workshop"], profile="reader"
        )[0]
        original = operations.PROFILES["reader"]
        operations.PROFILES["reader"] = original + ("workshop_read", "workshop_search")
        try:
            new = self.shop.store.create(
                principal="laptop", owner="alice", sources=["alice-workshop"], profile="reader"
            )[0]
        finally:
            operations.PROFILES["reader"] = original
        self.assertNotIn("workshop_read", self.shop.store.get(old.id).operations)
        self.assertIn("error", read(self.shop.session(old), file_ref("README.md")))
        self.assertIn("top", text_of(read(self.shop.session(new), file_ref("README.md"))), "positive control")

    def test_the_workshop_grant_reaches_no_rooms(self):
        g = self.shop.store.create(
            principal="laptop", owner="alice", sources=["alice-workshop", "alice"], profile="workshop-reader"
        )[0]
        s = self.shop.session(g)
        self.assertEqual([x.id for x in s.sources], ["alice-workshop"])
        self.assertEqual(read(s, "turtleos://room/alice/notes")["error"]["code"], NOT_FOUND)
        brief = text_of(read(s, "turtleos://brief"))
        self.assertNotIn("walk", brief)
        hits = json.loads(tool_text(tool(s, "search", query=ROOM_CANARY)))
        self.assertEqual(hits, [])
        self.assertTrue(json.loads(tool_text(tool(s, "search", query=SHOP_CANARY))), "positive control")

    def test_room_routes_do_not_open_a_workshop_source(self):
        s = self.s()
        for uri in ("turtleos://room/alice-workshop/notes", "turtleos://room/alice-workshop/note/README",
                    "turtleos://documents/alice-workshop", "turtleos://health/alice-workshop/picture"):
            self.assertEqual(read(s, uri)["error"]["code"], NOT_FOUND, uri)


class BootstrapTests(Base):
    def test_an_empty_folder_gets_the_practices_own_words_and_the_release(self):
        text = text_of(read(self.s(), "turtleos://workshop/alice-workshop/bootstrap"))
        self.assertIn("THE-PRACTICES-OWN-WORDS", text)
        head = git(self.shop.work, "rev-parse", "HEAD").strip()
        self.assertIn(head[:7], text.splitlines()[0])
        self.assertIn("no local clone", text)
        self.assertIn("Read-only", text)

    def test_unreadable_git_output_is_unavailable_not_a_crash(self):
        real = workshop._git
        workshop._git = lambda *a, **k: "not\x00enough"
        try:
            self.assertIsNone(workshop.head(self.shop.source()))
        finally:
            workshop._git = real
        self.assertIsNotNone(workshop.head(self.shop.source()), "positive control")

    def test_a_declared_bootstrap_that_is_missing_is_said_not_papered_over(self):
        self.shop.close()
        self.shop = Shop(bootstrap="system/nope.md")
        g = self.shop.grant()
        text = text_of(read(self.shop.session(g), "turtleos://workshop/alice-workshop/bootstrap"))
        self.assertIn("does not exist at this release", text)
        self.assertNotIn("THE-PRACTICES-OWN-WORDS", text)
        brief = text_of(read(self.shop.session(g), "turtleos://brief"))
        self.assertIn("bootstrap cannot be served", brief)

    def test_an_undeclared_bootstrap_is_said(self):
        self.shop.close()
        self.shop = Shop(bootstrap=None)
        g = self.shop.grant()
        text = text_of(read(self.shop.session(g), "turtleos://workshop/alice-workshop/bootstrap"))
        self.assertIn("declares no bootstrap file", text)

    def test_the_server_names_no_practice_file(self):
        """The bootstrap's preface is the server's; every practice path it mentions comes from the registry."""
        src = (REPO / "mcp_access" / "workshop.py").read_text()
        for word in ("AGENTS.md", "covenant", "bearings", "cast_summon", "desk/", "floor/"):
            self.assertNotIn(word, src.replace("`desk/`", ""), word)


class ReleaseStampTests(Base):
    def test_every_kind_of_workshop_answer_names_its_release(self):
        s = self.s()
        head = git(self.shop.work, "rev-parse", "HEAD").strip()[:7]
        self.assertTrue(text_of(read(s, file_ref("README.md"))).startswith(f"[workshop release {head}"))
        tree = json.loads(text_of(read(s, "turtleos://workshop/alice-workshop/tree")))
        self.assertTrue(tree["release"].startswith(head))
        hits = json.loads(tool_text(tool(s, "search", query=SHOP_CANARY)))
        self.assertEqual({h["release"] for h in hits}, {head})
        self.assertTrue(text_of(read(s, "turtleos://workshop/alice-workshop/bootstrap")).startswith(f"[workshop release {head}"))
        self.assertIn(head, text_of(read(s, "turtleos://brief")))

    def _stamp_follows_pushes(self) -> bool:
        """The row-2 check: plant a commit, read, compare the stamp; push another, read again."""
        first = self.shop.push("second release")
        a = text_of(read(self.s(), file_ref("README.md")))
        second = self.shop.push("third release")
        b = text_of(read(self.s(), file_ref("README.md")))
        return (
            a.startswith(f"[workshop release {first[:7]}")
            and b.startswith(f"[workshop release {second[:7]}")
            and "third release" in b
        )

    def test_the_next_read_after_a_push_is_the_new_release(self):
        self.assertTrue(self._stamp_follows_pushes())

    def test_mutation_a_cached_head_fails_the_same_check(self):
        real = workshop.head
        remembered = {}

        def cached(source):
            return remembered.setdefault(str(source.root), real(source))

        workshop.head = cached
        try:
            self.assertFalse(self._stamp_follows_pushes())
        finally:
            workshop.head = real

    def test_a_session_that_began_earlier_is_told_it_is_behind(self):
        self.assertNotIn("BEHIND", text_of(read(self.s(), file_ref("README.md"))), "nothing has moved yet")
        read(self.s(), "turtleos://workshop/alice-workshop/bootstrap")
        self.assertNotIn("BEHIND", text_of(read(self.s(), file_ref("README.md"))), "positive control: just began")
        self.shop.push("the Forge released again")
        text = text_of(read(self.s(), file_ref("README.md")))
        self.assertIn("BEHIND", text)
        self.assertIn("1 release later", text)
        self.assertIn("the Forge released again", text)
        hit = json.loads(tool_text(tool(self.s(), "search", query=SHOP_CANARY)))[0]
        self.assertEqual(hit["behind"]["count"], 1)

    def test_a_ref_that_carries_its_release_is_exact_without_any_marker(self):
        first = git(self.shop.work, "rev-parse", "HEAD").strip()[:7]
        self.shop.push("moved on")
        for_a_new_client = self.shop.session(self.shop.grant())  # no bootstrap read: no marker
        self.assertNotIn("BEHIND", text_of(read(for_a_new_client, file_ref("README.md"))))
        self.assertIn("BEHIND", text_of(read(for_a_new_client, file_ref("README.md", since=first))))

    def test_rejoining_by_bootstrap_clears_it(self):
        read(self.s(), "turtleos://workshop/alice-workshop/bootstrap")
        self.shop.push("moved on")
        self.assertIn("BEHIND", text_of(read(self.s(), file_ref("README.md"))))
        read(self.s(), "turtleos://workshop/alice-workshop/bootstrap")
        self.assertNotIn("BEHIND", text_of(read(self.s(), file_ref("README.md"))))

    def test_an_unknown_since_is_said_not_ignored(self):
        text = text_of(read(self.s(), file_ref("README.md", since="deadbee")))
        self.assertIn("BEHIND?", text)

    def test_search_and_tree_hand_out_refs_that_carry_the_release(self):
        s = self.s()
        head = git(self.shop.work, "rev-parse", "HEAD").strip()[:7]
        hit = json.loads(tool_text(tool(s, "search", query=SHOP_CANARY)))[0]
        self.assertTrue(hit["ref"].endswith(f"?since={head}"))
        tree = json.loads(text_of(read(s, "turtleos://workshop/alice-workshop/tree")))
        self.assertTrue(all(e["ref"].endswith(f"?since={head}") for e in tree["entries"]))
        self.shop.push("moved on")
        self.assertIn("BEHIND", text_of(read(self.s(), hit["ref"])))


class ConfinementTests(Base):
    def test_positive_control_a_nested_file_and_a_folder_are_readable(self):
        s = self.s()
        self.assertIn("Toward", text_of(read(s, file_ref("desk/intentions/bearings.md"))))
        tree = json.loads(text_of(read(s, "turtleos://workshop/alice-workshop/tree/desk")))
        self.assertEqual([e["path"] for e in tree["entries"]], ["desk/intentions"])
        top = json.loads(text_of(read(s, "turtleos://workshop/alice-workshop/tree")))
        self.assertIn("system", {e["path"] for e in top["entries"]})

    def test_nothing_names_anything_but_a_path_inside_the_tree(self):
        s = self.s()
        for path in ("../outside.txt", "desk/../README.md", "/etc/passwd", "-p", ":x", "desk//intentions",
                     "./README.md", "desk\\intentions", "..", "desk/intentions/../../../outside.txt"):
            self.assertIsNone(workshop.clean_path(path), path)
            self.assertNotIn(OUTSIDE_CANARY, json.dumps(read(s, file_ref(path))), path)
        self.assertEqual(workshop.clean_path("desk/intentions/bearings.md"), "desk/intentions/bearings.md")

    def test_a_symlink_in_the_repository_is_not_followed_out(self):
        s = self.s()
        reply = read(s, file_ref("link.md"))
        self.assertEqual(reply["error"]["code"], NOT_FOUND)
        self.assertNotIn(OUTSIDE_CANARY, json.dumps(reply))
        self.assertEqual(read(s, "turtleos://workshop/alice-workshop/tree/linkdir")["error"]["code"], NOT_FOUND)
        hits = json.dumps(tool_text(tool(s, "search", query=OUTSIDE_CANARY)))
        self.assertNotIn(OUTSIDE_CANARY, hits)

    def test_mutation_following_links_would_leak_the_planted_file(self):
        """The check has teeth: the planted file is really reachable by following the link."""
        target = os.readlink(self.shop.work / "link.md")
        self.assertIn(OUTSIDE_CANARY, Path(target).read_text())
        blob = git(self.shop.work, "cat-file", "-p", "HEAD:link.md")
        self.assertEqual(blob.strip(), target, "the link blob holds the path, which is why it must never be read as a file")

    def test_a_folder_is_not_a_file_and_a_file_is_not_a_folder(self):
        s = self.s()
        self.assertEqual(read(s, file_ref("desk"))["error"]["code"], NOT_FOUND)
        self.assertEqual(read(s, "turtleos://workshop/alice-workshop/tree/README.md")["error"]["code"], NOT_FOUND)

    def test_binary_files_are_not_dumped_and_big_files_are_cut_with_a_notice(self):
        s = self.s()
        self.assertIn("binary file", text_of(read(s, file_ref("blob.bin"))))
        self.shop.push("big", "big.md", ("line of words\n" * 40_000))
        text = text_of(read(self.s(), file_ref("big.md")))
        self.assertIn("truncated: showing", text)
        self.assertLess(len(text), workshop.MAX_BYTES + 1000)

    def test_another_source_id_is_not_found_exactly_like_a_missing_file(self):
        s = self.s()
        a = read(s, "turtleos://workshop/bob-workshop/file/README.md")
        b = read(s, file_ref("nope.md"))
        self.assertEqual(a["error"], b["error"])


class ReadOnlyTests(Base):
    def test_only_read_verbs_can_be_issued(self):
        src = self.shop.source()
        for verb in ("push", "commit", "update-ref", "fetch", "gc", "config", "checkout"):
            with self.assertRaises(ValueError):
                workshop._run(src, verb)
        self.assertIsNotNone(workshop._run(src, "rev-parse", "HEAD"), "positive control: a read verb runs")

    def test_every_git_call_in_the_module_uses_a_listed_verb(self):
        code = (REPO / "mcp_access" / "workshop.py").read_text()
        verbs = set(re.findall(r'_(?:git|run)\(source, "([a-z-]+)"', code))
        self.assertTrue(verbs, "the probe must find calls (positive control)")
        self.assertTrue(verbs <= workshop.GIT_VERBS, verbs - workshop.GIT_VERBS)

    def _refs(self) -> str:
        return git(self.shop.bare, "for-each-ref") + git(self.shop.bare, "count-objects", "-v")

    def test_reading_everything_changes_nothing_in_the_repository(self):
        before = self._refs()
        s = self.s()
        read(s, "turtleos://workshop/alice-workshop/bootstrap")
        read(s, "turtleos://workshop/alice-workshop/tree")
        read(s, file_ref("README.md"))
        tool(s, "search", query="top")
        self.assertEqual(before, self._refs())
        self.shop.push("a real change")
        self.assertNotEqual(before, self._refs(), "positive control: the probe can see a change")

    def test_the_connection_says_it_cannot_write(self):
        init = call(self.s(), "initialize", {"protocolVersion": "2025-06-18"})["result"]
        self.assertIn("cannot write", init["instructions"])
        for t in call(self.s(), "tools/list")["result"]["tools"]:
            self.assertTrue(t["annotations"]["readOnlyHint"], t["name"])


class SearchTests(Base):
    def test_first_matching_line_of_each_file_with_a_readable_ref(self):
        s = self.s()
        hits = json.loads(tool_text(tool(s, "search", query=SHOP_CANARY.lower())))
        self.assertEqual([h["title"] for h in hits], ["desk/intentions/bearings.md"])
        self.assertIn("line 3", hits[0]["snippet"])
        self.assertIn(SHOP_CANARY, text_of(read(s, hits[0]["ref"])), "positive control: the ref opens the file")
        self.assertEqual(json.loads(tool_text(tool(s, "search", query="no-such-words-anywhere"))), [])
        self.assertEqual(json.loads(tool_text(tool(s, "search", query=""))), [])

    def test_a_query_cannot_be_an_option(self):
        s = self.s()
        out = tool_text(tool(s, "search", query="--open-files-in-pager=touch /tmp/x"))
        self.assertEqual(json.loads(out), [])
        self.assertFalse(Path("/tmp/x").exists())


class AuditAndReceiptTests(Base):
    def test_audit_lands_in_the_owners_root_and_never_in_the_bare_repo(self):
        s = self.s()
        read(s, file_ref("README.md"))
        tool(s, "search", query="top")
        ops = [json.loads(line)["operation"] for line in (self.shop.root / AUDIT_REL).read_text().splitlines()]
        self.assertIn("workshop_read", ops)
        self.assertIn("workshop_search", ops)
        self.assertFalse((self.shop.bare / "state").exists())
        for p in self.shop.state.rglob("*"):
            if p.is_file():
                self.assertNotIn(SHOP_CANARY, p.read_text(errors="ignore"), p)

    def test_a_grant_narrowed_to_nothing_sees_no_workshop(self):
        g = self.shop.store.create(principal="laptop", owner="alice", sources=["alice-workshop"], profile="workshop-reader")[0]
        self.shop.store.update(g.id, operations=["capabilities", "brief"])  # as an owner narrowing a grant would
        s = self.shop.session(self.shop.store.get(g.id))
        self.assertEqual(s.sources, [], "no operation, no source")
        self.assertEqual(read(s, file_ref("README.md"))["error"]["code"], NOT_FOUND)
        self.assertIn("top", text_of(read(self.s(), file_ref("README.md"))), "positive control: the full grant still reads")

    def test_a_session_of_many_reads_leaves_one_receipt_naming_the_place_not_the_files(self):
        s = self.s()
        for path in ("README.md", "desk/intentions/bearings.md", BOOTSTRAP):
            read(s, file_ref(path))
        tool(s, "search", query="top")
        rows = receipts._load(self.shop.root / receipts.RECEIPTS_REL)
        self.assertEqual(len(rows), 1)
        text = rows[0]["posts"][0]["text"]
        self.assertIn("workshop", text)
        for leaked in (SHOP_CANARY, "bearings", "README"):
            self.assertNotIn(leaked, text)
        self.assertEqual(rows[0]["posts"][0]["to"], "private")

    def test_a_folder_listing_and_the_brief_stay_quiet(self):
        s = self.s()
        read(s, "turtleos://workshop/alice-workshop/tree")
        read(s, "turtleos://brief")
        self.assertFalse((self.shop.root / receipts.RECEIPTS_REL).exists())
        read(s, file_ref("README.md"))
        self.assertTrue((self.shop.root / receipts.RECEIPTS_REL).exists(), "positive control: a file read does queue one")


class HonestBriefTests(Base):
    def test_the_brief_names_the_release_and_the_bootstrap(self):
        text = text_of(read(self.s(), "turtleos://brief"))
        self.assertIn("workshop (the practice repository)", text)
        self.assertIn("turtleos://workshop/alice-workshop/bootstrap", text)
        self.assertNotIn("unavailable", text)

    def test_a_missing_repository_is_unavailable_and_nothing_is_recreated(self):
        import shutil

        shutil.rmtree(self.shop.bare)
        s = self.s()
        self.assertIn("unavailable", text_of(read(s, "turtleos://brief")))
        self.assertIn("error", read(s, file_ref("README.md")))
        self.assertFalse(self.shop.bare.exists(), "a read must not recreate the repository")
        self.assertEqual(json.loads(tool_text(tool(s, "search", query="top"))), [])


class SelfDescriptionTests(Base):
    def test_the_connection_explains_itself_and_offers_only_what_it_can_do(self):
        s = self.s()
        init = call(s, "initialize", {"protocolVersion": "2025-06-18"})["result"]
        text = init["instructions"]
        self.assertIn("alice-workshop (workshop)", text)
        self.assertIn("turtleos://workshop/alice-workshop/bootstrap", text)
        self.assertNotIn("health-picture", text)
        self.assertNotIn("conversation notes", text, "a workshop-only grant is not told it holds conversations")
        self.assertEqual(text.count("Start with") + text.count("Begin with"), 1, "one place to begin")
        # 2026-10-12: the first empty-folder `summon.` was not understood because nothing tied the word to
        # the bootstrap, and the agent used the rooms connection instead. The word must lead to the bootstrap.
        self.assertRegex(text, r"(?i)summon.*bootstrap", "a typed 'summon' must lead to the bootstrap")
        tools = call(s, "tools/list")["result"]["tools"]
        self.assertEqual({t["name"] for t in tools}, {"search", "read"})
        for t in tools:
            self.assertIn(f"`{t['name']}(", text)
            self.assertTrue(t["description"] and t["inputSchema"])
            self.assertNotIn("health", t["description"].lower())
            self.assertNotIn("conversation", t["description"].lower())
        listed = call(s, "resources/list")["result"]["resources"]
        templates = call(s, "resources/templates/list")["result"]["resourceTemplates"]
        for r in listed + templates:
            self.assertTrue(r.get("description"), r)
        uris = {r["uri"] for r in listed}
        self.assertIn("turtleos://workshop/alice-workshop/bootstrap", uris)
        self.assertFalse([u for u in uris if "/room/" in u or "/health/" in u or "/documents/" in u])
        self.assertTrue(any("workshop/{source}/file/{path}" in t["uriTemplate"] for t in templates))

    def test_a_room_reader_is_not_told_about_workshops(self):
        g = self.shop.store.create(principal="laptop", owner="alice", sources=["alice"], profile="reader")[0]
        s = self.shop.session(g)
        init = call(s, "initialize", {"protocolVersion": "2025-06-18"})["result"]
        self.assertNotIn("workshop", init["instructions"])
        self.assertNotIn("summon", init["instructions"].lower(), "only the workshop connection answers a summoning")
        self.assertIn("conversation notes", init["instructions"], "positive control: rooms keep their own intro")
        self.assertNotIn("workshop", json.dumps(call(s, "resources/templates/list")["result"]))


class GrantPlanTests(Base):
    def test_the_workshop_profile_plans_the_workshop_and_the_reader_plans_rooms(self):
        import mcp_grant

        self.assertEqual(mcp_grant.plan("alice", "workshop-reader", [], self.shop.registry), ["alice-workshop"])
        self.assertEqual(mcp_grant.plan("alice", "reader", [], self.shop.registry), ["alice"])

    def test_naming_the_wrong_family_is_refused_with_the_reason(self):
        import mcp_grant

        with self.assertRaises(SystemExit) as c:
            mcp_grant.plan("alice", "reader", ["alice-workshop"], self.shop.registry)
        self.assertIn("cannot reach", str(c.exception))
        with self.assertRaises(SystemExit):
            mcp_grant.plan("alice", "workshop-reader", ["alice"], self.shop.registry)

    def test_a_member_with_no_workshop_cannot_be_planned_one(self):
        import mcp_grant

        reg = {"mages": {"alice": {"practice_dir": str(self.shop.root), "admin": True}}}
        with self.assertRaises(SystemExit):
            mcp_grant.plan("alice", "workshop-reader", [], reg)

    def test_the_offer_says_what_the_grant_reaches(self):
        from mcp_access import offers

        offer = offers.create(
            self.shop.root, owner="alice", principal="laptop", sources=["alice-workshop"],
            profile="workshop-reader", url="https://h:8443/mcp",
        )
        self.assertIn("practice repository", " ".join(offers.describe(offer)))


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.shop = Shop()
        self.g, self.token = self.shop.store.create(
            principal="laptop", owner="alice", sources=["alice-workshop"], profile="workshop-reader"
        )
        self.client = TestClient(TestServer(build_app(self.shop.store, lambda: self.shop.registry)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.shop.close()

    async def test_the_workshop_connection_does_not_overwrite_the_rooms_connection(self):
        from mcp_access import offers

        self.shop.registry["mages"]["alice"]["tailscale_login"] = "alice@example.com"
        h = {"Tailscale-User-Login": "alice@example.com", "X-Forwarded-For": "203.0.113.9", "X-Turtleos-Client": "connect-tool"}
        names = {}
        for profile, sources in (("reader", ["alice"]), ("workshop-reader", ["alice-workshop"])):
            offer = offers.create(self.shop.root, owner="alice", principal="laptop", sources=sources,
                                  profile=profile, url="https://host:8443/mcp")
            offers.mark_ready(self.shop.root, offer.id)  # the owner's press in their river
            r = await self.client.post("/connect", headers=h)
            names[profile] = (r.status, (await r.json()).get("name") if r.status == 200 else None)
        self.assertEqual(names["reader"][1], "turtleos")
        self.assertEqual(names["workshop-reader"][1], "turtleos-workshop")

    async def test_an_empty_client_summons_over_the_wire(self):
        h = {
            "Authorization": f"Bearer {self.token}",
            "Tailscale-User-Login": "alice@example.com",
            "X-Forwarded-For": "203.0.113.7",
        }
        body = {"jsonrpc": "2.0", "id": 1, "method": "resources/read",
                "params": {"uri": "turtleos://workshop/alice-workshop/bootstrap"}}
        r = await self.client.post("/mcp", json=body, headers=h)
        self.assertEqual(r.status, 200)
        text = (await r.json())["result"]["contents"][0]["text"]
        self.assertIn("THE-PRACTICES-OWN-WORDS", text)
        self.assertTrue(text.startswith("[workshop release "))
        self.shop.push("while the client works")
        body["params"]["uri"] = file_ref("README.md")
        r = await self.client.post("/mcp", json=body, headers=h)
        self.assertIn("BEHIND", (await r.json())["result"]["contents"][0]["text"])


if __name__ == "__main__":
    unittest.main()
