#!/usr/bin/env python3
"""Prepare all routing inputs and reuse unchanged expensive results.

Large files and cache metadata stay local and ignored. Caller-supplied OSM_PBF
and GTFS_DIR paths are read-only inputs; the defaults are managed downloads.
"""
import csv
import datetime
import hashlib
import io
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

import fetch_isochrones as routing

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "refresh_cache.json"
OSM_URL = "https://download.geofabrik.de/north-america/canada/ontario-latest.osm.pbf"
FEEDS = {
    "ttc.zip": "https://opendata.toronto.ca/toronto.transit.commission/ttc-routes-and-schedules/OpenData_TTC_Schedules.zip",
    "go.zip": "https://assets.metrolinx.com/raw/upload/Documents/Metrolinx/Open%20Data/GO-GTFS.zip",
    "up.zip": "https://assets.metrolinx.com/raw/upload/Documents/Metrolinx/Open%20Data/UP-GTFS.zip",
}
USER_AGENT = "union-station-transit-isochrone/1.0 (+https://github.com/tianle91/StaticSites)"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_state():
    try:
        value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return {}
        for key in ("downloads", "clip", "routing"):
            if not isinstance(value.get(key, {}), dict):
                value.pop(key, None)
        if "downloads" in value:
            value["downloads"] = {key: record for key, record in value["downloads"].items()
                                  if isinstance(record, dict)}
        return value
    except (OSError, ValueError):
        return {}


def temporary_path(directory, suffix=""):
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=directory, suffix=suffix)
    os.close(descriptor)
    return pathlib.Path(name)


def publish(temporary, destination):
    """Only replace complete, validated files, preserving unchanged mtimes."""
    if destination.exists() and digest(temporary) == digest(destination):
        temporary.unlink()
    else:
        temporary.replace(destination)


def save_state(state):
    temporary = temporary_path(DATA_DIR)
    try:
        temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        publish(temporary, STATE_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def preflight():
    for tool in ("java", "osmium"):
        if not shutil.which(tool):
            raise RuntimeError(f"Missing {tool}; install Java 21 and osmium-tool (see README.md).")
    result = subprocess.run(["java", "-version"], capture_output=True, text=True,
                            check=False, timeout=30)
    if result.returncode:
        raise RuntimeError("Java 21 is unavailable; install a JDK and configure JAVA_HOME/PATH (see README.md).")
    version = re.search(r'version "(\d+)', result.stderr + result.stdout)
    if not version or int(version[1]) != 21:
        raise RuntimeError("A Java 21 JDK is required; configure JAVA_HOME/PATH (see README.md).")
    return subprocess.run(["osmium", "--version"], capture_output=True, text=True,
                          check=True, timeout=30).stdout


def validate_osm(path):
    subprocess.run(["osmium", "fileinfo", str(path)], check=True,
                   stdout=subprocess.DEVNULL, timeout=120)


def validate_gtfs(path, date):
    """Require structurally usable tables and a trip operating on the route date.

    calendar_dates additions/removals override the weekly calendar. A feed with
    date-only service is valid; calendar.txt itself is optional in GTFS.
    """
    fields = {
        "agency.txt": {"agency_name", "agency_url", "agency_timezone"},
        "stops.txt": {"stop_id", "stop_name", "stop_lat", "stop_lon"},
        "routes.txt": {"route_id", "route_type"},
        "trips.txt": {"route_id", "service_id", "trip_id"},
        "stop_times.txt": {"trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"},
    }
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"{path}: corrupt ZIP member")

        def rows(name, required):
            with archive.open(name) as stream:
                reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig"))
                if not required.issubset(reader.fieldnames or []):
                    raise ValueError(f"{path}: {name} is missing required columns")
                yield from reader

        for name, required in fields.items():
            if not next(rows(name, required), None):
                raise ValueError(f"{path}: empty required table {name}")
        active = set()
        day = date.strftime("%Y%m%d")
        weekday = date.strftime("%A").lower()
        if "calendar.txt" in archive.namelist():
            for row in rows("calendar.txt", {"service_id", "start_date", "end_date", weekday}):
                if row["start_date"] <= day <= row["end_date"] and row[weekday] == "1":
                    active.add(row["service_id"])
        if "calendar_dates.txt" in archive.namelist():
            for row in rows("calendar_dates.txt", {"service_id", "date", "exception_type"}):
                if row["date"] == day:
                    if row["exception_type"] == "1":
                        active.add(row["service_id"])
                    elif row["exception_type"] == "2":
                        active.discard(row["service_id"])
        if not any(row["service_id"] in active for row in rows("trips.txt", fields["trips.txt"])):
            raise ValueError(f"{path}: no active trips on {date}; obtain a current GTFS feed")


