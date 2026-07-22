"""Station snapping: exact stop-name match, nearest-stop fallback, give-up."""
import fetch_isochrones as fi

# stops = (name_index, coords_list) as returned by load_stop_coords()
STOPS = (
    {"richmond hill go": (43.874307, -79.426167),
     "union station go": (43.645195, -79.380600)},
    [(43.874307, -79.426167), (43.645195, -79.380600), (43.8000, -79.5000)],
)


def test_exact_name_match_wins_over_proximity():
    # Curated coord is ~250 m off; the name match lands on the real platform.
    assert fi.snap_to_stop("Richmond Hill GO", 43.872, -79.427, STOPS) == \
        (43.874307, -79.426167)


def test_falls_back_to_nearest_stop_when_name_unknown():
    # No name match; nearest stop (~tens of m away) within max_m is returned.
    snapped = fi.snap_to_stop("Nowhere Station", 43.8000, -79.5001, STOPS)
    assert snapped == (43.8000, -79.5000)


def test_keeps_curated_coord_when_nothing_close():
    # Unknown name and nearest stop is far (> max_m): keep the input coordinate.
    here = (45.0, -76.0)  # Ottawa-ish, far from any stop
    assert fi.snap_to_stop("Nowhere", here[0], here[1], STOPS, max_m=700) == here
