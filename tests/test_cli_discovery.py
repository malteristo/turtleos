"""A CLI tool that exists is not a CLI tool that runs.

Written 2026-08-14 after a rename made four content fetchers silently dead on
the live host. The venv had been built at `/Users/turtle/turtle-shell/venv`; the
directory later became `turtleos`. Every console script in `venv/bin` carries
its interpreter as an absolute path on line one, so `pip`, `yt-dlp`,
`trafilatura`, `twitter` and `rdt` all still existed, all still had the execute
bit, and none of them could exec. `readiness.py` reported *"yt-dlp installed
at ..."* the whole time, because it asked whether the file was there.

The swallow made it quiet: exec of a bad shebang raises, `_run_cli` catches
everything and returns `rc=-1`, and the caller reports a soft per-platform
failure and falls back. A capability disappeared and the failure it produced was
indistinguishable from a site that would not parse.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import content_fetch as cf


class RunnabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _script(self, name: str, shebang: str) -> str:
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"{shebang}\nprint('hi')\n")
        os.chmod(path, 0o755)
        return path

    def test_a_script_whose_interpreter_is_gone_is_not_runnable(self) -> None:
        """The live failure, reproduced exactly."""
        path = self._script("yt-dlp", "#!/Users/turtle/turtle-shell/venv/bin/python3.14")
        self.assertTrue(os.path.exists(path), "the file exists — that was the whole problem")
        self.assertTrue(os.access(path, os.X_OK), "and the execute bit is set, so X_OK cannot help")
        self.assertFalse(cf._runnable(path))

    def test_a_script_whose_interpreter_exists_is_runnable(self) -> None:
        """Negative control — the check must not condemn a working venv."""
        path = self._script("yt-dlp", f"#!{sys.executable}")
        self.assertTrue(cf._runnable(path))

    def test_a_missing_file_is_not_runnable(self) -> None:
        self.assertFalse(cf._runnable(os.path.join(self.tmp, "never-installed")))

    def test_a_binary_without_a_shebang_is_left_alone(self) -> None:
        """Compiled tools carry no interpreter line; do not invent a reason to reject them."""
        path = os.path.join(self.tmp, "compiled")
        with open(path, "wb") as fh:
            fh.write(b"\xcf\xfa\xed\xfe" + b"\x00" * 32)
        os.chmod(path, 0o755)
        self.assertTrue(cf._runnable(path))

    def test_an_empty_file_does_not_raise(self) -> None:
        path = os.path.join(self.tmp, "empty")
        Path(path).touch()
        self.assertTrue(cf._runnable(path))


class FallbackTests(unittest.TestCase):
    """A broken venv copy must degrade to the system tool, not to silence."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        self._real_bin = cf._VENV_BIN
        cf._VENV_BIN = self.bin
        self.addCleanup(lambda: setattr(cf, "_VENV_BIN", self._real_bin))

    def _broken(self, name: str) -> str:
        path = os.path.join(self.bin, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("#!/nonexistent/python3\nprint('hi')\n")
        os.chmod(path, 0o755)
        return path

    def test_a_broken_venv_script_falls_through_to_path(self) -> None:
        self._broken("some-tool")
        system = os.path.join(self.tmp, "system", "some-tool")
        os.makedirs(os.path.dirname(system))
        Path(system).touch()
        os.chmod(system, 0o755)
        original = os.environ.get("PATH", "")
        os.environ["PATH"] = os.path.dirname(system) + os.pathsep + original
        self.addCleanup(lambda: os.environ.__setitem__("PATH", original))
        self.assertEqual(cf._cli_path("some-tool"), system)

    def test_a_working_venv_script_still_wins_over_path(self) -> None:
        path = os.path.join(self.bin, "some-tool")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"#!{sys.executable}\nprint('hi')\n")
        os.chmod(path, 0o755)
        self.assertEqual(cf._cli_path("some-tool"), path)

    def test_nothing_anywhere_returns_none(self) -> None:
        self.assertIsNone(cf._cli_path("tool-that-does-not-exist-anywhere-xyz"))


if __name__ == "__main__":
    unittest.main()
