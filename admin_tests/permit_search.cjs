/* Optional Node 18+ regression checks: node admin_tests/permit_search.cjs */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { harness } = require("./map_explorer.cjs");
const root = path.resolve(__dirname, "..");
for (const slug of ["toronto-building-permits-map", "toronto-dinesafe-map"]) {
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(root, slug, "src/search.js"), "utf8"), context);
  const compile = vm.runInContext("FeatureSearch.compile", context);
  for (const number of ["38", "58", "118", "248", "8A", "8-10"])
    assert.equal(compile("8 The Esplanade")(number + " The Esplanade"), false, number);
  assert.equal(compile("8  THE  ESPLANADE")("8 The Esplanade M5E 1A5"), true);
  assert.equal(compile("220 Major St.")("220 MAJOR ST"), true);
  assert.equal(compile("8 The Esplanade")("71 Front St", "", "Mentioned: 8 The Esplanade"), false);
  assert.equal(compile("8A The Esplanade")("8A The Esplanade"), true);
  assert.equal(compile("8-10 The Esplanade")("8–10 The Esplanade"), true);
  assert.equal(compile("8 The Esplanade")("8 The Esplanade Unit 2"), true);
  assert.equal(compile("25 270971 BLD")("220 Major St", "25 270971 BLD"), true);
  assert.equal(compile("interior alterations")("220 Major St", "", "Interior  alterations"), true);
  assert.equal(compile("3 brewers", { addressOnly: false })("120 Adelaide St", "The 3 Brewers"), true);
  assert.equal(compile("8 the esplanade", { addressOnly: false })("38 The Esplanade", "Restaurant at 38 The Esplanade"), false);
  assert.equal(compile("parlour")("58 The Esplanade", "Dolly's Parlour"), true);
  assert.equal(compile("")("anything"), true);
}
async function main() {
  const h = await harness("toronto-building-permits-map", true, { deferChunks: true, console: { error() {} } });
  assert.equal(h.get("search").disabled, true, "disable search until initial insertion completes");
  // Changing the query during an insertion must not leave markers from the old
  // query behind when markercluster resumes its asynchronous work.
  h.search("8 The Esplanade");
  h.search("220  major st.");
  while (h.chunks.length) h.chunks.shift()();
  assert.equal(h.total(), 2);
  const group = [...h.map.layers].find((l) => l.options?.chunkedLoading);
  assert.equal(group.children.length, 1);
  assert.equal(group.children[0].options.recordCount, 2);
  assert.equal(h.get("search").disabled, false);
  assert.equal(h.get("permit-data").removed, true, "release raw JSON after parsing");
  h.search("8 The Esplanade");
  while (h.chunks.length) h.chunks.shift()();
  assert.equal(h.total(), 2);
  h.search("8  The Esplanade");
  while (h.chunks.length) h.chunks.shift()();
  assert.equal(h.total(), 2);
  for (const fn of h.get("search").listeners.focus) fn();
  assert.equal(h.get("panel").classList.contains("expanded"), true);
  assert.equal(h.get("sheet-toggle").attributes["aria-expanded"], "true");
  h.get("search").focused = true;
  h.get("search").listeners.keydown[0]({ key: "Enter" });
  assert.equal(h.get("search").focused, false);
  h.window.listeners.error[0]({ error: new Error("Test runtime failure") });
  assert.equal(h.get("stats").hidden, true, "hide stale counts after a runtime failure");
  assert.equal(h.get("search").disabled, true);
  h.window.innerWidth = 320;
  h.get("startup-show-details").click();
  const runtimeReport = JSON.parse(h.get("diagnostic-output").textContent);
  assert.equal(runtimeReport.viewport.width, 320, "refresh diagnostics when opened");
  assert.equal(runtimeReport.snapshot.records, 200984);
  assert.equal(runtimeReport.failure.message, "Test runtime failure");
  assert.equal(JSON.stringify(runtimeReport).includes("The Esplanade"), false);
  const bad = await harness("toronto-building-permits-map", true, {
    payload: "{ broken JSON", console: { error() {} },
  });
  assert.equal(bad.get("search").disabled, true);
  assert.equal(bad.get("startup-status").hidden, false);
  assert.match(bad.get("startup-status").textContent, /could not be loaded/);
  assert.equal(bad.get("startup-retry").hidden, false);
  bad.get("startup-show-details").click();
  assert.equal(bad.get("sources-panel").hidden, false);
  const diagnostics = JSON.parse(bad.get("diagnostic-output").textContent);
  assert.equal(diagnostics.phase, "Reading permit data");
  assert.equal(diagnostics.failure.name, "SyntaxError");
  assert.equal(diagnostics.build, "test-build");
  assert.equal(diagnostics.viewport.width, 390);
  assert.equal("query" in diagnostics, false);
  let retried = false;
  bad.window.location.reload = () => { retried = true; };
  bad.get("startup-retry").click();
  assert.equal(retried, true);
  const dinesafe = await harness("toronto-dinesafe-map");
  dinesafe.search("8 The Esplanade");
  assert.equal(dinesafe.total(), 0, "no establishments at 8 in this snapshot");
  console.log("PASS address boundaries, whitespace, units/ranges, mobile search, queued markers and startup diagnostics");
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
