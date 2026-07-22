"""Unit-test the offline reduction in fetch_data.py.

`reduce_to_establishments` and its helpers are pure (no network), so we can feed
them raw DineSafe-shaped rows and assert the per-establishment timeline the map's
sidebar consumes. Importing fetch_data constructs a Nominatim client but makes no
request until a row is missing coordinates, so this stays offline.
"""
import fetch_data


def _row(**kw):
    base = {
        "estId": "E1",
        "estName": "Sample Diner",
        "Establishment Type": "Restaurant",
        "address": "1 Test St",
        "Latitude": "43.65",
        "Longitude": "-79.38",
    }
    base.update(kw)
    return base


def test_infraction_detection_ignores_placeholders():
    # Clean inspections arrive as a row whose deficiency/severity are blank or the
    # literal "None"/"NA" the CKAN export uses.
    assert not fetch_data._is_infraction(_row(deficiencyDesc="None", severity="NA"))
    assert fetch_data._is_infraction(_row(deficiencyDesc="Fail to sanitize"))
    assert fetch_data._is_infraction(_row(severity="M - Minor"))


def test_infraction_detail_drops_blank_fields():
    d = fetch_data._infraction(_row(deficiencyDesc="Sanitation", severity="C - Crucial",
                                    action="None", Outcome="NA"))
    assert d == {"detail": "Sanitation", "severity": "C - Crucial"}  # blanks dropped


def test_reduce_builds_per_inspection_timeline():
    rows = [
        # Latest inspection: two infraction lines.
        _row(inspectionDate="2026-05-01", inspectionStatus="Conditional Pass",
             deficiencyDesc="Sanitation deficiency", severity="C - Crucial", action="Corrected"),
        _row(inspectionDate="2026-05-01", inspectionStatus="Conditional Pass",
             deficiencyDesc="Non-food contact surface", severity="M - Minor"),
        # An earlier, clean inspection.
        _row(inspectionDate="2025-06-01", inspectionStatus="Pass",
             deficiencyDesc="None", severity="None"),
    ]
    est = fetch_data.reduce_to_establishments(rows)
    e = est["E1"]
    # Current status/date come from the most recent inspection.
    assert e["status"] == "Conditional Pass"
    assert e["last_inspection"] == "2026-05-01"
    # Both inspection dates are tracked, each with its own infraction lines.
    insp = e["_inspections"]
    assert set(insp) == {"2026-05-01", "2025-06-01"}
    assert len(insp["2026-05-01"]["infractions"]) == 2
    assert insp["2026-05-01"]["infractions"][0]["detail"] == "Sanitation deficiency"
    assert insp["2025-06-01"]["infractions"] == []
