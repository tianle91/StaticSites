#!/usr/bin/env python3
"""
Read the quarterly source series from data/series.csv and plot free cash flow
against the macro backdrop across three panels that share one x-axis: the top panel
rebases the level series (aggregate FCF, aggregate cash, money-market-fund assets,
M2 money supply, the S&P 500) to 100 at a configurable anchor quarter to compare
growth; the middle panel shows the 3M / 2Y / 10Y / 30Y Treasury curve as raw yields
(%), which have a natural common scale and would blow up if rebased to a near-zero-
rate anchor; the bottom panel plots the S&P 500 ÷ liquidity ratio (also rebased to
100), with the liquidity denominator (an official series -- M2 or money-market-fund
assets) chosen via a picker in the interactive chart.

Free cash flow is the coarsest input (reported quarterly), so it sets both the
grid and the charted window: the chart spans the quarters in which every basket
member reports FCF. Renders a static PNG (matplotlib) or a responsive HTML chart
(native SVG), picked from the output file extension. Offline: refresh data/series.csv
with `make data`.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from staticsites.charts import chart_page, compact_label, matplotlib_style, png_sources, series_data
from staticsites import timeseries

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
SERIES_CSV = ROOT / "data" / "series.csv"
PULLED_STAMP = ROOT / "data" / "generated_at.txt"  # written by fetch_data.py

# Browser tab, bookmark and page heading.
PAGE_TITLE = "Free Cash Flow vs. M2, the S&amp;P 500 &amp; the Treasury Curve"

# Display label -> CSV column. Order controls legend/plot order. The aggregate
# FCF line is derived from the fcf_* columns (see build_rebased); the rest map
# straight through. Yields run light->dark from the short end to the long end.
SERIES_COLORS = {
    "Aggregate FCF (basket sum)": "#b64949",
    "Aggregate cash & equivalents (basket sum)": "#aa5633",
    "Money-market-fund assets (FRED: MMMFFAQ027S)": "#317f98",
    "M2 money supply (FRED: M2SL)": "#466aa0",
    "S&P 500 (^GSPC)": "#116965",
    "3M Treasury yield (FRED: DGS3MO)": "#a79bb5",
    "2Y Treasury yield (FRED: DGS2)": "#806493",
    "10Y Treasury yield (FRED: DGS10)": "#5f4778",
    "30Y Treasury yield (FRED: DGS30)": "#382650",
}

# Display label -> CSV column for the straight-through (non-derived) series.
# Money-market-fund assets sit next to the company-cash line (both are cash levels)
# and ahead of M2, so the top panel reads cash -> broad money -> equities.
MACRO_COLUMNS = {
    "Money-market-fund assets (FRED: MMMFFAQ027S)": "mmf",
    "M2 money supply (FRED: M2SL)": "m2",
    "S&P 500 (^GSPC)": "sp500",
    "3M Treasury yield (FRED: DGS3MO)": "dgs3mo",
    "2Y Treasury yield (FRED: DGS2)": "dgs2",
    "10Y Treasury yield (FRED: DGS10)": "dgs10",
    "30Y Treasury yield (FRED: DGS30)": "dgs30",
}

# The chart is split into two panels sharing one x-axis. Yields live in their own
# panel and are plotted as RAW percentages, not rebased to 100: they already share
# a natural common scale (percent), and rebasing them to an anchor quarter whose
# short rate was near zero (e.g. the 3M bill at ~0.03% in 2014) blows the index up
# into the thousands and crushes every other line. Everything else is a dollar/
# index level in incomparable units, so those ARE rebased to 100 to compare growth.
YIELD_LABELS = [
    "3M Treasury yield (FRED: DGS3MO)",
    "2Y Treasury yield (FRED: DGS2)",
    "10Y Treasury yield (FRED: DGS10)",
    "30Y Treasury yield (FRED: DGS30)",
]

# The third panel plots S&P-500-÷-liquidity ratios: how equity prices move relative
# to the cash in the system. Only OFFICIAL FRED series are offered as the denominator
# -- constructed proxies (e.g. "Fed net liquidity" = Fed balance sheet − Treasury
# General Account − reverse repo) are deliberately excluded. The interactive chart
# lets the viewer pick the denominator; each carries the short pro/con shown in the
# panel title next to the picker. `column` is the display label of the raw level in
# the aligned frame (see MACRO_COLUMNS); `color` matches that level's line up top.
SP500_LABEL = "S&P 500 (^GSPC)"
LIQUIDITY_MEASURES = [
    {
        "key": "m2",
        "name": "M2 money supply",
        "column": "M2 money supply (FRED: M2SL)",
        "color": "#466aa0",
        "pro": "broadest money measure, decades of history, short (~4-week) lag",
        "con": "broad and slow; includes retail savings that don't move prices; "
               "weak short-horizon link to equities; 2020 definitional break",
    },
    {
        "key": "mmf",
        "name": "Money-market-fund assets",
        "column": "Money-market-fund assets (FRED: MMMFFAQ027S)",
        "color": "#317f98",
        "pro": "“cash on the sidelines” that can rotate into stocks; at record highs",
        "con": "~10-week Z.1 lag; ambiguous sign (dry powder vs. risk-off flight); "
               "driven heavily by the level of short rates",
    },
]
# The denominator the static PNG leads with (it shows every measure) and the initial
# selection in the interactive picker.
DEFAULT_MEASURE_KEY = "m2"


def _measure(key: str) -> dict:
    for m in LIQUIDITY_MEASURES:
        if m["key"] == key:
            return m
    raise KeyError(key)


def compute_ratios(aligned: pd.DataFrame) -> dict[str, pd.Series]:
    """Raw S&P-500 ÷ liquidity ratio per available official measure, from the raw
    (un-rebased) aligned levels. Both inputs are levels on the same quarterly grid,
    so the quotient is a clean point-by-point ratio; its absolute units are arbitrary
    (index points per $bn/$mn), so callers rebase it to 100 before plotting. Liquidity
    levels are strictly positive, so no divide-by-zero guard is needed."""
    if SP500_LABEL not in aligned:
        return {}
    sp = aligned[SP500_LABEL]
    return {m["key"]: sp / aligned[m["column"]]
            for m in LIQUIDITY_MEASURES if m["column"] in aligned}


def _split_columns(columns) -> tuple[list[str], list[str]]:
    """Partition series labels into (rebased level panel, raw yield panel),
    preserving the SERIES_COLORS display order within each."""
    levels = [c for c in columns if c not in YIELD_LABELS]
    yields = [c for c in columns if c in YIELD_LABELS]
    return levels, yields


# Yield-curve inversion is shaded where the long rate sits below the short rate.
# The canonical recession signal is the 2s10s spread (10Y minus 2Y) going negative.
_INVERSION_LONG = "10Y Treasury yield (FRED: DGS10)"
_INVERSION_SHORT = "2Y Treasury yield (FRED: DGS2)"
INVERSION_LABEL = "Yield-curve inversion (10Y < 2Y)"
INVERSION_COLOR = "#b64949"


def inversion_spans(frame: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Contiguous [start, end] date spans where 10Y < 2Y (an inverted 2s10s curve).
    Each quarter-end that is inverted is widened by ~half a quarter so a lone
    inverted quarter is still a visible band and adjacent ones merge into one."""
    if _INVERSION_LONG not in frame or _INVERSION_SHORT not in frame:
        return []
    inverted = (frame[_INVERSION_LONG] < frame[_INVERSION_SHORT]).to_numpy()
    idx = pd.DatetimeIndex(frame.index)
    half = pd.Timedelta(days=46)
    spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    run_start: pd.Timestamp | None = None
    for i, inv in enumerate(inverted):
        if inv and run_start is None:
            run_start = idx[i]
        elif not inv and run_start is not None:
            spans.append((run_start - half, idx[i - 1] + half))
            run_start = None
    if run_start is not None:
        spans.append((run_start - half, idx[-1] + half))
    return spans

