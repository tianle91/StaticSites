"""Routing preparation is testable without Java, osmium, or live downloads."""
import datetime
import io
import json
import pathlib
import subprocess
import urllib.error
import zipfile

import pytest

import fetch_data as refresh

DATE = datetime.date(2026, 10, 14)


def feed(path, active=True, exceptions=None):
    tables = {
        "agency.txt": "agency_name,agency_url,agency_timezone\nTest,https://example.com,America/Toronto\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\ns,Union,43.65,-79.38\n",
        "routes.txt": "route_id,route_type\nr,2\n",
        "trips.txt": "route_id,service_id,trip_id\nr,weekday,t\n",
        "stop_times.txt": "trip_id,stop_id,stop_sequence,arrival_time,departure_time\nt,s,1,09:00:00,09:00:00\n",
        "calendar.txt": "service_id,start_date,end_date,wednesday\nweekday,20261001,20261031," + str(int(active)) + "\n",
    }
    if exceptions:
        tables["calendar_dates.txt"] = "service_id,date,exception_type\nweekday,20261014," + exceptions + "\n"
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in tables.items():
            archive.writestr(name, text)


@pytest.fixture
def local(tmp_path, monkeypatch):
    data = tmp_path / "data"
    src = tmp_path / "src"
    data.mkdir()
    src.mkdir()
    monkeypatch.setattr(refresh, "ROOT", tmp_path)
    monkeypatch.setattr(refresh, "DATA_DIR", data)
    monkeypatch.setattr(refresh, "STATE_PATH", data / "refresh_cache.json")
    for name in ("OSM_PBF", "GTFS_DIR"):
        monkeypatch.delenv(name, raising=False)
    (data / "transit_model.json").write_text("{}")
    (src / "fetch_isochrones.py").write_text("# routing")
    (tmp_path / "uv.lock").write_text("lock")
    return data


def test_service_calendar_exceptions_and_corruption(tmp_path):
    path = tmp_path / "feed.zip"
    feed(path)
    refresh.validate_gtfs(path, DATE)
    feed(path, exceptions="2")
    with pytest.raises(ValueError, match="no active trips"):
        refresh.validate_gtfs(path, DATE)
    feed(path, active=False, exceptions="1")
    refresh.validate_gtfs(path, DATE)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("agency.txt", "html error page")
    with pytest.raises(ValueError):
        refresh.validate_gtfs(path, DATE)
    path.write_bytes(b"not a zip")
    with pytest.raises(zipfile.BadZipFile):
        refresh.validate_gtfs(path, DATE)


def test_download_unchanged_conditional_and_invalid_preserves_previous(local, monkeypatch):
    destination = local / "ttc.zip"
    source = local / "source.zip"
    feed(source)
    content = source.read_bytes()
    state = {}
    requests = []

    def response(request, timeout):
        requests.append(request)
        result = io.BytesIO(content)
        result.headers = {"ETag": '"v1"', "Content-Length": str(len(content))}
        return result

    monkeypatch.setattr(refresh.urllib.request, "urlopen", response)
    validate = lambda path: refresh.validate_gtfs(path, DATE)
    refresh.download("https://example.com/feed", destination, validate, state)
    before = destination.stat().st_mtime_ns
    refresh.download("https://example.com/feed", destination, validate, state)
    assert destination.stat().st_mtime_ns == before
    assert requests[-1].get_header("If-none-match") == '"v1"'

    def not_modified(*args, **kwargs):
        raise urllib.error.HTTPError("url", 304, "unchanged", {}, None)

    monkeypatch.setattr(refresh.urllib.request, "urlopen", not_modified)
    refresh.download("https://example.com/feed", destination, validate, state)
    assert destination.stat().st_mtime_ns == before
    content = b"invalid"
    monkeypatch.setattr(refresh.urllib.request, "urlopen", response)
    with pytest.raises(zipfile.BadZipFile):
        refresh.download("https://example.com/feed", destination, validate, state)
    assert destination.stat().st_mtime_ns == before
    assert not list(local.glob("tmp*"))


def test_interrupted_download_preserves_previous(local, monkeypatch):
    destination = local / "file"
    destination.write_bytes(b"previous")

    class Interrupted(io.BytesIO):
        headers = {}

        def read(self, size=-1):
            raise OSError("connection interrupted")

    monkeypatch.setattr(refresh.urllib.request, "urlopen", lambda *a, **kw: Interrupted())
    with pytest.raises(OSError):
        refresh.download("https://example.com/file", destination, lambda p: None, {})
    assert destination.read_bytes() == b"previous"
    assert not list(local.glob("tmp*"))


def test_preflight_before_download(local, monkeypatch):
    monkeypatch.setattr(refresh.shutil, "which", lambda name: None)
    monkeypatch.setattr(refresh, "download", lambda *a: pytest.fail("download before preflight"))
    with pytest.raises(RuntimeError, match="Missing java"):
        refresh.main()


