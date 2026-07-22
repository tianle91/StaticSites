#!/usr/bin/env python3
"""Network step: pull every publicly-funded physiotherapy clinic from Ontario's
open-data CKAN datastore and geocode each address.

The ontario.ca page renders its clinic table client-side from this resource, so
we go straight to the API instead of scraping the page:
  https://www.ontario.ca/page/publicly-funded-physiotherapy-clinic-locations

Outputs (both consumed by build_map.py, both safe to commit):
  - clinics.json       : { "generated_at": "...", "clinics": [ ...marker dicts... ] }
  - geocode_cache.json : { "address": [lat, lon] | null }

Requires internet. Stdlib only. Respects the Nominatim usage policy (<=1
request/second, descriptive User-Agent, results cached so reruns are cheap) -
the first full run takes ~5 minutes, later ones are near-instant.
"""
import datetime
import json
import math
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).parent
CACHE_PATH = HERE / "geocode_cache.json"
CLINICS_PATH = HERE / "clinics.json"

CKAN = "https://data.ontario.ca"
# Resource backing the <onesite-interactive-table> on the ontario.ca page.
RESOURCE_ID = "6238e64a-e5a9-484b-97b2-774640f7ab99"
SOURCE_PAGE = "https://www.ontario.ca/page/publicly-funded-physiotherapy-clinic-locations"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "ontario-physiotherapy-clinics-map/1.0 (+https://github.com/tianle91/StaticMaps)"}

cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}


def save_cache() -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def _nominatim(**query):
    """One Nominatim lookup. Pass q= for free-form, or structured params (city=,
    state=, ...) - structured queries are what keep "Perth" from matching Perth
    *County* instead of the town.
    """
    params = urllib.parse.urlencode({**query, "format": "json", "limit": 1, "countrycodes": "ca"})
    req = urllib.request.Request(f"{NOMINATIM}?{params}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except Exception as exc:  # noqa: BLE001 - network/parse errors are non-fatal
        print(f"  ! geocode failed for {query!r}: {exc}", file=sys.stderr)
        return None
    finally:
        time.sleep(1.1)  # Nominatim usage policy: max 1 request/second
    return [float(data[0]["lat"]), float(data[0]["lon"])] if data else None


# Unit/suite noise the province writes into the street field. Nominatim indexes
# buildings, not units, so any of this left in the query turns a good address
# into a miss.
# "11-2007", "L2-414", "12A-10035", "E-310", "Unit A- 234". Requiring a digit
# after the dash keeps hyphenated street names ("Sainte-Marie") intact.
# The "&" alternative covers ranges of units: "1 & 2-1450", "12&13-2200", "1B & 1-9275".
UNIT_TOKEN = r"[A-Za-z]{0,2}\d*[A-Za-z]?"
UNIT_PREFIX = re.compile(
    rf"^(?:unit\s+)?{UNIT_TOKEN}(?:\s*&\s*{UNIT_TOKEN})*\s*-\s*(?=\d)", re.I)
# "Kingfisher Square, 9-920 Upper Wentworth Street" - a plaza name Nominatim
# won't match. Drop leading comma-segments that carry no house number.
PLAZA_PREFIX = re.compile(r"^[^,\d]+,\s*(?=\S)")
UNIT_SUFFIX = re.compile(
    r",?\s*\b(?:unit|suite|ste|apt|apartment|building|bldg|floor|fl|level|lower\s+level|"
    r"upper\s+level|entrance|box|po\s+box|rr|r\.r\.)\b\.?\s*[\w.-]*\s*$",
    re.I,
)
# "8 Glen Watford Dr G3-G5" - a trailing unit code, which unlike the "7" in
# "Highway 7" always mixes a letter with a digit, so requiring the letter keeps
# numbered highways and concession roads intact.
TRAILING_UNIT_CODE = re.compile(r"\s+[A-Za-z]\d+[A-Za-z]?(?:\s*-\s*[A-Za-z]?\d+[A-Za-z]?)?$")


def clean_street(street: str) -> str:
    """Strip unit/suite noise from a street line, leaving "<number> <street>"."""
    # Some rows pack a second line into the field ("124 Barker Street\nCarling
    # Heights Medical Centre"). Keep the first line that carries a house number.
    lines = [ln.strip() for ln in street.splitlines() if ln.strip()]
    s = next((ln for ln in lines if re.search(r"\d", ln)), street)
    s = s.strip().rstrip(",")
    s = PLAZA_PREFIX.sub("", s)
    s = UNIT_PREFIX.sub("", s)
    prev = None
    while prev != s:  # "…, Suite 300, Building A" needs more than one pass
        prev = s
        s = UNIT_SUFFIX.sub("", s).strip().rstrip(",")
    return TRAILING_UNIT_CODE.sub("", s).strip()


def address_candidates(street, city, postal):
    """Queries to try, most specific first. Each is a dict of Nominatim params.

    The plain free-form address goes first so previously cached results stay
    valid; the structured retries are what rescue unit-prefixed addresses.
    """
    full = ", ".join(p for p in [street, city, "Ontario", postal] if p)
    out = [{"q": full}] if full else []
    cleaned = clean_street(street)
    if cleaned and city:
        base = {"street": cleaned, "city": city, "state": "Ontario", "country": "Canada"}
        if postal:
            out.append({**base, "postalcode": postal})
        out.append(base)
        if cleaned != street:
            out.append({"q": ", ".join(p for p in [cleaned, city, "Ontario", postal] if p)})
        # Last resort: the street line alone ("1517 Niagara Stone Road, Hwy 55"
        # -> "1517 Niagara Stone Road"). Still bounded by the city + the
        # OUTLIER_KM check, so a loose match can't wander off.
        head = cleaned.split(",")[0].strip()
        if head and head != cleaned:
            out.append({"street": head, "city": city, "state": "Ontario", "country": "Canada"})
    return out


def _cached(params):
    """Run one Nominatim query, memoised on its parameters."""
    key = params.get("q") or "|".join(f"{k}={v}" for k, v in sorted(params.items()))
    if key in cache:
        return cache[key]
    result = _nominatim(**params)
    cache[key] = result  # cache misses too, so reruns don't re-hammer
    save_cache()
    return result


def geocode(street, city, postal, center):
    """Return ([lat, lon], precision) for a clinic address.

    Tries progressively looser queries and accepts the first hit that lands
    within OUTLIER_KM of the clinic's own city - Nominatim will happily match a
    same-named street in another county otherwise. Falls back to the city
    centre, and returns (None, ...) only if even that fails.
    """
    for params in address_candidates(street, city, postal):
        coord = _cached(params)
        if not coord:
            continue
        if center:
            off = km_between(coord, center)
            if off > OUTLIER_KM:
                print(f"  ~ rejected {params} - {off:.0f} km from {city}")
                continue
        print(f"  + {street}, {city} -> {coord}")
        return coord, "address"
    print(f"  ? no street match for {street}, {city} - using city centre")
    return center, "city"


def city_center(city):
    """Geocode a city once (cached under a "city:" key).

    Structured (not free-form) on purpose: a free-form "Perth, Ontario, Canada"
    returns Perth *County*'s centroid, and "Kenora" returns Kenora *District* -
    both hundreds of km from the town, which would silently poison both the
    fallback pins and the outlier check below.
    """
    if not city:
        return None
    key = f"city:{city}"
    if key in cache:
        return cache[key]
    result = _nominatim(city=city, state="Ontario", country="Canada")
    cache[key] = result
    save_cache()
    print(f"  city {city} -> {result}")
    return result


def km_between(a, b):
    """Rough great-circle distance in km - precise enough for an outlier check."""
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(h))


