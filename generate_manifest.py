#!/usr/bin/env python3
"""Aggregate every project's listing metadata into the committed sites.json.

    ./generate_manifest.py            # (re)write sites.json
    ./generate_manifest.py --check    # exit non-zero if sites.json is stale

`sites.json` is the machine-readable index that downstream consumers (e.g.
tianle91.github.io) read to regenerate their site list deterministically, instead
of parsing prose out of the READMEs. Each entry is:

    { "slug": ..., "title": ..., "description": ..., "output": ... }

where, per project (see AGENTS.md):

  - `slug`        = the directory name = [project].name
  - `title`       = [tool.staticsite].title            (the link text)
  - `description` = [project].description with the leading "<title> - " stripped
                    (so description reads as a standalone sentence, and the blurb
                    after the title is not duplicated)
  - `output`      = "<slug>/output/<slug>.html"        (the standard artifact)

Stdlib only, so it runs on whatever python3 is on PATH -- the system one here is
3.9, which predates tomllib, hence the tiny purpose-built reader below. A project
is anything with a Makefile (the same definition CI uses to discover projects).
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / "sites.json"

# Space + em dash + space: the separator between a site's title and its blurb in
# every [project].description. Kept as a named constant so the write side (the
# pyproject files) and this read side agree on the exact character.
TITLE_SEP = " — "


def read_pyproject_subset(text):
    """Return {table: {key: str_value}} for the simple `key = "value"` lines.

    Deliberately minimal: it only understands single-line string assignments,
    which is all this script needs (name, description, title). Arrays, numbers,
    and multi-line values are ignored, and `#` comments are skipped. Good enough
    for our own controlled pyproject.toml files, and avoids a tomllib dependency
    that the system python 3.9 does not have.
    """
    data = {}
    table = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            table = line[1:-1].strip()
            data.setdefault(table, {})
            continue
        if table is None or "=" not in line:
            continue
        key, _, rest = line.partition("=")
        rest = rest.strip()
        quote = rest[:1]
        if quote not in ('"', "'"):
            continue  # not a string value (array, number, bool) -- not needed
        end = rest.find(quote, 1)
        if end == -1:
            continue
        data[table][key.strip()] = rest[1:end]
    return data


def collect_sites():
    """Build the manifest list from every project directory, sorted by slug."""
    sites = []
    for makefile in sorted(ROOT.glob("*/Makefile")):
        project_dir = makefile.parent
        slug = project_dir.name
        pyproject = project_dir / "pyproject.toml"
        if not pyproject.exists():
            raise SystemExit("{}: has a Makefile but no pyproject.toml".format(slug))

        meta = read_pyproject_subset(pyproject.read_text(encoding="utf-8"))
        project = meta.get("project", {})
        staticsite = meta.get("tool.staticsite", {})

        name = project.get("name")
        if name != slug:
            raise SystemExit(
                "{}: [project].name is {!r}, expected to match the directory name"
                .format(slug, name))
        title = staticsite.get("title")
        if not title:
            raise SystemExit(
                "{}: missing [tool.staticsite].title -- add it (see AGENTS.md)"
                .format(slug))
        description = project.get("description", "")
        prefix = title + TITLE_SEP
        if description.startswith(prefix):
            description = description[len(prefix):]

        output = "{0}/output/{0}.html".format(slug)
        if not (project_dir / "output" / (slug + ".html")).exists():
            raise SystemExit(
                "{}: expected built artifact {} is missing -- run `make` there"
                .format(slug, output))

        sites.append({
            "slug": slug,
            "title": title,
            "description": description,
            "output": output,
        })
    return sites


def render(sites):
    """Deterministic JSON text: sorted keys are already fixed by insertion, so
    only indentation and a trailing newline need pinning."""
    return json.dumps(sites, indent=2, ensure_ascii=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true",
        help="don't write; exit 1 if sites.json is out of date")
    args = parser.parse_args()

    content = render(collect_sites())

    if args.check:
        current = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else ""
        if current != content:
            sys.stderr.write(
                "sites.json is out of date -- run ./generate_manifest.py and "
                "commit the result.\n")
            return 1
        print("sites.json is up to date.")
        return 0

    MANIFEST.write_text(content, encoding="utf-8")
    print("Wrote {} ({} site(s)).".format(MANIFEST.name, content.count('"slug"')))
    return 0


if __name__ == "__main__":
    sys.exit(main())
