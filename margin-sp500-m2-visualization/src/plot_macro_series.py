#!/usr/bin/env python3
"""
Download FINRA margin debit balances, FRED M2 / CPI / PPI, and S&P 500 levels,
align on a monthly grid from 2000 onward, rebase every series to 100 using a
configurable anchor date, and plot with vertical markers for major market events.

Renders a static PNG (matplotlib) or a zoomable HTML chart (plotly), picked from
the output file extension.
"""

from __future__ import annotations

import argparse
import io
from datetime import date
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"

FINRA_MARGIN_XLSX = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"

START = pd.Timestamp("2000-01-01")
# Use "today" in the execution environment (authoritative for the agent run).
END = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)

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
    ts = pd.Timestamp(ts).normalize()
    return ts.to_period("M").to_timestamp(how="end").normalize()


def _baseline_level(s: pd.Series, anchor: pd.Timestamp) -> float:
    """Last non-null observation on or before the month-end of the anchor month."""
    anchor_me = _month_end(anchor)
    s = s.dropna().sort_index()
    if s.empty:
        raise ValueError("Series is empty after dropping NaNs.")
    head = s.loc[:anchor_me]
    if head.empty:
        raise ValueError(f"No observations on or before {anchor_me:%Y-%m-%d}.")
    return float(head.iloc[-1])


def _rebase_to_anchor(s: pd.Series, anchor: pd.Timestamp) -> pd.Series:
    base = _baseline_level(s, anchor)
    if base == 0:
        raise ValueError("Baseline level is zero; cannot rebase.")
    return 100.0 * s / base


def _fetch_fred_monthly(series_id: str) -> pd.Series:
    r = requests.get(FRED_CSV.format(series=series_id), timeout=120)
    r.raise_for_status()
    df = pd.read_csv(io.BytesIO(r.content), parse_dates=["observation_date"])
    if series_id not in df.columns:
        raise KeyError(f"Column {series_id} missing from FRED CSV response.")
    s = df.set_index("observation_date")[series_id].sort_index()
    s = s.loc[(s.index >= START) & (s.index <= END)]
    # FRED uses month-beginning stamps; treat as month period end for alignment.
    s.index = s.index.to_period("M").to_timestamp(how="end").normalize()
    return s.astype(float)


def _fetch_margin_debit() -> pd.Series:
    r = requests.get(FINRA_MARGIN_XLSX, timeout=120)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), engine="openpyxl")
    ym = df.columns[0]
    debit_col = [c for c in df.columns if "Debit" in str(c)][0]
    raw = df[[ym, debit_col]].dropna()
    ts = pd.to_datetime(raw[ym].astype(str) + "-01", errors="coerce")
    s = pd.Series(raw[debit_col].astype(float).values, index=ts)
    s = s.groupby(s.index).last().sort_index()
    s.index = s.index.to_period("M").to_timestamp(how="end").normalize()
    s = s.loc[(s.index >= START) & (s.index <= END)]
    return s


def _fetch_sp500_monthly() -> pd.Series:
    tkr = yf.Ticker("^GSPC")
    hist = tkr.history(start=START, end=END, auto_adjust=False, actions=False)
    if hist.empty:
        raise RuntimeError("No S&P 500 data returned from Yahoo Finance (^GSPC).")
    px = hist["Close"].sort_index()
    if isinstance(px.index, pd.DatetimeIndex) and px.index.tz is not None:
        px.index = pd.to_datetime(px.index.date)
    monthly = px.resample("ME").last()
    monthly.index = monthly.index.normalize()
    return monthly.astype(float)


SERIES_COLORS = {
    "M2 (FRED: M2SL)": "#1f77b4",
    "CPI (FRED: CPIAUCSL)": "#ff7f0e",
    "PPI (FRED: PPIACO)": "#9467bd",
    "Margin debit (FINRA, $m)": "#d62728",
    "S&P 500 (^GSPC, month-end)": "#2ca02c",
}


