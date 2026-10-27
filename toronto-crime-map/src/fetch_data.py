#!/usr/bin/env python3
"""Explicit network refresh; validate every required source before publication.

ArcGIS limits responses. Fetch a fixed object-ID set in batches rather than
trusting offset pagination, and reject a changing source instead of committing a
partial snapshot. No geocoding: the published points are intentionally displaced.
"""
import argparse
import datetime as dt
import json
import math
import pathlib
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
BASE = "https://services.arcgis.com/S9th0jAJ7bqgIRjw/arcgis/rest/services/"
SOURCES = {
    "main": ("Major_Crime_Indicators_Open_Data", "REPORT_YEAR"),
    "homicide": ("Homicides_Open_Data_ASR_RC_TBL_002", "OCC_YEAR"),
    "shooting": ("Shooting_and_Firearm_Discharges_Open_Data", "OCC_YEAR"),
}
# These browser dependencies are committed and embedded by the offline builder.
# Keep the upstream licence notices in the downloaded files.
ASSETS = {
    "leaflet.js": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "leaflet.css": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    "markercluster.js": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js",
    "markercluster.css": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css",
    "markercluster-default.css": "https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css",
    "leaflet-LICENSE.txt": "https://unpkg.com/leaflet@1.9.4/LICENSE",
    "markercluster-LICENSE.txt": "https://unpkg.com/leaflet.markercluster@1.5.3/MIT-LICENCE.txt",
}
COLUMNS = ["source", "row_id", "event_id", "category", "offence", "reported",
           "occurred", "neighbourhood", "division", "premises", "lat", "lon",
           "deaths", "injuries"]
CATEGORIES = {"Assault", "Break and Enter", "Auto Theft", "Robbery", "Theft Over"}
COMMON = ["OBJECTID", "EVENT_UNIQUE_ID", "OCC_DATE", "NEIGHBOURHOOD_158",
          "DIVISION", "LAT_WGS84", "LONG_WGS84"]
EXTRA = {"main": ["REPORT_DATE", "CSI_CATEGORY", "OFFENCE", "PREMISES_TYPE"],
         "homicide": ["HOMICIDE_TYPE"], "shooting": ["EVENT_TYPE", "DEATH", "INJURIES"]}


