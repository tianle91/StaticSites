const esc = Explorer.esc;
const map = L.map("map").setView([DATA.origin.lat, DATA.origin.lon], 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

// --- Isochrone band layers (drawn largest-first so shorter times sit on top) ---
const bandLayers = {}; // minutes -> L.GeoJSON
const bandByMin = {}; // minutes -> band meta
for (const b of DATA.bands) bandByMin[b.minutes] = b;

const feats = DATA.geo.features
  .slice()
  .sort((a, b) => b.properties.minutes - a.properties.minutes);

for (const f of feats) {
  const color = f.properties.color;
  const layer = L.geoJSON(f, {
    style: {
      color: color,
      weight: 1.5,
      opacity: 0.9,
      fillColor: color,
      fillOpacity: 0.28,
    },
  }).addTo(map);
  bandLayers[f.properties.minutes] = layer;
}

// Origin marker.
L.marker([DATA.origin.lat, DATA.origin.lon], {
  icon: L.divIcon({
    className: "",
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    html: '<div style="font-size:20px;line-height:22px;text-align:center">&#9733;</div>',
  }),
  title: "Union Station",
  zIndexOffset: 1000,
})
  .bindPopup("<b>Union Station</b><br>Origin (0 min)")
  .addTo(map);

// --- Point-in-polygon: which band contains a clicked point? ---
function pointInRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0],
      yi = ring[i][1],
      xj = ring[j][0],
      yj = ring[j][1];
    const hit =
      yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
    if (hit) inside = !inside;
  }
  return inside;
}
function bandForPoint(lat, lon) {
  // Smallest-minute polygon containing the point, excluding interior holes.
  const sorted = DATA.geo.features
    .slice()
    .sort((a, b) => a.properties.minutes - b.properties.minutes);
  for (const f of sorted) {
    for (const poly of f.geometry.coordinates) {
      if (
        pointInRing(lon, lat, poly[0]) &&
        !poly.slice(1).some((hole) => pointInRing(lon, lat, hole))
      )
        return f.properties;
    }
  }
  return null;
}

// --- Nearest-station itinerary (precomputed step-by-step trip to Union) ---
function haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000,
    t = Math.PI / 180;
  const dLat = (lat2 - lat1) * t,
    dLon = (lon2 - lon1) * t;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * t) * Math.cos(lat2 * t) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
function nearestStation(lat, lon) {
  let best = null,
    bd = Infinity;
  for (const s of DATA.stations || []) {
    const d = haversineM(lat, lon, s.lat, s.lon);
    if (d < bd) {
      bd = d;
      best = s;
    }
  }
  return best ? { station: best, dist: bd } : null;
}
function legHtml(l) {
  if (l.mode === "Walk") return "<li>&#128694; Walk " + l.min + " min</li>";
  let s =
    "<b>" +
    esc(l.mode) +
    (l.route ? " " + esc(l.route) : "") +
    "</b> &middot; " +
    l.min +
    " min";
  if (l.from && l.to)
    s +=
      '<br><span class="legstops">' +
      esc(l.from) +
      " &rarr; " +
      esc(l.to) +
      (l.dep ? " (dep " + esc(l.dep) + ")" : "") +
      "</span>";
  return "<li>" + s + "</li>";
}
function legsUl(legs) {
  return "<ul>" + legs.map(legHtml).join("") + "</ul>";
}
// Itinerary via the nearest station, plus the walk from the point to that station.
const MAX_STATION_WALK_M = 3000; // hide the suggestion if no station is near
function itineraryHtml(lat, lon) {
  const n = nearestStation(lat, lon);
  if (
    !n ||
    n.dist > MAX_STATION_WALK_M ||
    !n.station.legs ||
    !n.station.legs.length
  )
    return "";
  const s = n.station;
  const walkMin = Math.round(n.dist / 80); // 80 m/min, matches the model
  const walk =
    walkMin > 0
      ? "<li>&#128694; Walk ~" + walkMin + " min to " + esc(s.name) + "</li>"
      : "";
  return (
    '<div class="itin"><div class="itin-h">Suggested trip via nearest station ' +
    "<b>" +
    esc(s.name) +
    "</b> (" +
    s.minutes +
    " min to Union):</div><ul>" +
    walk +
    s.legs.map(legHtml).join("") +
    "</ul></div>"
  );
}

