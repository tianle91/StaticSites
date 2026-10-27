#!/usr/bin/env python3
"""Render a portable HTML map from committed data and browser libraries, offline."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"


def render(data_dir=DATA_DIR):
    data = json.loads((data_dir / "crimes.json").read_text(encoding="utf-8"))
    template = (ROOT / "src" / "map.html").read_text(encoding="utf-8")
    # Escape script terminators even if a future upstream text contains HTML.
    payload = json.dumps(data, indent=2, ensure_ascii=False).replace("<", "\\u003c")
    template = template.replace("__APP__", (ROOT / "src" / "map.js").read_text(encoding="utf-8"))
    template = template.replace("__DATA__", payload)
    for key, files in {
        "__CSS__": ["leaflet.css", "markercluster.css", "markercluster-default.css"],
        "__JS__": ["leaflet.js", "markercluster.js"],
    }.items():
        template = template.replace(key, "\n".join((data_dir / name).read_text(encoding="utf-8") for name in files))
    return template


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "toronto-crime-map.html"
    html = render()
    if not target.exists() or target.read_text(encoding="utf-8") != html:
        target.write_text(html, encoding="utf-8")
    print(f"Built {target} ({len(html):,} characters)")


if __name__ == "__main__":
    main()
