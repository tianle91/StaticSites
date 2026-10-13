"""Exercise the workflow's actual shell discovery with mocked git/jq I/O."""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class DiscoveryTests(unittest.TestCase):
    def test_shared_template_local_changes_and_admin_only_changes(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        # Run the selector and deleted-project filtering verbatim. Mock jq only
        # passes through the list; its JSON formatting is not the behavior at risk.
        script = workflow.split('          if [[ "${{ github.event_name }}"', 1)[1]
        script = 'if [[ "${{ github.event_name }}"' + script
        script = script.split('          echo "projects=$projects"', 1)[0]
        script = script.replace("${{ github.event.pull_request.base.sha }}", "base")
        script += '\nprintf "%s\\n" "$projects"\n'
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for project in ("a", "b"):
                (root / project).mkdir()
                (root / project / "Makefile").touch()
            (root / "Makefile").touch()
            tools = root / "tools"
            tools.mkdir()
            for name, contents in {
                "git": '#!/bin/sh\nprintf "%s\\n" "$CHANGED_PATHS"\n',
                "jq": '#!/bin/sh\ncat\n',
            }.items():
                path = tools / name
                path.write_text(contents)
                path.chmod(0o755)
            cases = [
                ("pull_request", "python-project.mk", ["a", "b"]),
                ("pull_request", "a/src/build.py", ["a"]),
                ("pull_request", "README.md\n.github/notes.md", []),
                ("pull_request", "deleted/src/build.py", []),
                ("push", "", ["a", "b"]),
            ]
            for event, paths, expected in cases:
                with self.subTest(event=event, paths=paths):
                    result = subprocess.run(
                        ["bash", "-e", "-o", "pipefail", "-c",
                         script.replace("${{ github.event_name }}", event)],
                        cwd=root, capture_output=True, text=True,
                        env=dict(os.environ, CHANGED_PATHS=paths,
                                 PATH=str(tools) + os.pathsep + os.environ["PATH"]),
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.split(), expected)
