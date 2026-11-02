"""Explicit offline browser checks; not collected by ordinary `make test`.

After `make snapshot-browser`, run:
    make browser-test (from a project), or .venv/bin/python -m pytest -q tests/browser_snapshots.py
Fixtures use a loopback server and never fetch data or external assets.
"""
from contextlib import contextmanager

import pytest
from playwright.sync_api import TimeoutError, sync_playwright

from staticsites.snapshots import Snapshotter


@pytest.fixture(params=[1, 3])
def snapshot_site(tmp_path, request):
    return Snapshotter(tmp_path, kind="chart", expected_plots=request.param)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            yield browser
        finally:
            browser.close()


def markup(snapshot_site, *, count=None, readout=True, path="M0,0 L100,100", extra=""):
    if count is None:
        count = snapshot_site.EXPECTED_PLOTS
    plots = ''.join(f'<svg viewBox="0 0 200 150"><path class="series-line" d="{path}" /></svg>'
                    for _ in range(count))
    return ('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<div id="chart">' + plots + '</div><div id="readout">' +
            ('<strong>100</strong>' if readout else '') + '</div>'
            '<p id="inspect-period">Inspecting 2026-06-30</p>' + extra)


@contextmanager
def fixture_site(snapshot_site, tmp_path, monkeypatch, html):
    (tmp_path / 'fixture.html').write_text(html)
    monkeypatch.setattr(snapshot_site, 'ROOT', tmp_path)
    with snapshot_site.serve() as base:
        yield base + '/fixture.html'


@pytest.mark.parametrize('broken', ['missing_plot', 'missing_readout', 'invalid_path'])
def test_readiness_rejects_partial_charts(snapshot_site, browser, broken):
    options = {
        'missing_plot': {'count': snapshot_site.EXPECTED_PLOTS - 1},
        'missing_readout': {'readout': False},
        'invalid_path': {'path': 'M0,0 LNaN,100'},
    }[broken]
    page = browser.new_page()
    try:
        page.set_content(markup(snapshot_site, **options))
        with pytest.raises(TimeoutError):
            page.wait_for_function(snapshot_site.READY, timeout=800)
    finally:
        page.close()


def test_readiness_waits_for_moving_paths(snapshot_site, browser):
    page = browser.new_page()
    try:
        page.set_content(markup(snapshot_site, extra='''<script>
          let tick = 0;
          const timer = setInterval(() => {
            document.querySelector('path').setAttribute('d',`M0,0 L${100+tick},100`);
            if (++tick === 6) { clearInterval(timer); window.finishedAt = performance.now(); }
          }, 100);
        </script>'''))
        page.wait_for_function(snapshot_site.READY, timeout=3000)
        assert page.evaluate('window.__snapshotReady.since >= window.finishedAt')
    finally:
        page.close()


@pytest.mark.parametrize('failure,extra', [
    ('overflows', '<div style="width:2000px">overflow</div>'),
    ('Page errors', '<script>throw new Error("fixture render failed")</script>'),
    ('External requests', '<script src="https://example.invalid/blocked.js"></script>'),
])
def test_capture_rejects_bad_pages(snapshot_site, browser, tmp_path, monkeypatch, failure, extra):
    with fixture_site(snapshot_site, tmp_path, monkeypatch, markup(snapshot_site, extra=extra)) as url:
        with pytest.raises(RuntimeError, match=failure):
            snapshot_site.capture(browser, url, 'mobile', snapshot_site.VIEWS['mobile'])


def test_capture_produces_both_review_images(snapshot_site, browser, tmp_path, monkeypatch):
    with fixture_site(snapshot_site, tmp_path, monkeypatch, markup(snapshot_site)) as url:
        destination = tmp_path / 'review'
        snapshot_site.generate(browser, url, destination)
    assert sorted(path.name for path in destination.iterdir()) == ['desktop.jpg', 'mobile.jpg']
    assert all(path.read_bytes().startswith(b'\xff\xd8') for path in destination.iterdir())

@pytest.mark.parametrize('broken', ['missing_map','disabled_search','fading_tiles','failed_tiles','moving_map'])
def test_map_readiness_rejects_incomplete_maps(browser, tmp_path, broken):
    from staticsites.snapshots import Snapshotter
    snapshot = Snapshotter(tmp_path, kind='map')
    tile = ('data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" '
            'width="256" height="256"%3E%3C/svg%3E')
    if broken == 'failed_tiles':
        tile = 'data:image/png;base64,bm90IGFuIGltYWdl'
    map_id = 'wrong' if broken == 'missing_map' else 'map'
    disabled = 'disabled' if broken == 'disabled_search' else ''
    opacity = '.5' if broken == 'fading_tiles' else '1'
    animation = 'leaflet-zoom-anim' if broken == 'moving_map' else ''
    page = browser.new_page()
    try:
        page.set_content(f'''<div id="{map_id}" class="leaflet-container {animation}" style="width:256px;height:256px">
          <img class="leaflet-tile" style="opacity:{opacity}" src='{tile}'></div>
          <input id="search" {disabled}><div id="stats"><strong>1</strong></div>''')
        with pytest.raises(TimeoutError):
            page.wait_for_function(snapshot.READY, timeout=800)
    finally:
        page.close()


def test_map_readiness_accepts_complete_tiles(browser, tmp_path):
    from staticsites.snapshots import Snapshotter
    snapshot = Snapshotter(tmp_path, kind='map')
    page = browser.new_page()
    try:
        page.set_content('''<div id="map" class="leaflet-container" style="width:256px;height:256px">
          <img class="leaflet-tile" style="opacity:1" src='data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="256" height="256"%3E%3C/svg%3E'></div>
          <input id="search"><div id="stats"><strong>1</strong></div>''')
        page.wait_for_function(snapshot.READY, timeout=2500)
    finally:
        page.close()
