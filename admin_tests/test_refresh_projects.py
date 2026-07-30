"""Tests for the stdlib-only scheduled-refresh selector."""
import argparse
import datetime
import pathlib
import tempfile
import unittest

import refresh_projects


class RefreshMetadataTests(unittest.TestCase):
    def test_reads_refresh_table(self):
        text = """\
[project]
name = "demo"

[tool.staticsite.refresh]
enabled = true
every_days = 7
anchor_date = "2026-08-03"
timeout_minutes = 45
"""
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "pyproject.toml"
            path.write_text(text, encoding="utf-8")
            self.assertEqual(
                refresh_projects.read_refresh_metadata(path),
                {
                    "enabled": True,
                    "every_days": 7,
                    "anchor_date": "2026-08-03",
                    "timeout_minutes": 45,
                },
            )

    def test_due_dates_follow_anchor_and_interval(self):
        project = {
            "enabled": True,
            "every_days": 7,
            "anchor_date": datetime.date(2026, 8, 3),
        }
        self.assertFalse(
            refresh_projects.is_due(project, datetime.date(2026, 8, 2)))
        self.assertTrue(
            refresh_projects.is_due(project, datetime.date(2026, 8, 3)))
        self.assertFalse(
            refresh_projects.is_due(project, datetime.date(2026, 8, 4)))
        self.assertTrue(
            refresh_projects.is_due(project, datetime.date(2026, 8, 10)))

    def test_disabled_project_is_never_due(self):
        project = {
            "enabled": False,
            "every_days": 1,
            "anchor_date": datetime.date(2026, 1, 1),
        }
        self.assertFalse(
            refresh_projects.is_due(project, datetime.date(2026, 8, 3)))

    def test_explicit_selection_can_run_disabled_project(self):
        project = {
            "slug": "heavy-project",
            "enabled": False,
            "every_days": 30,
            "anchor_date": datetime.date(2026, 8, 1),
        }
        args = argparse.Namespace(
            project="heavy-project", all=False, date="2026-08-01")
        self.assertEqual(
            refresh_projects.select_projects([project], args), [project])


if __name__ == "__main__":
    unittest.main()
