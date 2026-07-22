# Ontario Publicly-Funded Physiotherapy Clinics Map

An interactive Leaflet map of every clinic and hospital listed on
[ontario.ca — publicly-funded physiotherapy clinic locations](https://www.ontario.ca/page/publicly-funded-physiotherapy-clinic-locations),
with phone, email, a text filter (name / city / postal code) and directions
links.

## Run

```bash
make        # builds output/ontario-physiotherapy-clinics-map.html from data/clinics.json (offline)
make data   # re-pulls the clinic list and geocodes it, then rebuilds (needs internet)
make open   # build and open in a browser
```

## Where the data comes from

The ontario.ca page renders its table client-side from an
`<onesite-interactive-table>` component, so there is nothing to scrape in the
served HTML. That component reads a CKAN datastore resource, which
`src/fetch_data.py` queries directly:

```
https://data.ontario.ca/api/3/action/datastore_search?resource_id=6238e64a-e5a9-484b-97b2-774640f7ab99
```

Fields published per clinic: type of facility, operating name, address, city,
postal code, phone, email. There are **no coordinates** in the source, so
`src/fetch_data.py` geocodes each address with OpenStreetMap Nominatim
(1 request/second, results cached in `data/geocode_cache.json`).

## Caveats

- **11 of 255 pins are city centres, not street addresses.** Those say so in the
  popup — the exact address is still listed, so confirm it there rather than
  trusting the dot. The rest are street-level matches.
- City lookups are **structured** (`city=&state=&country=`) rather than
  free-form on purpose: free-form `Perth, Ontario, Canada` returns Perth
  *County*'s centroid and `Kenora` returns Kenora *District* — both hundreds of
  km from the town. Street matches are also rejected if they land more than
  40 km from their own city.

### How addresses get matched

The province writes unit numbers into the street field, which Nominatim indexes
by building, not unit — so `11-2007 Lawrence Ave West` misses outright. Naively
geocoding the raw field leaves 110 of 255 clinics stuck at their city centre.
`clean_street()` strips the unit noise and `geocode()` then tries progressively
looser queries, taking the first hit that survives the 40 km check:

| Raw | Cleaned |
| --- | --- |
| `11-2007 Lawrence Ave West` | `2007 Lawrence Ave West` |
| `1B & 1-9275 Markham Road` | `9275 Markham Road` |
| `325 West Street, Suite 300, Building A` | `325 West Street` |
| `8 Glen Watford Dr G3-G5` | `8 Glen Watford Dr` |
| `Kingfisher Square, 9-920 Upper Wentworth Street` | `920 Upper Wentworth Street` |
| `124 Barker Street\nCarling Heights Medical Centre` | `124 Barker Street` |

That takes the city-centre fallbacks from 110 down to 11. The stragglers are a
source typo (`455 Simcoe Steet South`), highway-style addresses (`6-209 Highway
#20 East`) and rural county roads (`8433 Lennox and Addington County Rd 2`) that
OSM simply doesn't carry at house-number precision.

Note that `100-4500 Highway 7` cleans to `4500 Highway 7`, not `4500 Highway`:
the trailing-unit-code rule requires a letter next to the digit, so numbered
highways and concession roads survive.
- **Eligibility is limited** — generally seniors 65+, people 19 and under, and
  patients recently discharged from hospital or receiving ODSP/OW. Call the
  clinic before going.
- The province updates the list regularly; re-run `make data` for a fresh pull.
