#!/usr/bin/env python3
"""Scaffold a new project in this repo, in the standard layout.

    ./new-project.py my-new-map

Creates my-new-map/ with the layout and make targets specified in AGENTS.md, and
with a working placeholder build wired up end to end -- so that immediately
after scaffolding:

    cd my-new-map && make && make test

both pass, and CI picks the project up with no changes. Replace the placeholder
fetch/build/test with the real thing from there.

Stdlib only, so it runs on whatever python3 is on PATH (no venv needed yet).
"""
import argparse
import pathlib
import re
import stat
import sys

ROOT = pathlib.Path(__file__).resolve().parent

# Kebab-case: the directory name is also the package-ish name in pyproject.toml
# and the stem of the built artifact, so keep it to something safe everywhere.
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


FILES = {}

FILES["pyproject.toml"] = '''\
[project]
name = "__PROJECT__"
version = "0.0.0"
description = "__TITLE__."
requires-python = ">=3.11"

# Runtime dependencies. Say why each one is here.
dependencies = []

[dependency-groups]
dev = ["pytest>=8.0"]

[tool.uv]
# This project is an environment, not a distributable package -- nothing to build.
package = false

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
'''

FILES["Makefile"] = '''\
# __TITLE__.
# Run from this directory: cd __PROJECT__ && make
# Layout and target contract are the repo standard - see ../AGENTS.md.

PROJECT := __PROJECT__
VENV  := .venv
PY    := $(VENV)/bin/python
STAMP := $(VENV)/.stamp
OUT   := output/$(PROJECT).html

.PHONY: all deps test data open clean clean-venv

# Default target: one-shot offline build from the committed data/.
all: $(OUT)

# Create/refresh .venv from pyproject.toml. The stamp keeps `uv sync` from
# re-running on every build once the tree is warm.
deps: $(STAMP)

$(STAMP): pyproject.toml $(wildcard uv.lock)
	uv sync
	@touch $@

$(OUT): src/build_site.py data/example.json | $(STAMP)
	$(PY) src/build_site.py

test: | $(STAMP)
	$(PY) -m pytest -q

# Network step: refresh data/ from upstream, then rebuild. Everything that hits
# the network belongs here - `all` and `test` must stay offline.
data: | $(STAMP)
	$(PY) src/fetch_data.py
	$(PY) src/build_site.py

open: $(OUT)
	open $(OUT) 2>/dev/null || xdg-open $(OUT) 2>/dev/null || echo "Open $(OUT) manually."

clean:
	rm -f $(OUT)

clean-venv:
	rm -rf $(VENV)
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

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (src/ is one level down)
DATA_DIR = ROOT / "data"
OUT_PATH = DATA_DIR / "example.json"


def main() -> None:
    payload = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "items": [
            {"name": "Placeholder item", "value": 1},
        ],
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\\n", encoding="utf-8")
    print("Wrote {} with {} item(s).".format(OUT_PATH, len(payload["items"])))
    print("Done. Now run `make` to rebuild the site.")


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
PAYLOAD = json.dumps(DATA, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__TITLE__</title>
<style>
  body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
  main { max-width: 760px; margin: 40px auto; padding: 0 16px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  h2 { font-size: 14px; margin: 24px 0 6px; }
  p.meta { color: #555; font-size: 13px; margin: 0 0 20px; }
  li { margin: 4px 0; }
  footer.sources { margin-top: 28px; border-top: 1px solid #eee; padding-top: 12px;
    font-size: 13px; color: #555; }
  footer.sources a { color: #1f78b4; }
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

## Usage

```sh
make          # build output/__PROJECT__.html from the committed data/ (offline)
make open     # build, then open it in a browser
make test     # run the tests
make data     # refresh data/ from upstream (requires internet), then rebuild
```

`uv` creates this project's `.venv` on first run. Targets follow the repo
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
    sys.path.insert(0, str(target / "src"))
    import fetch_data  # noqa: E402 - imported from the freshly written project

    fetch_data.main()

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
for the project to the table in ../README.md.
""".format(name=name))


if __name__ == "__main__":
    main()
