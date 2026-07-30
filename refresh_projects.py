#!/usr/bin/env python3
"""Select and run scheduled project data refreshes.

    ./refresh_projects.py check
    ./refresh_projects.py select --date 2026-08-03
    ./refresh_projects.py run --date 2026-08-03
    ./refresh_projects.py run --all
    ./refresh_projects.py run --project toronto-dinesafe-map

Each project declares its cadence in [tool.staticsite.refresh] in
pyproject.toml. A project is due on its anchor date and every `every_days`
thereafter. This deterministic calculation avoids committing mutable
"last-run" state merely to keep the scheduler moving.

Stdlib only: this is repo-admin tooling and must run on the system Python 3.9.
"""
import argparse
import datetime
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REFRESH_TABLE = "tool.staticsite.refresh"
REQUIRED_KEYS = ("enabled", "every_days", "anchor_date", "timeout_minutes")


def _parse_value(raw):
    """Parse the small TOML scalar subset used by refresh metadata."""
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    if raw[:1] in ('"', "'") and raw[-1:] == raw[:1]:
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        raise ValueError("unsupported value {!r}".format(raw))


def read_refresh_metadata(path):
    """Read [tool.staticsite.refresh] without requiring Python 3.11 tomllib."""
    values = {}
    table = None
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            table = line[1:-1].strip()
            continue
        if table != REFRESH_TABLE or "=" not in line:
            continue
        key, _, raw_value = line.partition("=")
        key = key.strip()
        try:
            values[key] = _parse_value(raw_value)
        except ValueError as exc:
            raise ValueError("{}:{}: {}".format(path, line_number, exc))
    return values


def collect_projects():
    """Return validated project refresh records, sorted by project slug."""
    projects = []
    errors = []
    for makefile in sorted(ROOT.glob("*/Makefile")):
        project_dir = makefile.parent
        slug = project_dir.name
        pyproject = project_dir / "pyproject.toml"
        if not pyproject.exists():
            errors.append("{}: missing pyproject.toml".format(slug))
            continue
        try:
            refresh = read_refresh_metadata(pyproject)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        missing = [key for key in REQUIRED_KEYS if key not in refresh]
        if missing:
            errors.append(
                "{}: [{}] is missing {}".format(
                    slug, REFRESH_TABLE, ", ".join(missing)))
            continue

        enabled = refresh["enabled"]
        every_days = refresh["every_days"]
        timeout_minutes = refresh["timeout_minutes"]
        if not isinstance(enabled, bool):
            errors.append("{}: enabled must be true or false".format(slug))
        if isinstance(every_days, bool) or not isinstance(every_days, int) or every_days < 1:
            errors.append("{}: every_days must be a positive integer".format(slug))
        if (isinstance(timeout_minutes, bool)
                or not isinstance(timeout_minutes, int)
                or timeout_minutes < 1):
            errors.append("{}: timeout_minutes must be a positive integer".format(slug))
        try:
            anchor_date = datetime.date.fromisoformat(refresh["anchor_date"])
        except (TypeError, ValueError):
            errors.append("{}: anchor_date must be an ISO date (YYYY-MM-DD)".format(slug))
            continue

        projects.append({
            "slug": slug,
            "enabled": enabled,
            "every_days": every_days,
            "anchor_date": anchor_date,
            "timeout_minutes": timeout_minutes,
        })

    if errors:
        raise ValueError("\n".join(errors))
    return projects


def is_due(project, on_date):
    elapsed = (on_date - project["anchor_date"]).days
    return project["enabled"] and elapsed >= 0 and elapsed % project["every_days"] == 0


def select_projects(projects, args):
    by_slug = {project["slug"]: project for project in projects}
    if args.project:
        try:
            return [by_slug[args.project]]
        except KeyError:
            raise ValueError(
                "unknown project {!r}; choose one of: {}".format(
                    args.project, ", ".join(sorted(by_slug))))
    if args.all:
        return [project for project in projects if project["enabled"]]
    on_date = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    return [project for project in projects if is_due(project, on_date)]


def _selection_args(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--all", action="store_true",
        help="select every enabled project, regardless of cadence")
    group.add_argument(
        "--project",
        help="select exactly one project (including a disabled project)")
    parser.add_argument(
        "--date",
        help="selection date in YYYY-MM-DD (default: the local current date)")


def command_check(_args):
    projects = collect_projects()
    enabled = sum(project["enabled"] for project in projects)
    print("Refresh metadata is valid for {} project(s); {} enabled.".format(
        len(projects), enabled))
    return 0


def command_select(args):
    selected = select_projects(collect_projects(), args)
    print(" ".join(project["slug"] for project in selected))
    return 0


def command_run(args):
    selected = select_projects(collect_projects(), args)
    if not selected:
        print("No projects are due.")
        return 0

    for project in selected:
        slug = project["slug"]
        timeout = project["timeout_minutes"] * 60
        print("Refreshing {} ({} minute timeout per command)...".format(
            slug, project["timeout_minutes"]), flush=True)
        for target in ("data", "test", "all"):
            try:
                subprocess.run(
                    ["make", "-C", slug, target],
                    cwd=str(ROOT),
                    check=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                sys.stderr.write(
                    "{}: `make {}` exceeded {} minutes\n".format(
                        slug, target, project["timeout_minutes"]))
                return 1
            except subprocess.CalledProcessError as exc:
                sys.stderr.write(
                    "{}: `make {}` failed with exit code {}\n".format(
                        slug, target, exc.returncode))
                return exc.returncode or 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="validate every project's metadata")
    check.set_defaults(func=command_check)
    select = commands.add_parser("select", help="print selected project slugs")
    _selection_args(select)
    select.set_defaults(func=command_select)
    run = commands.add_parser("run", help="refresh, test, and build selected projects")
    _selection_args(run)
    run.set_defaults(func=command_run)
    args = parser.parse_args()
    try:
        return args.func(args)
    except ValueError as exc:
        sys.stderr.write("{}\n".format(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