# Nominatim sometimes resolves a unit-prefixed street address to a same-named
# road hundreds of km away (e.g. a Kenora clinic landing in the northern bush).
# Anything this far from its own city's centre is treated as a bad match and
# demoted to the city centre.
OUTLIER_KM = 40


def ckan(action, **params):
    url = f"{CKAN}/api/3/action/{action}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"CKAN {action} HTTP {exc.code} for {url}") from exc
    if not payload.get("success"):
        raise RuntimeError(f"CKAN {action} failed: {payload}")
    return payload["result"]


def clean(value) -> str:
    return str(value).strip() if value not in (None, "") else ""


def facility_category(kind: str) -> str:
    """Collapse the free-text 'Type of facility' column into two map layers."""
    return "hospital" if "hospital" in kind.lower() else "clinic"


def main() -> None:
    print("Fetching publicly-funded physiotherapy clinics from data.ontario.ca...")
    records = ckan("datastore_search", resource_id=RESOURCE_ID, limit=5000)["records"]
    print(f"  {len(records)} records.")

    clinics = []
    for rec in records:
        # Column names come straight from the published resource (note the
        # double space in "Operating  Name") - normalise on the way out.
        name = clean(rec.get("Operating  Name") or rec.get("Operating Name"))
        street = clean(rec.get("Clinic Address"))
        city = clean(rec.get("City"))
        postal = clean(rec.get("Postal Code"))
        if not name:
            continue
        address = ", ".join(p for p in [street, city, "Ontario", postal] if p)
        center = city_center(city)
        coord, precision = geocode(street, city, postal, center)
        if not coord:
            print(f"  ! dropping {name} ({address}): no coordinates", file=sys.stderr)
            continue
        clinics.append({
            "name": name,
            "category": facility_category(clean(rec.get("Type of facility"))),
            "facility_type": clean(rec.get("Type of facility")),
            "address": address,
            "city": city,
            "postal_code": postal,
            "phone": clean(rec.get("Clinic Phone")),
            "email": clean(rec.get("Clinic Email")),
            "lat": coord[0],
            "lon": coord[1],
            "precision": precision,  # "address" = street match, "city" = city centre only
        })

    CLINICS_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "source_page": SOURCE_PAGE,
                "resource_id": RESOURCE_ID,
                "total_records": len(records),
                "clinics": clinics,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    missing = len(records) - len(clinics)
    coarse = sum(1 for c in clinics if c["precision"] == "city")
    print(f"  Wrote {CLINICS_PATH} with {len(clinics)} geocoded clinics "
          f"({missing} without coordinates, {coarse} placed at the city centre).")
    print("Done. Now run `make` to rebuild index.html.")


if __name__ == "__main__":
    main()
