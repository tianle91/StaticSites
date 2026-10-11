#!/usr/bin/env python3
"""Delegate data/deps to independent projects; never import this from a project."""
import argparse
import os
import pathlib
import signal
import subprocess
import sys

from refresh_projects import collect_projects

ROOT = pathlib.Path(__file__).resolve().parent


def run_command(command, root, timeout):
    # Killing only make would leave its downloader/router running in the shared
    # checkout after a timeout. Own and terminate the entire process group.
    process = subprocess.Popen(command, cwd=str(root), start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise


def run(target, root=ROOT):
    # Discovery intentionally matches CI and does not filter by refresh.enabled.
    root = pathlib.Path(root).resolve()
    projects = sorted(path.parent for path in root.glob("*/Makefile"))
    timeouts = {}
    if target == "data":
        timeouts = {p["slug"]: p["timeout_minutes"] * 60
                    for p in collect_projects(root)}
    results = []
    for project in projects:
        print("Running {}: make {}".format(project.name, target), flush=True)
        try:
            code = run_command(
                ["make", "-C", str(project), target],
                root, timeouts.get(project.name, 1800),
            )
            status = "OK" if code == 0 else "FAILED ({})".format(code)
        except subprocess.TimeoutExpired:
            status = "FAILED (timeout)"
        except OSError as exc:
            status = "FAILED ({})".format(exc)
        results.append((project.name, status))
    print("\nmake {} summary:".format(target))
    for slug, status in results:
        print("  {}: {}".format(slug, status))
    if not results:
        print("  No projects discovered.")
    return int(any(status != "OK" for _, status in results))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("data", "deps"))
    args = parser.parse_args()
    try:
        return run(args.target)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
