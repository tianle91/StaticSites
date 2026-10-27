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

ROOT = pathlib.Path(__file__).resolve().parent

# Kebab-case: the directory name is also the package-ish name in pyproject.toml
# and the stem of the built artifact, so keep it to something safe everywhere.
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


FILES = {}

FILES["pyproject.toml"] = '''\
[project]
name = "__PROJECT__"
version = "0.0.0"
description = "__TITLE__ — TODO: one-line blurb for the homepage listing."
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

[tool.staticsite]
# Homepage-listing metadata, aggregated into the repo-root sites.json by
# ../generate_manifest.py. `title` is the link text; the blurb shown after it is
# [project].description with the leading "<title> — " stripped, so description
# must start with "<title> — ".
title = "__TITLE__"

'''

# Generated with uv lock for the empty placeholder + pytest. Shipping the lock
# keeps scaffolding stdlib-only and makes the first locked sync reproducible.
FILES["uv.lock"] = '''\
version = 1
revision = 5
requires-python = ">=3.11"

[[package]]
name = "colorama"
version = "0.4.6"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/d8/53/6f443c9a4a8358a93a6792e2acffb9d9d5cb0a5cfd8802644b7b1c9a02e4/colorama-0.4.6.tar.gz", hash = "sha256:08695f5cb7ed6e0531a20572697297273c47b8cae5a63ffc6d6ed5c201be6e44", size = 27697, upload-time = "2022-10-25T02:36:22.414Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/d1/d6/3965ed04c63042e047cb6a3e6ed1a63a35087b6a609aa3a15ed8ac56c221/colorama-0.4.6-py2.py3-none-any.whl", hash = "sha256:4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6", size = 25335, upload-time = "2022-10-25T02:36:20.889Z" },
]

[[package]]
name = "iniconfig"
version = "2.3.1"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/01/e1/2069291243c926a2ff1cd706c7f3eeb9b62144bf60f77c9fb9ff2fb26bd3/iniconfig-2.3.1.tar.gz", hash = "sha256:67f4b9c50da0dedf52af349e7749a80a9057a5031199791b906c3bb3ae878960", size = 21209, upload-time = "2026-10-06T22:48:38.076Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/56/43/4ca9e49d27a1fcf6bece6f6aec0ea46bb9112489b93d4b688fb415457bdb/iniconfig-2.3.1-py3-none-any.whl", hash = "sha256:9121e2c1fdb355232495be3194c8dfe87ccc2d5dee45947b78e68f499790d7a7", size = 7552, upload-time = "2026-10-06T22:48:36.959Z" },
]

[[package]]
name = "packaging"
version = "26.3"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/7d/fa/3944b40b07da9ce895c0e6303a5ab7d53da063554f534556b134a54d6093/packaging-26.3.tar.gz", hash = "sha256:94edc256424af38762eb31306eed28beb9f0efc50a8837492c9d6fd6004aed79", size = 313412, upload-time = "2026-08-04T18:15:28.737Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/63/34/ba1c580383c9eada3711951fef0795c80b829a078d72188184bcab9dd527/packaging-26.3-py3-none-any.whl", hash = "sha256:d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c", size = 129956, upload-time = "2026-08-04T18:15:27.159Z" },
]

[[package]]
name = "pluggy"
version = "1.6.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/f9/e2/3e91f31a7d2b083fe6ef3fa267035b518369d9511ffab804f839851d2779/pluggy-1.6.0.tar.gz", hash = "sha256:7dcc130b76258d33b90f61b658791dede3486c3e6bfb003ee5c9bfb396dd22f3", size = 69412, upload-time = "2025-05-15T12:30:07.975Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/54/20/4d324d65cc6d9205fabedc306948156824eb9f0ee1633355a8f7ec5c66bf/pluggy-1.6.0-py3-none-any.whl", hash = "sha256:e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746", size = 20538, upload-time = "2025-05-15T12:30:06.134Z" },
]

[[package]]
name = "pygments"
version = "2.21.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://files.pythonhosted.org/packages/49/2e/ced460408999b33da6b31b0021b0f37d329e202d4169aeb164493778f25b/pygments-2.21.0.tar.gz", hash = "sha256:610ca751c9bc2492b38eb9a38a7fbc93edbbb2d7182edaf34e66ae493dee5c8c", size = 5005329, upload-time = "2026-08-17T08:02:48.824Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/71/46/17f022dd3e953bf20a04a028a21ec746d942f8d2af30fa0f124fa0e6a684/pygments-2.21.0-py3-none-any.whl", hash = "sha256:2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9", size = 1250147, upload-time = "2026-08-17T08:02:44.912Z" },
]

[[package]]
name = "pytest"
version = "9.1.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "colorama", marker = "sys_platform == 'win32'" },
    { name = "iniconfig" },
    { name = "packaging" },
    { name = "pluggy" },
    { name = "pygments" },
]
sdist = { url = "https://files.pythonhosted.org/packages/e4/47/b9efed96c114afcfa3c9d3fe98a76a1d14c74a9e266d397cf6eb64be5e01/pytest-9.1.1.tar.gz", hash = "sha256:1088fbde8f2b49d95a549a195707afa7a76a3ce9bcadc26b6d71f0ffda5fe313", size = 1636369, upload-time = "2026-06-19T10:58:32.857Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/24/25/1de2678b631f5a49215c6c96fff41ba892b0a34df68d6d80292b1b48aa7f/pytest-9.1.1-py3-none-any.whl", hash = "sha256:37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c", size = 386536, upload-time = "2026-06-19T10:58:31.347Z" },
]

[[package]]
name = "__PROJECT__"
version = "0.0.0"
source = { virtual = "." }

[package.dev-dependencies]
dev = [
    { name = "pytest" },
]

[package.metadata]

[package.metadata.requires-dev]
dev = [{ name = "pytest", specifier = ">=8.0" }]
'''

FILES["Makefile"] = '''\
# __TITLE__.
# Run from this project: cd __PROJECT__ && make
# Shared Python/uv targets live in ../python-project.mk; build rules stay here.

PROJECT := __PROJECT__

include ../python-project.mk

$(OUT): src/build_site.py data/example.json
	$(PY) src/build_site.py
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

For a map project, follow the repo README's map interface convention: search and
matching counts above Layers / Results / Data sources tabs, toggleable feature
layers, clickable search results, linked provenance, and adjacent zoom / locate /
fit controls. Use a desktop sidebar and an expandable mobile bottom panel.
Copy browser helpers into this project's src/; do not import another project.
Request location only after a click, show browser accuracy and retry messages,
and explain what the counts and published coordinates represent.

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

## Refresh and dependencies

This project includes the repository's [shared Python/uv Make template](../python-project.mk).
Its own Makefile defines artifact inputs, rendering rules, and any configuration
overrides. Build inside the repository checkout so the shared template is available.

`make system-deps` installs [uv](https://formulae.brew.sh/formula/uv)
on macOS using [Homebrew](https://brew.sh), which must already be installed.
On other platforms, install those tools manually before `make deps` / `make data`.
System installation runs only when explicitly requested; other targets never
invoke it. Credentials must be supplied separately.

`make deps` installs this project's complete locked Python environment, including
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
for the project to the table in ../README.md. Set the homepage blurb in
pyproject.toml ([project].description + [tool.staticsite].title), then run
`make manifest` from the repo root to add the project to sites.json. Refresh data
only when `make data` is invoked; unchanged upstream content must preserve
committed bytes and timestamps.
""".format(name=name))


if __name__ == "__main__":
    main()
