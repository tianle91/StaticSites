"""Itinerary parsing: pick the fastest transit option, collapse walks, label legs."""
import datetime

import fetch_isochrones as fi

ROUTES = {"RH": ("Richmond Hill", 2), "L1": ("Line 1 Yonge-University", 1)}
STOPS = {"A": "Richmond Hill GO", "U": "Union Station GO"}


def _seg(option, segment, mode, route_id=float("nan"), tt_min=0, wait_min=0,
         dep=None, start="", end=""):
    return {
        "option": option, "segment": segment, "mode": mode, "route_id": route_id,
        "departure_time": dep, "start_stop_id": start, "end_stop_id": end,
        "travel_time": datetime.timedelta(minutes=tt_min),
        "wait_time": datetime.timedelta(minutes=wait_min),
    }


def test_picks_transit_option_over_all_walk_and_labels_legs():
    dep = datetime.datetime(2026, 7, 8, 8, 10)
    rows = [
        # option 0: pure-walk fallback (very long) - must be ignored.
        _seg(0, 0, "WALK", tt_min=450),
        # option 1: walk -> rail -> walk.
        _seg(1, 0, "WALK", tt_min=1),
        _seg(1, 1, "RAIL", route_id="RH", tt_min=50, dep=dep, start="A", end="U"),
        _seg(1, 2, "WALK", tt_min=1),
    ]
    legs = fi.itinerary_legs(rows, ROUTES, STOPS)
    assert legs == [
        {"mode": "Walk", "min": 1},
        {"mode": "Rail", "route": "Richmond Hill", "from": "Richmond Hill GO",
         "to": "Union Station GO", "dep": "08:10", "min": 50},
        {"mode": "Walk", "min": 1},
    ]


def test_consecutive_walks_are_merged():
    rows = [_seg(0, 0, "WALK", tt_min=3), _seg(0, 1, "WALK", tt_min=4)]
    # No transit option: falls back to the all-walk option, walks merged to 7.
    legs = fi.itinerary_legs(rows, ROUTES, STOPS)
    assert legs == [{"mode": "Walk", "min": 7}]


def test_route_type_maps_to_mode_label():
    dep = datetime.datetime(2026, 7, 8, 8, 20)
    rows = [_seg(0, 0, "SUBWAY", route_id="L1", tt_min=12, dep=dep, start="A", end="U")]
    legs = fi.itinerary_legs(rows, ROUTES, STOPS)
    assert legs[0]["mode"] == "Subway"
    assert legs[0]["route"] == "Line 1 Yonge-University"


def test_fastest_transit_option_chosen():
    dep = datetime.datetime(2026, 7, 8, 8, 0)
    rows = [
        _seg(1, 0, "RAIL", route_id="RH", tt_min=90, wait_min=5, dep=dep, start="A", end="U"),
        _seg(2, 0, "RAIL", route_id="RH", tt_min=40, wait_min=2, dep=dep, start="A", end="U"),
    ]
    legs = fi.itinerary_legs(rows, ROUTES, STOPS)
    assert len(legs) == 1 and legs[0]["min"] == 40
