/* Installed before external scripts and the large payload: even an early load
 * failure must leave a useful screen on a phone without a developer console. */
const PermitStartup = (() => {
  let phase = "Loading page",
    failure = null,
    ready = false,
    snapshot = null;
  const history = [];
  const scriptLoadErrors = [];
  // Keep useful source locations without URL queries/fragments, which may carry
  // private values in scripts added by a browser or hosting page.
  function sourceLocation(value) {
    if (!value) return null;
    try {
      const url = new URL(value, window.location.href);
      return /^https?:$/.test(url.protocol) ? url.origin + url.pathname : url.protocol;
    } catch {
      return null;
    }
  }
  function diagnostics() {
    const viewport = window.visualViewport;
    return JSON.stringify({
      build: document.querySelector('meta[name="permits-build"]').content,
      phase,
      ready,
      snapshot,
      browser: navigator.userAgent,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
        visibleHeight: viewport?.height ?? null,
      },
      failure,
      scriptLoadErrors,
      history,
    }, null, 2);
  }
  function render() {
    const status = document.getElementById("startup-status");
    if (!status) return;
    status.hidden = ready;
    status.textContent = failure
      ? "Permits could not be loaded or updated. Retry, or share the diagnostic details below."
      : phase + "…";
    document.getElementById("startup-retry").hidden = !failure;
    document.getElementById("startup-show-details").hidden = !failure;
    document.getElementById("search").disabled = !ready || !!failure;
    document.getElementById("diagnostic-output").textContent = diagnostics();
    document.getElementById("stats").hidden = !!failure;
  }
  function stage(value) {
    phase = value;
    history.push(value);
    if (history.length > 8) history.shift();
    render();
  }
  function fail(error, location = {}) {
    if (failure) return;
    failure = {
      phase,
      name: error?.name || "Error",
      message: String(error?.message || error).slice(0, 300),
      ...location,
    };
    ready = false;
    console.error("Permit map failed at " + phase, error);
    render();
  }
  window.addEventListener("error", (event) => {
    // ErrorEvent.error can be null (including restricted cross-origin errors).
    // Preserve its message instead of silently ignoring a runtime failure.
    if (event.error || event.message) {
      fail(event.error || new Error(event.message), {
        kind: "runtime",
        source: sourceLocation(event.filename),
        line: event.lineno || null,
        column: event.colno || null,
      });
    } else if (event.target?.tagName === "SCRIPT") {
      const script = event.target;
      const required = script.dataset?.permitRequired || null;
      const detail = { kind: "script-load", required, source: sourceLocation(script.src) };
      scriptLoadErrors.push(detail);
      if (scriptLoadErrors.length > 4) scriptLoadErrors.shift();
      // A browser/host may insert unrelated scripts. Their resource failures
      // must not disable a map whose own initialization is still succeeding.
      if (required) fail(new Error(required + " could not load."), detail);
      else render();
    }
  }, true);
  window.addEventListener("unhandledrejection", (event) => fail(event.reason));
  window.visualViewport?.addEventListener("resize", render);
  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("startup-show-details").onclick = () => {
      document.querySelectorAll(".explorer-tabs [role=tab]").forEach((button) => {
        button.setAttribute("aria-selected", String(button.dataset.tab === "sources"));
        button.tabIndex = button.dataset.tab === "sources" ? 0 : -1;
      });
      document.querySelectorAll(".explorer-panel").forEach((panel) => {
        panel.hidden = panel.id !== "sources-panel";
      });
      document.getElementById("startup-diagnostics").open = true;
      document.getElementById("panel").classList.add("expanded");
      document.getElementById("sheet-toggle").setAttribute("aria-expanded", "true");
      document.getElementById("sheet-toggle").setAttribute("aria-label", "Collapse map controls");
      render();
    };
    document.getElementById("startup-retry").onclick = () => window.location.reload();
    document.getElementById("startup-diagnostics").addEventListener("toggle", render);
    render();
  });
  return {
    stage,
    fail,
    async run(start) {
      if (failure) {
        render();
        return;
      }
      try {
        await start();
      } catch (error) {
        fail(error);
      }
    },
    dataLoaded(data) {
      snapshot = { retrievedAt: data.retrieved_at, records: data.permits.length };
    },
    ready() {
      if (failure) return;
      ready = true;
      stage("Ready");
    },
  };
})();
