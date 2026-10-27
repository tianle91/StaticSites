const map = L.map("map").setView(DATA.center, DATA.zoom);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

// One toggleable layer per facility type.
const layers = {};
for (const key in DATA.categories) layers[key] = L.layerGroup().addTo(map);

function markerIcon(color) {
  return L.divIcon({
    className: "",
    html:
      '<div style="width:16px;height:16px;border-radius:50%;background:' +
      color +
      ';border:2px solid #fff;box-shadow:0 0 3px rgba(0,0,0,.5)"></div>',
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -8],
  });
}

function esc(s) {
  return String(s == null ? "" : s).replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
  );
}

// Keep marker + record together so the search box can filter without rebuilding.
const entries = [];
const bounds = [];
for (const c of DATA.clinics) {
  const cat = DATA.categories[c.category] || {
    label: c.facility_type,
    color: "#555",
  };
  const popup =
    "<b>" +
    esc(c.name) +
    "</b><br>" +
    '<span class="cat">' +
    esc(cat.label) +
    "</span><br>" +
    (c.address ? esc(c.address) + "<br>" : "") +
    (c.precision === "city"
      ? '<span class="precision-note">Pin shows the city centre &mdash; exact address above.</span><br>'
      : "") +
    (c.phone
      ? '<a href="tel:' +
        esc(c.phone.replace(/[^0-9+]/g, "")) +
        '">' +
        esc(c.phone) +
        "</a><br>"
      : "") +
    (c.email
      ? '<a href="mailto:' + esc(c.email) + '">' + esc(c.email) + "</a><br>"
      : "") +
    '<a href="https://www.google.com/maps/dir/?api=1&destination=' +
    encodeURIComponent(c.address || c.lat + "," + c.lon) +
    '" target="_blank" rel="noopener">Directions &rarr;</a>';
  const marker = L.marker([c.lat, c.lon], {
    icon: markerIcon(cat.color),
    title: c.name,
  }).bindPopup(popup);
  marker.addTo(layers[c.category]);
  entries.push({
    marker,
    clinic: c,
    haystack: [c.name, c.city, c.postal_code, c.address]
      .join(" ")
      .toLowerCase(),
  });
  bounds.push([c.lat, c.lon]);
}

let visible = [];
Explorer.layers(
  Object.entries(DATA.categories).map(([id, c]) => ({ id, ...c })),
  update,
);
function update() {
  const q = document.getElementById("search").value.trim().toLowerCase(),
    counts = Object.fromEntries(
      Object.keys(DATA.categories).map((k) => [k, 0]),
    );
  visible = [];
  for (const e of entries) {
    const match = !q || e.haystack.includes(q),
      key = e.clinic.category;
    counts[key] = (counts[key] || 0) + (match ? 1 : 0);
    const show = match && Explorer.enabled(key);
    if (show) {
      layers[key].addLayer(e.marker);
      visible.push(e);
    } else layers[key].removeLayer(e.marker);
  }
  Explorer.layerCounts(counts);
  Explorer.count(visible.length, "locations", visible.length);
  Explorer.results(
    visible,
    (e) => e.clinic.name,
    (e) =>
      e.clinic.address +
      (e.clinic.precision === "city" ? " · City-centre pin" : ""),
    (e) => {
      Explorer.focus(map, e.marker.getLatLng());
      e.marker.openPopup();
    },
  );
}
document.getElementById("search").addEventListener("input", update);
document.getElementById("source").href = DATA.meta.source_page;
document.getElementById("generated").textContent = DATA.meta.generated_at;
Explorer.stamp(DATA.meta.generated_at);
Explorer.connect(map, {
  bounds: () => L.latLngBounds(visible.map((e) => e.marker.getLatLng())),
});
update();

if (visible.length)
  Explorer.fit(
    map,
    L.latLngBounds(visible.map((e) => e.marker.getLatLng())),
    12,
  );