# Where the FCF numbers came from is recorded by fetch_data.py in this marker
# ("label|url"), so the footer attributes the committed data accurately whatever
# produced it. Absent (e.g. an older pull) -> the Yahoo default below.
FCF_SOURCE_FILE = ROOT / "data" / "fcf_source.txt"
DEFAULT_FCF_SOURCE = (
    "Company free cash flow via Yahoo Finance",
    "https://finance.yahoo.com/quote/AAPL/cash-flow",
)

# The fixed (macro) part of the "Data sources" footer; the FCF entry is prepended
# at render time from fcf_source(). Shown on the chart itself so a reader who
# only has the image/page can see and follow where each series came from.
MACRO_SOURCES: list[tuple[str, str]] = [
    ("FRED M2 (M2SL)", "https://fred.stlouisfed.org/series/M2SL"),
    ("FRED 3M Treasury (DGS3MO)", "https://fred.stlouisfed.org/series/DGS3MO"),
    ("FRED 2Y Treasury (DGS2)", "https://fred.stlouisfed.org/series/DGS2"),
    ("FRED 10Y Treasury (DGS10)", "https://fred.stlouisfed.org/series/DGS10"),
    ("FRED 30Y Treasury (DGS30)", "https://fred.stlouisfed.org/series/DGS30"),
    ("S&P 500 via Yahoo Finance (^GSPC)", "https://finance.yahoo.com/quote/%5EGSPC"),
]


