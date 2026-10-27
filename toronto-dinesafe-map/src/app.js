// preferCanvas: the full DineSafe set is ~16k points; canvas keeps it smooth.
const map = L.map("map", { preferCanvas: true }).setView(
  DATA.center,
  DATA.zoom,
);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

// One toggleable layer per status category.
const layers = {};
for (const key in DATA.categories) layers[key] = L.layerGroup().addTo(map);

function esc(s) {
  return String(s == null ? "" : s).replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
  );
}
function catFor(key) {
  return DATA.categories[key] || { label: "Other / Unknown", color: "#777" };
}
// Map DineSafe's severity wording to a colour band (crucial > significant > minor).
function sevClass(sev) {
  const s = String(sev || "").toLowerCase();
  if (s.includes("crucial")) return "crucial";
  if (s.includes("significant")) return "significant";
  if (s.includes("minor")) return "minor";
  return "other";
}

// Keep marker + record together so the search box can filter without rebuilding.
const entries = [];
for (const e of DATA.establishments) {
  const cat = catFor(e.cat);
  const marker = L.circleMarker([e.lat, e.lon], {
    radius: 6,
    color: "#fff",
    weight: 1,
    fillColor: cat.color,
    fillOpacity: 0.9,
  });
  marker.on("click", () => openSidebar(e));
  marker.addTo(layers[e.cat]);
  entries.push({
    marker,
    rec: e,
    cat: e.cat,
    haystack: [e.name, e.type, e.address].join(" ").toLowerCase(),
  });
}

// ---- Detail sidebar -------------------------------------------------------
// Opens on a marker or search-result click; shows the current status, key
// facts, and the full inspection history (each visit's infractions).
const DINESAFE_URL =
  "https://www.toronto.ca/community-people/health-wellness-care/health-programs-advice/food-safety/dinesafe/";
const sidebar = document.getElementById("sidebar");
let detailOpener = null;

function fact(k, v) {
  return (
    '<div class="fact"><div class="k">' +
    esc(k) +
    '</div><div class="v">' +
    esc(v) +
    "</div></div>"
  );
}

function renderInspection(ins) {
  const c = catFor(ins.cat);
  const n =
    ins.infraction_count != null
      ? ins.infraction_count
      : (ins.infractions || []).length;
  let body;
  if (ins.infractions && ins.infractions.length) {
    body =
      '<ul class="infractions">' +
      ins.infractions
        .map((f) => {
          const sev = f.severity
            ? '<span class="sev sev-' +
              sevClass(f.severity) +
              '">' +
              esc(f.severity) +
              "</span>"
            : "";
          return (
            "<li>" +
            sev +
            esc(f.detail || "Infraction recorded") +
            (f.action
              ? '<div class="action">Action &mdash; ' + esc(f.action) + "</div>"
              : "") +
            (f.outcome
              ? '<div class="action">Outcome &mdash; ' +
                esc(f.outcome) +
                "</div>"
              : "") +
            "</li>"
          );
        })
        .join("") +
      "</ul>";
  } else if (n > 0 && ins.details_available === false) {
    // Summary-only data/dinesafe.json: we know the count but not the detail.
    body =
      '<p class="muted">' +
      n +
      " infraction" +
      (n === 1 ? "" : "s") +
      " recorded. Detailed descriptions are unavailable in this snapshot.</p>";
  } else if (n > 0) {
    body =
      '<p class="muted">' +
      n +
      " infraction" +
      (n === 1 ? "" : "s") +
      " recorded.</p>";
  } else {
    body = '<p class="no-infr">&#10003; No infractions recorded.</p>';
  }
  return (
    '<li class="insp"><div class="insp-top">' +
    '<span class="insp-date">' +
    esc(ins.date || "Date unknown") +
    "</span>" +
    '<span class="badge" style="background:' +
    c.color +
    '">' +
    esc(c.label) +
    "</span>" +
    "</div>" +
    body +
    "</li>"
  );
}

// The timeline the sidebar shows: the establishment's own `inspections` when the
// data carries them, otherwise a single entry synthesised from the summary fields
// (count is known, per-infraction detail is not until `make data` is re-run).
function timelineFor(e) {
  if (e.inspections && e.inspections.length) return e.inspections;
  if (e.last_inspection || e.status) {
    return [
      {
        date: e.last_inspection || "",
        status: e.status || "",
        cat: e.cat,
        infractions: [],
        infraction_count: e.infractions || 0,
        details_available: false,
      },
    ];
  }
  return [];
}

