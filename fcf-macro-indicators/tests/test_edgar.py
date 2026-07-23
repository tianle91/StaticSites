"""Offline tests for the SEC EDGAR YTD -> discrete-quarter reconstruction.

Cash-flow-statement XBRL facts are cumulative year-to-date (Q2 = 6 months, etc.),
so _discrete_quarterly must difference them back into single quarters. No network:
we feed it hand-built fact dicts shaped like data.sec.gov's companyconcept USD
units and assert on the reconstructed series.
"""
import pandas as pd

from fetch_data import _discrete_quarterly, _instant_quarterly


def _fact(end, val, fp, filed, *, start="2020-01-01", fy=2020):
    return {"start": start, "end": end, "val": val, "fp": fp, "fy": fy, "filed": filed}


def _full_year():
    # Cumulative YTD legs for one calendar fiscal year.
    return [
        _fact("2020-03-31", 100.0, "Q1", "2020-05-01"),
        _fact("2020-06-30", 250.0, "Q2", "2020-08-01"),
        _fact("2020-09-30", 450.0, "Q3", "2020-11-01"),
        _fact("2020-12-31", 700.0, "FY", "2021-02-01"),
    ]


def test_differences_ytd_into_discrete_quarters():
    s = _discrete_quarterly(_full_year())
    assert list(s.index) == [
        pd.Timestamp("2020-03-31"),
        pd.Timestamp("2020-06-30"),
        pd.Timestamp("2020-09-30"),
        pd.Timestamp("2020-12-31"),
    ]
    assert list(s.values) == [100.0, 150.0, 200.0, 250.0]  # Q2=250-100, Q3=450-250, Q4=700-450


def test_latest_filed_wins_on_restatement():
    facts = _full_year() + [_fact("2020-12-31", 999.0, "FY", "2021-06-01")]  # restated FY, filed later
    s = _discrete_quarterly(facts)
    assert s.loc[pd.Timestamp("2020-12-31")] == 999.0 - 450.0  # uses the restated annual


def test_missing_leg_omits_dependent_quarters_but_keeps_q4():
    # No Q2 filing: Q2 and Q3 can't be differenced, but Q4 = FY - 9M still can.
    facts = [f for f in _full_year() if f["fp"] != "Q2"]
    s = _discrete_quarterly(facts)
    assert list(s.index) == [pd.Timestamp("2020-03-31"), pd.Timestamp("2020-12-31")]
    assert s.loc[pd.Timestamp("2020-12-31")] == 700.0 - 450.0


def test_duration_mismatch_is_skipped():
    # A fact tagged Q1 but spanning 6 months is not a real Q1 leg -> dropped.
    facts = [_fact("2020-06-30", 100.0, "Q1", "2020-08-01")]  # ~6 months, expected ~3
    assert _discrete_quarterly(facts).empty


def test_empty_input():
    assert _discrete_quarterly([]).empty


def test_instant_takes_balance_at_each_quarter_end():
    # Balance-sheet instants: value taken as-reported at each end date, no diff.
    facts = [
        {"end": "2020-03-31", "val": 100.0, "filed": "2020-05-01"},
        {"end": "2020-06-30", "val": 120.0, "filed": "2020-08-01"},
    ]
    s = _instant_quarterly(facts)
    assert list(s.index) == [pd.Timestamp("2020-03-31"), pd.Timestamp("2020-06-30")]
    assert list(s.values) == [100.0, 120.0]


def test_instant_latest_filed_wins_for_same_end():
    facts = [
        {"end": "2020-06-30", "val": 120.0, "filed": "2020-08-01"},
        {"end": "2020-06-30", "val": 125.0, "filed": "2021-08-01"},  # restated later
    ]
    s = _instant_quarterly(facts)
    assert s.loc[pd.Timestamp("2020-06-30")] == 125.0


def test_instant_empty_input():
    assert _instant_quarterly([]).empty
