#!/usr/bin/env python3
"""Run repository checks and each project's test/build locally.

GitHub statuses describe an exact, clean HEAD, never uncommitted work. `auto`
publishes for clean commits and stays local for dirty checkouts; `required`
refuses dirty checkouts; `off` never contacts GitHub. Repo-admin tooling uses
only the Python 3.9 standard library, independently of project environments.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent


def git(root, *arguments):
    return subprocess.check_output(
        ["git", *arguments], cwd=str(root), text=True).strip()


def clean_commit(root, sha):
    # Include staged changes and new source files. Ignored envs/logs are fine.
    return (git(root, "rev-parse", "HEAD") == sha
            and not git(root, "status", "--porcelain", "--untracked-files=all"))


def github_repository(root, sha):
    # Use gh's existing login/keychain; never read or pass a token ourselves.
    result = subprocess.check_output(
        ["gh", "repo", "view", "--json", "nameWithOwner,url"],
        cwd=str(root), text=True)
    repository = json.loads(result)
    hostname = urllib.parse.urlparse(repository["url"]).hostname
    name = repository["nameWithOwner"]
    # A local-only commit cannot receive a remote status yet. Do not push here.
    subprocess.run(["gh", "api", "--hostname", hostname,
                    "repos/{}/commits/{}".format(name, sha), "--silent"],
                   cwd=str(root), check=True)
    return hostname, name


def post_status(root, repository, sha, name, state, description):
    hostname, slug = repository
    body = {"state": state, "context": "local-ci/" + name,
            "description": description}
    subprocess.run(
        ["gh", "api", "--hostname", hostname, "--method", "POST",
         "repos/{}/statuses/{}".format(slug, sha), "--input", "-", "--silent"],
        cwd=str(root), input=json.dumps(body), text=True, check=True)


def run_command(root, command, log):
    # Keep a local transcript without uploading logs or local paths to GitHub.
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, cwd=str(root), stdout=stream,
                                stderr=subprocess.STDOUT)
    print(log.read_text(encoding="utf-8"), end="", flush=True)
    return result.returncode


def run(root, statuses, venv=None):
    if venv and (pathlib.Path(venv).is_absolute() or ".." in pathlib.Path(venv).parts):
        raise ValueError("CI_VENV must be relative to each project, without '..'.")
    projects = [path.parent.name for path in sorted(root.glob("*/Makefile"))]
    if not projects:
        raise ValueError("No projects found (expected */Makefile).")
    sha = git(root, "rev-parse", "HEAD")
    clean = clean_commit(root, sha)
    if statuses == "required" and not clean:
        raise ValueError("Commit all changes before publishing statuses; use STATUSES=off for local checks.")
    publish = statuses != "off" and clean
    if statuses == "auto" and not clean:
        print("Uncommitted changes: running locally; no statuses will be attached to HEAD.", flush=True)

    repository = None
    failed = False
    if publish:
        try:
            repository = github_repository(root, sha)
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            print("Cannot prepare GitHub statuses: {}. Local checks will still run.".format(exc), file=sys.stderr)
            failed = True

    log_dir = root / ".local-ci" / sha
    log_dir.mkdir(parents=True, exist_ok=True)
    tasks = [("metadata", ["make", "check"])] + [
        (project, ["make", "-C", project, "test", "all"]
         + (["VENV=" + venv] if venv else []))
        for project in projects]
    results = []
    for name, command in tasks:
        print("\n=== {}: {} ===".format(name, " ".join(command)), flush=True)
        # A previous builder or another process may have modified the checkout.
        eligible = repository is not None and clean_commit(root, sha)
        if repository is not None and not eligible:
            print("Checkout changed; no status will be published for " + name, file=sys.stderr)
            failed = True
        pending = False
        try:
            if eligible:
                try:
                    post_status(root, repository, sha, name, "pending", "Running local checks")
                    pending = True
                except (OSError, subprocess.CalledProcessError) as exc:
                    print("Cannot publish pending status: " + str(exc), file=sys.stderr)
                    failed = True
            code = run_command(root, command, log_dir / (name + ".log"))
            unchanged = not eligible or clean_commit(root, sha)
            passed = code == 0 and unchanged
            if eligible:
                state = "success" if passed else ("failure" if code else "error")
                description = ("Local checks passed" if passed else
                               "Local checks failed; see local log" if code else
                               "Checkout changed during checks; commit generated output and rerun")
                try:
                    post_status(root, repository, sha, name, state, description)
                    pending = False
                except (OSError, subprocess.CalledProcessError) as exc:
                    print("Cannot publish result: " + str(exc), file=sys.stderr)
                    failed = True
            results.append((name, passed))
            failed = failed or not passed
        finally:
            # Interruptions/errors should not leave this project's status pending.
            if pending:
                try:
                    post_status(root, repository, sha, name, "error", "Local run interrupted or status reporting failed")
                except (OSError, subprocess.CalledProcessError) as exc:
                    print("Cannot clear pending status: " + str(exc), file=sys.stderr)

    # Catch edits or a changed HEAD during the final status API request too.
    if repository is not None and not clean_commit(root, sha):
        failed = True
        print("Checkout changed during verification; rerun on a clean commit.", file=sys.stderr)
        try:
            post_status(root, repository, sha, "metadata", "error", "Checkout changed during verification; commit changes and rerun")
        except (OSError, subprocess.CalledProcessError) as exc:
            print("Cannot report changed checkout: " + str(exc), file=sys.stderr)
    print("\n" + "\n".join("{}: {}".format(name, "PASS" if passed else "FAIL")
                              for name, passed in results))
    print("Local logs: " + str(log_dir))
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--statuses", choices=("auto", "off", "required"), default="auto")
    parser.add_argument("--venv", help="optional environment path relative to each project")
    args = parser.parse_args()
    try:
        return run(ROOT, args.statuses, args.venv)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