function openSidebar(e) {
  if (!sidebar.classList.contains("open"))
    detailOpener = document.activeElement;
  const cat = catFor(e.cat);
  document.getElementById("sb-title").textContent = e.name || "Establishment";
  document.getElementById("sb-badge").innerHTML =
    '<span class="badge" style="background:' +
    cat.color +
    '">' +
    esc(cat.label) +
    "</span>";
  document.getElementById("sb-sub").innerHTML =
    (e.type ? esc(e.type) : "") +
    (e.type && e.address ? " &middot; " : "") +
    (e.address ? esc(e.address) : "");

  const inspections = timelineFor(e);
  const latestN = e.infractions || 0;
  let facts = fact("Last inspected", e.last_inspection || "\u2014");
  facts += fact("Infractions (latest)", latestN);
  facts += fact("Inspections on record", inspections.length || "\u2014");
  if (e.min_per_year) facts += fact("Min. inspections/yr", e.min_per_year);

  const dest = encodeURIComponent(
    e.address ? e.address + ", Toronto, ON" : e.lat + "," + e.lon,
  );
  const actions =
    '<div class="sb-actions">' +
    '<a href="https://www.google.com/maps/dir/?api=1&destination=' +
    dest +
    '" target="_blank" rel="noopener">Directions &rarr;</a>' +
    '<a class="secondary" href="' +
    DINESAFE_URL +
    '" target="_blank" rel="noopener">DineSafe program</a></div>';

  const history = inspections.length
    ? '<h3>Inspection history</h3><ul class="timeline">' +
      inspections.map(renderInspection).join("") +
      "</ul>"
    : '<p class="muted">No inspection records on file.</p>';

  document.getElementById("sb-body").innerHTML =
    '<div class="facts">' + facts + "</div>" + actions + history;
  sidebar.classList.add("open");
  sidebar.setAttribute("aria-hidden", "false");
  sidebar.inert = false;
  sidebar.scrollTop = 0;
  document.getElementById("sb-close").focus();
}

function closeSidebar() {
  sidebar.classList.remove("open");
  sidebar.setAttribute("aria-hidden", "true");
  sidebar.inert = true;
  if (detailOpener) {
    detailOpener.focus();
    detailOpener = null;
  }
}
document.getElementById("sb-close").addEventListener("click", closeSidebar);
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") closeSidebar();
});
// Open at the default downtown view (ZOOM above) rather than fitting all ~18k
// city-wide pins, which would zoom right back out; a search still fits its matches.

let visible = [],
  userLoc = null;
const nearToggle = document.getElementById("near-toggle"),
  nearHint = document.getElementById("near-hint");
function fmtDist(m) {
  return m < 950
    ? Math.round(m / 10) * 10 + " m"
    : (m / 1000).toFixed(1) + " km";
}
function update() {
  const q = document.getElementById("search").value.trim().toLowerCase(),
    counts = Object.fromEntries(
      Object.keys(DATA.categories).map((k) => [k, 0]),
    );
  visible = [];
  for (const e of entries) {
    const match = !q || e.haystack.includes(q);
    if (match) counts[e.cat]++;
    const show = match && Explorer.enabled(e.cat);
    if (show) {
      layers[e.cat].addLayer(e.marker);
      visible.push(e);
    } else layers[e.cat].removeLayer(e.marker);
  }
  const near = nearToggle.checked && userLoc;
  if (near) {
    for (const e of visible)
      e._dist = map.distance(userLoc, [e.rec.lat, e.rec.lon]);
    visible.sort((a, b) => a._dist - b._dist);
  }
  Explorer.layerCounts(counts);
  Explorer.count(visible.length, "establishments", visible.length);
  Explorer.results(
    visible,
    (e) => e.rec.name,
    (e) =>
      [e.rec.address, catFor(e.cat).label, near ? fmtDist(e._dist) : ""]
        .filter(Boolean)
        .join(" · "),
    (e) => {
      Explorer.focus(map, e.marker.getLatLng());
      openSidebar(e.rec);
    },
  );
  nearHint.textContent = userLoc
    ? ""
    : " · use the location button to rank nearby";
}
Explorer.layers(
  Object.entries(DATA.categories).map(([id, c]) => ({ id, ...c })),
  update,
);
document.getElementById("source").href = DATA.meta.source_page;
document.getElementById("generated").textContent = DATA.meta.generated_at;
if (DATA.meta.sample) {
  const b = document.getElementById("sample-banner");
  b.hidden = false;
  b.textContent = "Sample data: fictional establishments.";
}
nearToggle.addEventListener("change", update);
document.getElementById("search").addEventListener("input", update);
Explorer.stamp(DATA.meta.generated_at);
Explorer.connect(map, {
  bounds: () => L.latLngBounds(visible.map((e) => e.marker.getLatLng())),
  located: (pos) => {
    userLoc = [pos.coords.latitude, pos.coords.longitude];
    update();
  },
});
closeSidebar();
update();
