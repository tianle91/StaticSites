/* Optional browser-logic checks using Node's built-ins only.
 * Run: node admin_tests/map_explorer.cjs
 * This complements real-browser layout checks; it does not emulate Leaflet's renderer.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "..");
const expected = {
  "ontario-physiotherapy-clinics-map": [255, 50],
  "toronto-building-permits-map": [200984, 155887],
  "toronto-crime-map": [66256, 28839],
  "toronto-dinesafe-map": [19770, 101],
  "toronto-vulnerable-services-map": [114, 113],
  "trca-flood-plain-map": [6783, 5482],
  "union-station-transit-isochrone": [129, 129],
};
const shared = fs.readFileSync(
  path.join(root, "src/staticsites/assets/maps/explorer.js"),
  "utf8",
);
async function harness(slug, mobile = false, override = {}) {
  const elements = new Map();
  const chunks = [];
  class Element {
    constructor(tag = "div") {
      this.tagName = tag;
      this.children = [];
      this.listeners = {};
      this.style = {};
      this.dataset = {};
      this.attributes = {};
      this._text = "";
      this.hidden = false;
      const classes = new Set();
      this.classList = {
        add: (c) => classes.add(c),
        remove: (c) => classes.delete(c),
        contains: (c) => classes.has(c),
        toggle: (c) => {
          if (classes.has(c)) {
            classes.delete(c);
            return false;
          }
          classes.add(c);
          return true;
        },
      };
    }
    set id(value) {
      this._id = value;
      elements.set(value, this);
    }
    get id() {
      return this._id;
    }
    set textContent(value) {
      this._text = String(value);
      this.children = [];
    }
    get textContent() {
      return this._text + this.children.map((c) => c.textContent).join("");
    }
    set innerHTML(value) {
      this._text = String(value);
      this.children = [];
    }
    get innerHTML() {
      return this.textContent;
    }
    append(...items) {
      this.children.push(...items);
    }
    replaceChildren(...items) {
      this._text = "";
      this.children = items;
    }
    setAttribute(key, value) {
      this.attributes[key] = value;
    }
    removeAttribute(key) {
      delete this.attributes[key];
    }
    addEventListener(key, fn) {
      (this.listeners[key] ||= []).push(fn);
    }
    focus() { this.focused = true; }
    blur() { this.focused = false; }
    remove() { this.textContent = ""; this.removed = true; }
    close() {
      this.open = false;
    }
    showModal() {
      this.open = true;
    }
    getBoundingClientRect() {
      return { height: 300 };
    }
    click() {
      this.onclick?.();
    }
  }
  const get = (id) => {
    if (!elements.has(id)) {
      const e = new Element();
      e.id = id;
      e.value = "";
    }
    return elements.get(id);
  };
  const tabs = ["layers", "results", "sources"].map((name) => {
    const e = get(name + "-tab");
    e.dataset.tab = name;
    return e;
  });
  const panels = ["layers", "results", "sources"].map((name) =>
    get(name + "-panel"),
  );
  const document = {
    getElementById: get,
    createElement: (tag) => new Element(tag),
    createTextNode: (value) => ({ textContent: String(value) }),
    addEventListener(name, fn) { (document.listeners[name] ||= []).push(fn); },
    listeners: {},
    documentElement: { style: { setProperty() {} } },
    querySelector: () => ({ content: "test-build" }),
    querySelectorAll: (selector) =>
      selector.includes("[role=tab]") ? tabs : panels,
  };
  class Bounds {
    constructor(points = []) {
      this.points = points;
    }
    isValid() {
      return this.points.length > 0;
    }
    extend(b) {
      if (b instanceof Bounds) this.points.push(...b.points);
      return this;
    }
  }
  const markers = [],
    controls = [],
    map = {
      layers: new Set(),
      handlers: {},
      setView(ll, zoom) {
        this.center = ll;
        this.zoom = zoom;
        return this;
      },
      fitBounds(bounds, opts) {
        this.lastFit = { bounds, opts };
        return this;
      },
      panBy(offset) {
        this.offset = offset;
      },
      getZoom() {
        return this.zoom;
      },
      addLayer(layer) {
        this.layers.add(layer);
        return this;
      },
      removeLayer(layer) {
        this.layers.delete(layer);
      },
      on(name, fn) {
        this.handlers[name] = fn;
      },
      closePopup() {
        this.popupClosed = true;
      },
      addControl(control) {
        control.onAdd();
        controls.push(control);
      },
      distance() {
        return 100;
      },
    };
  function layer(ll, options = {}) {
    return {
      options,
      children: [],
      ll,
      addTo(target) {
        target.addLayer(this);
        return this;
      },
      addLayer(child) {
        if (!this.children.includes(child)) this.children.push(child);
        return this;
      },
      addLayers(children) {
        const finish = () => {
          this.children.push(...children);
          this.options.chunkProgress?.(children.length, children.length);
        };
        if (override.deferChunks && this.options.chunkedLoading) chunks.push(finish);
        else finish();
        return this;
      },
      removeLayer(child) {
        this.children = this.children.filter((c) => c !== child);
      },
      hasLayer(child) {
        return this.children.includes(child);
      },
      clearLayers() {
        this.children = [];
      },
      bindPopup(content, options = {}) {
        this.popup = content;
        this.popupOptions = options;
        return this;
      },
      openPopup() {
        return this;
      },
      handlers: {},
      on(name, fn) {
        this.handlers[name] = fn;
        return this;
      },
      getAllChildMarkers() {
        return this.children;
      },
      getLatLng() {
        return this.ll;
      },
      setLatLng(value) {
        this.ll = value;
        return this;
      },
      setRadius(value) {
        this.options.radius = value;
        return this;
      },
      getBounds() {
        return new Bounds([ll || [43.7, -79.4]]);
      },
    };
  }
  const L = {
    map: () => map,
    tileLayer: () => layer(),
    layerGroup: () => layer(),
    featureGroup: (entries) => {
      const l = layer();
      l.children = entries || [];
      return l;
    },
    markerClusterGroup: (opts) => layer(null, opts),
    marker: (ll, opts) => {
      const m = layer(ll, opts);
      markers.push(m);
      return m;
    },
    circle: layer,
    circleMarker: layer,
    divIcon: (opts) => opts,
    latLngBounds: (points) => new Bounds(points),
    geoJSON: () => layer(),
    Control: {
      extend: (def) =>
        function () {
          Object.assign(this, def);
        },
    },
    DomUtil: {
      create: (tag, cls, parent) => {
        const e = new Element(tag);
        if (parent) parent.append(e);
        return e;
      },
    },
    DomEvent: { disableClickPropagation() {}, disableScrollPropagation() {} },
  };
  const geoCalls = [];
  const html = fs.readFileSync(
    path.join(root, slug, "output", slug + ".html"),
    "utf8",
  );
  const inert = html.match(/<script type="application\/json" id="permit-data">([\s\S]*?)<\/script>/);
  const start = html.indexOf("const DATA = ") + "const DATA = ".length;
  const data = override.data || JSON.parse(inert ? inert[1] : html.slice(start, html.indexOf(";\n", start)));
  get("permit-data").textContent = override.payload ?? JSON.stringify(data);
  const window = {
    innerWidth: mobile ? 390 : 1280, innerHeight: 844,
    listeners: {},
    addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); },
    visualViewport: { height: 844, addEventListener() {} },
    location: { reload() {} },
  };
  const context = vm.createContext({
    URL,
    document,
    window,
    L,
    DATA: data,
    matchMedia: () => ({ matches: mobile }),
    navigator: {
      userAgent: "test browser",
      geolocation: { getCurrentPosition: (...args) => geoCalls.push(args) },
    },
    setTimeout: (fn) => {
      fn();
      return 0;
    },
    clearTimeout() {},
    fetch: async () => {
      throw new Error("Offline fixture");
    },
    console: override.console || console,
  });
  const code = fs.readFileSync(
    path.join(root, "src/staticsites/assets/maps/explorer.js"),
    "utf8",
  );
  if (slug !== "toronto-building-permits-map")
    assert.equal(code, shared, slug + " has drifted from the common controls");
  if (["toronto-building-permits-map", "toronto-dinesafe-map"].includes(slug)) {
    vm.runInContext(fs.readFileSync(path.join(root, "src/staticsites/assets/maps/query.js"), "utf8"), context);
    vm.runInContext(fs.readFileSync(path.join(root, slug, "src/search.js"), "utf8"), context);
  }
  if (slug === "toronto-building-permits-map") {
    vm.runInContext(fs.readFileSync(path.join(root, slug, "src/startup.js"), "utf8"), context);
    for (const fn of document.listeners.DOMContentLoaded || []) fn();
  }
  vm.runInContext(code, context);
  await vm.runInContext(
    fs.readFileSync(path.join(root, slug, "src/app.js"), "utf8"),
    context,
  );
  const total = () =>
    Number(get("stats").children[0].textContent.replaceAll(",", ""));
  const inputs = () =>
    get("layer-controls").children.map((label) => label.children[0]);
  const search = (value) => {
    get("search").value = value;
    for (const fn of get("search").listeners.input) fn();
  };
  return { get, map, markers, geoCalls, context, total, inputs, search, window, chunks };
}
async function main() {
  for (const [slug, [total, withoutFirst]] of Object.entries(expected)) {
    const h = await harness(slug);
    assert.equal(h.total(), total, slug + ": initial total");
    assert.equal(h.geoCalls.length, 0, slug + ": location must be click-only");
    h.inputs()[0].checked = false;
    h.inputs()[0].onchange();
    assert.equal(h.total(), withoutFirst, slug + ": deselected layer total");
    h.get("clear-all").click();
    assert.equal(h.total(), 0);
    h.get("select-all").click();
    assert.equal(h.total(), total);
    h.search("no feature can match this unique nonsense");
    assert.equal(h.total(), 0);
    assert.equal(h.get("results").children.length, 0);
    // Layer counts must reset to zero rather than displaying stale values.
    for (const row of h.get("layer-controls").children) {
      if (!row.children[0].dataset.layer.startsWith("band-"))
        assert.equal(row.children[2].textContent, "0");
    }
    h.search("");
    assert.equal(h.total(), total);
    const locate = h.get("locate");
    locate.click();
    assert.equal(locate.disabled, true);
    assert.equal(h.geoCalls.length, 1);
    assert.equal(h.geoCalls[0][2].timeout, 8000);
    for (const code of [1, 2, 3]) {
      h.geoCalls.at(-1)[1]({ code });
      assert.equal(locate.disabled, false);
      assert.match(
        h.get("location-status").textContent,
        /denied|could not|timed out/,
      );
      locate.click();
    }
    const position = {
      coords: { latitude: 43.65, longitude: -79.38, accuracy: 25 },
    };
    h.geoCalls.at(-1)[0](position);
    assert.equal(locate.disabled, false);
    assert.match(h.get("location-status").textContent, /25 m/);
    assert.deepEqual(Array.from(h.map.center), [43.65, -79.38]);
    locate.click();
    h.geoCalls.at(-1)[0](position);
    assert.equal(
      h.markers.filter((m) => m.options.title === "You are here").length,
      1,
    );
    console.log(
      "PASS",
      slug,
      "(counts, search, layers, location success/error/retry)",
    );
    // The same phone controls must work independently in every map project.
    const phone = await harness(slug, true);
    for (const fn of phone.get("search").listeners.focus) fn();
    assert.equal(phone.get("panel").classList.contains("expanded"), true);
    phone.get("sheet-toggle").click();
    assert.equal(phone.get("sheet-toggle").textContent, "Show results & filters");
    phone.get("provenance").click();
    assert.equal(phone.get("panel").classList.contains("expanded"), true);
    assert.equal(phone.get("sources-panel").hidden, false);
    const detailMarker = phone.markers.find((m) => m.popupOptions?.detailTitle);
    if (detailMarker) {
      phone.map.handlers.popupopen({ popup: {
        options: detailMarker.popupOptions,
        getContent: () => detailMarker.popup,
      } });
      assert.equal(phone.map.popupClosed, true);
      assert.equal(phone.get("record-detail").open, true);
      assert.ok(phone.get("record-body").innerHTML.length > 0);
      phone.get("record-close").click();
      assert.equal(phone.get("record-detail").open, false);
    }
    if (slug === "toronto-dinesafe-map") {
      phone.get("results").children[0].click();
      assert.equal(phone.get("record-detail").open, true, "phone inspection history uses the dialog");
      assert.match(phone.get("record-body").innerHTML, /Inspection history/);
      assert.equal(phone.get("sidebar").classList.contains("open"), false);
    }
  }
  const mobile = await harness("ontario-physiotherapy-clinics-map", true);
  mobile.get("fit").click();
  assert.equal(mobile.map.lastFit.opts.paddingBottomRight[1], 330);
  console.log("PASS mobile fit reserves bottom-sheet space");

  const crime = await harness("toronto-crime-map");
  crime.search("GO-2025206289");
  assert.equal(crime.total(), 1);
  const cluster = [...crime.map.layers].find(
    (l) => l.options?.iconCreateFunction,
  );
  assert.equal(
    cluster.children.length,
    2,
    "keep both published points for the same incident",
  );
  assert.match(
    cluster.options.iconCreateFunction({
      getAllChildMarkers: () => cluster.children,
    }).html,
    />1<\/div>/,
  );
  const type = crime.inputs().find((i) => i.dataset.layer === "Assault");
  type.checked = false;
  type.onchange();
  assert.equal(crime.total(), 1);
  assert.equal(
    cluster.children.length,
    1,
    "only the selected type point remains mapped",
  );
  console.log("PASS overlapping incident types and differing source points");

  const transit = await harness("union-station-transit-isochrone");
  transit.context.DATA.geo.features = [
    {
      properties: { minutes: 30 },
      geometry: {
        type: "MultiPolygon",
        coordinates: [
          [
            [
              [0, 0],
              [10, 0],
              [10, 10],
              [0, 10],
              [0, 0],
            ],
            [
              [4, 4],
              [6, 4],
              [6, 6],
              [4, 6],
              [4, 4],
            ],
          ],
        ],
      },
    },
  ];
  assert.equal(vm.runInContext("bandForPoint(5,5)", transit.context), null);
  assert.equal(vm.runInContext("bandForPoint(2,2).minutes", transit.context), 30);
  console.log("PASS transit travel-time bands exclude polygon holes");
}
module.exports = { harness };
if (require.main === module) main().catch((error) => { console.error(error); process.exitCode = 1; });
