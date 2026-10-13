"""Exercise the generated project's dependency contract offline."""
import importlib.util
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("scaffolder", ROOT / "new-project.py")
scaffolder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scaffolder)


class DependencyContractTests(unittest.TestCase):
    def test_data_sync_failure_stops_before_fetch_for_every_project(self):
        makefiles = {path.parent.name: path.read_text()
                     for path in ROOT.glob("*/Makefile")}
        makefiles["scaffold"] = scaffolder.FILES["Makefile"]
        for name, makefile in makefiles.items():
            with self.subTest(project=name), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                (root / "Makefile").write_text(makefile)
                (root / "pyproject.toml").touch()
                (root / "uv.lock").touch()
                tools = root / "tools"
                tools.mkdir()
                uv = tools / "uv"
                uv.write_text('#!/bin/sh\necho sync >> calls\nexit 1\n')
                uv.chmod(0o755)
                # Dependency installation must finish before any fetch runs.
                (root / ".venv/bin").mkdir(parents=True)
                interpreter = root / ".venv/bin/python"
                interpreter.write_text('#!/bin/sh\necho fetch >> calls\n')
                interpreter.chmod(0o755)
                result = subprocess.run(
                    ["make", "data"], cwd=root, capture_output=True,
                    env=dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"]),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((root / "calls").read_text(), "sync\n")

    def test_actual_scaffolder_creates_independent_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            # Seed out-of-process so generated fetch_data cannot pollute imports.
            script = root / "new-project.py"
            shutil.copy(ROOT / "new-project.py", script)
            subprocess.run([os.sys.executable, str(script), "fresh-site"], check=True,
                           stdout=subprocess.DEVNULL)
            project = root / "fresh-site"
            self.assertTrue((project / "uv.lock").exists())
            self.assertTrue((project / "Makefile").exists())
            self.assertTrue((project / "data/example.json").exists())

    def test_install_reuse_failure_and_explicit_cleanup(self):
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
            self.assertEqual(len((root / "calls").read_text().splitlines()), 1)
            stamp = root / ".venv/.stamp"
            # Changed manifests require another sync; failed sync keeps the old stamp.
            os.utime(stamp, (0, 0))
            before = stamp.stat().st_mtime_ns
            self.assertNotEqual(make("deps", FAIL_SYNC="stale lock").returncode, 0)
            self.assertEqual(stamp.stat().st_mtime_ns, before)
            self.assertEqual(make("test").returncode, 0)
            self.assertEqual(len((root / "calls").read_text().splitlines()), 3)
            (root / ".venv/bin/python").unlink()
            self.assertNotEqual(make("deps").returncode, 0)
            self.assertNotEqual(make("test").returncode, 0)
            self.assertEqual(len((root / "calls").read_text().splitlines()), 3)
            self.assertEqual(make("clean-deps").returncode, 0)
            self.assertFalse((root / ".venv").exists())
            self.assertEqual(make("deps").returncode, 0)
            self.assertEqual(len((root / "calls").read_text().splitlines()), 4)
            self.assertTrue(all(line == "sync --locked" for line in (root / "calls").read_text().splitlines()))
            (root / "uv.lock").unlink()
            self.assertNotEqual(make("deps").returncode, 0)
            self.assertEqual(len((root / "calls").read_text().splitlines()), 4)
