#!/usr/bin/env python3
"""Build the single-file map offline from the committed snapshot and template."""
import hashlib
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
    for token, filename in [("__STARTUP_JS__", "startup.js"), ("__QUERY_JS__", "query.js"), ("__SEARCH_JS__", "search.js"), ("__EXPLORER_CSS__", "explorer.css"), ("__EXPLORER_JS__", "explorer.js"), ("__APP_JS__", "app.js")]:
        template = template.replace(token, source_text(ROOT, filename))
    template = template.replace("__CLUSTER_CSS__", "\n".join((ROOT / "src/vendor" / name).read_text(encoding="utf-8") for name in ["markercluster.css", "markercluster-default.css"]))
    license_text = (ROOT / "src/vendor/LICENSE.txt").read_text(encoding="utf-8")
    cluster_js = (ROOT / "src/vendor/markercluster.js").read_text(encoding="utf-8")
    template = template.replace("__CLUSTER_JS__", "/*\n" + license_text + "*/\n" + cluster_js)
    # Hash the code and data so phone diagnostics identify the exact artifact.
    build_id = hashlib.sha256((template + payload).encode("utf-8")).hexdigest()[:12]
    return template.replace("__BUILD_ID__", build_id).replace("__PAYLOAD__", payload)


def main():
    data = json.loads((DATA_DIR / "permits.json").read_text(encoding="utf-8"))
    html = render(data)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "toronto-building-permits-map.html"
    write_if_changed(path, html)
    print("Built " + str(path))


if __name__ == "__main__":
    main()