def fcf_source() -> tuple[str, str]:
    """(label, url) for the FCF data, from the marker fetch_data.py writes."""
    if FCF_SOURCE_FILE.exists():
        line = FCF_SOURCE_FILE.read_text(encoding="utf-8").strip()
        if "|" in line:
            label, url = line.split("|", 1)
            return label.strip(), url.strip()
    return DEFAULT_FCF_SOURCE


def data_sources() -> list[tuple[str, str]]:
    return [fcf_source(), *MACRO_SOURCES]


def data_pulled_date() -> str:
    return timeseries.data_pulled_date(PULLED_STAMP, SERIES_CSV)


def _quarter_end(ts: pd.Timestamp) -> pd.Timestamp:
    return timeseries.period_end(ts, "Q")


def _baseline_level(s: pd.Series, anchor: pd.Timestamp) -> float:
    return timeseries.baseline_level(s, anchor, frequency="Q")


def _rebase_to_anchor(s: pd.Series, anchor: pd.Timestamp) -> pd.Series:
    return timeseries.rebase(s, anchor, frequency="Q")


def load_series() -> pd.DataFrame:
    return timeseries.load_series(SERIES_CSV)


def _aggregate(frame: pd.DataFrame, prefix: str) -> pd.Series:
    """Sum the per-company columns with this prefix, restricted to quarters where
    *every* member reports, so the aggregate never jumps because a company drops
    in or out of the sample. Empty when no such columns exist."""
    cols = [c for c in frame.columns if c.startswith(prefix)]
    if not cols:
        return pd.Series(dtype=float)
    block = frame[cols].dropna(how="any")
    return block.sum(axis=1) if not block.empty else pd.Series(dtype=float)


def aggregate_fcf(frame: pd.DataFrame) -> pd.Series:
    """Summed per-company FCF (required series)."""
    fcf = _aggregate(frame, "fcf_")
    if fcf.empty:
        if not any(c.startswith("fcf_") for c in frame.columns):
            raise SystemExit("No fcf_* columns in series.csv - run `make data`.")
        raise RuntimeError("No quarter has FCF for every basket member.")
    return fcf


