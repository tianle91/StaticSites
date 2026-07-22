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

PAYLOAD = json.dumps(
    {
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
    },
    ensure_ascii=False,
)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Ontario Publicly-Funded Physiotherapy Clinics</title>
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
  #stats { font-size: 12px; background: #f3f7fb; border: 1px solid #d6e4f0; border-radius: 6px; padding: 8px; }
  #stats b { font-size: 16px; color: #1f78b4; }
  #search { width: 100%; box-sizing: border-box; margin-top: 10px; padding: 6px 8px;
    font-size: 13px; border: 1px solid #ccc; border-radius: 6px; }
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
  <h1>Publicly-Funded Physiotherapy</h1>
  <p>Clinics and hospitals across Ontario offering OHIP-covered physiotherapy for eligible patients.</p>

  <div id="stats"></div>
  <input id="search" type="search" placeholder="Filter by name, city or postal code&hellip;" autocomplete="off" />

  <h2>Legend</h2>
  <div id="legend"></div>

  <h2>Data sources</h2>
  <p><a id="source" href="#" target="_blank" rel="noopener">ontario.ca &mdash; publicly-funded physiotherapy clinic locations</a>
     (via the <a href="https://data.ontario.ca/dataset/publicly-funded-physiotherapy-clinics" target="_blank" rel="noopener">Ontario Open Data</a> CKAN datastore)</p>
  <p style="color:#666">Coordinates geocoded with &copy;
     <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> Nominatim; map tiles &copy; OpenStreetMap contributors.</p>
  <p id="generated" style="color:#666"></p>

  <details>
    <summary>Notes &amp; caveats</summary>
    <p>Eligibility is limited (generally seniors 65+, people 19 and under, and patients recently discharged from hospital or on ODSP/OW). <b>Call ahead</b> - clinic lists change and pins are geocoded from street addresses, so some sit at the city centre rather than the exact door. For questions, the Seniors' INFOline is <b>1-888-910-1999</b>.</p>
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

// One toggleable layer per facility type.
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

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

// Keep marker + record together so the search box can filter without rebuilding.
const entries = [];
const bounds = [];
for (const c of DATA.clinics) {
  const cat = DATA.categories[c.category] || { label: c.facility_type, color: '#555' };
  const popup =
    '<b>' + esc(c.name) + '</b><br>' +
    '<span class="cat" style="color:' + cat.color + '">' + esc(cat.label) + '</span><br>' +
    (c.address ? esc(c.address) + '<br>' : '') +
    (c.precision === 'city'
      ? '<span style="color:#a15c00">Pin shows the city centre &mdash; exact address above.</span><br>' : '') +
    (c.phone ? '<a href="tel:' + esc(c.phone.replace(/[^0-9+]/g, '')) + '">' + esc(c.phone) + '</a><br>' : '') +
    (c.email ? '<a href="mailto:' + esc(c.email) + '">' + esc(c.email) + '</a><br>' : '') +
    '<a href="https://www.google.com/maps/dir/?api=1&destination=' +
      encodeURIComponent(c.address || (c.lat + ',' + c.lon)) +
      '" target="_blank" rel="noopener">Directions &rarr;</a>';
  const marker = L.marker([c.lat, c.lon], { icon: markerIcon(cat.color), title: c.name })
    .bindPopup(popup);
  marker.addTo(layers[c.category]);
  entries.push({ marker, clinic: c, haystack: [c.name, c.city, c.postal_code, c.address].join(' ').toLowerCase() });
  bounds.push([c.lat, c.lon]);
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

// Header stats + provenance.
const stats = document.getElementById('stats');
function renderStats(shown) {
  const total = DATA.meta.mapped;
  stats.innerHTML = '<b>' + shown + '</b> of ' + total + ' mapped location' + (total === 1 ? '' : 's') +
    (DATA.meta.total_records > total
      ? '<br><span style="color:#666">' + (DATA.meta.total_records - total) + ' listed clinic(s) could not be geocoded</span>'
      : '') +
    (DATA.meta.city_only
      ? '<br><span style="color:#666">' + DATA.meta.city_only + ' pinned to their city centre only</span>'
      : '');
}
renderStats(entries.length);
document.getElementById('source').href = DATA.meta.source_page;
document.getElementById('generated').textContent = DATA.meta.generated_at
  ? 'Data pulled ' + DATA.meta.generated_at : '';

// Search box: hide non-matching markers in place (layer toggles still apply).
const search = document.getElementById('search');
search.addEventListener('input', () => {
  const q = search.value.trim().toLowerCase();
  let shown = 0;
  const visible = [];
  for (const e of entries) {
    const match = !q || e.haystack.includes(q);
    const layer = layers[e.clinic.category];
    if (match) {
      if (!layer.hasLayer(e.marker)) layer.addLayer(e.marker);
      shown++;
      visible.push([e.clinic.lat, e.clinic.lon]);
    } else if (layer.hasLayer(e.marker)) {
      layer.removeLayer(e.marker);
    }
  }
  renderStats(shown);
  if (q && visible.length) map.fitBounds(visible, { padding: [40, 40], maxZoom: 14 });
});

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
      map.setView(ll, 12);
    },
    () => {},  // denied/unavailable: keep the province-wide view
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


def main() -> None:
    out = HTML.replace("__PAYLOAD__", PAYLOAD)
    target = OUT_DIR / "ontario-physiotherapy-clinics-map.html"
    target.write_text(out, encoding="utf-8")
    by_cat = {}
    for c in DATA["clinics"]:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    breakdown = ", ".join(f"{n} {k}" for k, n in sorted(by_cat.items()))
    print(f"Wrote {target} ({len(DATA['clinics'])} mapped locations: {breakdown})")


if __name__ == "__main__":
    main()
