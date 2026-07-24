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
member reports FCF. Renders a static PNG (matplotlib) or a zoomable HTML chart
(plotly), picked from the output file extension. Offline: refresh data/series.csv
with `make data`.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
SERIES_CSV = ROOT / "data" / "series.csv"
PULLED_STAMP = ROOT / "data" / "generated_at.txt"  # written by fetch_data.py

# Browser tab / bookmark title for the HTML chart. Plotly's to_html() emits a
# document with an empty <head> and no <title>, so we inject this one.
PAGE_TITLE = "Free Cash Flow vs. M2, the S&amp;P 500 &amp; the Treasury Curve"

# Display label -> CSV column. Order controls legend/plot order. The aggregate
# FCF line is derived from the fcf_* columns (see build_rebased); the rest map
# straight through. Yields run light->dark from the short end to the long end.
SERIES_COLORS = {
    "Aggregate FCF (basket sum)": "#d62728",
    "Aggregate cash & equivalents (basket sum)": "#ff7f0e",
    "Money-market-fund assets (FRED: MMMFFAQ027S)": "#17becf",
    "M2 money supply (FRED: M2SL)": "#1f77b4",
    "S&P 500 (^GSPC)": "#2ca02c",
    "3M Treasury yield (FRED: DGS3MO)": "#c5b0d5",
    "2Y Treasury yield (FRED: DGS2)": "#9467bd",
    "10Y Treasury yield (FRED: DGS10)": "#6a3d9a",
    "30Y Treasury yield (FRED: DGS30)": "#3f007d",
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
        "color": "#1f77b4",
        "pro": "broadest money measure, decades of history, short (~4-week) lag",
        "con": "broad and slow; includes retail savings that don't move prices; "
               "weak short-horizon link to equities; 2020 definitional break",
    },
    {
        "key": "mmf",
        "name": "Money-market-fund assets",
        "column": "Money-market-fund assets (FRED: MMMFFAQ027S)",
        "color": "#17becf",
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


def _ratio_panel_title(key: str) -> str:
    """Third-panel title for a chosen denominator, with its pro/con as subtext. The
    interactive picker swaps this; the anchor date lives on the y-axis, not here, so
    re-anchoring never has to rewrite it."""
    m = _measure(key)
    return (f"S&P 500 ÷ {m['name']} (rebased to 100)"
            f"<br><sup>Pro: {m['pro']}  ·  Con: {m['con']}</sup>")


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
INVERSION_COLOR = "#d62728"


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
    """The date the committed data was pulled (stamped by `make data`), falling
    back to the CSV's own modification date so every chart carries a data date."""
    if PULLED_STAMP.exists():
        stamp = PULLED_STAMP.read_text(encoding="utf-8").strip()
        if stamp:
            return stamp[:10]
    if SERIES_CSV.exists():
        return date.fromtimestamp(SERIES_CSV.stat().st_mtime).isoformat()
    return ""


def _quarter_end(ts: pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(ts).normalize()
    return ts.to_period("Q").to_timestamp(how="end").normalize()


def _baseline_level(s: pd.Series, anchor: pd.Timestamp) -> float:
    """Last non-null observation on or before the quarter-end of the anchor."""
    anchor_qe = _quarter_end(anchor)
    s = s.dropna().sort_index()
    if s.empty:
        raise ValueError("Series is empty after dropping NaNs.")
    head = s.loc[:anchor_qe]
    if head.empty:
        raise ValueError(f"No observations on or before {anchor_qe:%Y-%m-%d}.")
    return float(head.iloc[-1])


def _rebase_to_anchor(s: pd.Series, anchor: pd.Timestamp) -> pd.Series:
    base = _baseline_level(s, anchor)
    if base == 0:
        raise ValueError("Baseline level is zero; cannot rebase.")
    return 100.0 * s / base


def load_series() -> pd.DataFrame:
    """Load the committed quarterly grid written by fetch_data.py."""
    if not SERIES_CSV.exists():
        raise SystemExit(f"{SERIES_CSV} is missing - run `make data` to fetch it.")
    return pd.read_csv(SERIES_CSV, parse_dates=["date"], index_col="date").sort_index()


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
    # Raw (un-rebased) aligned values, so the HTML chart can re-rebase the level
    # panel client-side when the viewer picks a different anchor quarter.
    rebased.attrs["raw"] = aligned
    # Raw S&P-÷-liquidity ratios for the third panel, keyed by measure. Rebased to
    # the anchor at render time and re-rebased client-side alongside the levels.
    rebased.attrs["ratio_raw"] = compute_ratios(aligned)
    return rebased


def render_png(rebased: pd.DataFrame, out_path: Path) -> None:
    anchor = rebased.attrs["anchor"]
    tickers = rebased.attrs.get("tickers", [])
    level_cols, yield_cols = _split_columns(rebased.columns)

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("ggplot")
    # Three panels on a shared x-axis: rebased levels on top, raw Treasury yields in
    # the middle, and S&P-÷-liquidity ratios at the bottom. The top panel is tallest
    # (it carries the aggregate + M2 + MMF + S&P lines).
    fig, (ax_lvl, ax_yld, ax_ratio) = plt.subplots(
        3, 1, figsize=(14, 12), dpi=140, sharex=True,
        gridspec_kw={"height_ratios": [3, 2, 1.6], "hspace": 0.10},
    )

    for col in level_cols:
        ax_lvl.plot(rebased.index, rebased[col], label=col, color=SERIES_COLORS[col],
                    linewidth=2.4 if col.startswith("Aggregate") else 1.7,
                    marker="o", markersize=4)
    ax_lvl.axhline(100.0, color="#999999", linewidth=0.8, linestyle="--", alpha=0.7, zorder=1)
    ax_lvl.set_ylabel(f"Index (100 = level at {anchor:%Y-%m-%d})", fontsize=10)
    ax_lvl.legend(loc="upper left", frameon=True, fontsize=9)

    for col in yield_cols:
        ax_yld.plot(rebased.index, rebased[col], label=col, color=SERIES_COLORS[col],
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
    ax_ratio.axhline(100.0, color="#999999", linewidth=0.8, linestyle="--", alpha=0.7, zorder=1)
    ax_ratio.set_ylabel(f"Index (100 = {anchor:%Y-%m-%d})", fontsize=10)
    if ratio_raw:
        ax_ratio.legend(loc="upper left", frameon=True, fontsize=9)

    # Shade inverted-curve periods as a band across all three panels.
    spans = inversion_spans(rebased)
    for i, (x0, x1) in enumerate(spans):
        for ax in (ax_lvl, ax_yld, ax_ratio):
            ax.axvspan(x0, x1, color=INVERSION_COLOR, alpha=0.09, zorder=0,
                       label=INVERSION_LABEL if (i == 0 and ax is ax_yld) else None)

    ax_yld.set_ylabel("Treasury yield (%)", fontsize=10)
    ax_yld.legend(loc="upper left", frameon=True, fontsize=9, ncol=2)
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

    pulled = data_pulled_date()
    fig.text(
        0.5, 0.005,
        (f"Data pulled {pulled} · " if pulled else "")
        + "Data sources: " + " · ".join(f"{label} ({url})" for label, url in data_sources()),
        ha="center", va="bottom", fontsize=6.0, color="#666666",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def render_html(rebased: pd.DataFrame, out_path: Path) -> None:
    """Zoomable/pannable plotly chart: drag to zoom, double-click to reset. Three
    panels share one x-axis -- rebased levels on top, raw Treasury yields in the
    middle, and S&P-÷-liquidity ratios below (denominator chosen via a picker)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    anchor = rebased.attrs["anchor"]
    tickers = rebased.attrs.get("tickers", [])
    level_cols, yield_cols = _split_columns(rebased.columns)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
        row_heights=[0.46, 0.30, 0.24],
        subplot_titles=(
            f"Levels rebased to 100 at {anchor:%Y-%m-%d}",
            "Treasury yields (%)",
            _ratio_panel_title(DEFAULT_MEASURE_KEY),
        ),
    )
    for col in level_cols:
        fig.add_trace(
            go.Scatter(
                x=rebased.index, y=rebased[col], name=col, legendgroup="levels",
                mode="lines+markers",
                line=dict(color=SERIES_COLORS[col], width=2.6 if col.startswith("Aggregate") else 1.7),
                marker=dict(size=5),
                hovertemplate="%{y:.1f}<extra>" + col + "</extra>",
            ),
            row=1, col=1,
        )
    for col in yield_cols:
        fig.add_trace(
            go.Scatter(
                x=rebased.index, y=rebased[col], name=col, legendgroup="yields",
                mode="lines+markers",
                line=dict(color=SERIES_COLORS[col], width=1.7),
                marker=dict(size=5),
                hovertemplate="%{y:.2f}%<extra>" + col + "</extra>",
            ),
            row=2, col=1,
        )

    fig.add_hline(y=100.0, line=dict(color="#999999", width=0.8, dash="dash"), row=1, col=1)

    # Shade inverted-curve periods as a full-height band spanning both panels, plus
    # one dummy trace so the shading gets a legend entry.
    spans = inversion_spans(rebased)
    for x0, x1 in spans:
        fig.add_vrect(x0=x0, x1=x1, fillcolor=INVERSION_COLOR, opacity=0.09,
                      line_width=0, layer="below")
    if spans:
        fig.add_trace(
            go.Scatter(
                x=[None], y=[None], mode="markers", name=INVERSION_LABEL,
                legendgroup="yields",
                marker=dict(size=12, symbol="square",
                            color="rgba(214,39,40,0.28)", line=dict(width=0)),
                hoverinfo="skip",
            ),
            row=2, col=1,
        )

    # Third panel: S&P 500 ÷ liquidity, one trace per official denominator, rebased
    # to 100 at the anchor. Only the default measure starts visible; the picker
    # (updatemenu below) toggles the others and swaps the pro/con panel title. Added
    # after the level/yield/inversion traces so their indices stay stable for the
    # re-rebase JS; the ratio traces re-rebase on click too (see _rebase_script).
    ratio_raw = rebased.attrs.get("ratio_raw", {})
    ratio_traces: list[tuple[str, int]] = []  # (measure key, trace index)
    for m in LIQUIDITY_MEASURES:
        series = ratio_raw.get(m["key"])
        if series is None:
            continue
        ratio_traces.append((m["key"], len(fig.data)))
        fig.add_trace(
            go.Scatter(
                x=series.index, y=_rebase_to_anchor(series, anchor),
                name=f"S&P 500 ÷ {m['name']}", legendgroup="ratio",
                mode="lines+markers", visible=(m["key"] == DEFAULT_MEASURE_KEY),
                line=dict(color=m["color"], width=2.0), marker=dict(size=5),
                hovertemplate="%{y:.1f}<extra>S&P 500 ÷ " + m["name"] + "</extra>",
            ),
            row=3, col=1,
        )
    if ratio_traces:
        fig.add_hline(y=100.0, line=dict(color="#999999", width=0.8, dash="dash"), row=3, col=1)

    # Movable vertical marker at the rebase anchor, spanning all panels (xref to the
    # top x-axis, yref to paper). The viewer clicks the chart to move it and re-rebase
    # the level + ratio panels (see _rebase_script); drawn here so the initial anchor
    # is marked without JS. Added last so it is the final shape -- the JS targets it
    # by index (anchor_shape_idx) to move it on click.
    fig.add_shape(type="line", x0=anchor, x1=anchor, xref="x", yref="paper",
                  y0=0, y1=1, line=dict(color="#111111", width=1.5, dash="dot"),
                  layer="above")
    anchor_shape_idx = len(fig.layout.shapes) - 1

    # Denominator picker for the ratio panel: each button shows only that measure's
    # ratio trace and swaps the panel title (subplot title = annotations[2]) to its
    # pro/con. method="update" carries [trace visibility, layout change, target trace
    # indices] so it touches only the ratio traces.
    ratio_idx = [ti for _, ti in ratio_traces]
    measure_buttons = [
        dict(
            label=_measure(key)["name"],
            method="update",
            args=[
                {"visible": [k == key for k, _ in ratio_traces]},
                {"annotations[2].text": _ratio_panel_title(key)},
                ratio_idx,
            ],
        )
        for key, _ in ratio_traces
    ]

    basket = (f"Aggregates sum {len(tickers)} companies: {', '.join(tickers)}"
              if tickers else "")
    fig.update_layout(
        template="plotly_white",
        title=dict(
            text=("Free cash flow & money-market-fund cash vs. M2, the S&P 500, and the Treasury curve"
                  + (f"<br><sup>{basket}</sup>" if basket else "")),
            font=dict(size=14),
        ),
        hovermode="x unified",
        dragmode="zoom",
        legend=dict(bgcolor="rgba(255,255,255,0.8)", bordercolor="#cccccc", borderwidth=1,
                    groupclick="toggleitem"),
        margin=dict(l=70, r=30, t=110, b=60),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=1.0,
                y=1.14,
                xanchor="right",
                showactive=True,
                buttons=[
                    dict(label="Levels: Linear", method="relayout", args=[{"yaxis.type": "linear"}]),
                    dict(label="Levels: Log", method="relayout", args=[{"yaxis.type": "log"}]),
                ],
            ),
            # Ratio-panel denominator picker, parked at the top-left above the chart.
            # Only shown when there is more than one official measure to choose from.
            *([dict(
                type="dropdown",
                direction="down",
                x=0.0,
                y=1.14,
                xanchor="left",
                yanchor="top",
                showactive=True,
                active=[k for k, _ in ratio_traces].index(DEFAULT_MEASURE_KEY),
                buttons=measure_buttons,
                bgcolor="rgba(255,255,255,0.9)",
                bordercolor="#cccccc",
                pad={"t": 2, "b": 2, "l": 4, "r": 4},
            )] if len(measure_buttons) > 1 else []),
        ],
    )
    # Label for the denominator picker. Appended (not passed to update_layout, which
    # would overwrite the subplot-title annotations the picker/JS reference by index).
    if len(measure_buttons) > 1:
        fig.add_annotation(
            text="Ratio denominator ▾", x=0.0, y=1.155, xref="paper", yref="paper",
            xanchor="left", yanchor="bottom", showarrow=False,
            font=dict(size=11, color="#666666"),
        )
    # Spikes on every panel; rangeslider/selector + x-axis title on the shared bottom
    # (ratio) x-axis.
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1, row=1, col=1)
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1, row=2, col=1)
    fig.update_xaxes(
        title_text="Quarter-end",
        showspikes=True,
        spikemode="across",
        spikethickness=1,
        rangeslider=dict(visible=True, thickness=0.05),
        rangeselector=dict(
            buttons=[
                dict(count=3, label="3y", step="year", stepmode="backward"),
                dict(count=5, label="5y", step="year", stepmode="backward"),
                dict(count=10, label="10y", step="year", stepmode="backward"),
                dict(step="all", label="All"),
            ]
        ),
        row=3, col=1,
    )
    fig.update_yaxes(title_text=f"Index (100 @ {anchor:%Y-%m-%d})", fixedrange=False,
                     showspikes=False, row=1, col=1)
    fig.update_yaxes(title_text="Yield (%)", fixedrange=False, showspikes=False, row=2, col=1)
    fig.update_yaxes(title_text=f"Index (100 @ {anchor:%Y-%m-%d})", fixedrange=False,
                     showspikes=False, row=3, col=1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    div_id = "fcf-chart"
    html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        div_id=div_id,
        config={"scrollZoom": True, "displaylogo": False, "responsive": True},
    )
    html = html.replace("<head>", "<head><title>" + PAGE_TITLE + "</title>", 1)
    html = html.replace("<body>", "<body>" + _rebase_control(rebased), 1)
    links = " · ".join(
        f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'
        for label, url in data_sources()
    )
    pulled = data_pulled_date()
    pulled_html = f"Data pulled {pulled} &middot; " if pulled else ""
    footer = (
        '<footer style="font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;'
        'font-size:12px;color:#666;text-align:center;padding:8px 16px 16px">'
        + pulled_html + "<strong>Data sources:</strong> " + links + "</footer>"
    )
    html = html.replace(
        "</body>",
        footer + _rebase_script(rebased, div_id, anchor_shape_idx, ratio_traces) + "</body>", 1)
    out_path.write_text(html, encoding="utf-8")


def _rebase_control(rebased: pd.DataFrame) -> str:
    """Hint text above the chart. Re-anchoring is done by clicking the chart (see
    _rebase_script); the current anchor is shown here and updated live."""
    anchor = rebased.attrs["anchor"]
    return (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;'
        'font-size:13px;color:#333;text-align:center;padding:10px 16px 0">'
        "\U0001f4cd <strong>Click the chart</strong> to rebase the top panel to that "
        'quarter &mdash; anchor: <span id="rebase-anchor-label" '
        f'style="font-variant-numeric:tabular-nums">{anchor:%Y-%m-%d}</span></div>'
    )


def _rebase_script(rebased: pd.DataFrame, div_id: str, anchor_shape_idx: int,
                   ratio_traces: list[tuple[str, int]]) -> str:
    """JS that re-rebases the level AND ratio traces when the viewer clicks the chart,
    entirely client-side (no rebuild): index i = 100 * raw[i] / raw[anchor]. The
    click x is snapped to the nearest quarter. Level traces are added first, so
    their indices are 0..len(level_cols)-1; the yield/inversion traces are left
    untouched; the ratio traces carry their own explicit indices (both denominators
    re-rebase, visible or not, so switching the picker after a re-anchor still lines
    up). The anchor marker line (shape `anchor_shape_idx`), the level + ratio y-axis
    titles, the levels panel title, and the hint label all follow the new anchor. The
    ratio panel title is left alone -- it holds the denominator's pro/con, not a date."""
    raw = rebased.attrs["raw"]
    ratio_raw = rebased.attrs.get("ratio_raw", {})
    level_cols, _ = _split_columns(rebased.columns)
    payload = {
        "dates": [f"{d:%Y-%m-%d}" for d in raw.index],
        "labels": level_cols,
        "raw": {c: [float(v) for v in raw[c]] for c in level_cols},
        "idx": list(range(len(level_cols))),
        "shape": anchor_shape_idx,
        "ratio": [{"idx": ti, "raw": [float(v) for v in ratio_raw[key]]}
                  for key, ti in ratio_traces if key in ratio_raw],
    }
    return (
        '<script type="text/javascript">(function(){'
        f"var D={json.dumps(payload)};"
        f'var gd=document.getElementById("{div_id}");'
        "if(!gd)return;"
        "var lbl=document.getElementById(\"rebase-anchor-label\");"
        "var times=D.dates.map(function(s){return new Date(s).getTime();});"
        "function nearest(x){"  # x may be an ISO string or epoch ms
        "var t=(typeof x===\"string\")?new Date(x).getTime():+x;"
        "var bi=0,bd=Infinity;"
        "for(var i=0;i<times.length;i++){var d=Math.abs(times[i]-t);if(d<bd){bd=d;bi=i;}}"
        "return bi;}"
        "function reb(vals,b){return vals.map(function(v){return b?100*v/b:null;});}"
        "function rebase(ai){"
        "var iso=D.dates[ai];"
        "var ys=D.labels.map(function(l){var r=D.raw[l];return reb(r,r[ai]);});"
        "Plotly.restyle(gd,{y:ys},D.idx);"
        "if(D.ratio.length){"
        "var rys=D.ratio.map(function(o){return reb(o.raw,o.raw[ai]);});"
        "Plotly.restyle(gd,{y:rys},D.ratio.map(function(o){return o.idx;}));}"
        "var rl={\"yaxis.title.text\":\"Index (100 @ \"+iso+\")\","
        "\"yaxis3.title.text\":\"Index (100 @ \"+iso+\")\","
        "\"annotations[0].text\":\"Levels rebased to 100 at \"+iso};"
        "rl[\"shapes[\"+D.shape+\"].x0\"]=iso;rl[\"shapes[\"+D.shape+\"].x1\"]=iso;"
        "Plotly.relayout(gd,rl);"
        "if(lbl)lbl.textContent=iso;}"
        "gd.on(\"plotly_click\",function(ev){"
        "if(!ev||!ev.points||!ev.points.length)return;"
        "rebase(nearest(ev.points[0].x));});"
        "gd.style.cursor=\"pointer\";"
        "})();</script>"
    )


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
    anchor = pd.Timestamp(args.rebase_date) if args.rebase_date.strip() else None
    build_chart(out, anchor)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
