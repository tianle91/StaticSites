#!/usr/bin/env python3
"""Render a portable HTML map from committed data and browser libraries, offline."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"


def prepare_payload(data):
    """Group by published incident ID without discarding offence/victim rows.

    Points are deliberately retained on each row: a few incident IDs have more
    than one published location, including differences between police feeds.
    """
    id_index = data["columns"].index("event_id")
    incidents = {}
    for row in data["rows"]:
        incidents.setdefault(row[id_index], []).append(row)
    return {**{k: v for k, v in data.items() if k != "rows"},
            "incidents": [{"id": key, "rows": rows} for key, rows in incidents.items()]}


def render(data_dir=DATA_DIR):
    data = prepare_payload(json.loads((data_dir / "crimes.json").read_text(encoding="utf-8")))
    template = (ROOT / "src/page.html").read_text(encoding="utf-8")
    for token, filename in [("__EXPLORER_CSS__", "explorer.css"), ("__EXPLORER_JS__", "explorer.js"), ("__APP_JS__", "app.js")]:
        template = template.replace(token, (ROOT / "src" / filename).read_text(encoding="utf-8"))
    for key, files in {
        "__CSS__": ["leaflet.css", "markercluster.css", "markercluster-default.css"],
        "__JS__": ["leaflet.js", "markercluster.js"],
    }.items():
        template = template.replace(key, "\n".join((data_dir / name).read_text(encoding="utf-8") for name in files))
    # Insert data last so upstream text cannot be mistaken for template tokens.
    return template.replace("__PAYLOAD__", json.dumps(data, indent=2, ensure_ascii=False).replace("<", "\\u003c"))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "toronto-crime-map.html"
    html = render()
    if not target.exists() or target.read_text(encoding="utf-8") != html:
        target.write_text(html, encoding="utf-8")
    print(f"Built {target} ({len(html):,} characters)")


if __name__ == "__main__":
    main()
