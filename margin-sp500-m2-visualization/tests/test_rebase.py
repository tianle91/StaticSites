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
