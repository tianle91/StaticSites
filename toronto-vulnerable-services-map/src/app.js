const esc = Explorer.esc;
const map = L.map("map").setView(DATA.center, DATA.zoom);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);
const points = L.layerGroup().addTo(map),
  entries = DATA.locations.map((rec) => {
    const c = DATA.categories[rec.category] || {
      color: "#555",
      label: rec.category,
    };
    const marker = L.marker([rec.lat, rec.lon], {
      title: rec.name,
      icon: L.divIcon({
        className: "",
        iconSize: [16, 16],
        html:
          '<div class="feature-dot" style="background:' + c.color + '"></div>',
      }),
    }).bindPopup(
      "<b>" +
        esc(rec.name) +
        "</b><br>" +
        esc(c.label) +
        "<br>" +
        esc(rec.address) +
        "<p>" +
        esc(rec.notes) +
        "</p>" +
        (rec.url
          ? '<a href="' +
            esc(rec.url) +
            '" target="_blank" rel="noopener">More information</a>'
          : ""),
    );
    return {
      rec,
      marker,
      haystack: [rec.name, rec.address, rec.notes, c.label]
        .join(" ")
        .toLowerCase(),
    };
  });
let visible = [];
function update() {
  const q = document.getElementById("search").value.trim().toLowerCase(),
    counts = Object.fromEntries(
      Object.keys(DATA.categories).map((k) => [k, 0]),
    );
  points.clearLayers();
  visible = [];
  for (const e of entries) {
    if (q && !e.haystack.includes(q)) continue;
    counts[e.rec.category]++;
    if (Explorer.enabled(e.rec.category)) {
      points.addLayer(e.marker);
      visible.push(e);
    }
  }
  Explorer.layerCounts(counts);
  Explorer.count(visible.length, "service locations", visible.length);
  Explorer.results(
    visible,
    (e) => e.rec.name,
    (e) => e.rec.address,
    (e) => {
      Explorer.focus(map, e.marker.getLatLng());
      e.marker.openPopup();
    },
  );
}
Explorer.layers(
  Object.entries(DATA.categories).map(([id, c]) => ({ id, ...c })),
  update,
);
document.getElementById("search").addEventListener("input", update);
if (DATA.shelter_meta) {
  const m = DATA.shelter_meta;
  document.getElementById("shelter-meta").textContent =
    "Shelter pins: " +
    m.count +
    " locations · occupancy " +
    (m.snapshot || "n/a") +
    " · data pulled " +
    (m.pulled || "n/a");
}
for (const d of DATA.directories) {
  const div = document.createElement("p"),
    a = document.createElement("a");
  a.href = d.url;
  a.textContent = d.name;
  a.target = "_blank";
  a.rel = "noopener";
  div.append(a, document.createTextNode(d.note ? " — " + d.note : ""));
  document.getElementById("directories").append(div);
}
Explorer.stamp(DATA.shelter_meta?.pulled);
Explorer.connect(map, {
  bounds: () => L.latLngBounds(visible.map((e) => e.marker.getLatLng())),
});
update();
if (visible.length)
  Explorer.fit(
    map,
    L.latLngBounds(visible.map((e) => e.marker.getLatLng())),
    14,
  );
// Live shelter occupancy from Toronto Open Data (CKAN). Graceful if offline/CORS-blocked.
const CKAN = "https://ckan0.cf.opendata.inter.prod-toronto.ca";
const DATASET = "daily-shelter-overnight-service-occupancy-capacity";
async function loadShelterStats() {
  const stats = document.getElementById("live-stats");
  try {
    const pkg = await fetch(
      CKAN + "/api/3/action/package_show?id=" + DATASET,
    ).then((r) => r.json());
    const active = pkg.result.resources.filter((r) => r.datastore_active);
    if (!active.length) throw new Error("no active resource");
    // Annual archive names sort after the live table: compare occupancy dates.
    const snapshots = (
      await Promise.all(
        active.map(async (resource) => {
          const query =
            "/api/3/action/datastore_search?resource_id=" + resource.id;
          const top = await fetch(
            CKAN +
              query +
              "&limit=1&sort=" +
              encodeURIComponent("OCCUPANCY_DATE desc"),
          ).then((r) => r.json());
          if (!top.success)
            throw new Error("cannot verify latest shelter date");
          const recs = top.result.records;
          if (!recs.length) return null;
          const dayRaw = recs[0].OCCUPANCY_DATE;
          const raw = String(dayRaw).slice(0, 10);
          // Older 2020s archives use two-digit years; keep their filter value intact.
          const day = /^[0-9]{2}-[0-9]{2}-[0-9]{2}$/.test(raw)
            ? "20" + raw
            : raw;
          return { rid: resource.id, dayRaw, day };
        }),
      )
    ).filter(Boolean);
    snapshots.sort(
      (a, b) => a.day.localeCompare(b.day) || a.rid.localeCompare(b.rid),
    );
    if (!snapshots.length) throw new Error("no records");
    const { rid, dayRaw } = snapshots[snapshots.length - 1];
    // SQL endpoint is disabled on Toronto's CKAN; use datastore_search + aggregate here.
    const ds = "/api/3/action/datastore_search?resource_id=" + rid;
    const filt = encodeURIComponent(JSON.stringify({ OCCUPANCY_DATE: dayRaw }));
    const all = await fetch(CKAN + ds + "&limit=10000&filters=" + filt).then(
      (r) => r.json(),
    );
    const rows = all.result.records;
    let users = 0;
    const locs = new Set();
    for (const r of rows) {
      users += Number(r.SERVICE_USER_COUNT) || 0;
      locs.add(r.LOCATION_ID);
    }
    const day = String(dayRaw).slice(0, 10);
    stats.innerHTML =
      "<b>" +
      users.toLocaleString() +
      "</b> people served<br>" +
      "across <b>" +
      rows.length +
      "</b> programs at <b>" +
      locs.size +
      "</b> locations<br>" +
      '<span style="color:#666">Toronto shelter system, ' +
      day +
      " &middot; " +
      '<a href="https://open.toronto.ca/dataset/' +
      DATASET +
      '/" target="_blank" rel="noopener">source</a></span>';
  } catch (e) {
    stats.innerHTML =
      '<span style="color:#888">Live shelter stats unavailable offline. ' +
      '<a href="https://open.toronto.ca/dataset/' +
      DATASET +
      '/" target="_blank" rel="noopener">Open the dataset &rarr;</a></span>';
  }
}
loadShelterStats();