def download(url, destination, validate, state):
    """HTTP validators are only trusted with their matching local content."""
    downloads = state.setdefault("downloads", {})
    cached = downloads.get(destination.name, {})
    headers = {"User-Agent": USER_AGENT}
    if (destination.exists() and cached.get("url") == url
            and cached.get("sha256") == digest(destination)):
        for key, header in (("etag", "If-None-Match"), ("last_modified", "If-Modified-Since")):
            if cached.get(key):
                headers[header] = cached[key]
    # An interrupted process must not leave a partial ZIP that the next run
    # mistakes for an optional transit feed. osmium requires the PBF extension.
    suffix = ".part" if destination.suffix == ".zip" else ".osm.pbf"
    temporary = temporary_path(destination.parent, suffix=suffix)
    try:
        try:
            response = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120)
        except urllib.error.HTTPError as exc:
            if exc.code == 304 and destination.exists() and len(headers) > 1:
                validate(destination)
                return
            raise
        with response:
            with temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream, length=1024 * 1024)
            metadata = {"url": url, "etag": response.headers.get("ETag"),
                        "last_modified": response.headers.get("Last-Modified")}
            expected_length = response.headers.get("Content-Length")
            if expected_length and temporary.stat().st_size != int(expected_length):
                raise ValueError(f"{url}: incomplete download")
        validate(temporary)
        metadata["sha256"] = digest(temporary)
        publish(temporary, destination)
        downloads[destination.name] = metadata
        save_state(state)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_inputs(state, date, osmium_version):
    feed_dir = pathlib.Path(os.environ.get("GTFS_DIR", str(DATA_DIR))).resolve()
    if "GTFS_DIR" not in os.environ:
        for name, url in FEEDS.items():
            download(url, feed_dir / name, lambda path: validate_gtfs(path, date), state)
    feeds = sorted(feed_dir.glob("*.zip"))
    if not feeds:
        raise ValueError(f"No GTFS feeds in {feed_dir}")
    for feed in feeds:
        validate_gtfs(feed, date)

    if "OSM_PBF" in os.environ:
        osm = pathlib.Path(os.environ["OSM_PBF"]).resolve()
        validate_osm(osm)
    else:
        raw = DATA_DIR / "gtha.osm.pbf"
        osm = DATA_DIR / "gtha-clipped.osm.pbf"
        download(OSM_URL, raw, validate_osm, state)
        south, north, west, east = routing.BBOX
        clip_key = signature({"raw": digest(raw), "bbox": routing.BBOX, "osmium": osmium_version})
        clip = state.get("clip", {})
        if not (osm.exists() and clip.get("signature") == clip_key
                and clip.get("sha256") == digest(osm)):
            temporary = temporary_path(DATA_DIR, suffix=".osm.pbf")
            try:
                subprocess.run(["osmium", "extract", "-b", f"{west},{south},{east},{north}",
                                str(raw), "-o", str(temporary), "--overwrite"], check=True)
                validate_osm(temporary)
                publish(temporary, osm)
                state["clip"] = {"signature": clip_key, "sha256": digest(osm)}
                save_state(state)
            finally:
                temporary.unlink(missing_ok=True)
    return osm, feeds


def validate_reachability(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or not value.get("points")
            or not isinstance(value.get("stations"), list)
            or not isinstance(value.get("grid_spacing_m"), (int, float))
            or value["grid_spacing_m"] <= 0):
        raise ValueError("Routing produced no usable reachability results")
    datetime.datetime.fromisoformat(value["arrival"])
    for station in value["stations"]:
        if not {"name", "mode", "lat", "lon", "minutes", "legs"}.issubset(station):
            raise ValueError("Invalid reachability station")
    for lat, lon, minutes in value["points"]:
        if not (all(math.isfinite(number) for number in (lat, lon, minutes))
                and -90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= minutes <= routing.MAX_MINUTES):
            raise ValueError("Invalid reachability point")


def refresh_routing(state, osm, feeds, date):
    key = signature({
        "osm": digest(osm), "feeds": [(str(path), digest(path)) for path in feeds],
        "date": date.isoformat(), "bbox": routing.BBOX,
        "arrival": routing.ARRIVE_HHMM, "percentile": routing.PERCENTILE,
        "grid": routing.GRID_SPACING_M, "minutes": routing.MAX_MINUTES,
        "model": digest(DATA_DIR / "transit_model.json"),
        "code": digest(ROOT / "src" / "fetch_isochrones.py"),
        "preparation": digest(pathlib.Path(__file__)), "lock": digest(ROOT / "uv.lock"),
    })
    previous = state.get("routing", {})
    destination = DATA_DIR / "reachability.json"
    if (destination.exists() and previous.get("signature") == key
            and previous.get("sha256") == digest(destination)):
        try:
            validate_reachability(destination)
            print("Routing inputs unchanged; reusing reachability.json.")
            return
        except (ValueError, KeyError, TypeError):
            pass
    temporary = temporary_path(DATA_DIR, suffix=".json")
    try:
        environment = dict(os.environ, OSM_PBF=str(osm), GTFS_DIR=str(feeds[0].parent),
                           REACHABILITY_OUT=str(temporary), SERVICE_DATE=date.isoformat())
        subprocess.run([sys.executable, str(ROOT / "src" / "fetch_isochrones.py")],
                       env=environment, check=True)
        validate_reachability(temporary)
        value = json.loads(temporary.read_text(encoding="utf-8"))
        existing = {}
        if destination.exists():
            try:
                existing = json.loads(destination.read_text(encoding="utf-8"))
            except ValueError:
                pass
        stamp = existing.pop("generated_at", None)
        value["generated_at"] = stamp if existing == value and stamp else datetime.date.today().isoformat()
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        publish(temporary, destination)
        state["routing"] = {"signature": key, "sha256": digest(destination)}
        save_state(state)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    osmium_version = preflight()
    state = read_state()
    date = routing.next_weekday()
    osm, feeds = prepare_inputs(state, date, osmium_version)
    refresh_routing(state, osm, feeds, date)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(f"Data refresh failed: {exc}", file=sys.stderr)
        sys.exit(1)
