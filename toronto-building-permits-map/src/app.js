const $ = (id) => document.getElementById(id),
  esc = Explorer.esc;
const map = L.map("map", { preferCanvas: true }).setView([43.74, -79.43], 11);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);
const fields = Object.fromEntries(DATA.columns.map((name, i) => [name, i])),
  get = (r, k) => r[fields[k]],
  rows = DATA.permits;
const types = [
  "Small Residential Projects",
  "Plumbing(PS)",
  "Mechanical(MS)",
  "Building Additions/Alterations",
  "Drain and Site Service",
  "New Houses",
];
const palette = [
  "#267ba0",
  "#458474",
  "#8364a6",
  "#bd8740",
  "#ba5e40",
  "#9c3651",
  "#647580",
];
const category = (r) =>
  types.includes(get(r, "type")) ? get(r, "type") : "Other";
for (const [id, key] of [
  ["status", "status"],
  ["type", "type"],
  ["year", "applied"],
]) {
  const values = [
    ...new Set(
      rows
        .map((r) => (id === "year" ? get(r, key).slice(0, 4) : get(r, key)))
        .filter(Boolean),
    ),
  ].sort();
  if (id === "year") values.reverse();
  for (const v of values) {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v;
    $(id).append(o);
  }
}
// Cluster every matched address; the number is permit records, not addresses.
const clusters = L.markerClusterGroup({
  maxClusterRadius: 45,
  iconCreateFunction: (c) =>
    L.divIcon({
      className: "",
      iconSize: [42, 42],
      html:
        '<div class="cluster">' +
        c
          .getAllChildMarkers()
          .reduce((n, m) => n + m.options.recordCount, 0)
          .toLocaleString() +
        "</div>",
    }),
}).addTo(map);
let locations = [];
function details(r) {
  return (
    "<strong>" +
    esc(get(r, "address")) +
    "</strong><br>" +
    esc(get(r, "number")) +
    " · revision " +
    esc(get(r, "revision")) +
    "<br>" +
    esc(get(r, "status")) +
    "<br>" +
    esc(get(r, "type")) +
    " · " +
    esc(get(r, "work")) +
    "<br>Structure: " +
    esc(get(r, "structure")) +
    "<br>Applied: " +
    esc(get(r, "applied") || "Unknown") +
    " · Issued: " +
    esc(get(r, "issued") || "Not recorded") +
    "<br>Estimated cost: " +
    (get(r, "cost") === null
      ? "Not disclosed"
      : new Intl.NumberFormat("en-CA", {
          style: "currency",
          currency: "CAD",
          maximumFractionDigits: 0,
        }).format(get(r, "cost"))) +
    "<p>" +
    esc(get(r, "description")) +
    "</p>"
  );
}
function show(r) {
  if (Number.isFinite(get(r, "lat")) && Number.isFinite(get(r, "lon"))) {
    const ll = [get(r, "lat"), get(r, "lon")];
    Explorer.focus(map, ll, 17);
    L.popup().setLatLng(ll).setContent(details(r)).openOn(map);
  } else
    Explorer.detail(
      get(r, "number"),
      details(r) +
        "<p>No matching City address point; this record has no pin.</p>",
    );
}
function update() {
  const q = $("search").value.toLowerCase().trim(),
    counts = Object.fromEntries([...types, "Other"].map((k) => [k, 0])),
    filtered = [],
    grouped = new Map();
  let mapped = 0;
  for (const r of rows) {
    if (
      ($("status").value && get(r, "status") !== $("status").value) ||
      ($("type").value && get(r, "type") !== $("type").value) ||
      ($("year").value && !get(r, "applied").startsWith($("year").value)) ||
      (q &&
        ![get(r, "address"), get(r, "number"), get(r, "description")]
          .join(" ")
          .toLowerCase()
          .includes(q))
    )
      continue;
    const cat = category(r);
    counts[cat]++;
    if (!Explorer.enabled(cat)) continue;
    filtered.push(r);
    if (!Number.isFinite(get(r, "lat")) || !Number.isFinite(get(r, "lon")))
      continue;
    mapped++;
    const key = get(r, "lat") + "," + get(r, "lon");
    if (!grouped.has(key))
      grouped.set(key, { point: [get(r, "lat"), get(r, "lon")], rows: [] });
    grouped.get(key).rows.push(r);
  }
  locations = [...grouped.values()];
  clusters.clearLayers();
  clusters.addLayers(
    locations.map((g) =>
      L.marker(g.point, {
        recordCount: g.rows.length,
        title: g.rows.length + " permits at this address",
        icon: L.divIcon({
          className: "",
          iconSize: [32, 32],
          html:
            '<div class="pin" style="background:' +
            palette[[...types, "Other"].indexOf(category(g.rows[0]))] +
            '">' +
            g.rows.length +
            "</div>",
        }),
      }).bindPopup(
        () =>
          "<b>" +
          g.rows.length +
          " permits at this address</b>" +
          g.rows.slice(0, 30).map(details).join("<hr>") +
          (g.rows.length > 30
            ? "<p>First 30 shown; search a permit number for its details.</p>"
            : ""),
      ),
    ),
  );
  Explorer.layerCounts(counts);
  Explorer.count(filtered.length, "permits", mapped);
  Explorer.results(
    filtered,
    (r) => get(r, "address") || get(r, "number"),
    (r) =>
      get(r, "number") +
      " · " +
      get(r, "status") +
      (get(r, "lat") === null ? " · No pin" : ""),
    show,
  );
}
Explorer.layers(
  [...types, "Other"].map((id, i) => ({ id, label: id, color: palette[i] })),
  update,
);
let pending;
$("search").addEventListener("input", () => {
  clearTimeout(pending);
  pending = setTimeout(update, 200);
});
for (const id of ["status", "type", "year"]) $(id).onchange = update;
Explorer.stamp(DATA.retrieved_at);
Explorer.connect(map, {
  bounds: () => L.latLngBounds(locations.map((g) => g.point)),
});
update();
