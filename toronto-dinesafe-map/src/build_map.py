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
    ensure_ascii=False,
)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Toronto DineSafe Food-Safety Inspections</title>
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
  #stats { font-size: 12px; background: #f3f7fb; border: 1px solid #d6e4f0; border-radius: 6px; padding: 8px; }
  #stats b { font-size: 16px; color: #1f78b4; }
  #search { width: 100%; box-sizing: border-box; margin-top: 10px; padding: 6px 8px;
    font-size: 13px; border: 1px solid #ccc; border-radius: 6px; }
  #results { list-style: none; margin: 6px 0 0; padding: 0; max-height: 210px; overflow: auto; }
  #results:empty { margin: 0; }
  #results li { padding: 6px 8px; border-radius: 6px; cursor: pointer; font-size: 12px;
    display: flex; align-items: center; gap: 7px; }
  #results li:hover, #results li.active { background: #eef4fb; }
  #results .r-name { font-weight: 600; color: #222; }
  #results .r-addr { color: #777; display: block; font-weight: 400; }
  #results .r-more { color: #888; text-align: center; cursor: default; }
  #results .r-more:hover { background: none; }
  .legend-row { display: flex; align-items: center; font-size: 12px; margin: 3px 0; }
  .dot { width: 12px; height: 12px; border-radius: 50%; margin-right: 7px; border: 1px solid rgba(0,0,0,.3); }
  .sample-banner { background: #fff6e5; border: 1px solid #f0c976; color: #7a5200;
    font-size: 12px; border-radius: 6px; padding: 8px; margin-bottom: 8px; }
  .leaflet-popup-content { font-size: 13px; }
  .leaflet-popup-content .cat { font-size: 11px; text-transform: uppercase; letter-spacing: .03em; font-weight: 600; }
  details > summary { cursor: pointer; font-weight: 600; font-size: 13px; margin-top: 10px; }
  .toggle { position: absolute; top: 10px; right: 10px; z-index: 1001; display: none;
    background: #fff; border: none; border-radius: 6px; padding: 8px 10px; box-shadow: 0 1px 6px rgba(0,0,0,.3); cursor: pointer; }

  /* Detail sidebar: slides in from the left when a business is clicked. */
  #sidebar { position: absolute; top: 0; left: 0; bottom: 0; z-index: 1200; width: 360px;
    max-width: 88%; background: #fff; box-shadow: 2px 0 12px rgba(0,0,0,.28);
    transform: translateX(-105%); transition: transform .2s ease; overflow: auto;
    -webkit-overflow-scrolling: touch; }
  #sidebar.open { transform: none; }
  .sb-head { position: sticky; top: 0; background: #fff; padding: 14px 16px 10px;
    border-bottom: 1px solid #eee; }
  .sb-close { position: absolute; top: 10px; right: 10px; border: none; background: #f2f2f2;
    border-radius: 50%; width: 28px; height: 28px; font-size: 16px; line-height: 1; cursor: pointer; color: #555; }
  .sb-close:hover { background: #e4e4e4; }
  .sb-head h2 { font-size: 17px; margin: 0 30px 6px 0; }
  .sb-body { padding: 12px 16px 24px; }
  .badge { display: inline-block; font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .03em; color: #fff; padding: 2px 8px; border-radius: 10px; }
  .sb-sub { font-size: 12.5px; color: #555; margin: 6px 0 0; }
  .facts { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 14px 0; }
  .fact { background: #f6f8fa; border: 1px solid #e6ebf0; border-radius: 8px; padding: 8px 10px; }
  .fact .k { font-size: 10.5px; text-transform: uppercase; letter-spacing: .03em; color: #7a8794; }
  .fact .v { font-size: 15px; font-weight: 600; color: #222; margin-top: 2px; }
  .sb-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 4px; }
  .sb-actions a { flex: 1; min-width: 120px; text-align: center; font-size: 12.5px; font-weight: 600;
    text-decoration: none; padding: 8px 10px; border-radius: 8px; background: #1f78b4; color: #fff; }
  .sb-actions a.secondary { background: #eef2f6; color: #1f78b4; }
  .sb-actions a:hover { filter: brightness(.95); }
  .sb-body h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .03em; color: #555;
    margin: 20px 0 8px; }
  .timeline { list-style: none; margin: 0; padding: 0; }
  .insp { border: 1px solid #e6ebf0; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
  .insp-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .insp-date { font-weight: 600; font-size: 13px; color: #222; }
  .infractions { list-style: none; margin: 9px 0 0; padding: 0; }
  .infractions li { font-size: 12.5px; color: #333; padding: 7px 0; border-top: 1px dashed #e6ebf0; }
  .infractions li:first-child { border-top: none; }
  .sev { display: inline-block; font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .02em; padding: 1px 6px; border-radius: 8px; margin-right: 6px; vertical-align: 1px; }
  .sev-crucial { background: #fdecea; color: #b71c1c; }
  .sev-significant { background: #fff3e0; color: #b25b00; }
  .sev-minor { background: #f1f8e9; color: #4b7a19; }
  .sev-other { background: #eceff1; color: #546e7a; }
  .action { color: #667; font-size: 11.5px; margin-top: 3px; }
  .muted { color: #888; font-size: 12.5px; margin: 8px 0 0; }
  .no-infr { color: #2e7d32; font-size: 12.5px; margin: 8px 0 0; }

  @media (max-width: 620px) {
    .panel { width: auto; left: 10px; right: 10px; max-height: 55%; display: none; }
    .toggle { display: block; }
    #sidebar { width: 100%; max-width: 100%; }
  }
</style>
</head>
<body>
<div id="map"></div>
<button class="toggle" id="toggle">Info</button>

<aside id="sidebar" aria-hidden="true">
  <div class="sb-head">
    <button class="sb-close" id="sb-close" title="Close" aria-label="Close">&times;</button>
    <h2 id="sb-title"></h2>
    <div id="sb-badge"></div>
    <p class="sb-sub" id="sb-sub"></p>
  </div>
  <div class="sb-body" id="sb-body"></div>
</aside>

<div class="panel" id="panel">
  <h1>Toronto DineSafe Inspections</h1>
  <p>Food-safety inspection results for Toronto restaurants, food stores and other
     establishments, coloured by the outcome of the most recent inspection.
     <b>Search below or click a pin</b> to see inspection details and past inspections.</p>

  <div id="sample-banner" class="sample-banner" style="display:none"></div>
  <div id="stats"></div>
  <input id="search" type="search" placeholder="Search by name, type or address&hellip;" autocomplete="off" />
  <ul id="results"></ul>

  <h2>Legend</h2>
  <div id="legend"></div>

  <h2>Data sources</h2>
  <ul class="sources">
    <li>Inspection results &mdash;
      <a id="source" href="https://open.toronto.ca/dataset/dinesafe/" target="_blank" rel="noopener">DineSafe, Toronto Open Data</a>
      (Toronto Public Health)</li>
    <li>Program details &mdash;
      <a href="https://www.toronto.ca/community-people/health-wellness-care/health-programs-advice/food-safety/dinesafe/" target="_blank" rel="noopener">City of Toronto &mdash; DineSafe</a></li>
    <li>Geocoding &amp; map tiles &mdash; &copy;
      <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors
      (via Nominatim)</li>
  </ul>
  <p id="generated" style="color:#666"></p>

  <details>
    <summary>Notes &amp; caveats</summary>
    <p>Each pin shows an establishment's <b>most recent</b> inspection outcome on
       record; statuses change as re-inspections happen, so confirm current status
       on the <a href="https://www.toronto.ca/community-people/health-wellness-care/health-programs-advice/food-safety/dinesafe/" target="_blank" rel="noopener">official DineSafe site</a>
       before relying on a pin. A <b>Conditional Pass</b> means minor infractions
       were found and must be corrected; <b>Closed</b> means the establishment was
       ordered closed at the time of inspection (it may have since reopened).
       Locations come from the dataset's own coordinates where present, otherwise
       geocoded from the address, so some pins are approximate.</p>
  </details>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
const DATA = __PAYLOAD__;

// preferCanvas: the full DineSafe set is ~16k points; canvas keeps it smooth.
const map = L.map('map', { preferCanvas: true }).setView(DATA.center, DATA.zoom);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// One toggleable layer per status category.
const layers = {};
for (const key in DATA.categories) layers[key] = L.layerGroup().addTo(map);

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function catFor(key) { return DATA.categories[key] || { label: 'Other / Unknown', color: '#777' }; }
// Map DineSafe's severity wording to a colour band (crucial > significant > minor).
function sevClass(sev) {
  const s = String(sev || '').toLowerCase();
  if (s.includes('crucial')) return 'crucial';
  if (s.includes('significant')) return 'significant';
  if (s.includes('minor')) return 'minor';
  return 'other';
}

// Keep marker + record together so the search box can filter without rebuilding.
const entries = [];
for (const e of DATA.establishments) {
  const cat = catFor(e.cat);
  const marker = L.circleMarker([e.lat, e.lon], {
    radius: 6, color: '#fff', weight: 1, fillColor: cat.color, fillOpacity: 0.9
  });
  marker.on('click', () => openSidebar(e));
  marker.addTo(layers[e.cat]);
  entries.push({ marker, rec: e, cat: e.cat,
    haystack: [e.name, e.type, e.address].join(' ').toLowerCase() });
}

// ---- Detail sidebar -------------------------------------------------------
// Opens on a marker or search-result click; shows the current status, key
// facts, and the full inspection history (each visit's infractions).
const DINESAFE_URL = 'https://www.toronto.ca/community-people/health-wellness-care/health-programs-advice/food-safety/dinesafe/';
const sidebar = document.getElementById('sidebar');

function fact(k, v) {
  return '<div class="fact"><div class="k">' + esc(k) + '</div><div class="v">' + esc(v) + '</div></div>';
}

function renderInspection(ins) {
  const c = catFor(ins.cat);
  const n = ins.infraction_count != null ? ins.infraction_count : (ins.infractions || []).length;
  let body;
  if (ins.infractions && ins.infractions.length) {
    body = '<ul class="infractions">' + ins.infractions.map(f => {
      const sev = f.severity
        ? '<span class="sev sev-' + sevClass(f.severity) + '">' + esc(f.severity) + '</span>' : '';
      return '<li>' + sev + esc(f.detail || 'Infraction recorded') +
        (f.action ? '<div class="action">Action &mdash; ' + esc(f.action) + '</div>' : '') +
        (f.outcome ? '<div class="action">Outcome &mdash; ' + esc(f.outcome) + '</div>' : '') +
        '</li>';
    }).join('') + '</ul>';
  } else if (n > 0 && ins.details_available === false) {
    // Summary-only data/dinesafe.json: we know the count but not the detail.
    body = '<p class="muted">' + n + ' infraction' + (n === 1 ? '' : 's') +
      ' recorded &mdash; run <code>make data</code> to load the specifics.</p>';
  } else if (n > 0) {
    body = '<p class="muted">' + n + ' infraction' + (n === 1 ? '' : 's') + ' recorded.</p>';
  } else {
    body = '<p class="no-infr">&#10003; No infractions recorded.</p>';
  }
  return '<li class="insp"><div class="insp-top">' +
    '<span class="insp-date">' + esc(ins.date || 'Date unknown') + '</span>' +
    '<span class="badge" style="background:' + c.color + '">' + esc(c.label) + '</span>' +
    '</div>' + body + '</li>';
}

// The timeline the sidebar shows: the establishment's own `inspections` when the
// data carries them, otherwise a single entry synthesised from the summary fields
// (count is known, per-infraction detail is not until `make data` is re-run).
function timelineFor(e) {
  if (e.inspections && e.inspections.length) return e.inspections;
  if (e.last_inspection || e.status) {
    return [{
      date: e.last_inspection || '', status: e.status || '', cat: e.cat,
      infractions: [], infraction_count: e.infractions || 0, details_available: false,
    }];
  }
  return [];
}

function openSidebar(e) {
  const cat = catFor(e.cat);
  document.getElementById('sb-title').textContent = e.name || 'Establishment';
  document.getElementById('sb-badge').innerHTML =
    '<span class="badge" style="background:' + cat.color + '">' + esc(cat.label) + '</span>';
  document.getElementById('sb-sub').innerHTML =
    (e.type ? esc(e.type) : '') + (e.type && e.address ? ' &middot; ' : '') + (e.address ? esc(e.address) : '');

  const inspections = timelineFor(e);
  const latestN = e.infractions || 0;
  let facts = fact('Last inspected', e.last_inspection || '\\u2014');
  facts += fact('Infractions (latest)', latestN);
  facts += fact('Inspections on record', inspections.length || '\\u2014');
  if (e.min_per_year) facts += fact('Min. inspections/yr', e.min_per_year);

  const dest = encodeURIComponent(e.address ? e.address + ', Toronto, ON' : (e.lat + ',' + e.lon));
  const actions = '<div class="sb-actions">' +
    '<a href="https://www.google.com/maps/dir/?api=1&destination=' + dest + '" target="_blank" rel="noopener">Directions &rarr;</a>' +
    '<a class="secondary" href="' + DINESAFE_URL + '" target="_blank" rel="noopener">DineSafe program</a></div>';

  const history = inspections.length
    ? '<h3>Inspection history</h3><ul class="timeline">' + inspections.map(renderInspection).join('') + '</ul>'
    : '<p class="muted">No inspection records on file.</p>';

  document.getElementById('sb-body').innerHTML =
    '<div class="facts">' + facts + '</div>' + actions + history;
  sidebar.classList.add('open');
  sidebar.setAttribute('aria-hidden', 'false');
  sidebar.scrollTop = 0;
}

function closeSidebar() {
  sidebar.classList.remove('open');
  sidebar.setAttribute('aria-hidden', 'true');
}
document.getElementById('sb-close').addEventListener('click', closeSidebar);
document.addEventListener('keydown', ev => { if (ev.key === 'Escape') closeSidebar(); });
// Open at the default downtown view (ZOOM above) rather than fitting all ~18k
// city-wide pins, which would zoom right back out; a search still fits its matches.

// Layer toggle control + legend (with per-status counts).
const overlays = {};
const legend = document.getElementById('legend');
for (const key in DATA.categories) {
  const c = DATA.categories[key];
  const n = DATA.meta.counts[key] || 0;
  if (!n) continue;  // hide empty categories
  overlays[c.label + ' (' + n + ')'] = layers[key];
  const row = document.createElement('div');
  row.className = 'legend-row';
  row.innerHTML = '<span class="dot" style="background:' + c.color + '"></span>' +
                  c.label + ' <span style="color:#888">&middot; ' + n + '</span>';
  legend.appendChild(row);
}
L.control.layers(null, overlays, { collapsed: false }).addTo(map);

// Header stats + provenance.
const stats = document.getElementById('stats');
function renderStats(shown) {
  stats.innerHTML = '<b>' + shown.toLocaleString() + '</b> of ' +
    DATA.meta.total.toLocaleString() + ' establishment' + (DATA.meta.total === 1 ? '' : 's') + ' shown';
}
renderStats(entries.length);
document.getElementById('source').href = DATA.meta.source_page;
document.getElementById('generated').textContent = DATA.meta.generated_at
  ? 'Data pulled ' + DATA.meta.generated_at : '';
if (DATA.meta.sample) {
  const b = document.getElementById('sample-banner');
  b.style.display = 'block';
  b.innerHTML = '<b>Sample data.</b> This is a small placeholder set with fictional ' +
    'establishments. Run <code>make data</code> to load the live DineSafe dataset.';
}

// Fly to an establishment and open its detail sidebar (from a search result).
function focusEntry(rec) {
  map.flyTo([rec.lat, rec.lon], Math.max(map.getZoom(), 16), { duration: 0.6 });
  openSidebar(rec);
}

// Search box: filter the pins in place (layer toggles still apply) AND list the
// matches so a business can be found and opened without hunting for its pin.
const search = document.getElementById('search');
const results = document.getElementById('results');
const RESULT_LIMIT = 40;

function renderResults(matches, q) {
  results.innerHTML = '';
  if (!q) return;
  for (const en of matches.slice(0, RESULT_LIMIT)) {
    const cat = catFor(en.cat);
    const li = document.createElement('li');
    li.innerHTML = '<span class="dot" style="background:' + cat.color + '"></span>' +
      '<span><span class="r-name">' + esc(en.rec.name) + '</span>' +
      (en.rec.address ? '<span class="r-addr">' + esc(en.rec.address) + '</span>' : '') + '</span>';
    li.addEventListener('click', () => focusEntry(en.rec));
    results.appendChild(li);
  }
  if (matches.length > RESULT_LIMIT) {
    const li = document.createElement('li');
    li.className = 'r-more';
    li.textContent = '+ ' + (matches.length - RESULT_LIMIT) + ' more\\u2026 keep typing to narrow';
    results.appendChild(li);
  }
}

search.addEventListener('input', () => {
  const q = search.value.trim().toLowerCase();
  let shown = 0;
  const visible = [];
  const matches = [];
  for (const en of entries) {
    const match = !q || en.haystack.includes(q);
    const layer = layers[en.cat];
    if (match) {
      if (!layer.hasLayer(en.marker)) layer.addLayer(en.marker);
      shown++;
      if (q) { matches.push(en); visible.push([en.rec.lat, en.rec.lon]); }
    } else if (layer.hasLayer(en.marker)) {
      layer.removeLayer(en.marker);
    }
  }
  renderStats(shown);
  renderResults(matches, q);
  if (q && visible.length) map.fitBounds(visible, { padding: [40, 40], maxZoom: 15 });
});

// Center on the user's location when available/permitted (button + auto-attempt).
let youMarker = null;
function locate() {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(
    pos => {
      const ll = [pos.coords.latitude, pos.coords.longitude];
      if (youMarker) youMarker.setLatLng(ll);
      else youMarker = L.circleMarker(ll, { radius: 8, color: '#fff', weight: 2,
        fillColor: '#2b8cbe', fillOpacity: 1 }).addTo(map).bindPopup('You are here');
      map.setView(ll, 14);
    },
    () => {},  // denied/unavailable: keep the city-wide view
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
    # Escape "<" so a field value like "</script>" (or "<!--") in the embedded
    # JSON can't close the <script> element and break the page. These become
    # < inside the JSON string literals, leaving the parsed data unchanged.
    payload = PAYLOAD.replace("<", "\\u003c")
    out = HTML.replace("__PAYLOAD__", payload)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "toronto-dinesafe-map.html"
    target.write_text(out, encoding="utf-8")
    breakdown = ", ".join(
        f"{counts[k]} {STATUS_CATEGORIES[k]['label']}" for k in STATUS_CATEGORIES if counts[k]
    )
    print(f"Wrote {target} ({len(establishments)} establishments: {breakdown})")


if __name__ == "__main__":
    main()
