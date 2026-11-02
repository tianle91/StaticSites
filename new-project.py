#!/usr/bin/env python3
"""Scaffold a new project in this repo, in the standard layout.

    ./new-project.py my-new-map

Creates my-new-map/ with the layout and make targets specified in AGENTS.md, and
with a working placeholder build wired up end to end -- so that immediately
after scaffolding:

    cd my-new-map && make && make test

both pass, and root make test / make data discover the project automatically. Replace the placeholder
fetch/build/test with the real thing from there.

Stdlib only, so it runs on whatever python3 is on PATH (no venv needed yet).
"""
import argparse
import pathlib
import re
import stat
import sys
import runpy

ROOT = pathlib.Path(__file__).resolve().parent

# Kebab-case: the directory name is also the project name in site.toml
# and the stem of the built artifact, so keep it to something safe everywhere.
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


FILES = {}

FILES["site.toml"] = '''\
[site]
name = "__PROJECT__"
title = "__TITLE__"
description = "__TITLE__ — TODO: one-line blurb for the homepage listing."
'''

FILES["pytest.ini"] = '''\
[pytest]
testpaths = tests
pythonpath = src
'''

FILES["Makefile"] = '''\
# Project configuration; artifact recipes and the Python environment are shared.
PROJECT := __PROJECT__
BUILD_SCRIPT := src/build_site.py
DATA_INPUTS := data/example.json
# Optional: SNAPSHOT_SCRIPT := src/snapshot_site.py

include ../artifact-project.mk
'''


FILES[".gitignore"] = '''\
# Generic Python/venv rules live in the repo-root .gitignore.
# Add project-specific exclusions here (large inputs, scratch files).
'''

FILES["src/fetch_data.py"] = '''\
#!/usr/bin/env python3
"""Network step (`make data`): refresh data/ from upstream.

Everything that touches the network lives here, and its output is committed, so
that `make` and `make test` stay offline and reproducible.

TODO: replace the placeholder below with the real fetch.
"""
import datetime
import json
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (src/ is one level down)
DATA_DIR = ROOT / "data"
OUT_PATH = DATA_DIR / "example.json"


def write_if_changed(path, content):
    """Publish validated content atomically; unchanged files keep their mtime."""
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     delete=False) as stream:
        temporary = pathlib.Path(stream.name)
        try:
            stream.write(content)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main() -> None:
    substantive = {
        "items": [
            {"name": "Placeholder item", "value": 1},
        ],
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if OUT_PATH.exists():
        existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        existing.pop("generated_at", None)
    if existing == substantive:
        print("{} is unchanged.".format(OUT_PATH))
        return
    payload = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        **substantive,
    }
    write_if_changed(OUT_PATH, json.dumps(payload, indent=2) + "\\n")
    print("Wrote {} with {} item(s).".format(OUT_PATH, len(payload["items"])))
    print("Data ready; make data rebuilds the site automatically.")


if __name__ == "__main__":
    main()
'''

FILES["src/build_site.py"] = '''\
#!/usr/bin/env python3
"""Build output/__PROJECT__.html from the committed data/.

Offline: reads only what is in data/, so `make` works from a fresh clone with no
network. TODO: replace the placeholder rendering with the real thing.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (src/ is one level down)
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"

DATA = json.loads((DATA_DIR / "example.json").read_text(encoding="utf-8"))

# The payload is embedded in the page so the artifact is self-contained: one file
# you can open or serve anywhere, with no sidecar requests.
PAYLOAD = json.dumps(DATA, indent=2, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__TITLE__</title>
<style>
  body { margin: 0; background: #f5f6f3; color: #182d37;
    font: 14px/1.6 system-ui, -apple-system, Segoe UI, sans-serif; }
  main { max-width: 1200px; margin: auto; padding: 35px 28px; }
  h1 { font-size: clamp(27px, 3.5vw, 38px); line-height: 1.25; margin: 0 0 8px; }
  h2 { font-size: 14px; margin: 24px 0 6px; }
  p.meta { color: #596b71; font-size: 14px; margin: 0 0 20px; }
  li { margin: 4px 0; }
  footer.sources { margin-top: 28px; border-top: 1px solid #dce2df; padding-top: 12px;
    font-size: 11px; color: #596b71; }
  footer.sources a { color: #116965; }
  @media (max-width: 640px) { main { padding: 23px 14px; } }
</style>
</head>
<body>
<main>
  <h1>__TITLE__</h1>
  <p class="meta" id="meta"></p>
  <ul id="items"></ul>

  <!-- Every site documents where its data came from, and links it. Replace these
       placeholders with the real upstream sources (keep them in sync with the
       "Data sources" section of README.md). -->
  <footer class="sources">
    <h2>Data sources</h2>
    <ul>
      <li><a href="https://example.com/" target="_blank" rel="noopener">TODO: upstream source</a></li>
    </ul>
  </footer>
</main>
<script>
const DATA = __PAYLOAD__;
document.getElementById('meta').textContent = 'Generated ' + DATA.generated_at;
for (const item of DATA.items) {
  const li = document.createElement('li');
  li.textContent = item.name + ' \\u2014 ' + item.value;
  document.getElementById('items').appendChild(li);
}
</script>
</body>
</html>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "__PROJECT__.html"
    target.write_text(HTML.replace("__PAYLOAD__", PAYLOAD), encoding="utf-8")
    print("Wrote {} ({} item(s))".format(target, len(DATA["items"])))


if __name__ == "__main__":
    main()
'''

