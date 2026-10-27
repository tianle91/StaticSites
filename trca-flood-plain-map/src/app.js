const $ = (id) => document.getElementById(id),
  esc = Explorer.esc;
const map = L.map("map", { preferCanvas: true }).setView([43.74, -79.43], 11);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);
const groups = {
    polygons: L.featureGroup().addTo(map),
    lines: L.featureGroup().addTo(map),
  },
  features = [...DATA.polygons.features, ...DATA.lines.features];
for (const name of [
  ...new Set(features.map((f) => f.properties.Watershed).filter(Boolean)),
].sort()) {
  const o = document.createElement("option");
  o.value = name;
  o.textContent = name;
  $("watershed").append(o);
}
function lineColor(label) {
  label = label.toUpperCase();
  return label.includes("SCREENING")
    ? "#7f2020"
    : label.includes("SPILL")
      ? "#e33636"
      : label.includes("UNDEFINED")
        ? "#c655d8"
        : label.includes("ENGINEERED")
          ? "#258ac2"
          : label.includes("ESTIMATED")
            ? "#56abc3"
            : "#d68d12";
}
let visible = [];
function update() {
  const q = $("search").value.toLowerCase().trim(),
    watershed = $("watershed").value,
    counts = {};
  visible = [];
  for (const group of Object.values(groups)) group.clearLayers();
  for (const kind of ["polygons", "lines"]) {
    const chosen = DATA[kind].features.filter((f) => {
      const p = f.properties;
      return (
        (!watershed || p.Watershed === watershed) &&
        (!q ||
          [p.Watershed, p.FloodPlainSource, p.Layer]
            .join(" ")
            .toLowerCase()
            .includes(q))
      );
    });
    counts[kind] = chosen.length;
    if (!Explorer.enabled(kind)) continue;
    for (const f of chosen) {
      if (!f.geometry) {
        visible.push({ f, layer: null });
        continue;
      }
      const layer = L.geoJSON(f, {
        style: () =>
          kind === "polygons"
            ? { color: "#258ac2", weight: 1, fillOpacity: 0.35 }
            : {
                color: lineColor(f.properties.Layer || ""),
                weight: /ENGINEERED|ESTIMATED/.test(f.properties.Layer || "")
                  ? 1.3
                  : 2.5,
                dashArray: (f.properties.Layer || "").includes("ESTIMATED")
                  ? "5 4"
                  : null,
              },
      });
      const p = f.properties;
      layer.bindPopup(
        "<strong>" +
          esc(p.FloodPlainSource || p.Layer || "Flood plain") +
          "</strong><br>" +
          esc(p.Watershed) +
          "<br><small>Generalized TRCA data; confirm precise limits with TRCA.</small>",
      );
      groups[kind].addLayer(layer);
      visible.push({ f, layer });
    }
  }
  Explorer.layerCounts(counts);
  Explorer.count(
    visible.length,
    "features",
    visible.filter((e) => e.layer).length,
    "",
    "without geometry",
  );
  Explorer.results(
    visible,
    (e) =>
      e.f.properties.FloodPlainSource || e.f.properties.Layer || "Flood plain",
    (e) =>
      (e.f.properties.Watershed || "Watershed not specified") +
      (e.layer ? "" : " · No geometry"),
    (e) => {
      if (e.layer) {
        Explorer.fit(map, e.layer.getBounds(), 15);
        e.layer.openPopup();
      } else
        Explorer.detail(
          "Flood plain record",
          "<p>" +
            esc(e.f.properties.Watershed) +
            " · No drawable geometry.</p>",
        );
    },
  );
}
Explorer.layers(
  [
    { id: "polygons", label: "Flood plain polygons", color: "#258ac2" },
    { id: "lines", label: "Boundaries, spills and updates", color: "#d68d12" },
  ],
  update,
);
let pending;
$("search").addEventListener("input", () => {
  clearTimeout(pending);
  pending = setTimeout(update, 200);
});
$("watershed").onchange = update;
Explorer.stamp(DATA.retrieved_at);
Explorer.connect(map, {
  bounds: () =>
    L.featureGroup(
      visible.filter((e) => e.layer).map((e) => e.layer),
    ).getBounds(),
  maxZoom: 15,
});
update();
$("fit").click();