def download(url, body=None):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, data=body, headers={"User-Agent": "StaticSites-TorontoCrimeMap/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read().decode("utf-8")
        except (OSError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def request_json(url, **params):
    encoded = urllib.parse.urlencode({"f": "json", **params})
    # Object-ID lists exceed ArcGIS's GET URL limit; POST avoids silent truncation
    # and 404 responses while retaining exact batch membership validation.
    payload = json.loads(download(url, encoded.encode()) if "objectIds" in params
                         else download(url + "?" + encoded))
    if "error" in payload:
        raise ValueError("ArcGIS query failed: " + str(payload["error"]))
    return payload


def text(value):
    return "" if value is None else str(value).strip()


def date(value):
    # Preserve the source's calendar date in Toronto; UTC midnight conversion can
    # otherwise make a report appear to fall on a different local day.
    from zoneinfo import ZoneInfo
    if value is None:
        return ""
    return dt.datetime.fromtimestamp(float(value) / 1000, ZoneInfo("America/Toronto")).date().isoformat()


def coordinates(lat, lon):
    # Missing and (0,0) locations must remain in totals, never become ocean pins.
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None
    if math.isfinite(lat) and math.isfinite(lon) and 43.5 <= lat <= 43.9 and -79.65 <= lon <= -79.0:
        return round(lat, 6), round(lon, 6)
    return None, None


def normalize(source, a):
    event = text(a["EVENT_UNIQUE_ID"])
    if not event:
        raise ValueError("Missing incident ID")
    category = text(a.get("CSI_CATEGORY")) if source == "main" else {"homicide": "Homicide", "shooting": "Shootings / discharges"}[source]
    if source == "main" and category not in CATEGORIES:
        raise ValueError("Unknown offence category: " + category)
    lat, lon = coordinates(a["LAT_WGS84"], a["LONG_WGS84"])
    occurred, reported = date(a["OCC_DATE"]), date(a.get("REPORT_DATE"))
    if not (reported if source == "main" else occurred):
        raise ValueError("Missing scope date")
    return [source, a["OBJECTID"], event, category,
            text(a.get("OFFENCE") or a.get("HOMICIDE_TYPE") or a.get("EVENT_TYPE")),
            reported, occurred, text(a["NEIGHBOURHOOD_158"]) or "Not specified",
            text(a["DIVISION"]), text(a.get("PREMISES_TYPE")), lat, lon,
            a.get("DEATH"), a.get("INJURIES")]


def fetch_source(source, start_year):
    service, year_field = SOURCES[source]
    url = BASE + service + "/FeatureServer/0"
    metadata = request_json(url)
    fields = COMMON + EXTRA[source]
    if not set(fields).issubset({f["name"] for f in metadata["fields"]}):
        raise ValueError("Source schema changed: " + source)
    where = f"{year_field} >= '{start_year}'"
    ids = request_json(url + "/query", where=where, returnIdsOnly="true").get("objectIds")
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Empty or duplicate object IDs: " + source)
    ids = sorted(ids)
    rows = []
    for offset in range(0, len(ids), 500):
        batch = ids[offset:offset + 500]
        result = request_json(url + "/query", objectIds=",".join(map(str, batch)),
                              outFields=",".join(fields), returnGeometry="false")
        attributes = [f["attributes"] for f in result["features"]]
        received = [a["OBJECTID"] for a in attributes]
        if result.get("exceededTransferLimit") or len(received) != len(batch) or set(received) != set(batch):
            raise ValueError("Incomplete source batch: " + source)
        rows.extend(normalize(source, a) for a in attributes)
    final_ids = request_json(url + "/query", where=where, returnIdsOnly="true").get("objectIds")
    final_metadata = request_json(url)
    if (sorted(final_ids or []) != ids or
            metadata.get("editingInfo") != final_metadata.get("editingInfo")):
        raise ValueError("Source changed during download; retry refresh: " + source)
    rows.sort(key=lambda row: row[1])
    summary = {"url": url, "where": where, "records": len(rows),
               "latest_date": max(r[5] if source == "main" else r[6] for r in rows),
               "source_edited": metadata.get("editingInfo", {}).get("lastEditDate")}
    print(f"{source}: {len(rows):,} validated records", flush=True)
    return rows, summary


def write_if_changed(path, content):
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = pathlib.Path(stream.name)
        try:
            stream.write(content)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def refresh(start_year=2025, data_dir=DATA_DIR):
    rows, summaries = [], {}
    for source in SOURCES:
        records, summary = fetch_source(source, start_year)
        rows.extend(records)
        summaries[source] = summary
    # Normalize upstream CRLF/trailing whitespace so identical assets compare
    # correctly with text-mode reads and do not churn on every refresh.
    assets = {name: "\n".join(line.rstrip() for line in download(url).splitlines()) + "\n"
              for name, url in ASSETS.items()}
    if any(not content.strip() for content in assets.values()):
        raise ValueError("Empty browser asset")
    substantive = {"start_year": start_year, "columns": COLUMNS, "sources": summaries, "rows": rows}
    target = data_dir / "crimes.json"
    existing = json.loads(target.read_text()) if target.exists() else {}
    # Source edit timestamps alone need not churn data if the selected records
    # are unchanged. Retain the previous fetch time for content-identical inputs.
    def content(payload):
        return {k: payload.get(k) for k in ("start_year", "columns", "rows")}
    if content(existing) == content(substantive):
        payload = existing
    else:
        payload = {"fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **substantive}
    # All downloads and validation finish before replacing any committed input.
    for name, value in assets.items():
        write_if_changed(data_dir / name, value)
    write_if_changed(target, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Snapshot ready: {len(rows):,} records; make data rebuilds the page.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2025,
                        help="inclusive report year (main) / occurrence year (other layers); default 2025")
    args = parser.parse_args()
    if not 2014 <= args.start_year <= dt.date.today().year:
        parser.error("start year must be between 2014 and the current year")
    refresh(args.start_year)


if __name__ == "__main__":
    main()
