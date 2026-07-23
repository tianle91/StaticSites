#!/usr/bin/env python3
"""
Read the quarterly source series from data/series.csv, rebase every series to 100
using a configurable anchor quarter, and plot free cash flow against the macro
backdrop: M2 money supply, the S&P 500, and the 3M / 2Y / 10Y / 30Y Treasury
curve.

Free cash flow is the coarsest input (quarterly, and only a handful of quarters
deep from yfinance), so it sets both the grid and the charted window: the chart
spans the quarters in which every basket member reports FCF. Renders a static PNG
(matplotlib) or a zoomable HTML chart (plotly), picked from the output file
extension. Offline: refresh data/series.csv with `make data`.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
SERIES_CSV = ROOT / "data" / "series.csv"
PULLED_STAMP = ROOT / "data" / "generated_at.txt"  # written by fetch_data.py
# Sentinel marking data/series.csv as illustrative sample values rather than a
# real upstream pull. Present only when the committed CSV was generated without
# network access; `make data` (fetch_data.py) deletes it on a successful real
# fetch, so a real render is never watermarked. See data/README.md.
SAMPLE_SENTINEL = ROOT / "data" / "SAMPLE_DATA.txt"
SAMPLE_BANNER = "ILLUSTRATIVE SAMPLE DATA — not real; run `make data` to replace"

# Browser tab / bookmark title for the HTML chart. Plotly's to_html() emits a
# document with an empty <head> and no <title>, so we inject this one.
PAGE_TITLE = "Free Cash Flow vs. M2, the S&amp;P 500 &amp; the Treasury Curve"

# Display label -> CSV column. Order controls legend/plot order. The aggregate
# FCF line is derived from the fcf_* columns (see build_rebased); the rest map
# straight through. Yields run light->dark from the short end to the long end.
SERIES_COLORS = {
    "Aggregate FCF (yfinance, summed)": "#d62728",
    "M2 money supply (FRED: M2SL)": "#1f77b4",
    "S&P 500 (^GSPC)": "#2ca02c",
    "3M Treasury yield (FRED: DGS3MO)": "#c5b0d5",
    "2Y Treasury yield (FRED: DGS2)": "#9467bd",
    "10Y Treasury yield (FRED: DGS10)": "#6a3d9a",
    "30Y Treasury yield (FRED: DGS30)": "#3f007d",
}

# Display label -> CSV column for the straight-through (non-derived) series.
MACRO_COLUMNS = {
    "M2 money supply (FRED: M2SL)": "m2",
    "S&P 500 (^GSPC)": "sp500",
    "3M Treasury yield (FRED: DGS3MO)": "dgs3mo",
    "2Y Treasury yield (FRED: DGS2)": "dgs2",
    "10Y Treasury yield (FRED: DGS10)": "dgs10",
    "30Y Treasury yield (FRED: DGS30)": "dgs30",
}

# Data sources, shown on the rendered chart itself so a reader who only has the
# image/page can see (and follow) where each series came from. (label, url).
DATA_SOURCES: list[tuple[str, str]] = [
    ("Company cash-flow statements via Yahoo Finance", "https://finance.yahoo.com/quote/AAPL/cash-flow"),
    ("FRED M2 (M2SL)", "https://fred.stlouisfed.org/series/M2SL"),
    ("FRED 3M Treasury (DGS3MO)", "https://fred.stlouisfed.org/series/DGS3MO"),
    ("FRED 2Y Treasury (DGS2)", "https://fred.stlouisfed.org/series/DGS2"),
    ("FRED 10Y Treasury (DGS10)", "https://fred.stlouisfed.org/series/DGS10"),
    ("FRED 30Y Treasury (DGS30)", "https://fred.stlouisfed.org/series/DGS30"),
    ("S&P 500 via Yahoo Finance (^GSPC)", "https://finance.yahoo.com/quote/%5EGSPC"),
]


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


def is_sample_data() -> bool:
    """True when the committed series.csv is the labeled sample, not a real pull."""
    return SAMPLE_SENTINEL.exists()


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


def aggregate_fcf(frame: pd.DataFrame) -> pd.Series:
    """Sum per-company FCF into one series, restricted to quarters where *every*
    basket member reports, so the aggregate never jumps because of a company
    dropping in or out of the sample."""
    fcf_cols = [c for c in frame.columns if c.startswith("fcf_")]
    if not fcf_cols:
        raise SystemExit("No fcf_* columns in series.csv - run `make data`.")
    fcf = frame[fcf_cols].dropna(how="any")
    if fcf.empty:
        raise RuntimeError("No quarter has FCF for every basket member.")
    return fcf.sum(axis=1)


def build_rebased(rebase_anchor: pd.Timestamp | None) -> pd.DataFrame:
    """Align FCF + macro on the common quarterly window and rebase each to 100."""
    frame = load_series()
    fcf = aggregate_fcf(frame)

    # The charted window is the quarters where aggregate FCF exists; macro is
    # quarterly and complete, so intersect the two indices.
    window = fcf.index.intersection(frame.index)
    if window.empty:
        raise RuntimeError("No overlap between FCF and macro series.")

    data = {"Aggregate FCF (yfinance, summed)": fcf.loc[window]}
    for label, col in MACRO_COLUMNS.items():
        data[label] = frame[col].loc[window]
    aligned = pd.DataFrame(data).sort_index().dropna()
    if aligned.empty:
        raise RuntimeError("No overlapping observations after alignment.")

    anchor = _quarter_end(rebase_anchor) if rebase_anchor is not None else aligned.index.min()
    if anchor < aligned.index.min() or anchor > aligned.index.max():
        raise ValueError(f"Rebase anchor {anchor:%Y-%m-%d} is outside the charted "
                         f"window [{aligned.index.min():%Y-%m-%d}, {aligned.index.max():%Y-%m-%d}].")

    rebased = pd.DataFrame({col: _rebase_to_anchor(aligned[col], anchor) for col in aligned.columns})
    rebased.attrs["anchor"] = anchor
    return rebased


def render_png(rebased: pd.DataFrame, out_path: Path) -> None:
    anchor = rebased.attrs["anchor"]

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("ggplot")
    fig, ax = plt.subplots(figsize=(14, 8), dpi=140)

    for col in rebased.columns:
        ax.plot(rebased.index, rebased[col], label=col, color=SERIES_COLORS[col],
                linewidth=2.4 if col.startswith("Aggregate FCF") else 1.7,
                marker="o", markersize=4)

    ax.axhline(100.0, color="#999999", linewidth=0.8, linestyle="--", alpha=0.7, zorder=1)

    if is_sample_data():
        ax.text(
            0.5, 0.5, "SAMPLE DATA", transform=ax.transAxes,
            fontsize=52, color="#d62728", alpha=0.12, rotation=24,
            ha="center", va="center", zorder=0, fontweight="bold",
        )

    title = ("Free cash flow vs. M2, the S&P 500, and the Treasury curve "
             f"(rebased to 100 at {anchor:%Y-%m-%d})")
    if is_sample_data():
        title = SAMPLE_BANNER + "\n" + title
    ax.set_title(title, fontsize=12, pad=12,
                 color="#d62728" if is_sample_data() else "black")
    ax.set_ylabel(f"Index (100 = each series at {anchor:%Y-%m-%d})", fontsize=10)
    ax.set_xlabel("Quarter-end")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(loc="upper left", frameon=True, fontsize=9)
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    pulled = data_pulled_date()
    fig.text(
        0.5, 0.005,
        (f"Data pulled {pulled} · " if pulled else "")
        + "Data sources: " + " · ".join(f"{label} ({url})" for label, url in DATA_SOURCES),
        ha="center", va="bottom", fontsize=6.0, color="#666666",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def render_html(rebased: pd.DataFrame, out_path: Path) -> None:
    """Zoomable/pannable plotly chart: drag to zoom, double-click to reset."""
    import plotly.graph_objects as go

    anchor = rebased.attrs["anchor"]

    fig = go.Figure()
    for col in rebased.columns:
        fig.add_trace(
            go.Scatter(
                x=rebased.index,
                y=rebased[col],
                name=col,
                mode="lines+markers",
                line=dict(color=SERIES_COLORS[col], width=2.6 if col.startswith("Aggregate FCF") else 1.7),
                marker=dict(size=5),
                hovertemplate="%{y:.1f}<extra>" + col + "</extra>",
            )
        )

    fig.add_hline(y=100.0, line=dict(color="#999999", width=0.8, dash="dash"))

    title_text = ("Free cash flow vs. M2, the S&P 500, and the Treasury curve "
                  f"(rebased to 100 at {anchor:%Y-%m-%d})")
    if is_sample_data():
        title_text = (f"<span style='color:#d62728'>{SAMPLE_BANNER}</span><br>"
                      + title_text)
        fig.add_annotation(
            text="SAMPLE DATA", xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=60, color="rgba(214,39,40,0.12)"),
            textangle=-24,
        )

    fig.update_layout(
        template="plotly_white",
        title=dict(
            text=title_text,
            font=dict(size=14),
        ),
        hovermode="x unified",
        dragmode="zoom",
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)", bordercolor="#cccccc", borderwidth=1),
        margin=dict(l=70, r=30, t=90, b=60),
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
        title_text="Quarter-end",
        showspikes=True,
        spikemode="across",
        spikethickness=1,
        rangeslider=dict(visible=True, thickness=0.06),
    )
    fig.update_yaxes(
        title_text=f"Index (100 = each series at {anchor:%Y-%m-%d})",
        fixedrange=False,
        showspikes=False,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        config={"scrollZoom": True, "displaylogo": False, "responsive": True},
    )
    html = html.replace("<head>", "<head><title>" + PAGE_TITLE + "</title>", 1)
    links = " · ".join(
        f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'
        for label, url in DATA_SOURCES
    )
    pulled = data_pulled_date()
    pulled_html = f"Data pulled {pulled} &middot; " if pulled else ""
    footer = (
        '<footer style="font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;'
        'font-size:12px;color:#666;text-align:center;padding:8px 16px 16px">'
        + pulled_html + "<strong>Data sources:</strong> " + links + "</footer>"
    )
    html = html.replace("</body>", footer + "</body>", 1)
    out_path.write_text(html, encoding="utf-8")


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