const STN_BY_NAME = Object.fromEntries(
  (DATA.stations || []).map((s) => [s.name, s]),
);
const stations = L.layerGroup().addTo(map),
  entries = DATA.nodes
    .filter((n) => n.mode !== "origin")
    .map((rec) => {
      const s = STN_BY_NAME[rec.name],
        popup =
          "<b>" +
          esc(rec.name) +
          "</b><br>" +
          esc(rec.line) +
          " · " +
          esc(DATA.mode_label[rec.mode] || rec.mode) +
          "<br>" +
          (s && s.legs?.length
            ? "<b>" +
              s.minutes +
              " min</b> to Union (morning peak):" +
              legsUl(s.legs)
            : "<b>~" + rec.minutes + " min</b> to/from Union (typical)");
      const marker = L.marker([rec.lat, rec.lon], {
        title: rec.name,
        icon: L.divIcon({
          className: "",
          iconSize: [12, 12],
          html:
            '<div class="feature-dot" style="background:' +
            (DATA.mode_color[rec.mode] || "#555") +
            '"></div>',
        }),
      }).bindPopup(popup);
      return {
        rec,
        marker,
        haystack: [rec.name, rec.line, DATA.mode_label[rec.mode], rec.mode]
          .join(" ")
          .toLowerCase(),
      };
    });
let visible = [];
function update() {
  const q = document.getElementById("search").value.trim().toLowerCase(),
    counts = {};
  stations.clearLayers();
  visible = [];
  for (const e of entries) {
    if (q && !e.haystack.includes(q)) continue;
    counts[e.rec.mode] = (counts[e.rec.mode] || 0) + 1;
    if (Explorer.enabled(e.rec.mode)) {
      visible.push(e);
      stations.addLayer(e.marker);
    }
  }
  for (const b of DATA.bands) {
    const layer = bandLayers[b.minutes];
    if (Explorer.enabled("band-" + b.minutes)) layer.addTo(map);
    else map.removeLayer(layer);
  }
  Explorer.layerCounts(
    Object.fromEntries(
      [...new Set(entries.map((e) => e.rec.mode))].map((id) => [
        id,
        counts[id] || 0,
      ]),
    ),
  );
  Explorer.count(
    visible.length,
    "stations",
    null,
    DATA.bands.filter((b) => Explorer.enabled("band-" + b.minutes)).length +
      " travel-time bands enabled",
  );
  Explorer.results(
    visible,
    (e) => e.rec.name,
    (e) => e.rec.line + " · " + (DATA.mode_label[e.rec.mode] || e.rec.mode),
    (e) => {
      Explorer.focus(map, e.marker.getLatLng());
      e.marker.openPopup();
    },
  );
}
Explorer.layers(
  [
    ...DATA.bands.map((b) => ({
      id: "band-" + b.minutes,
      label: b.label,
      color: b.color,
    })),
    ...[...new Set(entries.map((e) => e.rec.mode))].map((id) => ({
      id,
      label: DATA.mode_label[id] || id,
      color: DATA.mode_color[id],
    })),
  ],
  update,
);
const result = document.getElementById("result");
let clickMarker = null;
function showTrip(lat, lon) {
  const band = bandForPoint(lat, lon);
  result.innerHTML = band
    ? "From here you can reach Union within <b>" +
      esc(band.label) +
      "</b> by transit (morning peak)." +
      itineraryHtml(lat, lon)
    : "This point is outside the modelled travel-time bands. Coverage is limited to the modelled transit network.";
  Explorer.tab("results");
}
map.on("click", (e) => {
  const { lat, lng } = e.latlng;
  if (clickMarker) map.removeLayer(clickMarker);
  clickMarker = L.circleMarker([lat, lng], {
    radius: 6,
    color: "#222",
    weight: 2,
    fillColor: "#fff",
    fillOpacity: 1,
  }).addTo(map);
  showTrip(lat, lng);
});
document.getElementById("assume").textContent = DATA.service_assumption;
document.getElementById("generated").textContent = DATA.generated_at;
document.getElementById("search").addEventListener("input", update);
Explorer.stamp(DATA.generated_at);
Explorer.connect(map, {
  bounds: () => {
    const b = L.latLngBounds(visible.map((e) => e.marker.getLatLng()));
    for (const band of DATA.bands)
      if (Explorer.enabled("band-" + band.minutes))
        b.extend(bandLayers[band.minutes].getBounds());
    return b;
  },
  located: (pos) => showTrip(pos.coords.latitude, pos.coords.longitude),
});
update();
