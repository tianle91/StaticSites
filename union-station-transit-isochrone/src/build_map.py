#!/usr/bin/env python3
"""Build a self-contained interactive Leaflet map of transit isochrones around
Union Station (30 / 60 / 90 / 120 minutes) from isochrones.geojson and
transit_model.json.

Stdlib only - no pip install, no network needed at build time. The generated
index.html needs the internet only for OpenStreetMap tiles.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (src/ is one level down)
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
GEO = json.loads((OUT_DIR / "isochrones.geojson").read_text(encoding="utf-8"))
MODEL = json.loads((DATA_DIR / "transit_model.json").read_text(encoding="utf-8"))
# Per-station step-by-step trips to Union (from `make data`); empty without it.
_REACH = DATA_DIR / "reachability.json"
STATIONS = json.loads(_REACH.read_text(encoding="utf-8")).get("stations", []) \
    if _REACH.exists() else []

MODE_COLOR = {
    "origin": "#000000",
    "subway": "#1f78b4",
    "go": "#1b7a3d",
    "up": "#9b59b6",
    "streetcar": "#e31a1c",
    "bus": "#ff7f00",
}
MODE_LABEL = {
    "subway": "Subway",
    "go": "GO Rail",
    "up": "UP Express",
    "streetcar": "Streetcar",
    "bus": "Bus",
}

def _generated_at() -> str:
    """Use recorded provenance rather than filesystem dates, which vary by clone."""
    if _REACH.exists():
        stamp = json.loads(_REACH.read_text(encoding="utf-8")).get("generated_at")
        if stamp:
            return str(stamp)[:10]
    return str(MODEL.get("generated_at", ""))[:10]


PAYLOAD = json.dumps({
    "geo": GEO,
    "origin": MODEL["origin"],
    "bands": MODEL["bands"],
    "nodes": MODEL["nodes"],
    "service_assumption": MODEL["service_assumption"],
    "generated_at": _generated_at(),
    "stations": STATIONS,
    "mode_color": MODE_COLOR,
    "mode_label": MODE_LABEL,
}, indent=2, ensure_ascii=False)

HTML = (ROOT / "src/page.html").read_text(encoding="utf-8")


def main():
    # Escape "<" so a field value like "</script>" (or "<!--") in the embedded
    # JSON can't close the <script> element and break the page. These become
    # < inside the JSON string literals, leaving the parsed data unchanged.
    out = HTML
    for token, filename in [("__EXPLORER_CSS__", "explorer.css"), ("__EXPLORER_JS__", "explorer.js"), ("__APP_JS__", "app.js")]:
        out = out.replace(token, (ROOT / "src" / filename).read_text(encoding="utf-8"))
    out = out.replace("__PAYLOAD__", PAYLOAD.replace("<", "\\u003c"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "union-station-transit-isochrone.html"
    target.write_text(out, encoding="utf-8")
    n_nodes = sum(1 for n in MODEL["nodes"] if n["mode"] != "origin")
    print(f"Wrote {target} ({len(GEO['features'])} bands, {n_nodes} stations)")


if __name__ == "__main__":
    main()
