/* One incident can have several offence/victim rows and published points.
   Filter membership by type, but retain all source rows in incident details. */
const $ = (id) => document.getElementById(id),
  esc = Explorer.esc;
const colors = {
  Assault: "#ba5e40",
  "Break and Enter": "#8364a6",
  "Auto Theft": "#267ba0",
  Robbery: "#bd8740",
  "Theft Over": "#458474",
  Homicide: "#9c3651",
  "Shootings / discharges": "#5f4a95",
};
const incidents = DATA.incidents.map((event) => {
  const rows = event.rows.map((row) =>
    Object.fromEntries(DATA.columns.map((k, i) => [k, row[i]])),
  );
  return {
    id: event.id,
    rows,
    haystack: rows
      .map((r) =>
        [
          r.event_id,
          r.category,
          r.offence,
          r.neighbourhood,
          r.division,
          r.premises,
          r.occurred,
          r.reported,
        ].join(" "),
      )
      .join(" ")
      .toLowerCase(),
  };
});
const map = L.map("map", { preferCanvas: true }).setView([43.71, -79.39], 11);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution:
    '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);
// Unique IDs, rather than summed point counts: ten IDs have multiple published points.
const clusters = L.markerClusterGroup({
  maxClusterRadius: 45,
  iconCreateFunction: (c) =>
    L.divIcon({
      className: "",
      iconSize: [42, 42],
      html:
        '<div class="cluster">' +
        new Set(
          c.getAllChildMarkers().flatMap((m) => m.options.incidentIds),
        ).size.toLocaleString() +
        "</div>",
    }),
}).addTo(map);
function details(e) {
  return (
    "<h3>Incident " +
    esc(e.id) +
    "</h3><p>" +
    e.rows.length +
    " source row(s) · approximate intersection location(s)</p>" +
    e.rows
      .map(
        (r) =>
          '<div class="event"><b>' +
          esc(r.category) +
          " · " +
          esc(r.offence) +
          "</b><p>Source: " +
          esc(r.source) +
          " · Record " +
          esc(r.row_id) +
          "</p><p>Reported " +
          esc(r.reported || "not specified") +
          " · Occurred " +
          esc(r.occurred || "not specified") +
          "</p><p>" +
          esc(r.neighbourhood) +
          " · " +
          esc(r.division) +
          "</p>" +
          (r.premises ? "<p>Premises: " + esc(r.premises) + "</p>" : "") +
          (r.source === "shooting"
            ? "<p>Deaths: " +
              esc(r.deaths ?? "not specified") +
              " · Injuries: " +
              esc(r.injuries ?? "not specified") +
              "</p>"
            : "") +
          "<p>Published coordinates: " +
          (r.lat === null || r.lon === null
            ? "unavailable"
            : esc(r.lat) + ", " + esc(r.lon)) +
          "</p></div>",
      )
      .join("")
  );
}
let visible = [],
  points = [];
function update() {
  const q = $("search").value.trim().toLowerCase(),
    counts = Object.fromEntries(Object.keys(colors).map((k) => [k, 0])),
    grouped = new Map();
  visible = [];
  for (const e of incidents) {
    if (q && !e.haystack.includes(q)) continue;
    for (const type of new Set(e.rows.map((r) => r.category))) counts[type]++;
    const selected = e.rows.filter((r) => Explorer.enabled(r.category));
    if (!selected.length) continue;
    const valid = selected.filter(
      (r) => Number.isFinite(r.lat) && Number.isFinite(r.lon),
    );
    visible.push({ ...e, points: valid });
    for (const r of valid) {
      const key = r.lat + "," + r.lon;
      if (!grouped.has(key))
        grouped.set(key, {
          ll: [r.lat, r.lon],
          events: new Map(),
          types: new Set(),
        });
      const g = grouped.get(key);
      g.events.set(e.id, e);
      g.types.add(r.category);
    }
  }
  clusters.clearLayers();
  points = [];
  for (const g of grouped.values()) {
    const color = g.types.size === 1 ? colors[[...g.types][0]] : "#254b60",
      events = [...g.events.values()];
    const marker = L.marker(g.ll, {
      incidentIds: [...g.events.keys()],
      title: events.length + " incident(s) at approximate location",
      icon: L.divIcon({
        className: "",
        iconSize: [32, 32],
        html:
          '<div class="pin" style="background:' +
          color +
          '">' +
          events.length +
          "</div>",
      }),
    }).bindPopup(() => {
      const div = document.createElement("div");
      div.innerHTML =
        events.slice(0, 20).map(details).join("<hr>") +
        (events.length > 20
          ? "<p>First 20 incidents shown here. Search an incident ID for all its records.</p>"
          : "");
      return div;
    });
    points.push(marker);
  }
  clusters.addLayers(points);
  Explorer.layerCounts(counts);
  Explorer.count(
    visible.length,
    "distinct incidents",
    visible.filter((e) => e.points.length).length,
    visible.reduce((n, e) => n + e.rows.length, 0).toLocaleString() +
      " source rows retained",
  );
  Explorer.results(
    visible,
    (e) => e.id,
    (e) =>
      [...new Set(e.rows.map((r) => r.category))].join(" · ") +
      (e.points.length ? "" : " · No pin in selected types"),
    (e) => {
      if (e.points.length) {
        const r = e.points[0];
        Explorer.focus(map, [r.lat, r.lon]);
        L.popup().setLatLng([r.lat, r.lon]).setContent(details(e)).openOn(map);
      } else Explorer.detail("Incident " + e.id, details(e));
    },
  );
}
Explorer.layers(
  Object.entries(colors).map(([id, color]) => ({ id, label: id, color })),
  update,
);
let timer;
$("search").addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(update, 200);
});
Explorer.stamp(DATA.fetched_at);
Explorer.connect(map, {
  bounds: () => L.latLngBounds(points.map((m) => m.getLatLng())),
});
update();

for (const [name, source] of Object.entries(DATA.sources || {})) {
  const p = document.createElement("p");
  p.textContent =
    {
      main: "Community Safety Indicators",
      homicide: "Homicides",
      shooting: "Shootings / discharges",
    }[name] +
    ": " +
    source.records.toLocaleString() +
    " source rows · latest included date " +
    source.latest_date;
  document.getElementById("source-coverage").append(p);
}

$("scope").textContent =
  "Police-reported incidents · " + (DATA.start_year ?? 2025) + " onward";
