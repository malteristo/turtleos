"""Tests for Mini ops report formatting (Layer 1)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class OpsReportTests(unittest.TestCase):
    def test_format_ops_markdown_pass(self) -> None:
        from scripts.write_ops_report import format_ops_markdown

        bundle = {
            "meta": {
                "job": "test",
                "generated_at": "2026-06-26T12:00:00+00:00",
                "hostname": "test-host",
            },
            "ops_overall": "pass",
            "shake_report": {"functional_gate": "pass", "artifacts": []},
            "canary": {"overall": "green", "checks": []},
            "updates": {
                "turtleos_summary": "main @ abc12345, divergence=synced",
                "workshop_summary": "no git clone",
            },
            "suite_steps": [],
        }
        md = format_ops_markdown(bundle)
        self.assertIn("Spirit Ops Report", md)
        self.assertIn("PASS", md)
        self.assertIn("Functional gate: **pass**", md)

    def test_write_path_section_reaches_the_report(self) -> None:
        """Name the reader: the ledger must land in the markdown a human opens."""
        from scripts.write_ops_report import format_ops_markdown

        bundle = {
            "meta": {"job": "test", "generated_at": "", "hostname": "h"},
            "ops_overall": "pass",
            "shake_report": {"functional_gate": "pass", "artifacts": []},
            "canary": {"overall": "green", "checks": []},
            "updates": {},
            "suite_steps": [],
            "write_paths": {
                "window_days": 30,
                "section": "## Write-path ratios (last 30d)\n\n| date_keep  ⚠︎ never fired |",
            },
        }
        md = format_ops_markdown(bundle)
        self.assertIn("Write-path ratios", md)
        self.assertIn("never fired", md)

        # And absence stays quiet rather than printing an empty heading.
        bundle["write_paths"] = {}
        self.assertNotIn("Write-path ratios", format_ops_markdown(bundle))

    def test_every_shake_script_runs_in_the_nightly_suite(self) -> None:
        """Name the class: no shake script may exist outside the suite unexempted.

        Six of twelve went unrun for weeks — and they were the recently-shipped
        six, so the features least proven by time were the ones nothing
        re-checked. A per-script assertion would not have caught it; only
        enumerating the directory does.
        """
        from scripts.shake_report import DEFAULT_OFFLINE_SUITE, SUITE_EXEMPT

        on_disk = {
            f"scripts/{p.name}" for p in (REPO / "scripts").glob("shake_*.py")
        }
        self.assertTrue(on_disk, "positive control: found no shake scripts at all")

        in_suite = {entry.split()[0] for entry in DEFAULT_OFFLINE_SUITE}
        unrun = on_disk - in_suite - set(SUITE_EXEMPT)
        self.assertEqual(
            unrun,
            set(),
            f"shake scripts that nothing re-runs: {sorted(unrun)} — "
            "add to DEFAULT_OFFLINE_SUITE or record why in SUITE_EXEMPT",
        )

        missing = in_suite - on_disk
        self.assertEqual(missing, set(), f"suite names scripts that do not exist: {sorted(missing)}")

    def test_every_suite_member_declares_itself_offline_safe(self) -> None:
        """A live tool must not be able to join the nightly gate quietly.

        `shake_spawn_eddy.py` spawns a real eddy in the real river — it is the
        helper `shake_flow.py --live` calls, not a check. It was added to the
        suite on 2026-08-06 and put two blank threads in the operator's river
        before the chronicle gave it away. The declaration makes "does this
        mutate anything a practitioner sees" a question you have to answer.
        """
        from scripts.shake_report import DEFAULT_OFFLINE_SUITE, SUITE_EXEMPT

        undeclared = []
        for entry in DEFAULT_OFFLINE_SUITE:
            rel = entry.split()[0]
            # Read, don't import: importing a shake script runs its module body.
            src = (REPO / rel).read_text(encoding="utf-8")
            if "OFFLINE_SAFE = True" not in src:
                undeclared.append(rel)
        self.assertEqual(
            undeclared,
            [],
            f"suite members with no OFFLINE_SAFE declaration: {undeclared}",
        )

        # And the known live tool stays out, with its reason recorded.
        self.assertIn("scripts/shake_spawn_eddy.py", SUITE_EXEMPT)
        self.assertNotIn(
            "scripts/shake_spawn_eddy.py",
            {e.split()[0] for e in DEFAULT_OFFLINE_SUITE},
        )
        self.assertIn("live", SUITE_EXEMPT["scripts/shake_spawn_eddy.py"].lower())

    def test_ops_runner_suite_is_not_a_second_copy(self) -> None:
        """The nightly must run the list the report publishes, not a twin."""
        from scripts.ops_runner import SUITE_STEPS
        from scripts.shake_report import offline_suite_steps

        self.assertEqual(SUITE_STEPS[0][0], "unittest")
        self.assertEqual(SUITE_STEPS[1:], offline_suite_steps())

    def test_summary_line_names_a_stale_tracking_ref(self) -> None:
        """The one line a human reads must carry the caveat, not just the JSON.

        The nightly report's Summary said `divergence=up_to_date` while the
        Mini sat three commits behind; `tracking_ref_stale: true` was fifteen
        lines lower inside a fenced JSON block nobody reads at 02:15.
        """
        from scripts.ops_runner import _update_summary

        stale = _update_summary(
            {
                "divergence": {"state": "unknown", "ahead": None, "behind": None},
                "current": {"branch": "main", "sha": "abc12345def", "dirty": False},
                "source": {"tracking_ref_stale": True, "remote_head_sha": "999888777"},
            }
        )
        self.assertIn("stale", stale.lower())
        self.assertIn("99988877", stale)
        self.assertNotIn("up_to_date", stale)

        fresh = _update_summary(
            {
                "divergence": {"state": "up_to_date", "ahead": 0, "behind": 0},
                "current": {"branch": "main", "sha": "abc12345def", "dirty": False},
                "source": {"tracking_ref_stale": False, "remote_head_sha": "abc12345def"},
            }
        )
        self.assertIn("up_to_date", fresh)
        self.assertNotIn("stale", fresh.lower())

    def test_format_ops_markdown_includes_diagnosis(self) -> None:
        from scripts.write_ops_report import format_ops_markdown

        bundle = {
            "meta": {"job": "test", "generated_at": "t", "hostname": "h"},
            "ops_overall": "fail",
            "shake_report": {
                "functional_gate": "fail",
                "spirit_failed_artifacts": ["shake-river-latest.json"],
                "artifacts": [],
            },
            "canary": {"overall": "green", "checks": []},
            "updates": {"turtleos_summary": "x", "workshop_summary": "y"},
            "suite_steps": [{"name": "shake_river", "exit_code": 1, "stderr": "boom"}],
            "local_diagnosis": "- River shake failed",
        }
        md = format_ops_markdown(bundle)
        self.assertIn("FAIL", md)
        self.assertIn("Local diagnosis (qwen)", md)
        self.assertIn("River shake failed", md)

    def test_write_ops_artifacts(self) -> None:
        import tempfile

        from scripts.write_ops_report import write_ops_artifacts

        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "automation-reports"
            bundle = {
                "meta": {"job": "unittest", "generated_at": "t", "hostname": "h"},
                "ops_overall": "pass",
                "shake_report": {"functional_gate": "pass"},
                "canary": {"overall": "green"},
                "updates": {},
                "suite_steps": [],
            }
            paths = write_ops_artifacts(bundle, reports_dir=reports)
            self.assertTrue(Path(paths["latest_md"]).is_file())
            self.assertTrue(Path(paths["latest_json"]).is_file())
            latest = Path(paths["latest_md"]).read_text(encoding="utf-8")
            self.assertIn("Spirit Ops Report", latest)


    def test_sync_ops_harvest_commits_and_pushes(self) -> None:
        import subprocess
        import tempfile

        from scripts.ops_harvest_sync import sync_ops_harvest
        from scripts.write_ops_report import write_ops_artifacts

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bare = base / "magic.git"
            repo = base / "workshop"
            reports = repo / "desk" / "craft" / "automation-reports"
            subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
            repo.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "ops@test"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "ops"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True, capture_output=True)
            (repo / "desk" / "craft").mkdir(parents=True)
            (repo / "README.md").write_text("workshop", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True)

            bundle = {
                "meta": {"job": "unittest", "generated_at": "t", "hostname": "h"},
                "ops_overall": "pass",
                "shake_report": {"functional_gate": "pass"},
                "canary": {"overall": "green"},
                "updates": {},
                "suite_steps": [],
            }
            paths = write_ops_artifacts(bundle, reports_dir=reports)
            result = sync_ops_harvest(paths, bundle=bundle)
            self.assertEqual(result["status"], "pushed")
            self.assertIn("desk/craft/automation-reports/latest.md", result["paths"])

            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(status.stdout.strip(), "")

            bare_head = subprocess.run(
                ["git", "rev-parse", "main"],
                cwd=bare,
                capture_output=True,
                text=True,
                check=True,
            )
            repo_head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(bare_head.stdout.strip(), repo_head.stdout.strip())
