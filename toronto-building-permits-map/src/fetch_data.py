#!/usr/bin/env python3
"""Fetch Toronto Open Data permits and municipal address points.

The full active register is retained. GEO_ID is joined to municipal ADDRESS_POINT_ID;
unmatched records remain searchable without a pin. No geocoding is performed.
Both sources must succeed before any committed snapshot is replaced.
"""
import argparse
import csv
import datetime
import json
import math
import pathlib
import tempfile
import time
import urllib.parse

import ijson
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_PATH = DATA_DIR / "permits.json"
CKAN = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
COLUMNS = ["number", "revision", "address", "type", "structure", "work", "status",
           "applied", "issued", "cost", "description", "lat", "lon"]


def download(url, target):
    for attempt in range(3):
        try:
            # requests follows the portal's download redirects reliably. Stream
            # the large address export and restart from zero after a disconnect.
            with requests.get(url, stream=True, timeout=(30, 180)) as source:
                source.raise_for_status()
                with target.open("wb") as output:
                    for block in source.iter_content(1024 * 1024):
                        output.write(block)
            return
        except (OSError, requests.RequestException):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def catalogue(slug, directory):
    path = directory / (slug + ".json")
    download(CKAN + "/api/3/action/package_show?" + urllib.parse.urlencode({"id": slug}), path)
    payload = json.loads(path.read_text())
    if not payload.get("success"):
        raise ValueError("Toronto catalogue query failed")
    return payload["result"]["resources"]


def source_file(resources, name, directory):
    matches = [r for r in resources if r["name"].lower() == name.lower()]
    if len(matches) != 1:
        raise ValueError("Cannot find unique official download: " + name)
    path = directory / name.replace(" ", "-")
    download(matches[0]["url"], path)
    return path


def records(path, required):
    # utf-8-sig accepts the optional BOM on the City's exported CSVs.
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("Missing required fields in " + str(path))
        for row in reader:
            if None in row:
                raise ValueError("Malformed CSV row")
            yield row


def text(value):
    return str(value).strip() if value is not None else ""


def identifier(value):
    value = text(value)
    # Some CSV exports turn integer IDs into e.g. 575725.0.
    return value[:-2] if value.endswith(".0") else value


def point(row):
    geometry = row.get("geometry") or row.get("GEOMETRY")
    if geometry:
        parsed = json.loads(geometry) if isinstance(geometry, str) else geometry
        if parsed.get("type") == "MultiPoint" and len(parsed.get("coordinates", [])) == 1:
            # The portal's GeoJSON export wraps each address in a MultiPoint;
            # its datastore represents the same single coordinate as Point.
            lon, lat = parsed["coordinates"][0][:2]
        elif parsed.get("type") == "Point":
            lon, lat = parsed["coordinates"][:2]
        else:
            raise ValueError("Unexpected municipal address geometry")
    else:
        lon = row.get("LONGITUDE", row.get("longitude"))
        lat = row.get("LATITUDE", row.get("latitude"))
    lat, lon = float(lat), float(lon)
    if not (math.isfinite(lat) and math.isfinite(lon) and 43 < lat < 45 and -81 < lon < -78):
        raise ValueError("Invalid municipal address coordinates")
    return round(lat, 6), round(lon, 6)


def geojson_records(path):
    # The official complete address export is hundreds of MB; stream features.
    with path.open("rb") as stream:
        for feature in ijson.items(stream, "features.item", use_float=True):
            if feature.get("type") != "Feature":
                raise ValueError("Invalid address GeoJSON feature")
            yield {**feature["properties"], "geometry": feature["geometry"]}


def address_index(rows, expected_count=None):
    addresses = {}
    count = 0
    for row in rows:
        count += 1
        key = identifier(row.get("ADDRESS_POINT_ID"))
        if not key:
            raise ValueError("Address point has no municipal ADDRESS_POINT_ID")
        # Land points precede entrances; point ID breaks ties deterministically.
        priority = (0 if row.get("ADDRESS_CLASS") == "L" else 1, int(identifier(row["ADDRESS_POINT_ID"])))
        coordinates = point(row)
        if key not in addresses or priority < addresses[key][0]:
            addresses[key] = (priority, coordinates)
    if not count:
        raise ValueError("Empty address source")
    if expected_count is not None and count != expected_count:
        raise ValueError(f"Incomplete address source: expected {expected_count}, received {count}")
    return {key: value[1] for key, value in addresses.items()}


def cost(value):
    try:
        number = float(text(value).replace(",", ""))
    except ValueError:
        return None
    return number if math.isfinite(number) and number >= 0 else None


