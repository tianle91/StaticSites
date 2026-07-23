import unittest

import pandas as pd

from plot_fcf_macro import (
    _INVERSION_LONG,
    _INVERSION_SHORT,
    _baseline_level,
    _quarter_end,
    _rebase_control,
    _rebase_script,
    _rebase_to_anchor,
    _split_columns,
    aggregate_cash,
    aggregate_fcf,
    basket_tickers,
    inversion_spans,
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


class BasketTickersTest(unittest.TestCase):
    def test_reads_tickers_off_fcf_columns(self) -> None:
        frame = pd.DataFrame(columns=["m2", "fcf_AAA", "cash_AAA", "fcf_BBB", "sp500"])
        self.assertEqual(basket_tickers(frame), ["AAA", "BBB"])


class SplitColumnsTest(unittest.TestCase):
    def test_partitions_levels_from_yields(self) -> None:
        cols = [
            "Aggregate FCF (basket sum)",
            "M2 money supply (FRED: M2SL)",
            "10Y Treasury yield (FRED: DGS10)",
            "2Y Treasury yield (FRED: DGS2)",
        ]
        levels, yields = _split_columns(cols)
        self.assertEqual(levels, ["Aggregate FCF (basket sum)", "M2 money supply (FRED: M2SL)"])
        self.assertEqual(yields, ["10Y Treasury yield (FRED: DGS10)", "2Y Treasury yield (FRED: DGS2)"])


class InversionSpansTest(unittest.TestCase):
    def _frame(self, long_vals, short_vals) -> pd.DataFrame:
        idx = pd.period_range("2022Q1", periods=len(long_vals), freq="Q").to_timestamp(how="end").normalize()
        return pd.DataFrame({_INVERSION_LONG: long_vals, _INVERSION_SHORT: short_vals}, index=idx)

    def test_flags_and_merges_contiguous_inverted_quarters(self) -> None:
        # 10Y < 2Y in the middle two quarters only -> one merged span covering them.
        frame = self._frame([4.0, 3.0, 3.0, 4.0], [3.0, 3.5, 3.5, 3.0])
        spans = inversion_spans(frame)
        self.assertEqual(len(spans), 1)
        start, end = spans[0]
        self.assertTrue(start < frame.index[1] < frame.index[2] < end)

    def test_no_span_when_never_inverted(self) -> None:
        frame = self._frame([4.0, 4.0], [3.0, 3.0])
        self.assertEqual(inversion_spans(frame), [])

    def test_empty_when_yield_columns_absent(self) -> None:
        frame = pd.DataFrame({"m2": [1.0]}, index=pd.to_datetime(["2024-03-31"]))
        self.assertEqual(inversion_spans(frame), [])


class RebaseControlTest(unittest.TestCase):
    def _rebased(self) -> pd.DataFrame:
        idx = pd.to_datetime(["2024-03-31", "2024-06-30", "2024-09-30"])
        raw = pd.DataFrame(
            {"Aggregate FCF (basket sum)": [10.0, 20.0, 40.0],
             "10Y Treasury yield (FRED: DGS10)": [4.0, 4.2, 4.1]},
            index=idx,
        )
        # The rebased frame the renderer holds; only attrs are needed by the helpers.
        rebased = raw.copy()
        rebased.attrs["raw"] = raw
        rebased.attrs["anchor"] = pd.Timestamp("2024-06-30")
        return rebased

    def test_control_lists_every_quarter_and_marks_the_anchor(self) -> None:
        html = _rebase_control(self._rebased())
        self.assertEqual(html.count("<option"), 3)
        self.assertIn('value="2024-06-30" selected', html)
        self.assertEqual(html.count("selected"), 1)

    def test_script_embeds_raw_level_data_only(self) -> None:
        script = _rebase_script(self._rebased(), "chart-id")
        self.assertIn("chart-id", script)
        self.assertIn("Aggregate FCF (basket sum)", script)
        # Yields are not rebased, so their raw data must not be embedded.
        self.assertNotIn("DGS10", script)
        self.assertIn("Plotly.restyle", script)


if __name__ == "__main__":
    unittest.main()
