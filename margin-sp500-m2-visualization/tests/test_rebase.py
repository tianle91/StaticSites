import unittest

import pandas as pd

from plot_macro_series import _baseline_level, _month_end, _rebase_to_anchor


class RebaseHelpersTest(unittest.TestCase):
    def test_month_end_mid_month_anchor(self) -> None:
        anchor = pd.Timestamp("2020-02-20")
        self.assertEqual(_month_end(anchor), pd.Timestamp("2020-02-29"))

    def test_baseline_uses_last_observation_on_or_before_anchor_month_end(self) -> None:
        idx = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])
        s = pd.Series([90.0, 100.0, 110.0], index=idx)
        anchor = pd.Timestamp("2020-02-15")
        self.assertEqual(_baseline_level(s, anchor), 100.0)

    def test_rebase_sets_anchor_month_end_to_one_hundred(self) -> None:
        idx = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])
        s = pd.Series([50.0, 100.0, 150.0], index=idx)
        rebased = _rebase_to_anchor(s, pd.Timestamp("2020-02-20"))
        self.assertAlmostEqual(rebased.loc[pd.Timestamp("2020-02-29")], 100.0)
        self.assertAlmostEqual(rebased.loc[pd.Timestamp("2020-03-31")], 150.0)


if __name__ == "__main__":
    unittest.main()


def test_series_keep_independent_endpoints_and_internal_gaps(monkeypatch):
    import math
    import plot_macro_series as plot

    dates = pd.to_datetime(['2020-01-31', '2020-02-29', '2020-03-31', '2020-05-31'])
    frame = pd.DataFrame({
        'm2': [10., 20., float('nan'), float('nan')],
        'cpi': [100., 110., 120., float('nan')],
        'ppi': [200., 210., float('nan'), 220.],
        'margin_debit': [30., 40., 50., float('nan')],
        'sp500': [1000., 1100., 1200., 1300.],
    }, index=dates)
    monkeypatch.setattr(plot, 'load_series', lambda: frame)
    rebased = plot.build_rebased(pd.Timestamp('2020-01-01'))
    payload = plot.chart_payload(rebased)
    series = {series['id']: series['points'] for series in payload['panels'][0]['series']}
    assert payload['domain'][-1] == '2020-05-31'
    assert [point['value'] for point in series['M2 (FRED: M2SL)']] == [100., 200., None, None, None]
    ppi = series['PPI (FRED: PPIACO)']
    assert ppi[2]['value'] is None and ppi[3]['value'] is None
    assert ppi[4]['value'] == 110.
    assert math.isclose(series['S&P 500 (^GSPC, month-end)'][-1]['value'], 130.)
    assert series['Margin debit (FINRA, $m)'][-1]['value'] is None
