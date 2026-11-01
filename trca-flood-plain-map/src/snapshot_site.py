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

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = ROOT / "tests" / "snapshots"
VIEWS = {"desktop": (1440, 900), "mobile": (390, 844)}

# Network-idle is unsuitable: the service map has an optional live API panel.
# A fixed delay can catch Leaflet mid-zoom or before chunked markers finish.
# Require completed initialization, fonts, loaded/faded-in tiles, no zoom/pan
# animation, and unchanged map geometry for half a second instead.
READY = """() => {
  const map = document.getElementById('map');
  const search = document.getElementById('search');
  const stats = document.getElementById('stats');
  const tiles = map ? [...map.querySelectorAll('img.leaflet-tile')] : [];
  const rect = map?.getBoundingClientRect();
  const intersects = image => {
    const box = image.getBoundingClientRect();
    return box.right > rect.left && box.left < rect.right &&
      box.bottom > rect.top && box.top < rect.bottom;
  };
  const visible = tiles.filter(intersects);
  const ready = document.readyState === 'complete' &&
    document.fonts.status === 'loaded' &&
    (!map || (map.classList.contains('leaflet-container') &&
      stats?.querySelector('strong') && search && !search.disabled &&
      !map.classList.contains('leaflet-zoom-anim') &&
      !map.classList.contains('leaflet-pan-anim') && visible.length > 0 &&
      visible.every(image => image.complete && image.naturalWidth > 0 &&
        Number(getComputedStyle(image).opacity) === 1)));
  const signature = JSON.stringify([
    innerWidth, innerHeight, stats?.textContent,
    tiles.map(image => {
      const box = image.getBoundingClientRect();
      return [image.src, box.x, box.y, box.width, box.height,
        getComputedStyle(image).opacity];
    }),
    [...document.querySelectorAll('.leaflet-zoom-animated')].map(
      element => element.getAttribute('style')),
  ]);
  const previous = window.__snapshotReady;
  if (!ready || !previous || previous.signature !== signature) {
    window.__snapshotReady = {signature, since: performance.now()};
    return false;
  }
  return performance.now() - previous.since >= 500;
}"""


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
    """Use a fresh context for each view: no search, storage or location state."""
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
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_function(READY, timeout=60_000)
        if errors:
            raise RuntimeError("Page errors: " + "; ".join(errors))
        if page.evaluate("document.documentElement.scrollWidth > innerWidth"):
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
            "Check network access to map scripts/tiles. For a missing browser, "
            "run make snapshot-browser explicitly."
        ) from error
    print(f"Wrote desktop and mobile review snapshots to {SNAPSHOTS}")


if __name__ == "__main__":
    main()
