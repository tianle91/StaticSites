#!/usr/bin/env python3
"""Build a self-contained interactive Leaflet map of Ontario's publicly-funded
physiotherapy clinics from clinics.json.

Stdlib only - no pip install, no network needed at build time. Marker
coordinates come from `make data` (fetch_data.py); addresses that Nominatim
could only resolve to a city land on that city's centre, so treat pins as
approximate and phone ahead.
"""
import json
import pathlib
from staticsites.assets import source_text, read_template
from staticsites.assets import script_json
from staticsites.pipeline import write_if_changed

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (src/ is one level down)
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
DATA = json.loads((DATA_DIR / "clinics.json").read_text(encoding="utf-8"))

CATEGORIES = {
    "clinic": {"label": "Community physiotherapy clinic", "color": "#1f78b4"},
    "hospital": {"label": "Hospital", "color": "#b15928"},
}
CENTER = [44.0, -79.5]  # southern Ontario; overridden by fitBounds once pins load
ZOOM = 7

PAYLOAD = script_json({
        "categories": CATEGORIES,
        "clinics": DATA["clinics"],
        "center": CENTER,
        "zoom": ZOOM,
        "meta": {
            "generated_at": DATA.get("generated_at", ""),
            "source_page": DATA.get("source_page", ""),
            "total_records": DATA.get("total_records", len(DATA["clinics"])),
            "mapped": len(DATA["clinics"]),
            "city_only": sum(1 for c in DATA["clinics"] if c.get("precision") == "city"),
        },
    })

HTML = read_template(ROOT / "src/page.html")


def main() -> None:
    # Escape "<" so a field value like "</script>" (or "<!--") in the embedded
    # JSON can't close the <script> element and break the page. These become
    # < inside the JSON string literals, leaving the parsed data unchanged.
    out = HTML
    for token, filename in [("__EXPLORER_CSS__", "explorer.css"), ("__EXPLORER_JS__", "explorer.js"), ("__APP_JS__", "app.js")]:
        out = out.replace(token, source_text(ROOT, filename))
    out = out.replace("__PAYLOAD__", PAYLOAD.replace("<", "\\u003c"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "ontario-physiotherapy-clinics-map.html"
    write_if_changed(target, out)
    by_cat = {}
    for c in DATA["clinics"]:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    breakdown = ", ".join(f"{n} {k}" for k, n in sorted(by_cat.items()))
    print(f"Wrote {target} ({len(DATA['clinics'])} mapped locations: {breakdown})")


if __name__ == "__main__":
    main()