def normalize(permits, addresses, expected_count=None):
    result = []
    unmatched = 0
    for row in permits:
        number, revision = text(row.get("PERMIT_NUM")), text(row.get("REVISION_NUM"))
        if not number:
            raise ValueError("Missing permit number")
        # A permit/revision can cover multiple property rows. Retain all of them.
        location = addresses.get(identifier(row.get("GEO_ID")))
        if location is None:
            unmatched += 1
        address = " ".join(text(row.get(key)) for key in
                           ["STREET_NUM", "STREET_NAME", "STREET_TYPE", "STREET_DIRECTION"] if text(row.get(key)))
        result.append([number, revision, address, text(row.get("PERMIT_TYPE")),
                       text(row.get("STRUCTURE_TYPE")), text(row.get("WORK")), text(row.get("STATUS")) or "Unknown",
                       text(row.get("APPLICATION_DATE"))[:10], text(row.get("ISSUED_DATE"))[:10],
                       cost(row.get("EST_CONST_COST")), text(row.get("DESCRIPTION")),
                       *(location if location else (None, None))])
    if not result:
        raise ValueError("Empty permit source")
    if expected_count is not None and len(result) != expected_count:
        raise ValueError(f"Incomplete permit source: expected {expected_count}, received {len(result)}")
    if unmatched == len(result):
        raise ValueError("No permits matched municipal address points; check source schemas")
    result.sort(key=lambda row: tuple(str(value) for value in row))
    return {"columns": COLUMNS, "stats": {"total": len(result), "mapped": len(result) - unmatched, "unmatched": unmatched}, "permits": result}


def write_snapshot(path, substantive):
    existing = json.loads(path.read_text()) if path.exists() else {}
    previous = {k: v for k, v in existing.items() if k != "retrieved_at"}
    if previous == substantive:
        return False
    payload = {"retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), **substantive}
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = pathlib.Path(stream.name)
        try:
            json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def source_count(resources, directory):
    matches = [r for r in resources if r.get("datastore_active")]
    if len(matches) != 1:
        raise ValueError("Cannot identify source count resource")
    path = directory / (matches[0]["id"] + "-count.json")
    download(CKAN + "/api/3/action/datastore_search?" + urllib.parse.urlencode({
        "resource_id": matches[0]["id"], "limit": 0}), path)
    response = json.loads(path.read_text())
    if not response.get("success") or response["result"].get("total_was_estimated"):
        raise ValueError("Cannot confirm exact upstream record count")
    return int(response["result"]["total"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--permits-csv", type=pathlib.Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--addresses-csv", type=pathlib.Path)
    group.add_argument("--addresses-geojson", type=pathlib.Path)
    parser.add_argument("--expected-permits", type=int)
    parser.add_argument("--expected-addresses", type=int)
    args = parser.parse_args()
    if args.permits_csv and args.expected_permits is None:
        parser.error("--permits-csv requires --expected-permits from the official source count")
    if (args.addresses_csv or args.addresses_geojson) and args.expected_addresses is None:
        parser.error("address overrides require --expected-addresses from the official source count")
    with tempfile.TemporaryDirectory() as temporary:
        directory = pathlib.Path(temporary)
        permit_resources = None if args.permits_csv else catalogue("building-permits-active-permits", directory)
        address_resources = None if (args.addresses_csv or args.addresses_geojson) else catalogue(
            "address-points-municipal-toronto-one-address-repository", directory)
        permit_count = args.expected_permits if args.expected_permits is not None else source_count(permit_resources, directory)
        address_count = args.expected_addresses if args.expected_addresses is not None else source_count(address_resources, directory)
        permits = args.permits_csv or source_file(permit_resources, "building-permits-active-permits.csv", directory)
        addresses = args.addresses_csv or args.addresses_geojson or source_file(address_resources, "Address Points - 4326.geojson", directory)
        source = records(addresses, {"ADDRESS_ID", "ADDRESS_POINT_ID"}) if args.addresses_csv else geojson_records(addresses)
        index = address_index(source, address_count)
        data = normalize(records(permits, {"PERMIT_NUM", "REVISION_NUM", "GEO_ID", "STATUS", "STREET_NUM", "STREET_NAME", "APPLICATION_DATE"}), index, permit_count)
        changed = write_snapshot(OUT_PATH, data)
        print("Permit snapshot " + ("updated: " if changed else "unchanged: ") + str(data["stats"]))


if __name__ == "__main__":
    main()
