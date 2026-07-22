#!/usr/bin/env python3
"""Network step (`make data`): pull DineSafe from Toronto Open Data and reduce it
to one map pin per establishment (its latest inspection + status), writing a
compact, committable data/dinesafe.json.

DineSafe is Toronto Public Health's food-safety inspection program. The Open Data
resource has **one row per infraction/inspection line**, which is far too large
and too fine-grained to map directly, so this step collapses it to the current
state of each establishment:

  - status            : Establishment Status of its most recent inspection
                        (Pass / Conditional Pass / Closed)
  - last_inspection   : that inspection's date
  - infractions       : how many infraction lines that inspection recorded

Coordinates: the DineSafe rows carry Latitude/Longitude for most establishments;
where they are missing or unparseable we fall back to geocoding the address with
OpenStreetMap Nominatim (cached in data/geocode_cache.json), the same approach
the other maps in this repo use.

Requires internet. Re-run with `make data` whenever you want fresher inspections.
The result is committed so that `make` and `make test` build offline.
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
OUT_PATH = DATA_DIR / "dinesafe.json"
CACHE_PATH = DATA_DIR / "geocode_cache.json"

CKAN = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
DATASET = "dinesafe"
SOURCE_PAGE = "https://open.toronto.ca/dataset/dinesafe/"
USER_AGENT = "toronto-dinesafe-map/1.0 (+https://github.com/tianle91/StaticSites)"

# RateLimiter sleeps between calls for us, keeping this inside Nominatim's
# 1 request/second policy. Only hit when a row is missing coordinates.
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
    cache[address] = result  # cache misses too, so we don't re-hammer unknown addresses
    save_cache()
    return result


def ckan(action, **params):
    r = requests.get(f"{CKAN}/api/3/action/{action}", params=params,
                     headers={"User-Agent": USER_AGENT}, timeout=120)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"CKAN {action} failed: {payload}")
    return payload["result"]


def active_resource_id() -> str:
    """The current, datastore-active DineSafe resource (the queryable table)."""
    pkg = ckan("package_show", id=DATASET)
    active = [r for r in pkg["resources"] if r.get("datastore_active")]
    if not active:
        raise RuntimeError("No datastore-active resource on the DineSafe dataset.")
    # Prefer the most recently modified active resource.
    active.sort(key=lambda r: r.get("last_modified") or r.get("created") or "")
    return active[-1]["id"]


def iter_records(rid, batch=10000):
    """Page through every row of a datastore resource."""
    offset = 0
    while True:
        res = ckan("datastore_search", resource_id=rid, limit=batch, offset=offset)
        records = res.get("records", [])
        if not records:
            break
        for rec in records:
            yield rec
        offset += len(records)
        total = res.get("total")
        print(f"  ...{offset}" + (f"/{total}" if total else "") + " rows")
        if total is not None and offset >= total:
            break


def _get(rec, *names):
    """First non-empty value among possible column spellings."""
    for n in names:
        if n in rec and rec[n] not in (None, ""):
            return rec[n]
    return None


def _clean_address(addr) -> str:
    """Upstream fills an absent unit/suite with the literal token "None"
    (e.g. "1 Blue Jays Way None M5V 1J4"). Drop those tokens and tidy whitespace
    so pins and directions links read cleanly."""
    if not addr:
        return ""
    return " ".join(p for p in str(addr).split() if p != "None")


def _is_infraction(rec) -> bool:
    """True when a DineSafe row records an actual infraction. Clean inspections
    come through as a single row whose severity/deficiency columns are blank or
    the literal string "None" (the CKAN export uses "None"/"NA" placeholders)."""
    for val in (_get(rec, "deficiencyDesc", "Infraction Details", "infraction_details"),
                _get(rec, "severity")):
        if val and str(val).strip().lower() not in ("none", "na"):
            return True
    return False


def _coord(rec):
    lat = _get(rec, "Latitude", "latitude")
    lon = _get(rec, "Longitude", "longitude")
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    # DineSafe sits inside the GTA; reject obvious junk (0,0 etc.).
    if 43.0 <= lat <= 44.2 and -80.2 <= lon <= -78.8:
        return [round(lat, 5), round(lon, 5)]
    return None


def reduce_to_establishments(records):
    """Collapse inspection rows to one current record per establishment."""
    est = {}
    for rec in records:
        eid = _get(rec, "estId", "oldEstId", "Establishment ID", "establishment_id") \
            or _get(rec, "estName", "Establishment Name")
        if not eid:
            continue
        date = str(_get(rec, "inspectionDate", "Inspection Date", "inspection_date") or "")
        e = est.get(eid)
        if e is None:
            e = est[eid] = {
                "name": _get(rec, "estName", "Establishment Name", "establishment_name") or "Establishment",
                "type": _get(rec, "Establishment Type", "Establishmenttype", "establishment_type") or "",
                "address": _clean_address(_get(rec, "address", "Establishment Address", "establishment_address")),
                "status": _get(rec, "inspectionStatus", "Establishment Status", "establishment_status") or "",
                "last_inspection": date,
                "min_per_year": _get(rec, "Min. Inspections Per Year", "min_inspections_per_year") or "",
                "coord": _coord(rec),
                "_infractions": {},  # inspection date -> count, so we can report the latest
            }
        # Track infractions per inspection date; keep the newest inspection's status.
        if _is_infraction(rec):
            e["_infractions"][date] = e["_infractions"].get(date, 0) + 1
        else:
            e["_infractions"].setdefault(date, 0)
        if date and date >= (e["last_inspection"] or ""):
            e["last_inspection"] = date
            e["status"] = _get(rec, "inspectionStatus", "Establishment Status", "establishment_status") or e["status"]
        if e["coord"] is None:
            e["coord"] = _coord(rec)
    return est


def main() -> None:
    print("Fetching DineSafe from Toronto Open Data...")
    rid = active_resource_id()
    est = reduce_to_establishments(iter_records(rid))
    print(f"  {len(est)} distinct establishments; resolving coordinates...")

    establishments = []
    geocoded = dropped = 0
    for e in est.values():
        coord = e["coord"]
        if coord is None:
            addr = ", ".join(p for p in [e["address"], "Toronto", "Ontario"] if p)
            coord = geocode(addr)
            if coord:
                geocoded += 1
        if not coord:
            dropped += 1
            continue
        establishments.append({
            "name": e["name"],
            "type": e["type"],
            "address": e["address"],
            "lat": coord[0],
            "lon": coord[1],
            "status": e["status"],
            "last_inspection": e["last_inspection"][:10] if e["last_inspection"] else "",
            "infractions": e["_infractions"].get(e["last_inspection"], 0),
            "min_per_year": e["min_per_year"],
        })

    establishments.sort(key=lambda x: (x["name"] or "").lower())
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.datetime.now().strftime("%Y-%m-%d"),
                "source_page": SOURCE_PAGE,
                "total_records": len(establishments),
                "establishments": establishments,
            },
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    if geocoded:
        print(f"  geocoded {geocoded} establishment(s) whose rows lacked coordinates")
    if dropped:
        print(f"  dropped {dropped} establishment(s) with no usable location")
    print(f"Wrote {OUT_PATH} with {len(establishments)} establishments.")
    print("Done. Now run `make` to rebuild the map.")


if __name__ == "__main__":
    main()
