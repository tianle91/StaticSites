"""Exercise root delegation and the generated dependency contract offline."""
import contextlib
import importlib.util
import io
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import run_projects

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("scaffolder", ROOT / "new-project.py")
scaffolder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scaffolder)


class DispatcherTests(unittest.TestCase):
    def test_discovery_continues_and_includes_disabled_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for name in ("z-new", "a-disabled", "m-failed"):
                project = root / name
                project.mkdir()
                (project / "Makefile").write_text("data:\n\t@true\n")
                (project / "pyproject.toml").write_text(
                    scaffolder.FILES["pyproject.toml"].replace("__PROJECT__", name)
                    .replace("timeout_minutes = 30", "timeout_minutes = 1" if name == "a-disabled" else "timeout_minutes = 30"))
            (root / "Makefile").touch()
            (root / "not-project").mkdir()
            with mock.patch.object(run_projects, "run_command", side_effect=[0, 2, 0]) as command:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(run_projects.run("data", root), 1)
            self.assertEqual([pathlib.Path(call.args[0][2]).name for call in command.call_args_list],
                             ["a-disabled", "m-failed", "z-new"])
            self.assertEqual([call.args[2] for call in command.call_args_list], [60, 1800, 1800])
            self.assertIn("m-failed: FAILED (2)", output.getvalue())
            self.assertIn("z-new: OK", output.getvalue())

    def test_timeout_continues_and_deps_needs_no_refresh_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for name in ("a", "b"):
                (root / name).mkdir()
                (root / name / "Makefile").touch()
            with mock.patch.object(run_projects, "run_command", side_effect=[
                    subprocess.TimeoutExpired("make", 1800), 0]) as command:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(run_projects.run("deps", root), 1)
                self.assertEqual(command.call_count, 2)

    def test_timeout_terminates_the_process_group(self):
        with mock.patch.object(run_projects.subprocess, "Popen") as popen:
            process = popen.return_value
            process.pid = 123
            process.wait.side_effect = [subprocess.TimeoutExpired("make", 1), 0]
            with mock.patch.object(run_projects.os, "killpg") as kill:
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_projects.run_command(["make", "data"], ROOT, 1)
                kill.assert_called_once_with(123, run_projects.signal.SIGKILL)
                self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_actual_scaffolder_is_automatically_discovered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            # Seed out-of-process so generated fetch_data cannot pollute imports.
            script = root / "new-project.py"
            shutil.copy(ROOT / "new-project.py", script)
            subprocess.run([os.sys.executable, str(script), "fresh-site"], check=True,
                           stdout=subprocess.DEVNULL)
            project = root / "fresh-site"
            self.assertTrue((project / "uv.lock").exists())
            with mock.patch.object(run_projects, "run_command", return_value=0) as command:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(run_projects.run("data", root), 0)
                self.assertEqual(command.call_args.args[0][2], str(project.resolve()))


class DependencyContractTests(unittest.TestCase):
    def test_repair_repeat_failure_and_missing_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "Makefile").write_text(scaffolder.FILES["Makefile"])
            (root / "pyproject.toml").touch()
            (root / "uv.lock").touch()
            tools = root / "tools"
            tools.mkdir()
            uv = tools / "uv"
            uv.write_text('#!/bin/sh\necho "$*" >> calls\n'
                          'test -z "$FAIL_SYNC" || exit 1\n'
                          'mkdir -p .venv/bin\n'
                          'printf "#!/bin/sh\\nexit 0\\n" > .venv/bin/python\n'
                          'chmod +x .venv/bin/python\n')
            uv.chmod(0o755)
            environment = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"])

            def make(target, **extra):
                return subprocess.run(["make", target], cwd=root,
                                      env=dict(environment, **extra), capture_output=True)

            self.assertEqual(make("deps").returncode, 0)
            self.assertEqual(make("deps").returncode, 0)
            stamp = root / ".venv/.stamp"
            before = stamp.stat().st_mtime_ns
            self.assertNotEqual(make("deps", FAIL_SYNC="stale lock").returncode, 0)
            self.assertEqual(stamp.stat().st_mtime_ns, before)
            self.assertEqual(make("test").returncode, 0)
            self.assertEqual(len((root / "calls").read_text().splitlines()), 3)
            (root / ".venv/bin/python").unlink()
            self.assertEqual(make("test").returncode, 0)
            self.assertEqual(len((root / "calls").read_text().splitlines()), 4)
            self.assertTrue(all(line == "sync --locked" for line in (root / "calls").read_text().splitlines()))
            (root / "uv.lock").unlink()
            self.assertNotEqual(make("deps").returncode, 0)
            self.assertEqual(len((root / "calls").read_text().splitlines()), 4)
