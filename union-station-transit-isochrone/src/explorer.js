/* Project-local explorer UI. No source is loaded from another project. */
const Explorer = (() => {
  const byId = (id) => document.getElementById(id);
  const esc = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const choices = new Map();
  const mobile = () => matchMedia("(max-width:760px)").matches;
  function collapse() {
    byId("panel").classList.remove("expanded");
    byId("sheet-toggle").setAttribute("aria-expanded", "false");
    byId("sheet-toggle").setAttribute("aria-label", "Expand map controls");
  }
  function sheetHeight() {
    return mobile() ? byId("panel").getBoundingClientRect().height : 0;
  }
  function tab(name) {
    document.querySelectorAll(".explorer-tabs [role=tab]").forEach((button) => {
      button.setAttribute("aria-selected", String(button.dataset.tab === name));
      button.tabIndex = button.dataset.tab === name ? 0 : -1;
    });
    document
      .querySelectorAll(".explorer-panel")
      .forEach((panel) => (panel.hidden = panel.id !== name + "-panel"));
  }
  document.querySelectorAll(".explorer-tabs [role=tab]").forEach((button) => {
    button.onclick = () => tab(button.dataset.tab);
    button.onkeydown = (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
        return;
      event.preventDefault();
      const buttons = [
        ...document.querySelectorAll(".explorer-tabs [role=tab]"),
      ];
      const index = buttons.indexOf(button);
      const next =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? buttons.length - 1
            : (index + (event.key === "ArrowRight" ? 1 : buttons.length - 1)) %
              buttons.length;
      buttons[next].focus();
      tab(buttons[next].dataset.tab);
    };
  });
  tab("layers");
  byId("provenance").onclick = () => tab("sources");
  byId("sheet-toggle").onclick = () => {
    const expanded = byId("panel").classList.toggle("expanded");
    byId("sheet-toggle").setAttribute("aria-expanded", String(expanded));
    byId("sheet-toggle").setAttribute(
      "aria-label",
      expanded ? "Collapse map controls" : "Expand map controls",
    );
  };
  byId("search").addEventListener("input", () =>
    tab(byId("search").value.trim() ? "results" : "layers"),
  );
  const status = (message) => {
    byId("location-status").textContent = message;
  };
  function count(
    total,
    unit,
    mapped,
    note = "",
    missingLabel = "without a pin",
  ) {
    const stats = byId("stats");
    stats.replaceChildren();
    const number = document.createElement("strong");
    number.textContent = total.toLocaleString();
    stats.append(number, document.createTextNode(" " + unit));
    const secondary = document.createElement("div");
    secondary.className = "secondary";
    secondary.textContent =
      mapped == null
        ? note
        : mapped.toLocaleString() +
          " mapped · " +
          (total - mapped).toLocaleString() +
          " " +
          missingLabel +
          (note ? " · " + note : "");
    stats.append(secondary);
  }
  function layers(items, onChange) {
    const target = byId("layer-controls");
    target.replaceChildren();
    choices.clear();
    for (const item of items) {
      const label = document.createElement("label");
      label.className = "layer-row";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = item.checked !== false;
      input.dataset.layer = item.id;
      const name = document.createElement("span");
      name.className = "layer-label";
      const dot = document.createElement("span");
      dot.className = "swatch";
      dot.style.background = item.color;
      name.append(dot, document.createTextNode(item.label));
      const n = document.createElement("span");
      n.className = "layer-count";
      n.textContent =
        typeof item.count === "number"
          ? item.count.toLocaleString()
          : (item.count ?? "");
      label.append(input, name, n);
      target.append(label);
      choices.set(item.id, { input, n, item });
      input.onchange = () => {
        if (item.layer) {
          if (input.checked) item.layer.addTo(item.map);
          else item.map.removeLayer(item.layer);
        }
        onChange();
      };
    }
    for (const [id, value] of [
      ["select-all", true],
      ["clear-all", false],
    ])
      byId(id).onclick = () => {
        for (const { input, item } of choices.values()) {
          input.checked = value;
          if (item.layer) {
            if (value) item.layer.addTo(item.map);
            else item.map.removeLayer(item.layer);
          }
        }
        onChange();
      };
  }
  const enabled = (id) => choices.get(id)?.input.checked ?? false;
  function layerCounts(counts) {
    for (const [id, n] of Object.entries(counts)) {
      const choice = choices.get(id);
      if (choice) choice.n.textContent = Number(n).toLocaleString();
    }
  }
  function results(items, label, summary, onSelect, limit = 50) {
    const target = byId("results");
    target.replaceChildren();
    for (const item of items.slice(0, limit)) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "feature-result";
      const title = document.createElement("strong");
      title.textContent = label(item);
      const sub = document.createElement("small");
      sub.textContent = summary(item);
      button.append(title, sub);
      button.onclick = () => onSelect(item);
      target.append(button);
    }
    byId("result-note").textContent = !items.length
      ? "No features match the selected layers and search."
      : items.length > limit
        ? "First " +
          limit +
          " of " +
          items.length.toLocaleString() +
          " matches listed. Narrow the search to find a specific feature."
        : items.length.toLocaleString() + " matching features.";
  }
  function stamp(value) {
    byId("snapshot-date").textContent = value
      ? "Snapshot " + String(value).slice(0, 10)
      : "Committed snapshot";
    byId("snapshot-provenance").textContent = byId("snapshot-date").textContent;
  }
  function fit(map, bounds, maxZoom = 16) {
    collapse();
    if (bounds?.isValid()) {
      map.fitBounds(bounds, {
        paddingTopLeft: [30, 30],
        paddingBottomRight: [30, sheetHeight() + 30],
        maxZoom,
      });
      status("");
    } else status("No mapped features match the selected layers and search.");
  }
  function focus(map, ll, zoom = 16) {
    collapse();
    map.setView(ll, zoom, { animate: false });
    if (mobile()) map.panBy([0, sheetHeight() / 2], { animate: false });
  }
  function detail(title, html) {
    const dialog = byId("record-detail");
    byId("record-title").textContent = title;
    byId("record-body").innerHTML = html;
    if (!dialog.open) dialog.showModal();
  }
  byId("record-close").onclick = () => byId("record-detail").close();
  function connect(map, config) {
    if (mobile()) map.panBy([0, sheetHeight() / 2], { animate: false });
    let userMarker = null,
      accuracyCircle = null;
    const Control = L.Control.extend({
      options: { position: "topleft" },
      onAdd() {
        const container = L.DomUtil.create(
          "div",
          "leaflet-bar explorer-control",
        );
        const button = L.DomUtil.create("button", "", container);
        button.type = "button";
        button.id = "locate";
        button.title = "Center on my location";
        button.setAttribute("aria-label", "Center on my location");
        button.textContent = "◎";
        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.disableScrollPropagation(container);
        button.onclick = () => {
          if (!navigator.geolocation) {
            status(
              "Location is unavailable. Use a browser with location support on HTTPS or localhost.",
            );
            return;
          }
          button.disabled = true;
          button.setAttribute("aria-busy", "true");
          status("Finding your location…");
          const finish = (message) => {
            button.disabled = false;
            button.removeAttribute("aria-busy");
            status(message);
          };
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              const ll = [pos.coords.latitude, pos.coords.longitude],
                accuracy = pos.coords.accuracy;
              if (userMarker) userMarker.setLatLng(ll);
              else
                userMarker = L.marker(ll, {
                  icon: L.divIcon({
                    className: "",
                    html: '<div class="you-dot"></div>',
                    iconSize: [18, 18],
                    iconAnchor: [9, 9],
                  }),
                  zIndexOffset: 2000,
                  title: "You are here",
                })
                  .addTo(map)
                  .bindPopup("You are here");
              if (Number.isFinite(accuracy) && accuracy > 0) {
                if (accuracyCircle)
                  accuracyCircle.setLatLng(ll).setRadius(accuracy);
                else
                  accuracyCircle = L.circle(ll, {
                    radius: accuracy,
                    color: "#258fc1",
                    weight: 1,
                    fillOpacity: 0.08,
                    interactive: false,
                  }).addTo(map);
              } else if (accuracyCircle) {
                map.removeLayer(accuracyCircle);
                accuracyCircle = null;
              }
              focus(map, ll, 14);
              finish(
                "Centered on your location." +
                  (Number.isFinite(accuracy) && accuracy > 0
                    ? " Browser accuracy: about " +
                      Math.max(1, Math.round(accuracy)).toLocaleString() +
                      " m."
                    : ""),
              );
              if (config.located) config.located(pos);
            },
            (error) =>
              finish(
                {
                  1: "Location access was denied. Enable location for this site in your browser, then try again.",
                  2: "Your location could not be determined. Please try again.",
                  3: "Finding your location timed out. Please try again.",
                }[error.code] ||
                  "Your location could not be determined. Please try again.",
              ),
            { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
          );
        };
        return container;
      },
    });
    map.addControl(new Control());
    const Fit = L.Control.extend({
      options: { position: "topleft" },
      onAdd() {
        const container = L.DomUtil.create(
            "div",
            "leaflet-bar explorer-control",
          ),
          button = L.DomUtil.create("button", "", container);
        button.type = "button";
        button.id = "fit";
        button.title = "Fit matching features";
        button.setAttribute("aria-label", "Fit matching features");
        button.textContent = "⛶";
        L.DomEvent.disableClickPropagation(container);
        button.onclick = () => {
          fit(map, config.bounds(), config.maxZoom || 16);
        };
        return container;
      },
    });
    map.addControl(new Fit());
    // Location stays in memory only and is requested solely by the locate button.
  }
  return {
    esc,
    tab,
    count,
    layers,
    enabled,
    layerCounts,
    results,
    stamp,
    fit,
    focus,
    detail,
    connect,
    collapse,
    status,
  };
})();
