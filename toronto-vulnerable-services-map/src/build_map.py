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
    ensure_ascii=False,
)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Toronto &amp; Ontario Vulnerable-Population Services Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
<style>
  html, body { margin: 0; height: 100%; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
  #map { position: absolute; inset: 0; }
  .panel {
    position: absolute; top: 10px; right: 10px; z-index: 1000; width: 320px;
    max-height: calc(100% - 20px); overflow: auto; background: #fff;
    border-radius: 8px; box-shadow: 0 1px 6px rgba(0,0,0,.3); padding: 12px 14px;
  }
  .panel h1 { font-size: 16px; margin: 0 0 4px; }
  .panel h2 { font-size: 13px; margin: 14px 0 6px; text-transform: uppercase; letter-spacing: .03em; color: #555; }
  .panel p { font-size: 12px; color: #444; margin: 4px 0; }
  .panel a { color: #1f78b4; text-decoration: none; }
  .panel a:hover { text-decoration: underline; }
  .sources { font-size: 12px; color: #444; margin: 4px 0; padding-left: 18px; }
  .sources li { margin: 3px 0; }
  .dir { font-size: 12px; margin: 6px 0; }
  .dir .note { color: #666; display: block; }
  #stats { font-size: 12px; background: #f3f7fb; border: 1px solid #d6e4f0; border-radius: 6px; padding: 8px; }
  #stats b { font-size: 16px; color: #1f78b4; }
  .legend-row { display: flex; align-items: center; font-size: 12px; margin: 3px 0; }
  .dot { width: 12px; height: 12px; border-radius: 50%; margin-right: 7px; border: 1px solid rgba(0,0,0,.3); }
  .leaflet-popup-content { font-size: 13px; }
  .leaflet-popup-content .cat { font-size: 11px; text-transform: uppercase; letter-spacing: .03em; }
  details > summary { cursor: pointer; font-weight: 600; font-size: 13px; margin-top: 10px; }
  .toggle { position: absolute; top: 10px; right: 10px; z-index: 1001; display: none;
    background: #fff; border: none; border-radius: 6px; padding: 8px 10px; box-shadow: 0 1px 6px rgba(0,0,0,.3); cursor: pointer; }
  @media (max-width: 620px) {
    .panel { width: auto; left: 10px; right: 10px; max-height: 55%; display: none; }
    .toggle { display: block; }
  }
</style>
</head>
<body>
<div id="map"></div>
<button class="toggle" id="toggle">Info</button>
<div class="panel" id="panel">
  <h1>Toronto &amp; Ontario Services</h1>
  <p>Shelters, warming &amp; respite centres, food, harm reduction and housing supports for vulnerable residents.</p>

  <div id="stats">Loading live shelter data&hellip;</div>

  <div id="shelter-meta" style="font-size:11px;color:#666;margin-top:6px"></div>

  <h2>Legend</h2>
  <div id="legend"></div>

  <h2>Directories &amp; Data</h2>
  <div id="directories"></div>

  <h2>Data sources</h2>
  <ul class="sources">
    <li>Curated service locations &mdash; compiled from the City/Province pages linked above; see the
      <a href="https://github.com/tianle91/StaticSites/blob/main/toronto-vulnerable-services-map/data/SOURCES.md" target="_blank" rel="noopener">Sources document</a></li>
    <li>Live shelter occupancy &mdash;
      <a href="https://open.toronto.ca/dataset/daily-shelter-overnight-service-occupancy-capacity/" target="_blank" rel="noopener">Toronto Open Data</a>
      (Daily Shelter &amp; Overnight Service Occupancy)</li>
    <li>Geocoding &amp; map tiles &mdash; &copy;
      <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors
      (via Nominatim)</li>
  </ul>

  <details>
    <summary>Notes &amp; caveats</summary>
    <p>Warming and respite sites are <b>seasonal</b> - confirm open/close status on the live City pages. Harm-reduction sites are volatile (several Ontario sites closed/relocated in 2025). Marker coordinates are approximate (from street addresses). For emergency shelter, call Central Intake <b>416-338-4766</b> or <b>311</b>.</p>
  </details>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
const DATA = __PAYLOAD__;

const map = L.map('map').setView(DATA.center, DATA.zoom);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// One toggleable layer per category.
const layers = {};
for (const key in DATA.categories) layers[key] = L.layerGroup().addTo(map);

function markerIcon(color) {
  return L.divIcon({
    className: '',
    html: '<div style="width:16px;height:16px;border-radius:50%;background:' + color +
          ';border:2px solid #fff;box-shadow:0 0 3px rgba(0,0,0,.5)"></div>',
    iconSize: [16, 16], iconAnchor: [8, 8], popupAnchor: [0, -8]
  });
}

const bounds = [];
for (const loc of DATA.locations) {
  const cat = DATA.categories[loc.category] || { label: loc.category, color: '#555' };
  const popup =
    '<b>' + loc.name + '</b><br>' +
    '<span class="cat" style="color:' + cat.color + '">' + cat.label + '</span><br>' +
    (loc.address ? loc.address + '<br>' : '') +
    (loc.notes ? '<span style="color:#555">' + loc.notes + '</span><br>' : '') +
    (loc.url ? '<a href="' + loc.url + '" target="_blank" rel="noopener">More info &rarr;</a>' : '');
  L.marker([loc.lat, loc.lon], { icon: markerIcon(cat.color), title: loc.name })
    .bindPopup(popup)
    .addTo(layers[loc.category]);
  bounds.push([loc.lat, loc.lon]);
}
if (bounds.length) map.fitBounds(bounds, { padding: [40, 40] });

// Layer toggle control + legend.
const overlays = {};
const legend = document.getElementById('legend');
for (const key in DATA.categories) {
  const c = DATA.categories[key];
  overlays[c.label] = layers[key];
  const row = document.createElement('div');
  row.className = 'legend-row';
  row.innerHTML = '<span class="dot" style="background:' + c.color + '"></span>' + c.label;
  legend.appendChild(row);
}
L.control.layers(null, overlays, { collapsed: false }).addTo(map);

// Shelter-layer provenance: snapshot date + when the data was pulled.
if (DATA.shelter_meta) {
  const m = DATA.shelter_meta;
  document.getElementById('shelter-meta').innerHTML =
    'Shelter pins: ' + m.count + ' locations &middot; occupancy ' + (m.snapshot || 'n/a') +
    ' &middot; data pulled ' + (m.pulled || 'n/a');
}

// Center on the user's location when available/permitted (button + auto-attempt).
let youMarker = null;
function locate() {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(
    pos => {
      const ll = [pos.coords.latitude, pos.coords.longitude];
      if (youMarker) youMarker.setLatLng(ll);
      else youMarker = L.marker(ll, { icon: L.divIcon({
          className: '',
          html: '<div style="width:20px;height:20px;position:relative">' +
                '<div style="position:absolute;top:50%;left:0;right:0;height:3px;background:#e63946;transform:translateY(-50%)"></div>' +
                '<div style="position:absolute;left:50%;top:0;bottom:0;width:3px;background:#e63946;transform:translateX(-50%)"></div>' +
                '<div style="position:absolute;top:50%;left:50%;width:8px;height:8px;background:#e63946;border:2px solid #fff;border-radius:50%;transform:translate(-50%,-50%)"></div>' +
                '</div>',
          iconSize: [20, 20], iconAnchor: [10, 10], popupAnchor: [0, -10]
        }) }).addTo(map).bindPopup('You are here');
      map.setView(ll, 14);
    },
    () => {},  // denied/unavailable: keep the default Toronto view
    { enableHighAccuracy: true, timeout: 8000 }
  );
}
const LocateControl = L.Control.extend({
  options: { position: 'topleft' },
  onAdd() {
    const a = L.DomUtil.create('a', 'leaflet-bar leaflet-control');
    a.href = '#';
    a.title = 'Center on my location';
    a.innerHTML = '&#9678;';
    a.style.cssText = 'width:30px;height:30px;line-height:30px;text-align:center;font-size:18px;background:#fff;';
    L.DomEvent.on(a, 'click', e => { L.DomEvent.preventDefault(e); locate(); });
    return a;
  },
});
map.addControl(new LocateControl());
locate();  // use the user's location if the browser provides it

// Directories list.
const dirs = document.getElementById('directories');
for (const d of DATA.directories) {
  const el = document.createElement('div');
  el.className = 'dir';
  el.innerHTML = '<a href="' + d.url + '" target="_blank" rel="noopener">' + d.name + '</a>' +
                 (d.note ? '<span class="note">' + d.note + '</span>' : '');
  dirs.appendChild(el);
}

// Mobile info toggle.
const panel = document.getElementById('panel');
const toggle = document.getElementById('toggle');
toggle.addEventListener('click', () => {
  const shown = panel.style.display === 'block';
  panel.style.display = shown ? 'none' : 'block';
  toggle.textContent = shown ? 'Info' : 'Close';
});

// Live shelter occupancy from Toronto Open Data (CKAN). Graceful if offline/CORS-blocked.
const CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca';
const DATASET = 'daily-shelter-overnight-service-occupancy-capacity';
async function loadShelterStats() {
  const stats = document.getElementById('stats');
  try {
    const pkg = await fetch(CKAN + '/api/3/action/package_show?id=' + DATASET).then(r => r.json());
    const active = pkg.result.resources.filter(r => r.datastore_active);
    if (!active.length) throw new Error('no active resource');
    active.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    const rid = active[active.length - 1].id;
    // SQL endpoint is disabled on Toronto's CKAN; use datastore_search + aggregate here.
    const ds = '/api/3/action/datastore_search?resource_id=' + rid;
    const top = await fetch(CKAN + ds + '&limit=1&sort=' + encodeURIComponent('OCCUPANCY_DATE desc')).then(r => r.json());
    const recs = top.result.records;
    if (!recs.length) throw new Error('no records');
    const dayRaw = recs[0].OCCUPANCY_DATE;
    const filt = encodeURIComponent(JSON.stringify({ OCCUPANCY_DATE: dayRaw }));
    const all = await fetch(CKAN + ds + '&limit=10000&filters=' + filt).then(r => r.json());
    const rows = all.result.records;
    let users = 0; const locs = new Set();
    for (const r of rows) { users += Number(r.SERVICE_USER_COUNT) || 0; locs.add(r.LOCATION_ID); }
    const day = String(dayRaw).slice(0, 10);
    stats.innerHTML =
      '<b>' + users.toLocaleString() + '</b> people served<br>' +
      'across <b>' + rows.length + '</b> programs at <b>' + locs.size + '</b> locations<br>' +
      '<span style="color:#666">Toronto shelter system, ' + day + ' &middot; ' +
      '<a href="https://open.toronto.ca/dataset/' + DATASET + '/" target="_blank" rel="noopener">source</a></span>';
  } catch (e) {
    stats.innerHTML = '<span style="color:#888">Live shelter stats unavailable offline. ' +
      '<a href="https://open.toronto.ca/dataset/' + DATASET + '/" target="_blank" rel="noopener">Open the dataset &rarr;</a></span>';
  }
}
loadShelterStats();
</script>
</body>
</html>
"""


def main() -> None:
    # Escape "<" so a field value like "</script>" (or "<!--") in the embedded
    # JSON can't close the <script> element and break the page. These become
    # < inside the JSON string literals, leaving the parsed data unchanged.
    out = HTML.replace("__PAYLOAD__", PAYLOAD.replace("<", "\\u003c"))
    target = OUT_DIR / "toronto-vulnerable-services-map.html"
    target.write_text(out, encoding="utf-8")
    curated = len(LOCATIONS) - shelter_count
    print(f"Wrote {target} ({curated} curated locations + {shelter_count} live shelter "
          f"locations, {len(DIRECTORIES)} directory links)")


if __name__ == "__main__":
    main()
