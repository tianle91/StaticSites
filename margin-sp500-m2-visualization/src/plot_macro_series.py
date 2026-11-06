#!/usr/bin/env python3
"""
Read the monthly source series from data/series.csv, rebase every series to 100
using a configurable anchor date, and plot with vertical markers for major
market events.

Renders a static PNG (matplotlib) or a responsive HTML chart (native SVG), picked from
the output file extension. Offline: refresh data/series.csv with `make data`.
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
PAGE_TITLE = "Margin Debt vs. the S&amp;P 500, M2, CPI &amp; PPI"



def data_pulled_date() -> str:
    return timeseries.data_pulled_date(PULLED_STAMP, SERIES_CSV)

START = pd.Timestamp("2000-01-01")

DEFAULT_REBASE = pd.Timestamp("2020-02-20")

# (event_date, label) — US-market-centric milestones; labels kept short for the legend box.
MARKET_EVENTS: list[tuple[date, str]] = [
    (date(2000, 3, 24), "Dot-com peak"),
    (date(2001, 9, 11), "9/11"),
    (date(2008, 9, 15), "Lehman"),
    (date(2011, 8, 5), "US downgrade"),
    (date(2020, 2, 19), "Pre-COVID peak"),
    (date(2020, 3, 23), "COVID low"),
    (date(2022, 1, 3), "2022 drawdown"),
    (date(2022, 6, 13), "Fed 75 bp"),
    (date(2023, 3, 10), "SVB"),
]


def _month_end(ts: pd.Timestamp) -> pd.Timestamp:
    return timeseries.period_end(ts, "M")


def _baseline_level(s: pd.Series, anchor: pd.Timestamp) -> float:
    return timeseries.baseline_level(s, anchor, frequency="M")


def _rebase_to_anchor(s: pd.Series, anchor: pd.Timestamp) -> pd.Series:
    return timeseries.rebase(s, anchor, frequency="M")


def load_series() -> pd.DataFrame:
    return timeseries.load_series(SERIES_CSV)


SERIES_COLORS = {
    "M2 (FRED: M2SL)": "#466aa0",
    "CPI (FRED: CPIAUCSL)": "#806493",
    "PPI (FRED: PPIACO)": "#70868b",
    "Margin debit (FINRA, $m)": "#aa5633",
    "S&P 500 (^GSPC, month-end)": "#116965",
}

# Data sources, shown on the rendered chart itself so a reader who only has the
# image/page can see (and follow) where each series came from. (label, url).
DATA_SOURCES: list[tuple[str, str]] = [
    ("FINRA margin statistics", "https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics"),
    ("FRED M2 (M2SL)", "https://fred.stlouisfed.org/series/M2SL"),
    ("FRED CPI (CPIAUCSL)", "https://fred.stlouisfed.org/series/CPIAUCSL"),
    ("FRED PPI (PPIACO)", "https://fred.stlouisfed.org/series/PPIACO"),
    ("S&P 500 via Yahoo Finance (^GSPC)", "https://finance.yahoo.com/quote/%5EGSPC"),
]


def build_rebased(rebase_anchor: pd.Timestamp) -> pd.DataFrame:
    """Align the committed series on month-ends and rebase each to 100 at the anchor."""
    anchor = pd.Timestamp(rebase_anchor).normalize()
    anchor_me = _month_end(anchor)

    frame = load_series()
    end = frame.index.max()
    if anchor_me < START or anchor_me > end:
        raise ValueError(f"Rebase anchor month-end {anchor_me:%Y-%m-%d} is outside "
                         f"[{START.date()}, {end.date()}].")
    frame = frame.loc[(frame.index >= START) & (frame.index <= end)].dropna(how="all")

    aligned = frame.asfreq("ME")
    if aligned.empty:
        raise RuntimeError("No observations available for the chart.")

    for col in aligned.columns:
        _baseline_level(aligned[col], anchor)

    rebased = pd.DataFrame(
        {
            "M2 (FRED: M2SL)": _rebase_to_anchor(aligned["m2"], anchor),
            "CPI (FRED: CPIAUCSL)": _rebase_to_anchor(aligned["cpi"], anchor),
            "PPI (FRED: PPIACO)": _rebase_to_anchor(aligned["ppi"], anchor),
            "Margin debit (FINRA, $m)": _rebase_to_anchor(aligned["margin_debit"], anchor),
            "S&P 500 (^GSPC, month-end)": _rebase_to_anchor(aligned["sp500"], anchor),
        }
    )
    rebased.attrs["anchor"] = anchor
    rebased.attrs["anchor_month_end"] = anchor_me
    return rebased


def render_png(rebased: pd.DataFrame, out_path: Path) -> None:
    anchor = rebased.attrs["anchor"]
    anchor_me = rebased.attrs["anchor_month_end"]

    matplotlib_style()
    fig, ax = plt.subplots(figsize=(14, 8), dpi=140)

    for col in rebased.columns:
        ax.plot(rebased.index, rebased[col], label=compact_label(col), color=SERIES_COLORS[col], linewidth=1.8)

    y_min, y_max = rebased.min().min(), rebased.max().max()
    pad = (y_max - y_min) * 0.04
    span = y_max - y_min
    ax.set_ylim(y_min - pad, y_max + pad + span * 0.22)

    shown = 0
    for ev_date, label in MARKET_EVENTS:
        if not (rebased.index.min() <= pd.Timestamp(ev_date) <= rebased.index.max()):
            continue
        ax.axvline(pd.Timestamp(ev_date), color="#8a989b", linewidth=0.9, alpha=0.55, zorder=1)
        y_text = y_max + pad * 0.15 - span * 0.035 * (shown % 9)
        shown += 1
        ax.annotate(
            label,
            xy=(mdates.date2num(pd.Timestamp(ev_date)), y_text),
            xytext=(0, 0),
            textcoords="offset points",
            rotation=90,
            va="top",
            ha="right",
            fontsize=7,
            color="#596b71",
        )

    ax.set_title(
        "Margin, S&P 500, M2, CPI, and PPI (rebased to 100 using each series level on or before "
        f"{anchor_me:%Y-%m-%d}; anchor date {anchor:%Y-%m-%d})",
        fontsize=12,
        pad=12,
    )
    ax.set_ylabel(
        "Index (anchor = 100)",
        fontsize=10,
    )
    ax.set_xlabel("Month-end")
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0.07, 1, 1))

    # Attribute the data sources on the image itself (URLs can't be clickable in a
    # PNG, but a reader with only the picture can still see where the data is from).
    png_sources(fig, DATA_SOURCES, data_pulled_date())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def chart_payload(rebased: pd.DataFrame) -> dict:
    start, end = rebased.index.min(), rebased.index.max()
    return {
        'domain': [start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')],
        'markers': False,
        'panels': [{'id': 'levels', 'title': 'Indexed market series',
                    'unit': 'index', 'axis': 'Index (anchor = 100)', 'reference': 100,
                    'series': [series_data(rebased[col], name=compact_label(col),
                                           color=SERIES_COLORS[col], key=col)
                               for col in rebased.columns]}],
        'events': [{'date': date.isoformat(), 'label': label} for date, label in MARKET_EVENTS
                   if start <= pd.Timestamp(date) <= end],
    }


def render_html(rebased: pd.DataFrame, out_path: Path) -> None:
    """Responsive native SVG page, built entirely from the committed series."""
    anchor_me = rebased.attrs['anchor_month_end']
    html = chart_page(chart_payload(rebased), title=PAGE_TITLE,
                      subtitle='Margin debt, equity prices, money supply and inflation.',
                      context=f'Monthly observations · Missing values stay empty · Index 100 uses each series on or before {anchor_me:%Y-%m-%d}.',
                      sources=DATA_SOURCES, pulled=data_pulled_date())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not out_path.exists() or out_path.read_text(encoding='utf-8') != html:
        out_path.write_text(html, encoding='utf-8')


def build_chart(out_path: Path, rebase_anchor: pd.Timestamp) -> None:
    rebased = build_rebased(rebase_anchor)
    if out_path.suffix.lower() in {".html", ".htm"}:
        render_html(rebased, out_path)
    else:
        render_png(rebased, out_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot margin debt, S&P 500, M2, CPI, and PPI rebased to a configurable anchor date.",
    )
    parser.add_argument(
        "--rebase-date",
        default=DEFAULT_REBASE.strftime("%Y-%m-%d"),
        help="Calendar anchor; each series uses the last non-null month-end on or before this month’s month-end (default: %(default)s).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_DIR / "margin_sp500_m2_2000.png",
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
    anchor = pd.Timestamp(args.rebase_date)
    build_chart(out, anchor)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
