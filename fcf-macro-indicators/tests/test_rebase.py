import unittest

import pandas as pd

from plot_fcf_macro import (
    _baseline_level,
    _quarter_end,
    _rebase_to_anchor,
    aggregate_cash,
    aggregate_fcf,
)


class RebaseHelpersTest(unittest.TestCase):
    def test_quarter_end_mid_quarter_anchor(self) -> None:
        self.assertEqual(_quarter_end(pd.Timestamp("2024-05-14")), pd.Timestamp("2024-06-30"))
        self.assertEqual(_quarter_end(pd.Timestamp("2024-02-01")), pd.Timestamp("2024-03-31"))

    def test_baseline_uses_last_observation_on_or_before_anchor_quarter_end(self) -> None:
        idx = pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30"])
        s = pd.Series([90.0, 100.0, 110.0], index=idx)
        # A mid-quarter anchor resolves to that quarter's end (2024-06-30 -> 100).
        self.assertEqual(_baseline_level(s, pd.Timestamp("2024-05-15")), 100.0)

    def test_rebase_sets_anchor_quarter_to_one_hundred(self) -> None:
        idx = pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30"])
        s = pd.Series([50.0, 100.0, 150.0], index=idx)
        rebased = _rebase_to_anchor(s, pd.Timestamp("2024-06-30"))
        self.assertAlmostEqual(rebased.loc[pd.Timestamp("2024-06-30")], 100.0)
        self.assertAlmostEqual(rebased.loc[pd.Timestamp("2024-09-30")], 150.0)


class AggregateFcfTest(unittest.TestCase):
    def test_sums_only_quarters_where_every_member_reports(self) -> None:
        idx = pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30"])
        frame = pd.DataFrame(
            {
                "fcf_AAA": [10.0, 20.0, 30.0],
                "fcf_BBB": [1.0, 2.0, float("nan")],  # BBB missing 2024-09-30
                "m2": [100.0, 101.0, 102.0],
            },
            index=idx,
        )
        agg = aggregate_fcf(frame)
        # The all-members-present quarters sum; the incomplete quarter is dropped.
        self.assertEqual(list(agg.index), [pd.Timestamp("2024-03-31"), pd.Timestamp("2024-06-30")])
        self.assertEqual(agg.loc[pd.Timestamp("2024-03-31")], 11.0)
        self.assertEqual(agg.loc[pd.Timestamp("2024-06-30")], 22.0)

    def test_raises_without_fcf_columns(self) -> None:
        frame = pd.DataFrame({"m2": [1.0]}, index=pd.to_datetime(["2024-03-31"]))
        with self.assertRaises(SystemExit):
            aggregate_fcf(frame)


class AggregateCashTest(unittest.TestCase):
    def test_sums_only_quarters_where_every_member_reports(self) -> None:
        idx = pd.to_datetime(["2024-03-31", "2024-06-30"])
        frame = pd.DataFrame(
            {
                "cash_AAA": [5.0, 6.0],
                "cash_BBB": [1.0, float("nan")],  # BBB missing 2024-06-30
                "m2": [100.0, 101.0],
            },
            index=idx,
        )
        agg = aggregate_cash(frame)
        self.assertEqual(list(agg.index), [pd.Timestamp("2024-03-31")])
        self.assertEqual(agg.loc[pd.Timestamp("2024-03-31")], 6.0)

    def test_empty_without_cash_columns(self) -> None:
        # Optional series: absent cash columns yield an empty series (no error),
        # so a CSV predating the cash columns still renders.
        frame = pd.DataFrame({"m2": [1.0]}, index=pd.to_datetime(["2024-03-31"]))
        self.assertTrue(aggregate_cash(frame).empty)


if __name__ == "__main__":
    unittest.main()
