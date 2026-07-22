#!/usr/bin/env python3
"""Build a self-contained interactive Leaflet map of transit isochrones around
Union Station (30 / 60 / 90 / 120 minutes) from isochrones.geojson and
transit_model.json.

Stdlib only - no pip install, no network needed at build time. The generated
index.html needs the internet only for OpenStreetMap tiles.
"""
import datetime
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
    """When the reachability bands were last computed by `make data`. Prefer the
    stamp in the model; fall back to the data file's date so the page always
    carries a data-pulled date."""
    stamp = MODEL.get("generated_at")
    if stamp:
        return str(stamp)[:10]
    return datetime.date.fromtimestamp((DATA_DIR / "transit_model.json").stat().st_mtime).isoformat()


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
}, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Union Station Transit Isochrones</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
<style>
  html, body { margin: 0; height: 100%; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
  #map { position: absolute; inset: 0; }
  .panel {
    position: absolute; top: 10px; right: 10px; z-index: 1000; width: 300px;
    max-height: calc(100% - 20px); overflow: auto; background: #fff;
    border-radius: 8px; box-shadow: 0 1px 6px rgba(0,0,0,.3); padding: 12px 14px;
  }
  .panel h1 { font-size: 16px; margin: 0 0 4px; }
  .panel h2 { font-size: 12px; margin: 14px 0 6px; text-transform: uppercase; letter-spacing: .03em; color: #555; }
  .panel p { font-size: 12px; color: #444; margin: 4px 0; }
  .panel a { color: #1f78b4; text-decoration: none; }
  .panel a:hover { text-decoration: underline; }
  .sources { font-size: 12px; color: #444; margin: 4px 0; padding-left: 18px; }
  .sources li { margin: 3px 0; }
  .legend-row { display: flex; align-items: center; font-size: 12px; margin: 4px 0; }
  .swatch { width: 14px; height: 14px; border-radius: 3px; margin-right: 8px; border: 1px solid rgba(0,0,0,.25); }
  .dot { width: 11px; height: 11px; border-radius: 50%; margin-right: 8px; border: 1px solid rgba(0,0,0,.3); }
  #result { font-size: 12px; background: #f3f7fb; border: 1px solid #d6e4f0; border-radius: 6px; padding: 8px; }
  #result b { font-size: 15px; }
  .itin { margin-top: 8px; border-top: 1px solid #d6e4f0; padding-top: 6px; }
  .itin-h { margin-bottom: 4px; }
  .itin-h b { font-size: 12px; }
  .itin ul { margin: 4px 0 0; padding-left: 16px; }
  .itin li { margin: 2px 0; }
  .itin li b { font-size: 12px; }
  .legstops { color: #667; }
  details > summary { cursor: pointer; font-weight: 600; font-size: 12px; margin-top: 10px; }
  .leaflet-popup-content { font-size: 13px; }
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
  <h1>Morning commute to Union Station</h1>
  <p>Where you can live and still reach Toronto&rsquo;s Union Station by public
     transit in 30&nbsp;min, 1&nbsp;h, 1.5&nbsp;h and 2&nbsp;h, arriving during the
     weekday morning peak &mdash; subway, streetcar, bus, GO rail and UP Express,
     plus the walk at each end.</p>

  <div id="result">Click anywhere on the map to estimate the transit trip to Union.</div>

  <h2>Time bands</h2>
  <div id="legend"></div>

  <h2>Stations</h2>
  <div id="modes"></div>

  <h2>Assumptions</h2>
  <p id="assume"></p>

  <h2>Data sources</h2>
  <ul class="sources">
    <li>Street &amp; walk network:
      <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>
      (&copy; OpenStreetMap contributors), via a
      <a href="https://download.geofabrik.de/north-america/canada/ontario.html" target="_blank" rel="noopener">Geofabrik</a> extract</li>
    <li>TTC subway / streetcar / bus schedules (GTFS):
      <a href="https://open.toronto.ca/dataset/ttc-routes-and-schedules/" target="_blank" rel="noopener">Toronto Open Data</a></li>
    <li>GO Transit &amp; UP Express schedules (GTFS):
      <a href="https://www.metrolinx.com/en/about-us/open-data" target="_blank" rel="noopener">Metrolinx Open Data</a></li>
    <li>Multimodal transit routing:
      <a href="https://r5py.readthedocs.io/" target="_blank" rel="noopener">r5py</a> (Conveyal R5)</li>
    <li>Map tiles: &copy;
      <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors</li>
  </ul>
  <p id="generated" style="color:#666;font-size:12px"></p>

  <details>
    <summary>Method &amp; caveats</summary>
    <p>Each band is the area from which you can <i>reach</i> Union Station within
       that time, arriving during the weekday morning peak. It is computed by
       routing a grid of points to Union with r5py &mdash; real multimodal transit
       (subway + streetcar + bus + GO + UP) including the walk at each end &mdash;
       and tracing the reachable area, assuming you time your departure to catch
       service. <b>GO &amp; UP service varies a lot by time of day</b> and several
       GO lines run peak-direction only, so reach is larger in the morning peak
       than off-peak. Coordinates and grid are approximate.</p>
  </details>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
const DATA = __PAYLOAD__;

const map = L.map('map').setView([DATA.origin.lat, DATA.origin.lon], 11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// --- Isochrone band layers (drawn largest-first so shorter times sit on top) ---
const bandLayers = {};      // minutes -> L.GeoJSON
const bandByMin = {};       // minutes -> band meta
for (const b of DATA.bands) bandByMin[b.minutes] = b;

const feats = DATA.geo.features.slice().sort((a, b) => b.properties.minutes - a.properties.minutes);
const overlays = {};
for (const f of feats) {
  const color = f.properties.color;
  const layer = L.geoJSON(f, {
    style: { color: color, weight: 1.5, opacity: 0.9, fillColor: color, fillOpacity: 0.28 }
  }).addTo(map);
  bandLayers[f.properties.minutes] = layer;
  overlays[f.properties.label] = layer;
}

// Origin marker.
L.marker([DATA.origin.lat, DATA.origin.lon], {
  icon: L.divIcon({ className: '', iconSize: [22, 22], iconAnchor: [11, 11],
    html: '<div style="font-size:20px;line-height:22px;text-align:center">&#9733;</div>' }),
  title: 'Union Station', zIndexOffset: 1000
}).bindPopup('<b>Union Station</b><br>Origin (0 min)').addTo(map);

// --- Station markers (toggleable layer) ---
const stationLayer = L.layerGroup();
function stationIcon(color) {
  return L.divIcon({ className: '',
    html: '<div style="width:9px;height:9px;border-radius:50%;background:' + color +
          ';border:1.5px solid #fff;box-shadow:0 0 2px rgba(0,0,0,.6)"></div>',
    iconSize: [9, 9], iconAnchor: [4.5, 4.5], popupAnchor: [0, -5] });
}
const STN_BY_NAME = {};
for (const s of (DATA.stations || [])) STN_BY_NAME[s.name] = s;
for (const n of DATA.nodes) {
  if (n.mode === 'origin') continue;
  const color = DATA.mode_color[n.mode] || '#555';
  let popup = '<b>' + n.name + '</b><br>' + n.line + ' &middot; ' +
              (DATA.mode_label[n.mode] || n.mode) + '<br>';
  const s = STN_BY_NAME[n.name];
  if (s && s.legs && s.legs.length) {
    popup += '<b>' + s.minutes + ' min</b> to Union (morning peak):' + legsUl(s.legs);
  } else {
    popup += '<b>~' + n.minutes + ' min</b> to/from Union (typical)';
  }
  L.marker([n.lat, n.lon], { icon: stationIcon(color), title: n.name })
    .bindPopup(popup).addTo(stationLayer);
}
stationLayer.addTo(map);
overlays['Stations'] = stationLayer;

L.control.layers(null, overlays, { collapsed: false }).addTo(map);

// --- Legend ---
const legend = document.getElementById('legend');
for (const b of DATA.bands) {
  const row = document.createElement('div');
  row.className = 'legend-row';
  row.innerHTML = '<span class="swatch" style="background:' + b.color + '"></span>' + b.label;
  legend.appendChild(row);
}
const modes = document.getElementById('modes');
const presentModes = [...new Set(DATA.nodes.map(n => n.mode))].filter(m => m !== 'origin');
const modeOrder = ['subway', 'streetcar', 'bus', 'go', 'up'];
presentModes.sort((a, b) => (modeOrder.indexOf(a) + 1 || 99) - (modeOrder.indexOf(b) + 1 || 99));
for (const m of presentModes) {
  const row = document.createElement('div');
  row.className = 'legend-row';
  row.innerHTML = '<span class="dot" style="background:' + (DATA.mode_color[m] || '#555') +
                  '"></span>' + (DATA.mode_label[m] || m);
  modes.appendChild(row);
}
document.getElementById('assume').textContent = DATA.service_assumption;
document.getElementById('generated').textContent = DATA.generated_at
  ? 'Data pulled ' + DATA.generated_at : '';

// --- Point-in-polygon: which band contains a clicked point? ---
function pointInRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
    const hit = ((yi > lat) !== (yj > lat)) &&
                (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi);
    if (hit) inside = !inside;
  }
  return inside;
}
function bandForPoint(lat, lon) {
  // Smallest-minute band whose any polygon ring contains the point.
  const sorted = DATA.geo.features.slice().sort((a, b) => a.properties.minutes - b.properties.minutes);
  for (const f of sorted) {
    for (const poly of f.geometry.coordinates) {
      if (pointInRing(lon, lat, poly[0])) return f.properties;
    }
  }
  return null;
}

// --- Nearest-station itinerary (precomputed step-by-step trip to Union) ---
function haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000, t = Math.PI / 180;
  const dLat = (lat2 - lat1) * t, dLon = (lon2 - lon1) * t;
  const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(lat1 * t) * Math.cos(lat2 * t) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
function nearestStation(lat, lon) {
  let best = null, bd = Infinity;
  for (const s of (DATA.stations || [])) {
    const d = haversineM(lat, lon, s.lat, s.lon);
    if (d < bd) { bd = d; best = s; }
  }
  return best ? { station: best, dist: bd } : null;
}
function legHtml(l) {
  if (l.mode === 'Walk') return '<li>&#128694; Walk ' + l.min + ' min</li>';
  let s = '<b>' + l.mode + (l.route ? ' ' + l.route : '') + '</b> &middot; ' + l.min + ' min';
  if (l.from && l.to) s += '<br><span class="legstops">' + l.from + ' &rarr; ' + l.to +
                           (l.dep ? ' (dep ' + l.dep + ')' : '') + '</span>';
  return '<li>' + s + '</li>';
}
function legsUl(legs) {
  return '<ul>' + legs.map(legHtml).join('') + '</ul>';
}
// Itinerary via the nearest station, plus the walk from the point to that station.
const MAX_STATION_WALK_M = 3000;  // hide the suggestion if no station is near
function itineraryHtml(lat, lon) {
  const n = nearestStation(lat, lon);
  if (!n || n.dist > MAX_STATION_WALK_M || !n.station.legs || !n.station.legs.length) return '';
  const s = n.station;
  const walkMin = Math.round(n.dist / 80);  // 80 m/min, matches the model
  const walk = walkMin > 0
    ? '<li>&#128694; Walk ~' + walkMin + ' min to ' + s.name + '</li>' : '';
  return '<div class="itin"><div class="itin-h">Suggested trip via nearest station ' +
         '<b>' + s.name + '</b> (' + s.minutes + ' min to Union):</div><ul>' +
         walk + s.legs.map(legHtml).join('') + '</ul></div>';
}

const result = document.getElementById('result');
let clickMarker = null;
map.on('click', e => {
  const { lat, lng } = e.latlng;
  const band = bandForPoint(lat, lng);
  if (clickMarker) map.removeLayer(clickMarker);
  clickMarker = L.circleMarker([lat, lng], { radius: 6, color: '#222', weight: 2,
    fillColor: '#fff', fillOpacity: 1 }).addTo(map);
  if (band) {
    result.innerHTML = 'From here you can reach Union within <b style="color:' + band.color + '">' +
      band.label + '</b> by transit (morning peak).' + itineraryHtml(lat, lng);
    clickMarker.bindPopup('&le; ' + band.minutes + ' min to Union').openPopup();
  } else {
    result.innerHTML = 'From here Union is <b>more than 2&nbsp;hours</b> away by the modelled transit network.';
    clickMarker.bindPopup('Beyond 2 h').openPopup();
  }
});

// --- Geolocation: "you are here" + check against the bands ---
let youMarker = null;
function locate(recenter = true) {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(pos => {
    const ll = [pos.coords.latitude, pos.coords.longitude];
    if (youMarker) youMarker.setLatLng(ll);
    else youMarker = L.circleMarker(ll, { radius: 8, color: '#fff', weight: 2,
      fillColor: '#2b8cbe', fillOpacity: 1 }).addTo(map).bindPopup('You are here');
    const band = bandForPoint(ll[0], ll[1]);
    result.innerHTML = band
      ? 'From you, Union is within <b style="color:' + band.color + '">' + band.label + '</b> by transit (morning peak).' + itineraryHtml(ll[0], ll[1])
      : 'From you, Union is <b>more than 2&nbsp;hours</b> away by the modelled network.';
    if (recenter) map.setView(ll, 12);
  }, () => {}, { enableHighAccuracy: true, timeout: 8000 });
}

// Auto-show the user's location on load ONLY if geolocation is already granted -
// so first-time visitors keep the "Click anywhere..." intro and aren't hit with an
// unsolicited permission prompt. Otherwise they use the locate button (which asks).
if (navigator.permissions && navigator.permissions.query) {
  navigator.permissions.query({ name: 'geolocation' })
    .then(p => { if (p.state === 'granted') locate(false); })  // no recenter on load
    .catch(() => {});
}
const LocateControl = L.Control.extend({
  options: { position: 'topleft' },
  onAdd() {
    const a = L.DomUtil.create('a', 'leaflet-bar leaflet-control');
    a.href = '#'; a.title = 'Center on my location'; a.innerHTML = '&#9678;';
    a.style.cssText = 'width:30px;height:30px;line-height:30px;text-align:center;font-size:18px;background:#fff;';
    L.DomEvent.on(a, 'click', ev => { L.DomEvent.preventDefault(ev); locate(); });
    return a;
  },
});
map.addControl(new LocateControl());

// Mobile info toggle.
const panel = document.getElementById('panel');
const toggle = document.getElementById('toggle');
toggle.addEventListener('click', () => {
  const shown = panel.style.display === 'block';
  panel.style.display = shown ? 'none' : 'block';
  toggle.textContent = shown ? 'Info' : 'Close';
});
</script>
</body>
</html>
"""


def main():
    out = HTML.replace("__PAYLOAD__", PAYLOAD)
    target = OUT_DIR / "union-station-transit-isochrone.html"
    target.write_text(out, encoding="utf-8")
    n_nodes = sum(1 for n in MODEL["nodes"] if n["mode"] != "origin")
    print(f"Wrote {target} ({len(GEO['features'])} bands, {n_nodes} stations)")


if __name__ == "__main__":
    main()