def build_rebased(rebase_anchor: pd.Timestamp) -> pd.DataFrame:
    """Fetch every series, align on month-ends, and rebase each to 100 at the anchor."""
    anchor = pd.Timestamp(rebase_anchor).normalize()
    anchor_me = _month_end(anchor)
    if anchor_me < START or anchor_me > END:
        raise ValueError(f"Rebase anchor month-end {anchor_me:%Y-%m-%d} is outside [{START.date()}, {END.date()}].")

    m2 = _fetch_fred_monthly("M2SL")
    cpi = _fetch_fred_monthly("CPIAUCSL")
    ppi = _fetch_fred_monthly("PPIACO")
    margin = _fetch_margin_debit()
    spx = _fetch_sp500_monthly()

    frame = pd.DataFrame(
        {
            "m2": m2,
            "cpi": cpi,
            "ppi": ppi,
            "margin_debit": margin,
            "sp500": spx,
        }
    ).sort_index()
    frame = frame.loc[(frame.index >= START) & (frame.index <= END)]
    frame = frame.dropna(how="all")

    aligned = frame.ffill(limit=2).dropna()
    if aligned.empty:
        raise RuntimeError("No overlapping observations after alignment.")

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

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("ggplot")
    fig, ax = plt.subplots(figsize=(14, 8), dpi=140)

    for col in rebased.columns:
        ax.plot(rebased.index, rebased[col], label=col, color=SERIES_COLORS[col], linewidth=1.8)

    y_min, y_max = rebased.min().min(), rebased.max().max()
    pad = (y_max - y_min) * 0.04
    span = y_max - y_min
    ax.set_ylim(y_min - pad, y_max + pad + span * 0.22)

    shown = 0
    for ev_date, label in MARKET_EVENTS:
        if not (rebased.index.min() <= pd.Timestamp(ev_date) <= rebased.index.max()):
            continue
        ax.axvline(pd.Timestamp(ev_date), color="#7f7f7f", linewidth=0.9, alpha=0.55, zorder=1)
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
            color="#444444",
        )

    ax.set_title(
        "Margin, S&P 500, M2, CPI, and PPI (rebased to 100 using each series level on or before "
        f"{anchor_me:%Y-%m-%d}; anchor date {anchor:%Y-%m-%d})",
        fontsize=12,
        pad=12,
    )
    ax.set_ylabel(
        f"Index (100 = value on or before {_month_end(anchor):%Y-%m-%d}, by series)",
        fontsize=10,
    )
    ax.set_xlabel("Month-end")
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="upper left", frameon=True, fontsize=9)
    fig.autofmt_xdate()
    fig.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def render_html(rebased: pd.DataFrame, out_path: Path) -> None:
    """Zoomable/pannable plotly chart: drag to zoom, double-click to reset."""
    import plotly.graph_objects as go

    anchor = rebased.attrs["anchor"]
    anchor_me = rebased.attrs["anchor_month_end"]

    fig = go.Figure()
    for col in rebased.columns:
        fig.add_trace(
            go.Scatter(
                x=rebased.index,
                y=rebased[col],
                name=col,
                mode="lines",
                line=dict(color=SERIES_COLORS[col], width=1.8),
                hovertemplate="%{y:.1f}<extra>" + col + "</extra>",
            )
        )

    for ev_date, label in MARKET_EVENTS:
        ev = pd.Timestamp(ev_date)
        if not (rebased.index.min() <= ev <= rebased.index.max()):
            continue
        fig.add_vline(
            x=ev,
            line=dict(color="#7f7f7f", width=0.9, dash="dot"),
            annotation_text=label,
            annotation_position="top",
            annotation=dict(textangle=-90, font=dict(size=9, color="#444444"), yanchor="top"),
        )

    fig.update_layout(
        template="plotly_white",
        title=dict(
            text=(
                "Margin, S&P 500, M2, CPI, and PPI (rebased to 100 using each series level on or "
                f"before {anchor_me:%Y-%m-%d}; anchor date {anchor:%Y-%m-%d})"
            ),
            font=dict(size=14),
        ),
        hovermode="x unified",
        dragmode="zoom",
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)", bordercolor="#cccccc", borderwidth=1),
        margin=dict(l=70, r=30, t=110, b=60),
        # Linear/log toggle — log makes the pre-2020 range legible once zoomed out.
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=1.0,
                y=1.12,
                xanchor="right",
                showactive=True,
                buttons=[
                    dict(label="Linear", method="relayout", args=[{"yaxis.type": "linear"}]),
                    dict(label="Log", method="relayout", args=[{"yaxis.type": "log"}]),
                ],
            )
        ],
    )
    fig.update_xaxes(
        title_text="Month-end",
        showspikes=True,
        spikemode="across",
        spikethickness=1,
        rangeslider=dict(visible=True, thickness=0.06),
        rangeselector=dict(
            buttons=[
                dict(count=1, label="1y", step="year", stepmode="backward"),
                dict(count=5, label="5y", step="year", stepmode="backward"),
                dict(count=10, label="10y", step="year", stepmode="backward"),
                dict(step="all", label="All"),
            ]
        ),
    )
    fig.update_yaxes(
        title_text=f"Index (100 = value on or before {anchor_me:%Y-%m-%d}, by series)",
        fixedrange=False,
        showspikes=False,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        out_path,
        include_plotlyjs="cdn",
        full_html=True,
        config={"scrollZoom": True, "displaylogo": False, "responsive": True},
    )


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
        help="Output path; .html renders the zoomable chart, anything else a static PNG (default: %(default)s)",
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