def aggregate_cash(frame: pd.DataFrame) -> pd.Series:
    """Summed per-company cash & equivalents. Optional: empty when the committed
    CSV predates the cash columns, in which case the chart omits the line."""
    return _aggregate(frame, "cash_")


def basket_tickers(frame: pd.DataFrame) -> list[str]:
    """The companies whose FCF/cash the aggregate lines sum, read off the fcf_*
    column names so the chart names exactly what was fetched into series.csv."""
    return [c[len("fcf_"):] for c in frame.columns if c.startswith("fcf_")]


def build_rebased(rebase_anchor: pd.Timestamp | None) -> pd.DataFrame:
    """Align FCF + macro on the common quarterly window. Level series (FCF, cash,
    money-market-fund assets, M2, S&P 500) are rebased to 100; Treasury yields are
    kept as raw percentages (see YIELD_LABELS) for their own panel."""
    frame = load_series()
    fcf = aggregate_fcf(frame)

    # The charted window is the quarters where aggregate FCF exists; macro is
    # quarterly and complete, so intersect the two indices.
    window = fcf.index.intersection(frame.index)
    if window.empty:
        raise RuntimeError("No overlap between FCF and macro series.")

    data = {"Aggregate FCF (basket sum)": fcf.loc[window]}
    # Cash & equivalents is optional -- include the line only when present.
    cash = aggregate_cash(frame)
    if not cash.empty:
        data["Aggregate cash & equivalents (basket sum)"] = cash.reindex(window)
    for label, col in MACRO_COLUMNS.items():
        data[label] = frame[col].loc[window]
    aligned = pd.DataFrame(data).sort_index().dropna()
    if aligned.empty:
        raise RuntimeError("No overlapping observations after alignment.")

    anchor = _quarter_end(rebase_anchor) if rebase_anchor is not None else aligned.index.min()
    if anchor < aligned.index.min() or anchor > aligned.index.max():
        raise ValueError(f"Rebase anchor {anchor:%Y-%m-%d} is outside the charted "
                         f"window [{aligned.index.min():%Y-%m-%d}, {aligned.index.max():%Y-%m-%d}].")

    # Rebase only the level series; yields stay in raw percent for their own panel.
    rebased = pd.DataFrame({
        col: (aligned[col] if col in YIELD_LABELS else _rebase_to_anchor(aligned[col], anchor))
        for col in aligned.columns
    })
    rebased.attrs["anchor"] = anchor
    rebased.attrs["tickers"] = basket_tickers(frame)
    # Preserve aligned source levels for inspection alongside the indexed frame.
    rebased.attrs["raw"] = aligned
    # Raw S&P-÷-liquidity ratios for the third panel, keyed by measure. Rebased to
    # the configured anchor at render time for both HTML and PNG.
    rebased.attrs["ratio_raw"] = compute_ratios(aligned)
    return rebased


