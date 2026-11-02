"""Shared-environment Make contract and scaffolder, entirely offline."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('scaffolder', ROOT/'new-project.py')
scaffolder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scaffolder)


class SharedEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in ['environment.mk','python-project.mk','artifact-project.mk']:
            shutil.copy(ROOT/name, self.root/name)
        (self.root/'pyproject.toml').touch()
        (self.root/'uv.lock').touch()
        (self.root/'.python-version').write_text('3.12\n')
        (self.root/'src/staticsites').mkdir(parents=True)
        self.tools = self.root/'tools'
        self.tools.mkdir()
        uv = self.tools/'uv'
        uv.write_text('''#!/bin/sh
case "$UV_PROJECT_ENVIRONMENT" in "$TEST_REPO"/*) ;; *) echo "unsafe fixture environment" >&2; exit 90;; esac
printf '%s:%s\\n' "$UV_PROJECT_ENVIRONMENT" "$*" >> installs
[ -z "$FAIL_SYNC" ] || exit 1
mkdir -p "$UV_PROJECT_ENVIRONMENT/bin"
cat > "$UV_PROJECT_ENVIRONMENT/bin/python" <<'SH'
#!/bin/sh
printf '%s:%s\\n' "$PWD" "$*" >> "$TEST_REPO/calls"
SH
chmod +x "$UV_PROJECT_ENVIRONMENT/bin/python"
''')
        uv.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.tools)+os.pathsep+os.environ['PATH'], TEST_REPO=str(self.root))
        # These are isolated builds, never children of the outer CI Make invocation.
        for key in ('MAKEFLAGS','MAKEOVERRIDES','MFLAGS','MAKELEVEL','VENV','PY','STAMP'):
            self.env.pop(key, None)
        for name in ['a','b']:
            project = self.root/name
            project.mkdir()
            (project/'Makefile').write_text('''PROJECT := example
SNAPSHOT_SCRIPT := src/capture.py
include ../python-project.mk
$(OUT):
\t@mkdir -p output
\t@echo built > $@
''')

    def make(self, project, *targets, **extra):
        return subprocess.run(['make','-C',str(self.root/project),*targets], capture_output=True,
                              env=dict(self.env, **extra))

    def test_projects_share_one_install_and_keep_commands_local(self):
        for project,target in [('a','all'),('b','test'),('a','data')]:
            result=self.make(project,target)
            self.assertEqual(result.returncode,0,result.stderr.decode())
        installs=(self.root/'installs').read_text().splitlines()
        self.assertEqual(installs,[str(self.root/'.venv')+':sync --locked --all-groups'])
        self.assertFalse((self.root/'a/.venv').exists())
        self.assertFalse((self.root/'b/.venv').exists())
        self.assertEqual((self.root/'calls').read_text().splitlines(),
                         [str(self.root/'b')+':-m pytest -q', str(self.root/'a')+':src/fetch_data.py'])
        self.assertTrue((self.root/'a/output/example.html').exists())

    def test_current_outputs_validate_env_without_automatic_repair(self):
        self.assertEqual(self.make('a','all').returncode,0)
        stamp=self.root/'.venv/.stamp'
        before=stamp.stat().st_mtime_ns
        (self.root/'.venv/bin/python').unlink()
        for target in ['all','test','data','deps','output/example.html']:
            result=self.make('a',target)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(b'make clean-deps then make deps',result.stderr)
        self.assertEqual(stamp.stat().st_mtime_ns,before)
        self.assertEqual(len((self.root/'installs').read_text().splitlines()),1)

    def test_failed_sync_stops_fetch_and_keeps_old_stamp(self):
        self.assertEqual(self.make('a','deps').returncode,0)
        stamp=self.root/'.venv/.stamp'
        os.utime(stamp,(0,0))
        self.assertNotEqual(self.make('b','data',FAIL_SYNC='yes').returncode,0)
        self.assertEqual(stamp.stat().st_mtime_ns,0)
        self.assertFalse((self.root/'calls').exists())
        self.assertEqual(self.make('b','deps').returncode,0)
        (self.root/'uv.lock').unlink()
        self.assertNotEqual(self.make('a','deps').returncode,0)

    def test_cleanup_preserves_project_inputs_outputs_and_snapshots(self):
        self.assertEqual(self.make('a','all').returncode,0)
        for filename in ['data/cache.json','tests/snapshots/mobile.jpg','site.toml']:
            p=self.root/'a'/filename
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text('keep')
        self.assertEqual(self.make('b','clean-deps').returncode,0)
        self.assertFalse((self.root/'.venv').exists())
        for filename in ['data/cache.json','tests/snapshots/mobile.jpg','site.toml','output/example.html']:
            self.assertTrue((self.root/'a'/filename).exists())
        self.assertTrue((self.root/'uv.lock').exists())

    def test_snapshots_are_explicit_and_assets_invalidate_artifacts(self):
        self.assertEqual(self.make('a','all','test','data').returncode,0)
        self.assertNotIn('capture',(self.root/'calls').read_text())
        self.assertEqual(self.make('a','snapshots','snapshot-browser').returncode,0)
        calls=(self.root/'calls').read_text()
        self.assertIn('src/capture.py',calls)
        self.assertIn('-m playwright install --only-shell chromium',calls)
        output=self.root/'a/output/example.html'
        os.utime(output,(0,0))
        (self.root/'src/staticsites/ui.js').touch()
        self.assertEqual(self.make('a','all').returncode,0)
        self.assertGreater(output.stat().st_mtime_ns,0)

    def test_artifact_template_builds_formats_and_tracks_declared_inputs(self):
        project=self.root/'a'
        (project/'src').mkdir()
        (project/'src/render.py').touch()
        (project/'data').mkdir()
        (project/'data/input.json').write_text('{}')
        (project/'Makefile').write_text('''PROJECT := example
BUILD_SCRIPT := src/render.py
DATA_INPUTS := data/input.json
ARTIFACT_FORMATS := html png
BUILD_OUTPUT_FLAG := -o
include ../artifact-project.mk
''')
        self.assertEqual(self.make('a','deps').returncode,0)
        interpreter=self.root/'.venv/bin/python'
        interpreter.write_text('''#!/bin/sh
echo "$*" >> "$TEST_REPO/render-calls"
mkdir -p output
test -f "$3" || echo built > "$3"
''')
        interpreter.chmod(0o755)
        self.assertEqual(self.make('a').returncode,0)
        self.assertEqual((self.root/'render-calls').read_text().splitlines(),
                         ['src/render.py -o output/example.html','src/render.py -o output/example.png'])
        for name in ('example.html','example.png'):
            self.assertTrue((project/'output'/name).exists())
            os.utime(project/'output'/name,(0,0))
        self.assertEqual(self.make('a','all').returncode,0)
        self.assertEqual(len((self.root/'render-calls').read_text().splitlines()),4)
        # Unchanged publisher bytes must not cause an endless Make rebuild loop.
        self.assertEqual(self.make('a','all').returncode,0)
        self.assertEqual(len((self.root/'render-calls').read_text().splitlines()),4)

    def test_artifact_template_rejects_a_successful_builder_with_missing_output(self):
        project=self.root/'a'
        (project/'src').mkdir()
        (project/'src/build_site.py').touch()
        (project/'Makefile').write_text('PROJECT := example\ninclude ../artifact-project.mk\n')
        result=self.make('a','all')
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'Builder did not produce output/example.html',result.stderr)

    def test_alternate_environment_is_still_shared(self):
        for name in ['a','b']:
            self.assertEqual(self.make(name,'deps','VENV=.venv-ci').returncode,0)
        self.assertTrue((self.root/'.venv-ci/.stamp').exists())
        self.assertFalse((self.root/'.venv').exists())
        self.assertEqual(len((self.root/'installs').read_text().splitlines()),1)

    def test_fake_installer_refuses_environment_outside_its_fixture(self):
        result = self.make('a', 'deps', 'VENV=' + str(self.root.parent/'outside-test-env'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'unsafe fixture environment', result.stderr)

    def test_cleanup_rejects_ancestors_and_project_directories_before_removal(self):
        # Stub rm even for this negative test: a regression must never execute
        # the dangerous command it is meant to reject.
        remover = self.tools/'rm'
        remover.write_text('#!/bin/sh\necho called >> "$TEST_REPO/removal-calls"\n')
        remover.chmod(0o755)
        for directory in ('..', '/', '.', 'src', 'a/data', 'a/output'):
            result = self.make('a','clean-deps','VENV='+directory)
            self.assertNotEqual(result.returncode,0,directory)
            self.assertIn(b'Refusing unsafe environment cleanup',result.stderr)
        self.assertFalse((self.root/'removal-calls').exists())

    def test_python_pin_change_invalidates_the_shared_stamp(self):
        self.assertEqual(self.make('a','deps').returncode,0)
        (self.root/'.python-version').write_text('3.13\n')
        # Use distinct whole-second mtimes even on coarse Make/filesystem clocks.
        for name in ('pyproject.toml','uv.lock'):
            os.utime(self.root/name,(0,0))
        os.utime(self.root/'.venv/.stamp',(1,1))
        os.utime(self.root/'.python-version',(2,2))
        self.assertEqual(self.make('b','deps').returncode,0)
        self.assertEqual(len((self.root/'installs').read_text().splitlines()),2)

    def test_shared_ui_does_not_rebuild_cached_data_artifacts(self):
        project = self.root/'a'
        (project/'Makefile').write_text('''PROJECT := example
OUTPUTS := output/example.html output/model.geojson
include ../python-project.mk
$(OUTPUTS):
\t@mkdir -p output
\t@echo built > $@
''')
        self.assertEqual(self.make('a','all').returncode,0)
        geometry = project/'output/model.geojson'
        os.utime(geometry,(0,0))
        (self.root/'src/staticsites/ui.js').touch()
        self.assertEqual(self.make('a','all').returncode,0)
        self.assertEqual(geometry.stat().st_mtime_ns,0)

    def test_explicit_system_installation(self):
        for tool,body in [('uname','echo "${TEST_OS:-Darwin}"'),('brew','echo "$*" >> "$TEST_REPO/brew-calls"')]:
            p=self.tools/tool
            p.write_text('#!/bin/sh\n'+body+'\n')
            p.chmod(0o755)
        self.assertEqual(self.make('a','system-deps').returncode,0)
        self.assertEqual((self.root/'brew-calls').read_text(),'install uv\n')
        self.assertNotEqual(self.make('a','system-deps',TEST_OS='Linux').returncode,0)
        self.assertFalse((self.root/'.venv').exists())

    def test_scaffolder_uses_root_lock_and_metadata_only_projects(self):
        shutil.copy(ROOT/'new-project.py',self.root/'new-project.py')
        subprocess.run([sys.executable,str(self.root/'new-project.py'),'fresh-site'],check=True,stdout=subprocess.DEVNULL)
        project=self.root/'fresh-site'
        self.assertTrue((project/'site.toml').exists())
        self.assertTrue((project/'pytest.ini').exists())
        self.assertTrue((project/'data/example.json').exists())
        self.assertFalse((project/'pyproject.toml').exists())
        self.assertFalse((project/'uv.lock').exists())
        self.assertIn('../artifact-project.mk',(project/'Makefile').read_text())
