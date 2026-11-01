"""Capture review images explicitly; ordinary builds and tests remain offline.

Copied project-local intentionally: projects share no Python runtime helpers.
Playwright's browser download is a separate, explicit Make target.
"""
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = ROOT / "tests" / "snapshots"
VIEWS = {"desktop": (1440, 900), "mobile": (390, 844)}

# Native charts render from embedded data. Require every plot, completed readout,
# loaded fonts and stable geometry/paths: a successful navigation alone can leave
# a blank or partially rendered page. Recheck after responsive resize callbacks.
EXPECTED_PLOTS = 1
READY = """() => {
  const chart = document.getElementById('chart');
  const readout = document.getElementById('readout');
  const period = document.getElementById('inspect-period');
  const plots = chart ? [...chart.querySelectorAll('svg')].filter(
    svg => svg.querySelector('path.series-line')) : [];
  const ready = document.readyState === 'complete' &&
    document.fonts.status === 'loaded' && plots.length === __EXPECTED_PLOTS__ &&
    readout?.querySelector('strong') && period?.textContent.trim() &&
    plots.every(svg => {
      const box = svg.getBoundingClientRect();
      return box.width > 0 && box.height > 0 &&
        [...svg.querySelectorAll('path.series-line')].every(path =>
          path.getAttribute('d') && !/NaN|Infinity/.test(path.getAttribute('d')) &&
          path.getTotalLength() > 0);
    });
  const signature = JSON.stringify([
    innerWidth, innerHeight, document.documentElement.scrollHeight,
    readout?.textContent, period?.textContent,
    plots.map(svg => {
      const box = svg.getBoundingClientRect();
      return [box.x, box.y, box.width, box.height, svg.getAttribute('viewBox'),
        [...svg.querySelectorAll('path.series-line')].map(path => path.getAttribute('d'))];
    }),
  ]);
  const previous = window.__snapshotReady;
  if (!ready || !previous || previous.signature !== signature) {
    window.__snapshotReady = {signature, since: performance.now()};
    return false;
  }
  return performance.now() - previous.since >= 500;
}""".replace('__EXPECTED_PLOTS__', str(EXPECTED_PLOTS))


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


@contextmanager
def serve():
    """Bind only loopback, choose a free port, and always stop the server."""
    handler = partial(QuietHandler, directory=str(ROOT))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join()


def capture(browser, url, name, size):
    """Use a fresh context for each view: default series, no storage or location state."""
    width, height = size
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        color_scheme="light",
        reduced_motion="reduce",
        locale="en-CA",
        timezone_id="America/Toronto",
        is_mobile=name == "mobile",
        has_touch=name == "mobile",
    )
    try:
        page = context.new_page()
        errors = []
        # These chart pages are self-contained. Fail rather than silently fetching
        # a future CDN/font dependency during an otherwise offline capture.
        blocked = []
        origin = urlsplit(url).netloc

        def route_request(route):
            address = urlsplit(route.request.url)
            if address.scheme in ('http', 'https') and address.netloc != origin:
                blocked.append(route.request.url)
                route.abort()
            else:
                route.continue_()

        page.route('**/*', route_request)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_function(READY, timeout=60_000)
        if blocked:
            raise RuntimeError('External requests in self-contained chart: ' + '; '.join(blocked))
        if errors:
            raise RuntimeError("Page errors: " + "; ".join(errors))
        if page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"):
            raise RuntimeError(f"{name} page overflows its viewport")
        return page.screenshot(type="jpeg", quality=90, full_page=False, animations="disabled")
    finally:
        context.close()


def publish(captures, destination=SNAPSHOTS):
    """Stage both completed captures before replacing any committed image."""
    destination.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".snapshot-", dir=destination) as directory:
        staged = []
        for name, content in captures.items():
            target = destination / f"{name}.jpg"
            if target.exists() and target.read_bytes() == content:
                continue
            path = Path(directory) / target.name
            path.write_bytes(content)
            staged.append((path, target))
        for path, target in staged:
            path.replace(target)


def generate(browser, url, destination=SNAPSHOTS):
    captures = {name: capture(browser, url, name, size) for name, size in VIEWS.items()}
    publish(captures, destination)


def main():
    # Import lazily so offline unit tests do not need to launch a browser.
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError as error:
        raise SystemExit("Environment incomplete: run make clean-deps then make deps.") from error

    artifact = ROOT / "output" / f"{ROOT.name}.html"
    if not artifact.is_file():
        raise SystemExit("Missing built HTML; run make first.")
    try:
        with serve() as base, sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                generate(browser, f"{base}/output/{artifact.name}")
            finally:
                browser.close()
    except (Error, RuntimeError, OSError) as error:
        raise SystemExit(
            f"Snapshot capture failed: {error}\n"
            "Check chart rendering and page errors. For a missing browser, "
            "run make snapshot-browser explicitly."
        ) from error
    print(f"Wrote desktop and mobile review snapshots to {SNAPSHOTS}")


if __name__ == "__main__":
    main()
