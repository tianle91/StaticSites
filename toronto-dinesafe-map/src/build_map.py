#!/usr/bin/env python3
"""Build a self-contained interactive Leaflet map of Toronto's DineSafe
food-safety inspection results from data/dinesafe.json.

Stdlib only - no pip install, no network needed at build time. One pin per
establishment, coloured by the result of its most recent inspection (Pass /
Conditional Pass / Closed). Markers are drawn on a canvas renderer because the
full city dataset is ~16k establishments; plain DOM markers would be too heavy.

Coordinates and the per-establishment reduction come from `make data`
(fetch_data.py). Statuses reflect the latest inspection on record and can change
- always confirm current status on the official DineSafe site before relying on
a pin.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (src/ is one level down)
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
DATA = json.loads((DATA_DIR / "dinesafe.json").read_text(encoding="utf-8"))

# DineSafe reports one of three establishment statuses; anything else is grouped
# under "Other" so an unexpected value never silently drops a pin.
STATUS_CATEGORIES = {
    "pass": {"label": "Pass", "color": "#2e7d32"},
    "conditional": {"label": "Conditional Pass", "color": "#f39c12"},
    "closed": {"label": "Closed / Suspended", "color": "#c0392b"},
    "other": {"label": "Other / Unknown", "color": "#777777"},
}


def status_key(status: str) -> str:
    s = (status or "").strip().lower()
    if s.startswith("pass"):
        return "pass"
    if "conditional" in s:
        return "conditional"
    if "close" in s or "suspend" in s:
        return "closed"
    return "other"


# Attach a category key to each establishment and drop rows without a location.
# Also normalise every establishment to an `inspections` timeline the sidebar can
# always render: newer data from `make data` carries the full per-inspection
# history; an older summary-only data/dinesafe.json is back-filled with a single
# entry synthesised from its latest-inspection fields so the sidebar still works.
establishments = []
counts = {k: 0 for k in STATUS_CATEGORIES}
for e in DATA.get("establishments", []):
    if e.get("lat") is None or e.get("lon") is None:
        continue
    key = status_key(e.get("status"))
    e = dict(e)
    e["cat"] = key
    # Newer data from `make data` carries a per-inspection `inspections` timeline;
    # enrich each entry with its status colour-key and infraction count so the
    # sidebar can render it directly. An older summary-only data/dinesafe.json has
    # no timeline - the page synthesises a single entry from the summary fields at
    # display time (see openSidebar), so we don't bloat the payload here.
    inspections = e.get("inspections")
    if inspections:
        for ins in inspections:
            ins["cat"] = status_key(ins.get("status"))
            ins["infraction_count"] = len(ins.get("infractions") or [])
    counts[key] += 1
    establishments.append(e)

CENTER = [43.6532, -79.3832]  # downtown Toronto; the user's location recenters when permitted
ZOOM = 13

PAYLOAD = json.dumps(
    {
        "categories": STATUS_CATEGORIES,
        "establishments": establishments,
        "center": CENTER,
        "zoom": ZOOM,
        "meta": {
            "generated_at": DATA.get("generated_at", ""),
            "source_page": DATA.get("source_page", "https://open.toronto.ca/dataset/dinesafe/"),
            "total": len(establishments),
            "counts": counts,
            "sample": bool(DATA.get("sample")),
        },
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
    target = OUT_DIR / "toronto-dinesafe-map.html"
    target.write_text(out, encoding="utf-8")
    breakdown = ", ".join(
        f"{counts[k]} {STATUS_CATEGORIES[k]['label']}" for k in STATUS_CATEGORIES if counts[k]
    )
    print(f"Wrote {target} ({len(establishments)} establishments: {breakdown})")


if __name__ == "__main__":
    main()