def test_default_preparation_clipping_cache_and_overrides(local, monkeypatch):
    calls = []

    def download(url, path, validate, state):
        calls.append(path.name)
        if path.suffix == ".zip":
            feed(path)
        elif not path.exists():
            path.write_bytes(b"osm")

    clips = []

    def run(command, **kwargs):
        clips.append(command)
        pathlib.Path(command[command.index("-o") + 1]).write_bytes(b"clipped")

    monkeypatch.setattr(refresh, "download", download)
    monkeypatch.setattr(refresh, "validate_osm", lambda path: None)
    monkeypatch.setattr(refresh.subprocess, "run", run)
    state = {}
    osm, feeds = refresh.prepare_inputs(state, DATE, "osmium version")
    assert calls == ["ttc.zip", "go.zip", "up.zip", "gtha.osm.pbf"]
    assert len(feeds) == 3
    before = osm.stat().st_mtime_ns
    refresh.prepare_inputs(state, DATE, "osmium version")
    assert len(clips) == 1 and osm.stat().st_mtime_ns == before
    monkeypatch.setattr(refresh.routing, "BBOX", (43, 44, -81, -78))
    refresh.prepare_inputs(state, DATE, "osmium version")
    assert len(clips) == 2
    feed(local / "optional.zip")
    monkeypatch.setenv("OSM_PBF", str(osm))
    monkeypatch.setenv("GTFS_DIR", str(local))
    calls.clear()
    _, feeds = refresh.prepare_inputs(state, DATE, "osmium version")
    assert calls == [] and len(feeds) == 4


def test_routing_cache_invalidation_and_failure_preserves_previous(local, monkeypatch):
    osm = local / "osm.pbf"
    osm.write_bytes(b"osm")
    gtfs = local / "ttc.zip"
    feed(gtfs)
    runs = []

    def route(command, env, check):
        runs.append(env)
        pathlib.Path(env["REACHABILITY_OUT"]).write_text(json.dumps({
            "points": [[43.65, -79.38, 20]], "stations": [], "grid_spacing_m": 1000,
            "arrival": env["SERVICE_DATE"] + "T09:00:00",
        }))

    monkeypatch.setattr(refresh.subprocess, "run", route)
    state = {}
    refresh.refresh_routing(state, osm, [gtfs], DATE)
    destination = local / "reachability.json"
    before = destination.stat().st_mtime_ns
    refresh.refresh_routing(state, osm, [gtfs], DATE)
    assert len(runs) == 1
    assert destination.stat().st_mtime_ns == before
    monkeypatch.setattr(refresh.routing, "PERCENTILE", 50)
    refresh.refresh_routing(state, osm, [gtfs], DATE)
    assert len(runs) == 2
    assert destination.stat().st_mtime_ns == before  # same substantive result
    for path in (osm, refresh.ROOT / "uv.lock", refresh.ROOT / "src/fetch_isochrones.py"):
        path.write_text("changed")
        refresh.refresh_routing(state, osm, [gtfs], DATE)
    assert len(runs) == 5
    refresh.refresh_routing(state, osm, [gtfs], DATE + datetime.timedelta(days=7))
    assert len(runs) == 6
    destination.unlink()
    refresh.refresh_routing(state, osm, [gtfs], DATE + datetime.timedelta(days=7))
    assert len(runs) == 7
    destination.write_text("invalid")
    refresh.refresh_routing(state, osm, [gtfs], DATE + datetime.timedelta(days=7))
    assert len(runs) == 8
    previous = destination.read_bytes()
    monkeypatch.setattr(refresh.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(
        subprocess.CalledProcessError(1, "routing")))
    osm.write_bytes(b"new")
    with pytest.raises(subprocess.CalledProcessError):
        refresh.refresh_routing(state, osm, [gtfs], DATE)
    assert destination.read_bytes() == previous


def test_corrupt_cache_and_empty_results(local):
    refresh.STATE_PATH.write_text('{"routing": [], "downloads": {"bad": []}}')
    assert refresh.read_state() == {"downloads": {}}
    result = local / "reachability.json"
    result.write_text('{"points": [], "stations": [], "grid_spacing_m": 1000}')
    with pytest.raises(ValueError):
        refresh.validate_reachability(result)


@pytest.mark.parametrize("version,code", [("openjdk version \"17.0.1\"", 0), ("No Java Runtime", 1)])
def test_wrong_or_missing_java_runtime(monkeypatch, version, code):
    monkeypatch.setattr(refresh.shutil, "which", lambda name: "/tools/" + name)
    monkeypatch.setattr(refresh.subprocess, "run", lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], code, stdout="", stderr=version))
    with pytest.raises(RuntimeError, match="Java 21"):
        refresh.preflight()
