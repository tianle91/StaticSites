"""Local orchestration and status provenance, with no GitHub/network calls."""
import contextlib
import io
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

import local_ci

ROOT = pathlib.Path(__file__).resolve().parent.parent


class LocalCITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        for name in ("b", "a"):
            (self.root / name).mkdir()
            (self.root / name / "Makefile").touch()
        (self.root / "Makefile").touch()
        self.git = mock.patch.object(local_ci, "git", return_value="abc123").start()
        self.clean = mock.patch.object(local_ci, "clean_commit", return_value=True).start()
        self.commands = mock.patch.object(local_ci, "run_command", return_value=0).start()
        self.repository = mock.patch.object(local_ci, "github_repository", return_value=("github.com", "owner/repo")).start()
        self.status = mock.patch.object(local_ci, "post_status").start()
        self.addCleanup(mock.patch.stopall)

    def run_ci(self, mode):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return local_ci.run(self.root, mode)

    def test_discovery_and_keep_going_after_project_failure(self):
        self.commands.side_effect = [0, 1, 0]
        self.assertEqual(self.run_ci("off"), 1)
        self.assertEqual([c.args[1] for c in self.commands.call_args_list], [
            ["make", "check"], ["make", "-C", "a", "test", "all"],
            ["make", "-C", "b", "test", "all"]])
        self.repository.assert_not_called()
        self.status.assert_not_called()

    def test_dirty_auto_runs_without_publishing_and_required_refuses(self):
        self.clean.return_value = False
        self.assertEqual(self.run_ci("auto"), 0)
        self.status.assert_not_called()
        self.repository.assert_not_called()
        self.commands.reset_mock()
        with self.assertRaisesRegex(ValueError, "Commit all changes"):
            self.run_ci("required")
        self.commands.assert_not_called()

    def test_every_clean_project_gets_pending_then_its_actual_result(self):
        self.commands.side_effect = [0, 1, 0]
        self.assertEqual(self.run_ci("required"), 1)
        self.assertEqual([(c.args[3], c.args[4]) for c in self.status.call_args_list], [
            ("metadata", "pending"), ("metadata", "success"),
            ("a", "pending"), ("a", "failure"),
            ("b", "pending"), ("b", "success")])
        self.assertTrue(all(c.args[2] == "abc123" for c in self.status.call_args_list))

    def test_generated_changes_cannot_get_a_success_status(self):
        # Initial checkout, metadata before/after, then project a before/after.
        self.clean.side_effect = [True, True, True, True, False, False, False]
        self.assertEqual(self.run_ci("required"), 1)
        states = [(c.args[3], c.args[4]) for c in self.status.call_args_list]
        self.assertIn(("a", "error"), states)
        self.assertNotIn(("a", "success"), states)
        self.assertNotIn(("b", "success"), states)

    def test_auth_or_api_failure_fails_but_still_runs_checks(self):
        self.repository.side_effect = subprocess.CalledProcessError(1, ["gh"])
        self.assertEqual(self.run_ci("required"), 1)
        self.assertEqual(self.commands.call_count, 3)
        self.status.assert_not_called()

    def test_interruption_clears_pending_status(self):
        self.commands.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.run_ci("required")
        self.assertEqual([c.args[4] for c in self.status.call_args_list], ["pending", "error"])

    def test_root_data_dispatches_all_projects_and_reports_failure(self):
        (self.root / "Makefile").write_text((ROOT / "Makefile").read_text())
        for name, code in (("a", 1), ("b", 0)):
            (self.root / name / "Makefile").write_text(
                "data:\n\t@echo {} >> ../calls\n\t@exit {}\n".format(name, code))
        result = subprocess.run(["make", "data"], cwd=self.root,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / "calls").read_text().splitlines(), ["a", "b"])

    def test_separate_environment_is_only_passed_to_project_commands(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(local_ci.run(self.root, "off", ".venv/verification"), 0)
        self.assertEqual(self.commands.call_args_list[0].args[1], ["make", "check"])
        self.assertEqual(self.commands.call_args_list[1].args[1][-1], "VENV=.venv/verification")
        with self.assertRaisesRegex(ValueError, "relative"):
            local_ci.run(self.root, "off", "../shared-environment")


if __name__ == "__main__":
    unittest.main()
