"""Explicit offline browser checks; not collected by ordinary `make test`.

After `make snapshot-browser`, run:
    .venv/bin/python -m pytest -q tests/browser_snapshots.py
Fixtures use a loopback server and never fetch data or external assets.
"""
from contextlib import contextmanager

import pytest
from playwright.sync_api import TimeoutError, sync_playwright

import snapshot_site


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            yield browser
        finally:
            browser.close()


def markup(*, count=None, readout=True, path="M0,0 L100,100", extra=""):
    if count is None:
        count = snapshot_site.EXPECTED_PLOTS
    plots = ''.join(f'<svg viewBox="0 0 200 150"><path class="series-line" d="{path}" /></svg>'
                    for _ in range(count))
    return ('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<div id="chart">' + plots + '</div><div id="readout">' +
            ('<strong>100</strong>' if readout else '') + '</div>'
            '<p id="inspect-period">Inspecting 2026-06-30</p>' + extra)


@contextmanager
def fixture_site(tmp_path, monkeypatch, html):
    (tmp_path / 'fixture.html').write_text(html)
    monkeypatch.setattr(snapshot_site, 'ROOT', tmp_path)
    with snapshot_site.serve() as base:
        yield base + '/fixture.html'


@pytest.mark.parametrize('broken', ['missing_plot', 'missing_readout', 'invalid_path'])
def test_readiness_rejects_partial_charts(browser, broken):
    options = {
        'missing_plot': {'count': snapshot_site.EXPECTED_PLOTS - 1},
        'missing_readout': {'readout': False},
        'invalid_path': {'path': 'M0,0 LNaN,100'},
    }[broken]
    page = browser.new_page()
    try:
        page.set_content(markup(**options))
        with pytest.raises(TimeoutError):
            page.wait_for_function(snapshot_site.READY, timeout=800)
    finally:
        page.close()


def test_readiness_waits_for_moving_paths(browser):
    page = browser.new_page()
    try:
        page.set_content(markup(extra='''<script>
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
def test_capture_rejects_bad_pages(browser, tmp_path, monkeypatch, failure, extra):
    with fixture_site(tmp_path, monkeypatch, markup(extra=extra)) as url:
        with pytest.raises(RuntimeError, match=failure):
            snapshot_site.capture(browser, url, 'mobile', snapshot_site.VIEWS['mobile'])


def test_capture_produces_both_review_images(browser, tmp_path, monkeypatch):
    with fixture_site(tmp_path, monkeypatch, markup()) as url:
        destination = tmp_path / 'review'
        snapshot_site.generate(browser, url, destination)
    assert sorted(path.name for path in destination.iterdir()) == ['desktop.jpg', 'mobile.jpg']
    assert all(path.read_bytes().startswith(b'\xff\xd8') for path in destination.iterdir())