def render_png(rebased: pd.DataFrame, out_path: Path) -> None:
    anchor = rebased.attrs["anchor"]
    tickers = rebased.attrs.get("tickers", [])
    level_cols, yield_cols = _split_columns(rebased.columns)

    matplotlib_style()
    # Three panels on a shared x-axis: rebased levels on top, raw Treasury yields in
    # the middle, and S&P-÷-liquidity ratios at the bottom. The top panel is tallest
    # (it carries the aggregate + M2 + MMF + S&P lines).
    fig, (ax_lvl, ax_yld, ax_ratio) = plt.subplots(
        3, 1, figsize=(14, 12), dpi=140, sharex=True,
        gridspec_kw={"height_ratios": [3, 2, 1.6], "hspace": 0.10},
    )

    for col in level_cols:
        ax_lvl.plot(rebased.index, rebased[col], label=compact_label(col), color=SERIES_COLORS[col],
                    linewidth=2.4 if col.startswith("Aggregate") else 1.7,
                    marker="o", markersize=4)
    ax_lvl.axhline(100.0, color="#8a989b", linewidth=0.8, linestyle="--", alpha=0.7, zorder=1)
    ax_lvl.set_ylabel(f"Index (100 = level at {anchor:%Y-%m-%d})", fontsize=10)
    ax_lvl.legend(loc="upper left", frameon=False, fontsize=9)

    for col in yield_cols:
        ax_yld.plot(rebased.index, rebased[col], label=compact_label(col), color=SERIES_COLORS[col],
                    linewidth=1.7, marker="o", markersize=4)

    # Bottom panel: S&P 500 ÷ liquidity, rebased to 100. The static PNG shows every
    # official denominator at once (the interactive chart offers a picker instead).
    ratio_raw = rebased.attrs.get("ratio_raw", {})
    for m in LIQUIDITY_MEASURES:
        series = ratio_raw.get(m["key"])
        if series is None:
            continue
        ax_ratio.plot(series.index, _rebase_to_anchor(series, anchor),
                      label=f"S&P 500 ÷ {m['name']}", color=m["color"],
                      linewidth=1.9, marker="o", markersize=4)
    ax_ratio.axhline(100.0, color="#8a989b", linewidth=0.8, linestyle="--", alpha=0.7, zorder=1)
    ax_ratio.set_ylabel(f"Index (100 = {anchor:%Y-%m-%d})", fontsize=10)
    if ratio_raw:
        ax_ratio.legend(loc="upper left", frameon=False, fontsize=9)

    # Shade inverted-curve periods as a band across all three panels.
    spans = inversion_spans(rebased)
    for i, (x0, x1) in enumerate(spans):
        for ax in (ax_lvl, ax_yld, ax_ratio):
            ax.axvspan(x0, x1, color=INVERSION_COLOR, alpha=0.09, zorder=0,
                       label=INVERSION_LABEL if (i == 0 and ax is ax_yld) else None)

    ax_yld.set_ylabel("Treasury yield (%)", fontsize=10)
    ax_yld.legend(loc="upper left", frameon=False, fontsize=9, ncol=2)
    ax_ratio.set_xlabel("Quarter-end")
    ax_ratio.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax_ratio.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    basket = f"Aggregates sum {len(tickers)} companies: {', '.join(tickers)}" if tickers else ""
    fig.suptitle(
        "Free cash flow & money-market-fund cash vs. M2, the S&P 500, and the Treasury curve\n"
        f"Levels rebased to 100 at {anchor:%Y-%m-%d}; Treasury yields shown as raw %"
        + (f"  ·  {basket}" if basket else ""),
        fontsize=12,
    )
    fig.autofmt_xdate()
    fig.subplots_adjust(left=0.06, right=0.98, top=0.90, bottom=0.13)

    png_sources(fig, data_sources(), data_pulled_date())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


LEVEL_UNITS = {
    "Aggregate FCF (basket sum)": "USD",
    "Aggregate cash & equivalents (basket sum)": "USD",
    "Money-market-fund assets (FRED: MMMFFAQ027S)": "million USD",
    "M2 money supply (FRED: M2SL)": "billion USD",
    SP500_LABEL: "pts",
}


def indexed_series(values, original, *, unit, decimals=2, **style):
    series = series_data(values, **style)
    series['originalUnit'] = unit
    series['originalDecimals'] = decimals
    for point, raw_point in zip(
        series['points'], series_data(original.reindex(values.index), **style)['points'], strict=True
    ):
        point['original'] = raw_point['value']
    return series


