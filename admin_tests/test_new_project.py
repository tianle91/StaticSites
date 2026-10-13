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


def prepare_project(directory, makefile):
    """Keep the same root-template/project arrangement as a real checkout."""
    repository = pathlib.Path(directory)
    shutil.copy(ROOT / "python-project.mk", repository / "python-project.mk")
    project = repository / "project"
    project.mkdir()
    (project / "Makefile").write_text(makefile)
    return project


class DependencyContractTests(unittest.TestCase):
    def test_project_overrides_data_rebuild_and_cleanup(self):
        makefile = '''PROJECT := custom
VENV := .custom-env
OUT := output/main.html
OUTPUTS := $(OUT) output/extra.txt
OPEN_FILE := output/extra.txt
CLEAN_FILES := $(OUTPUTS) data/routing.json
FETCH_SCRIPT := src/custom_fetch.py
PYTEST_ARGS := -q -x
BREW_FORMULAE := uv extra-tool
BREW_CASKS := extra-cask
include ../python-project.mk

$(OUTPUTS):
\t@mkdir -p output
\t@touch $@
'''
        with tempfile.TemporaryDirectory() as directory:
            root = prepare_project(directory, makefile)
            (root / "pyproject.toml").touch()
            (root / "uv.lock").touch()
            (root / "data").mkdir()
            for name in ("routing.json", "curated.json", "geocode_cache.json"):
                (root / "data" / name).write_text("keep")
            tools = root / "tools"
            tools.mkdir()
            uv = tools / "uv"
            uv.write_text('#!/bin/sh\n'
                          'echo "$UV_PROJECT_ENVIRONMENT:$*" >> installs\n'
                          'mkdir -p "$UV_PROJECT_ENVIRONMENT/bin"\n'
                          'printf \'#!/bin/sh\\necho "$*" >> calls\\n\' > "$UV_PROJECT_ENVIRONMENT/bin/python"\n'
                          'chmod +x "$UV_PROJECT_ENVIRONMENT/bin/python"\n')
            uv.chmod(0o755)
            interpreter = root / ".custom-env/bin/python"

            def make(*arguments):
                # Exercise the normal repo-root invocation and recursive rebuild.
                return subprocess.run(["make", "-C", str(root), *arguments],
                                      cwd=directory, capture_output=True,
                                      env=dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"]))

            self.assertEqual(make("data").returncode, 0)
            self.assertEqual((root / "installs").read_text(), ".custom-env:sync --locked\n")
            self.assertFalse((root / ".venv").exists())
            self.assertTrue((root / "output/main.html").exists())
            self.assertTrue((root / "output/extra.txt").exists())
            self.assertEqual(make("test").returncode, 0)
            self.assertEqual((root / "calls").read_text().splitlines(),
                             ["src/custom_fetch.py", "-m pytest -q -x"])
            self.assertEqual(make("clean").returncode, 0)
            self.assertFalse((root / "output/main.html").exists())
            self.assertFalse((root / "output/extra.txt").exists())
            self.assertFalse((root / "data/routing.json").exists())
            self.assertTrue((root / "data/curated.json").exists())
            self.assertTrue((root / "data/geocode_cache.json").exists())
            self.assertTrue(interpreter.exists())
            self.assertEqual(make("clean-deps").returncode, 0)
            self.assertFalse((root / ".custom-env").exists())
            self.assertTrue((root / "uv.lock").exists())
            # The default goal must remain all despite included setup targets.
            (root / ".custom-env/bin").mkdir(parents=True)
            interpreter.write_text('#!/bin/sh\nexit 0\n')
            interpreter.chmod(0o755)
            (root / ".custom-env/.stamp").touch()
            self.assertEqual(make().returncode, 0)
            self.assertTrue((root / "output/main.html").exists())
            self.assertTrue((root / "output/extra.txt").exists())

    def test_current_outputs_still_validate_environment_without_repair(self):
        makefiles = {path.parent.name: path.read_text()
                     for path in ROOT.glob("*/Makefile")}
        makefiles["scaffold"] = scaffolder.FILES["Makefile"].replace("__PROJECT__", "scaffold")
        for name, makefile in makefiles.items():
            with self.subTest(project=name), tempfile.TemporaryDirectory() as directory:
                root = prepare_project(directory, makefile)
                (root / "pyproject.toml").touch()
                (root / "uv.lock").touch()
                if name == "scaffold":
                    for filename in ("src/build_site.py", "data/example.json"):
                        path = root / filename
                        path.parent.mkdir(exist_ok=True)
                        path.touch()
                    outputs = ["scaffold.html"]
                else:
                    # Read real prerequisites without copying large transit inputs.
                    for folder in ("src", "data"):
                        (root / folder).symlink_to(ROOT / name / folder, target_is_directory=True)
                    outputs = [path.name for path in (ROOT / name / "output").iterdir()
                               if path.is_file()]
                (root / "output").mkdir()
                for filename in outputs:
                    (root / "output" / filename).write_text("already built")
                tools = root / "tools"
                tools.mkdir()
                uv = tools / "uv"
                uv.write_text('#!/bin/sh\necho sync >> calls\nexit 1\n')
                uv.chmod(0o755)
                (root / ".venv/bin").mkdir(parents=True)
                interpreter = root / ".venv/bin/python"
                interpreter.write_text('#!/bin/sh\necho python >> calls\n')
                interpreter.chmod(0o755)
                stamp = root / ".venv/.stamp"
                stamp.touch()
                stamp_before = stamp.stat().st_mtime_ns
                environment = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"])

                def make(target):
                    return subprocess.run(["make", target], cwd=root,
                                          env=environment, capture_output=True)

                before = {path.name: path.stat().st_mtime_ns
                          for path in (root / "output").iterdir()}
                self.assertEqual(make("all").returncode, 0)
                self.assertFalse((root / "calls").exists())
                interpreter.unlink()
                for target in ("all", "test", "data", "deps", "output/" + name + ".html"):
                    result = make(target)
                    self.assertNotEqual(result.returncode, 0, target)
                    self.assertIn(b"make clean-deps then make deps", result.stderr, target)
                self.assertFalse((root / "calls").exists())
                self.assertEqual(stamp.stat().st_mtime_ns, stamp_before)
                self.assertEqual(before, {path.name: path.stat().st_mtime_ns
                                         for path in (root / "output").iterdir()})

    def test_explicit_system_installation_and_prerequisite_failures(self):
        makefiles = {path.parent.name: path.read_text()
                     for path in ROOT.glob("*/Makefile")}
        makefiles["scaffold"] = scaffolder.FILES["Makefile"]
        for name, makefile in makefiles.items():
            with self.subTest(project=name), tempfile.TemporaryDirectory() as directory:
                root = prepare_project(directory, makefile)
                tools = root / "tools"
                tools.mkdir()
                uname = tools / "uname"
                uname.write_text('#!/bin/sh\necho "${TEST_OS:-Darwin}"\n')
                uname.chmod(0o755)
                brew = tools / "brew"
                brew.write_text('#!/bin/sh\necho "$*" >> calls\nexit "${BREW_EXIT:-0}"\n')
                brew.chmod(0o755)

                def install(**extra):
                    return subprocess.run(
                        [shutil.which("make"), "system-deps"], cwd=root, capture_output=True,
                        env=dict(os.environ, PATH=str(tools), **extra),
                    )

                self.assertEqual(install().returncode, 0)
                expected = (["install uv osmium-tool", "install --cask temurin@21"]
                            if name == "union-station-transit-isochrone" else ["install uv"])
                self.assertEqual((root / "calls").read_text().splitlines(), expected)
                self.assertFalse((root / ".venv").exists())
                (root / "calls").unlink()
                result = install(TEST_OS="Linux")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"supports macOS", result.stderr)
                self.assertFalse((root / "calls").exists())
                self.assertNotEqual(install(BREW_EXIT="1").returncode, 0)
                self.assertEqual(len((root / "calls").read_text().splitlines()), 1)
                (root / "calls").unlink()
                brew.unlink()
                result = install()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"Install Homebrew", result.stderr)
                self.assertFalse((root / "calls").exists())

    def test_data_sync_failure_stops_before_fetch_for_every_project(self):
        makefiles = {path.parent.name: path.read_text()
                     for path in ROOT.glob("*/Makefile")}
        makefiles["scaffold"] = scaffolder.FILES["Makefile"]
        for name, makefile in makefiles.items():
            with self.subTest(project=name), tempfile.TemporaryDirectory() as directory:
                root = prepare_project(directory, makefile)
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

    def test_actual_scaffolder_creates_project_using_shared_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            # Seed out-of-process so generated fetch_data cannot pollute imports.
            script = root / "new-project.py"
            shutil.copy(ROOT / "new-project.py", script)
            shutil.copy(ROOT / "python-project.mk", root / "python-project.mk")
            subprocess.run([os.sys.executable, str(script), "fresh-site"], check=True,
                           stdout=subprocess.DEVNULL)
            project = root / "fresh-site"
            self.assertTrue((project / "uv.lock").exists())
            self.assertTrue((project / "Makefile").exists())
            self.assertTrue((project / "data/example.json").exists())

    def test_install_reuse_failure_and_explicit_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = prepare_project(directory, scaffolder.FILES["Makefile"])
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