FILES["tests/test_build_smoke.py"] = '''\
"""Smoke test the offline build end-to-end, without touching the network.

Rebuilds a minimal copy of the project layout (src/ + data/ + output/) in a temp
dir and runs the builder there, so it never clobbers the committed output.
"""
import pathlib
import shutil
import subprocess
import sys
import runpy

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECT = "__PROJECT__"


@pytest.fixture
def built(tmp_path):
    for sub in ("src", "data", "output"):
        (tmp_path / sub).mkdir()
    shutil.copy(ROOT / "src" / "build_site.py", tmp_path / "src" / "build_site.py")
    shutil.copy(ROOT / "data" / "example.json", tmp_path / "data" / "example.json")
    subprocess.run([sys.executable, "src/build_site.py"], cwd=tmp_path, check=True)
    return (tmp_path / "output" / (PROJECT + ".html")).read_text()


def test_html_is_self_contained(built):
    assert built.startswith("<!DOCTYPE html")
    assert "__PAYLOAD__" not in built          # payload was substituted


def test_documents_data_sources(built):
    # Every site must document its data sources on the page itself.
    assert "Data sources" in built
'''

FILES["README.md"] = '''\
# __PROJECT__

__TITLE__.

TODO: one paragraph on what this shows and why it is interesting.

Use the shared build-time package in ../src/staticsites for map controls,
plot components, snapshot capture and data-pipeline helpers. Keep dataset parsing,
validation rules, search fields and page-specific behavior here. Shared CSS/JS is
embedded into output HTML; a published site must not require this checkout or
Python. Maps may retain documented external tiles/scripts.

For snapshots, configure staticsites.snapshots.Snapshotter in src/snapshot_site.py
and set SNAPSHOT_SCRIPT before the Make include. Run make snapshot-browser
explicitly for browser setup and make snapshots for desktop/mobile review JPEGs.

## Usage

```sh
make          # build output/__PROJECT__.html from the committed data/ (offline)
make open     # build, then open it in a browser
make test     # run the tests
make data     # refresh data/ from upstream (requires internet), then rebuild
```

`make deps` installs the repository-root `.venv` from the single root lockfile. Targets follow the repo
standard -- see the [repo README](../README.md).

## Layout

| Path | What it is |
| --- | --- |
| `src/fetch_data.py` | Network step (`make data`): refreshes `data/` from upstream |
| `src/build_site.py` | Offline build: renders `output/__PROJECT__.html` from `data/` |
| `data/example.json` | Committed input for the build |
| `output/__PROJECT__.html` | Generated output (committed so it works without a build) |

## Data sources

TODO: list each upstream source, with a link and any licence or attribution
requirements.

## Caveats

TODO: anything a reader should know before trusting the output.

## Refresh and dependencies

This project includes the repository's [shared Python/uv Make template](../python-project.mk).
Its own Makefile defines artifact inputs, rendering rules, and any configuration
overrides. Build inside the repository checkout so the shared template is available.

`make system-deps` installs [uv](https://formulae.brew.sh/formula/uv)
on macOS using [Homebrew](https://brew.sh), which must already be installed.
On other platforms, install those tools manually before `make deps` / `make data`.
System installation runs only when explicitly requested; other targets never
invoke it. Credentials must be supplied separately.

`make deps` installs the repository's complete locked Python environment, including
test dependencies, when it is new or the dependency manifests change. `make data`
uses the same setup before fetching all required upstream inputs. Repeated commands
reuse the environment; they do not attempt repairs. To reinstall from scratch, run
`make clean-deps && make deps` (`clean-venv` remains an alias). Missing or stale
locks fail without being rewritten.
Dependency setup may require network access; installed builds/tests are offline.
`make data` obtains every required input and rebuilds outputs automatically.
Unchanged upstream content preserves data timestamps; missing generated files are
restored. Required-source failures retain previous datasets and return an error.
'''


def titleize(name):
    """my-new-map -> My New Map"""
    return " ".join(word.capitalize() for word in name.split("-"))


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold a new project in the repo standard layout.")
    parser.add_argument("name", help="project directory name, in kebab-case")
    args = parser.parse_args()

    name = args.name.strip().rstrip("/")
    if not NAME_RE.match(name):
        parser.error(
            "'{}' is not kebab-case (lowercase letters/digits separated by single "
            "hyphens), e.g. toronto-bike-lanes-map".format(name))

    target = ROOT / name
    if target.exists():
        parser.error("{}/ already exists".format(name))

    title = titleize(name)
    for rel, template in FILES.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.replace("__PROJECT__", name).replace("__TITLE__", title),
                        encoding="utf-8")

    # Seed data/ so the very first `make` has an input and succeeds offline.
    (target / "output").mkdir(exist_ok=True)
    runpy.run_path(str(target / "src/fetch_data.py"), run_name="__main__")

    # The builders are meant to be runnable directly, like the ones they mimic.
    for script in (target / "src").glob("*.py"):
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print("""
Created {name}/ in the standard layout. Next:

    cd {name}
    make && make test        # both should pass right away
    git add {name}

Then replace the placeholders: src/fetch_data.py (the real upstream fetch),
src/build_site.py (the real rendering), the TODOs in README.md, and add a row
for the project to the table in ../README.md. Set the homepage blurb in
site.toml ([site].description + [site].title), then run
`make manifest` from the repo root to add the project to sites.json. Refresh data
only when `make data` is invoked; unchanged upstream content must preserve
committed bytes and timestamps.
""".format(name=name))


if __name__ == "__main__":
    main()
