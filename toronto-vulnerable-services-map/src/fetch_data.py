#!/usr/bin/env python3
"""Network step: geocode curated addresses and pull every distinct shelter
location from the Toronto Open Data API, then geocode those too.

Outputs (both consumed by build_map.py, both safe to commit):
  - geocode_cache.json : { "address": [lat, lon] | null }  (refines curated pins)
  - shelters.json      : { "date": "...", "locations": [ ...marker dicts... ] }

Requires internet. geopy's RateLimiter enforces the Nominatim usage policy
(<=1 request/second, descriptive User-Agent); results are cached on disk so
reruns are cheap. Re-run with `make data` whenever you want fresh shelter data.
"""
import datetime
import json
import pathlib
import sys

import requests
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

ROOT = pathlib.Path(__file__).resolve().parent.parent  # project root (src/ is one level down)
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
SERVICES = json.loads((DATA_DIR / "services.json").read_text(encoding="utf-8"))
CACHE_PATH = DATA_DIR / "geocode_cache.json"
SHELTERS_PATH = DATA_DIR / "shelters.json"

CKAN = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
DATASET = "daily-shelter-overnight-service-occupancy-capacity"
USER_AGENT = "toronto-vulnerable-services-map/1.0 (+https://github.com/tianle91/StaticSites)"

# RateLimiter sleeps between calls for us, which is what keeps this inside
# Nominatim's 1 request/second policy.
_nominatim = Nominatim(user_agent=USER_AGENT, timeout=30)
_lookup = RateLimiter(_nominatim.geocode, min_delay_seconds=1.1, swallow_exceptions=False)

cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}


def save_cache() -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def geocode(address):
    """Return [lat, lon] for an address, using the on-disk cache. None if not found."""
    if not address:
        return None
    if address in cache:
        return cache[address]
    try:
        loc = _lookup(address, country_codes="ca", exactly_one=True)
    except Exception as exc:  # noqa: BLE001 - network/parse errors are non-fatal
        print(f"  ! geocode failed for {address!r}: {exc}", file=sys.stderr)
        return None
    result = [loc.latitude, loc.longitude] if loc else None
    cache[address] = result  # cache misses too, so we don't re-hammer for unknown addresses
    save_cache()
    if result:
        print(f"  + {address} -> {result}")
    else:
        print(f"  ? no match for {address}")
    return result


def ckan(action, **params):
    r = requests.get(f"{CKAN}/api/3/action/{action}", params=params,
                     headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"CKAN {action} failed: {payload}")
    return payload["result"]


def refine_curated() -> None:
    print("Geocoding curated addresses (refines approximate pins)...")
    for loc in SERVICES["locations"]:
        geocode(loc.get("address"))


def fetch_shelters() -> None:
    print("Fetching shelter locations from Toronto Open Data...")
    pkg = ckan("package_show", id=DATASET)
    active = sorted(
        (r for r in pkg["resources"] if r.get("datastore_active")),
        key=lambda r: r.get("name", ""),
    )
    if not active:
        raise RuntimeError("No datastore-active resource on the dataset.")
    rid = active[-1]["id"]

    # The SQL endpoint (datastore_search_sql) is disabled on Toronto's CKAN, so
    # use datastore_search: find the latest date, then pull that day's rows and
    # aggregate by location in Python.
    top = ckan("datastore_search", resource_id=rid, limit=1, sort="OCCUPANCY_DATE desc")["records"]
    if not top:
        raise RuntimeError("Resource has no records.")
    day_raw = top[0]["OCCUPANCY_DATE"]
    day = str(day_raw)[:10]
    rows = ckan("datastore_search", resource_id=rid, limit=10000,
                filters=json.dumps({"OCCUPANCY_DATE": day_raw}))["records"]
    print(f"  {len(rows)} program rows for {day}; aggregating by location...")

    agg = {}
    for r in rows:
        if not r.get("LOCATION_ADDRESS"):
            continue
        a = agg.setdefault(r.get("LOCATION_ID"), {
            "name": r.get("LOCATION_NAME") or "Shelter location",
            "parts": [r.get("LOCATION_ADDRESS"), r.get("LOCATION_CITY") or "Toronto",
                      r.get("LOCATION_PROVINCE") or "Ontario"],
            "users": 0, "programs": 0,
        })
        a["users"] += int(float(r.get("SERVICE_USER_COUNT") or 0))
        a["programs"] += 1
    print(f"  {len(agg)} distinct shelter locations.")

    locations = []
    for a in agg.values():
        address = ", ".join(p for p in a["parts"] if p)
        coord = geocode(address)
        if not coord:
            continue
        locations.append({
            "name": a["name"],
            "category": "shelter",
            "address": address,
            "lat": coord[0],
            "lon": coord[1],
            "notes": f"{a['users']} served in {a['programs']} program(s) on {day}.",
            "url": f"https://open.toronto.ca/dataset/{DATASET}/",
        })

    SHELTERS_PATH.write_text(
        json.dumps(
            {
                "date": day,                                        # occupancy snapshot date
                "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),  # when this data was pulled
                "source": DATASET,
                "locations": locations,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"  Wrote {SHELTERS_PATH} with {len(locations)} geocoded locations (date {day}).")


def main() -> None:
    refine_curated()
    try:
        fetch_shelters()
    except Exception as exc:  # noqa: BLE001 - keep curated geocoding even if the API is down
        print(f"! Shelter fetch failed ({exc}); shelters.json left unchanged.", file=sys.stderr)
    print("Done. Now run `make` to rebuild the map.")


if __name__ == "__main__":
    main()
