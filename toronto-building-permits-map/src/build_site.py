#!/usr/bin/env python3
"""Build the single-file map offline from the committed snapshot and template."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"


def render(data):
    # Escape HTML script terminators even when they appear in upstream text.
    payload = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template = (ROOT / "src/page.html").read_text(encoding="utf-8")
    for token, filename in [("__EXPLORER_CSS__", "explorer.css"), ("__EXPLORER_JS__", "explorer.js"), ("__APP_JS__", "app.js")]:
        template = template.replace(token, (ROOT / "src" / filename).read_text(encoding="utf-8"))
    template = template.replace("__CLUSTER_CSS__", "\n".join((ROOT / "src/vendor" / name).read_text(encoding="utf-8") for name in ["markercluster.css", "markercluster-default.css"]))
    license_text = (ROOT / "src/vendor/LICENSE.txt").read_text(encoding="utf-8")
    cluster_js = (ROOT / "src/vendor/markercluster.js").read_text(encoding="utf-8")
    template = template.replace("__CLUSTER_JS__", "/*\n" + license_text + "*/\n" + cluster_js)
    return template.replace("__PAYLOAD__", payload)


def main():
    data = json.loads((DATA_DIR / "permits.json").read_text(encoding="utf-8"))
    html = render(data)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "toronto-building-permits-map.html"
    if not path.exists() or path.read_text(encoding="utf-8") != html:
        path.write_text(html, encoding="utf-8")
    print("Built " + str(path))


if __name__ == "__main__":
    main()
