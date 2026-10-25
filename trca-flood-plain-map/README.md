# TRCA flood plain map

An interactive Leaflet map of the Toronto and Region Conservation Authority's
published riverine flood plain polygons **and attributed floodline boundaries**.
Filter by watershed or search mapped source names; click features for details,
fit the selection, and toggle polygon and boundary overlays independently. Engineered boundaries are blue,
estimated boundaries are dashed cyan, spills are red, and pending updates are amber.

## Usage

```sh
make        # offline build from committed data/floodplain.json
make test   # offline fetch-validation and rendering tests
make data   # download both open datasets and rebuild (internet required)
make open   # open output/trca-flood-plain-map.html
```

## Data sources

- © Toronto and Region Conservation Authority — [TRCA Open Data Portal](https://trca-camaps.opendata.arcgis.com/).
- [Floodline TRCA Polygon](https://trca-camaps.opendata.arcgis.com/datasets/camaps::floodline-trca-polygon):
  published `Floodline_TRCA_Polygon/FeatureServer/1`.
- [Floodline TRCA Line](https://trca-camaps.opendata.arcgis.com/datasets/camaps::floodline-trca-line):
  published `Floodline_TRCA_Line/FeatureServer/0`. The polygon documentation
  requires this companion layer to identify spills, undefined limits and updates.
- [TRCA data terms and disclaimer](https://www.arcgis.com/home/item.html?id=50ee80b4a2dc4d3ebfb71a2fc33d597a).
  Data is supplied as is; TRCA does not warrant completeness or currency.
- [Official viewer and explanations](https://trca.ca/conservation/flood-risk-management/flood-plain-map-viewer/).
- [Leaflet](https://leafletjs.com/) and © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)
  for the map library and base-map tiles.

## Fetch and layout

`src/fetch_data.py` queries the portal's published feature APIs, not the viewer
HTML. It enumerates object IDs and downloads every record in bounded batches,
checks completeness, sorts by object ID, and writes `data/floodplain.json`
atomically only after both required layers validate. Unchanged content retains
its retrieval date, bytes and modification time. Shapely simplifies validated geometries locally while preserving topology. Server-side
simplification is avoided because the service can return null geometries. Coordinates are WGS84, rounded
to six decimal places and generalized with an approximately ten-metre tolerance
for display. `src/build_site.py` embeds the snapshot in `src/page.html` to produce
`output/trca-flood-plain-map.html`; no runtime data API is required.

## Caveats

This is generalized riverine flood plain mapping, not an engineering-approved
regulatory map or a property-level flood determination. It excludes flooding
from urban drainage capacity constraints. Outside the shaded area does not mean
safe or unregulated. Spill, spill screening, undefined and pending-update lines
need particular care: adjacent lands may be affected even without a polygon.
Confirm precise limits and current information directly with TRCA.

The page searches watershed and source names, not arbitrary street addresses.
The snapshot is embedded; Leaflet and base-map tiles require internet access.
Data refreshes run only when `make data` is invoked.

## Refresh and dependencies

This project includes the repository's [shared Python/uv Make template](../python-project.mk).
Its own Makefile defines artifact inputs, rendering rules, and any configuration
overrides. Build inside the repository checkout so the shared template is available.

`make system-deps` installs [uv](https://formulae.brew.sh/formula/uv)
on macOS using [Homebrew](https://brew.sh), which must already be installed.
On other platforms, install those tools manually before `make deps` / `make data`.
System installation runs only when explicitly requested; other targets never
invoke it. Credentials must be supplied separately.

`make deps` installs this project's complete locked Python environment, including
test dependencies, when it is new or the dependency manifests change. `make data`
uses the same setup before fetching all required upstream inputs. Repeated commands
reuse the environment; they do not attempt repairs. To reinstall from scratch, run
`make clean-deps && make deps` (`clean-venv` remains an alias). Missing or stale
locks fail without being rewritten.
Dependency setup may require network access; installed builds/tests are offline.
`make data` obtains every required input and rebuilds outputs automatically.
Unchanged upstream content preserves data timestamps; missing generated files are
restored. Required-source failures retain previous datasets and return an error.
