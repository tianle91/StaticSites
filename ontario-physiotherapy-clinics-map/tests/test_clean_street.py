#!/usr/bin/env python3
"""Regression tests for the address cleaner.

Run with `make test`. Every case here is a real row from the province's clinic list. The two
"survives" groups matter most - they are the ways an over-eager rule would
quietly corrupt a good address instead of merely failing to improve a bad one.
"""
from fetch_data import clean_street

CASES = [
    # (raw street field, expected cleaned form)

    # Unit prefixes, the dominant failure mode.
    ("11-2007 Lawrence Ave West", "2007 Lawrence Ave West"),
    ("L2-414 Victoria Avenue North", "414 Victoria Avenue North"),
    ("12A-10035 Hurontario Street", "10035 Hurontario Street"),
    ("E-310 Wellington Road South", "310 Wellington Road South"),
    ("C-730 Industrial Road", "730 Industrial Road"),
    ("Unit A- 234 Laurier Avenue West", "234 Laurier Avenue West"),
    # ...including ranges of units joined by "&".
    ("1 & 2-1450 Headon Road", "1450 Headon Road"),
    ("12&13-2200 Rutherford Road", "2200 Rutherford Road"),
    ("1B & 1-9275 Markham Road", "9275 Markham Road"),

    # Trailing unit/suite/building noise, including multiple segments.
    ("1308 Queen Street East, Unit 1", "1308 Queen Street East"),
    ("325 West Street, Suite 300, Building A", "325 West Street"),
    ("145 Saddler Street East, Box 1180", "145 Saddler Street East"),
    ("12-2121 Carling Avenue, Entrance 6", "2121 Carling Avenue"),
    ("649 Scottsdale Drive, Lower Level 1", "649 Scottsdale Drive"),
    ("20 Emma Street, Building B", "20 Emma Street"),
    ("8 Glen Watford Dr G3-G5", "8 Glen Watford Dr"),

    # A plaza name in front of the house number.
    ("Kingfisher Square, 9-920 Upper Wentworth Street", "920 Upper Wentworth Street"),

    # A second line packed into the field.
    ("124 Barker Street\nCarling Heights Medical Centre", "124 Barker Street"),
    ("1517 Niagara Stone Road, Hwy 55\nPO Box 794", "1517 Niagara Stone Road, Hwy 55"),

    # Survives untouched: numbered highways/roads must keep their number, or
    # "4500 Highway 7" would degrade to "4500 Highway".
    ("100-4500 Highway 7", "4500 Highway 7"),
    ("3-4119 Petrolia Line", "4119 Petrolia Line"),
    ("318383 Grey Rd 1", "318383 Grey Rd 1"),
    ("8433 Lennox and Addington County Rd 2", "8433 Lennox and Addington County Rd 2"),

    # Survives untouched: an already-clean address is not a candidate for any rule.
    ("1657 Dundas Street East", "1657 Dundas Street East"),
    ("192 Main Street", "192 Main Street"),
    ("1 Meno Ya Win Way", "1 Meno Ya Win Way"),
]


def test_clean_street():
    for raw, want in CASES:
        got = clean_street(raw)
        assert got == want, f"clean_street({raw!r}) == {got!r}, expected {want!r}"


def test_every_result_keeps_a_house_number():
    """A cleaned street must still start with a number - otherwise the rules ate
    the part Nominatim actually matches on."""
    for raw, _ in CASES:
        got = clean_street(raw)
        assert got[:1].isdigit(), f"clean_street({raw!r}) == {got!r} lost its house number"
