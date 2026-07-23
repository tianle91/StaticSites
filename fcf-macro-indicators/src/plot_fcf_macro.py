#!/usr/bin/env python3
"""
Read the quarterly source series from data/series.csv and plot free cash flow
against the macro backdrop across two panels that share one x-axis: the top panel
rebases the level series (aggregate FCF, aggregate cash, M2 money supply, the
S&P 500) to 100 at a configurable anchor quarter to compare growth; the bottom
panel shows the 3M / 2Y / 10Y / 30Y Treasury curve as raw yields (%), which have a
natural common scale and would blow up if rebased to a near-zero-rate anchor.

Free cash flow is the coarsest input (reported quarterly), so it sets both the
grid and the charted window: the chart spans the quarters in which every basket
member reports FCF. Renders a static PNG (matplotlib) or a zoomable HTML chart
(plotly), picked from the output file extension. Offline: refresh data/series.csv
with `make data`.
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

# Browser tab / bookmark title for the HTML chart. Plotly's to_html() emits a
# document with an empty <head> and no <title>, so we inject this one.
PAGE_TITLE = "Free Cash Flow vs. M2, the S&amp;P 500 &amp; the Treasury Curve"

# Display label -> CSV column. Order controls legend/plot order. The aggregate
# FCF line is derived from the fcf_* columns (see build_rebased); the rest map
# straight through. Yields run light->dark from the short end to the long end.
SERIES_COLORS = {
    "Aggregate FCF (basket sum)": "#d62728",
    "Aggregate cash & equivalents (basket sum)": "#ff7f0e",
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
    M2, S&P 500) are rebased to 100; Treasury yields are kept as raw percentages
    (see YIELD_LABELS) for their own panel."""
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
    return rebased


def render_png(rebased: pd.DataFrame, out_path: Path) -> None:
    anchor = rebased.attrs["anchor"]
    tickers = rebased.attrs.get("tickers", [])
    level_cols, yield_cols = _split_columns(rebased.columns)

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("ggplot")
    # Two panels on a shared x-axis: rebased levels on top, raw Treasury yields
    # below. The top panel is taller (it carries the aggregate + M2 + S&P lines).
    fig, (ax_lvl, ax_yld) = plt.subplots(
        2, 1, figsize=(14, 10), dpi=140, sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.08},
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

    # Shade inverted-curve periods as a band across both panels.
    spans = inversion_spans(rebased)
    for i, (x0, x1) in enumerate(spans):
        for ax in (ax_lvl, ax_yld):
            ax.axvspan(x0, x1, color=INVERSION_COLOR, alpha=0.09, zorder=0,
                       label=INVERSION_LABEL if (i == 0 and ax is ax_yld) else None)

    ax_yld.set_ylabel("Treasury yield (%)", fontsize=10)
    ax_yld.set_xlabel("Quarter-end")
    ax_yld.legend(loc="upper left", frameon=True, fontsize=9, ncol=2)
    ax_yld.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax_yld.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    basket = f"Aggregates sum {len(tickers)} companies: {', '.join(tickers)}" if tickers else ""
    fig.suptitle(
        "Free cash flow vs. M2, the S&P 500, and the Treasury curve\n"
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
    """Zoomable/pannable plotly chart: drag to zoom, double-click to reset. Two
    panels share one x-axis -- rebased levels on top, raw Treasury yields below."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    anchor = rebased.attrs["anchor"]
    tickers = rebased.attrs.get("tickers", [])
    level_cols, yield_cols = _split_columns(rebased.columns)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        row_heights=[0.6, 0.4],
        subplot_titles=(f"Levels rebased to 100 at {anchor:%Y-%m-%d}", "Treasury yields (%)"),
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

    basket = (f"Aggregates sum {len(tickers)} companies: {', '.join(tickers)}"
              if tickers else "")
    fig.update_layout(
        template="plotly_white",
        title=dict(
            text=("Free cash flow vs. M2, the S&P 500, and the Treasury curve"
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
            )
        ],
    )
    # Spikes + rangeslider/selector live on the shared (bottom) x-axis.
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1, row=1, col=1)
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
        row=2, col=1,
    )
    fig.update_yaxes(title_text=f"Index (100 @ {anchor:%Y-%m-%d})", fixedrange=False,
                     showspikes=False, row=1, col=1)
    fig.update_yaxes(title_text="Yield (%)", fixedrange=False, showspikes=False, row=2, col=1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        config={"scrollZoom": True, "displaylogo": False, "responsive": True},
    )
    html = html.replace("<head>", "<head><title>" + PAGE_TITLE + "</title>", 1)
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
