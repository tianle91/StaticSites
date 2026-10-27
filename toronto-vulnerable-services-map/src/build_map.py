#!/usr/bin/env python3
"""Build a self-contained interactive Leaflet map of Toronto/Ontario services
for vulnerable populations from services.json.

Stdlib only - no pip install, no network needed at build time. The generated
index.html pulls live shelter-occupancy stats from the Toronto Open Data API
client-side (in the browser) when opened with an internet connection.
"""
import datetime
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (src/ is one level down)
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
DATA = json.loads((DATA_DIR / "services.json").read_text(encoding="utf-8"))

# Optional artifacts produced by `make data` (fetch_data.py). Absent on a fresh
# offline build - the map still works from the curated locations alone.
CACHE_PATH = DATA_DIR / "geocode_cache.json"
SHELTERS_PATH = DATA_DIR / "shelters.json"
SHELTER_CATEGORY = {"label": "Shelter / Overnight (live)", "color": "#b15928"}

CATEGORIES = dict(DATA["categories"])
DIRECTORIES = DATA["directories"]
CENTER = DATA["map_center"]
ZOOM = DATA["map_zoom"]


def _load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# Refine curated pins with geocoded coordinates where available.
cache = _load(CACHE_PATH) or {}
LOCATIONS = []
for loc in DATA["locations"]:
    loc = dict(loc)
    coord = cache.get(loc.get("address"))
    if coord:
        loc["lat"], loc["lon"] = coord[0], coord[1]
    LOCATIONS.append(loc)

# Merge in geocoded shelter locations as their own toggleable layer.
shelters = _load(SHELTERS_PATH)
shelter_count = 0
shelter_meta = None
if shelters and shelters.get("locations"):
    CATEGORIES["shelter"] = SHELTER_CATEGORY
    LOCATIONS.extend(shelters["locations"])
    shelter_count = len(shelters["locations"])
    # "pulled" date: prefer the recorded timestamp, else fall back to the file mtime.
    pulled = shelters.get("generated_at")
    if not pulled:
        pulled = datetime.date.fromtimestamp(SHELTERS_PATH.stat().st_mtime).isoformat()
    shelter_meta = {"snapshot": shelters.get("date", ""), "pulled": pulled, "count": shelter_count}

# Data passed to the browser as JSON (only what the page needs).
PAYLOAD = json.dumps(
    {
        "categories": CATEGORIES,
        "locations": LOCATIONS,
        "directories": DIRECTORIES,
        "center": CENTER,
        "zoom": ZOOM,
        "shelter_meta": shelter_meta,
    },
    indent=2,
    ensure_ascii=False,
)

HTML = (ROOT / "src/page.html").read_text(encoding="utf-8")


def main() -> None:
    # Escape "<" so a field value like "</script>" (or "<!--") in the embedded
    # JSON can't close the <script> element and break the page. These become
    # < inside the JSON string literals, leaving the parsed data unchanged.
    out = HTML
    for token, filename in [("__EXPLORER_CSS__", "explorer.css"), ("__EXPLORER_JS__", "explorer.js"), ("__APP_JS__", "app.js")]:
        out = out.replace(token, (ROOT / "src" / filename).read_text(encoding="utf-8"))
    out = out.replace("__PAYLOAD__", PAYLOAD.replace("<", "\\u003c"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "toronto-vulnerable-services-map.html"
    target.write_text(out, encoding="utf-8")
    curated = len(LOCATIONS) - shelter_count
    print(f"Wrote {target} ({curated} curated locations + {shelter_count} live shelter "
          f"locations, {len(DIRECTORIES)} directory links)")


if __name__ == "__main__":
    main()
