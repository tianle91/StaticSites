"""Service-date selection: Easter, statutory holidays, holiday-skipping Wednesday."""
import datetime

import fetch_isochrones as fi


def test_easter_known_years():
    assert fi._easter(2024) == datetime.date(2024, 3, 31)
    assert fi._easter(2025) == datetime.date(2025, 4, 20)
    assert fi._easter(2026) == datetime.date(2026, 4, 5)
    assert fi._easter(2027) == datetime.date(2027, 3, 28)


def test_nth_weekday():
    # Family Day = 3rd Monday of February 2026 -> Feb 16.
    assert fi._nth_weekday(2026, 2, 0, 3) == datetime.date(2026, 2, 16)
    # Labour Day = 1st Monday of September 2026 -> Sep 7.
    assert fi._nth_weekday(2026, 9, 0, 1) == datetime.date(2026, 9, 7)


def test_ontario_holidays_2026():
    h = fi.ontario_holidays(2026)
    expected = {
        datetime.date(2026, 1, 1),    # New Year's Day
        datetime.date(2026, 2, 16),   # Family Day
        datetime.date(2026, 4, 3),    # Good Friday
        datetime.date(2026, 5, 18),   # Victoria Day
        datetime.date(2026, 7, 1),    # Canada Day
        datetime.date(2026, 8, 3),    # Civic Holiday
        datetime.date(2026, 9, 7),    # Labour Day
        datetime.date(2026, 10, 12),  # Thanksgiving
        datetime.date(2026, 12, 25),  # Christmas Day
        datetime.date(2026, 12, 26),  # Boxing Day
    }
    assert expected <= h


def test_victoria_day_when_may24_is_monday():
    # Regression: May 24 is itself a Monday in 2027 and 2032 -> Victoria Day = May 24
    # (the old formula subtracted an extra week and returned May 17).
    assert datetime.date(2027, 5, 24) in fi.ontario_holidays(2027)
    assert datetime.date(2027, 5, 24).weekday() == 0
    assert datetime.date(2032, 5, 24) in fi.ontario_holidays(2032)
    # And the normal case (Tue+) still resolves to the preceding Monday.
    assert datetime.date(2026, 5, 18) in fi.ontario_holidays(2026)


def test_next_weekday_is_a_non_holiday_wednesday():
    d = fi.next_weekday()
    assert d.weekday() == 2                         # Wednesday
    assert d > datetime.date.today()                # strictly in the future
    assert d not in fi.ontario_holidays(d.year)     # never a holiday