def chart_payload(rebased: pd.DataFrame) -> dict:
    anchor = rebased.attrs['anchor']
    levels, yields = _split_columns(rebased.columns)
    start, end = rebased.index.min(), rebased.index.max()
    original = rebased.attrs['raw']
    panels = [
        {'id': 'levels', 'title': 'Corporate cash & the macro backdrop', 'unit': 'index',
         'axis': f'Index (100 = {anchor:%Y-%m-%d})', 'reference': 100,
         'series': [indexed_series(rebased[col], original[col], unit=LEVEL_UNITS[col],
                                   name=compact_label(col), color=SERIES_COLORS[col], key=col)
                    for col in levels]},
        {'id': 'yields', 'title': 'Treasury yields', 'unit': '%', 'axis': 'Treasury yield (%)', 'zero': True,
         'series': [series_data(rebased[col], name=compact_label(col), color=SERIES_COLORS[col], key=col)
                    for col in yields]},
    ]
    choices = []
    for measure in LIQUIDITY_MEASURES:
        raw = rebased.attrs.get('ratio_raw', {}).get(measure['key'])
        if raw is None:
            continue
        values = _rebase_to_anchor(raw, anchor).loc[start:end]
        choices.append({'key': measure['key'], 'label': measure['name'],
                        'description': 'Pro: ' + measure['pro'] + '. Limitation: ' + measure['con'] + '.',
                        'series': [indexed_series(values, raw, unit='pts per ' + LEVEL_UNITS[measure['column']],
                                                   decimals=6, name='S&P 500 ÷ ' + measure['name'],
                                                   color=measure['color'], key='ratio-' + measure['key'])]})
    if choices:
        panels.append({'id': 'ratio', 'title': 'Equities relative to liquidity', 'unit': 'index',
                       'axis': f'Index (100 = {anchor:%Y-%m-%d})', 'reference': 100,
                       'choices': choices, 'defaultChoice': DEFAULT_MEASURE_KEY})
    return {'domain': [start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')],
            'anchor': anchor.strftime('%Y-%m-%d'), 'panels': panels,
            'bands': [{'from': left.strftime('%Y-%m-%d'), 'to': right.strftime('%Y-%m-%d'),
                       'label': INVERSION_LABEL, 'color': INVERSION_COLOR}
                      for left, right in inversion_spans(rebased)]}


def render_html(rebased: pd.DataFrame, out_path: Path) -> None:
    """Native SVG panels share one calendar axis, with on-plot inspection."""
    anchor = rebased.attrs['anchor']
    tickers = rebased.attrs.get('tickers', [])
    basket = 'Basket: ' + ', '.join(tickers) + '.' if tickers else ''
    html = chart_page(chart_payload(rebased), title=PAGE_TITLE,
                      subtitle='Quarterly corporate cash, liquidity, equity prices and Treasury yields. ' + basket,
                      context=f'Levels and ratios indexed to 100 at {anchor:%Y-%m-%d}; yields are raw percentages. Shading marks 10Y < 2Y inversion.',
                      sources=data_sources(), pulled=data_pulled_date())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not out_path.exists() or out_path.read_text(encoding='utf-8') != html:
        out_path.write_text(html, encoding='utf-8')


def build_chart(out_path: Path, rebase_anchor: pd.Timestamp | None) -> None:
    rebased = build_rebased(rebase_anchor)
    if out_path.suffix.lower() in {".html", ".htm"}:
        render_html(rebased, out_path)
    else:
        render_png(rebased, out_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot free cash flow vs. M2, the S&P 500, and the Treasury curve, rebased to 100.",
    )
    parser.add_argument(
        "--rebase-date",
        default="",
        help="Anchor quarter; each series is rebased to its level at this quarter-end. "
             "Default: the first quarter of the charted window.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_DIR / "fcf-macro-indicators.html",
        help="Output path; .html renders the interactive chart, anything else a static PNG (default: %(default)s)",
    )
    parser.add_argument(
        "output_positional",
        nargs="?",
        type=Path,
        default=None,
        help="Optional output path; overrides -o/--output when provided.",
    )
    args = parser.parse_args()
    out = (args.output_positional or args.output).expanduser().resolve()
    anchor = pd.Timestamp(args.rebase_date) if args.rebase_date.strip() else None
    build_chart(out, anchor)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
