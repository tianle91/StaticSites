#!/usr/bin/env python3
"""Build the single-file map offline from the committed snapshot and template."""
import json
import pathlib
from staticsites.assets import source_text, read_template
from staticsites.assets import script_json
from staticsites.pipeline import write_if_changed

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"


def render(data):
    # Escape HTML script terminators even when they appear in upstream text.
    payload = script_json(data)
    template = read_template(ROOT / "src/page.html")
    for token, filename in [("__EXPLORER_CSS__", "explorer.css"), ("__EXPLORER_JS__", "explorer.js"), ("__APP_JS__", "app.js")]:
        template = template.replace(token, source_text(ROOT, filename))
    return template.replace("__PAYLOAD__", payload)


def main():
    data = json.loads((DATA_DIR / "floodplain.json").read_text(encoding="utf-8"))
    html = render(data)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "trca-flood-plain-map.html"
    write_if_changed(path, html)
    print("Built " + str(path))


if __name__ == "__main__":
    main()
