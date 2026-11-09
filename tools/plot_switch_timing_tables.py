"""Render switch-timing audit tables as presentation-ready PNGs.

Table 1 — signal summary (hard-coded from PRESENT_03_slides.md):
  results/mag7_switch_tests_table.png

Table 2 — per-name top-5 months + underlying move + share (06_edge_concentration.csv):
  results/mag7_edge_concentration_table.png

Usage: .venv/bin/python tools/plot_switch_timing_tables.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

plt.rcParams["font.sans-serif"] = [
    "Noto Sans CJK SC",
    "PingFang SC",
    "Helvetica Neue",
    "Arial",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent

SURFACE = "#fdfdfc"
INK = "#1a1a1a"
NAVY = "#14213d"
INK2 = "#45443f"
MUTED = "#6b6a64"
STRIPE = "#f6f5f1"
GRID = "#e8e6de"
NEG = "#c0392b"
WARN = "#b45309"
GOLD_BG = "#fbf8ee"
GOLD_BORDER = "#c9a227"

TESTS = [
    (
        "Realized skew — own history, vs SPY, vs QQQ",
        "corr all within ±0.06–0.16",
        "Noise, in all three reference frames",
    ),
    (
        "Windows tried: 1mo / 3mo / 6mo lookback",
        "same conclusion at every window",
        "Not a lookback-length problem",
    ),
    (
        "IV wing (wing_z, from our own Cap/Call Yield)\n— strongest candidate",
        "pooled t = 1.13 / 0.98",
        "Direction plausible, insignificant once pooled",
    ),
    (
        "Trading the rule, Mag7 equal-weight",
        "−13 / −14 bp per month",
        "Loses to always-B",
    ),
]

# Only names where B has a real, interpretable edge at this target.
# (GOOGL/MSFT/AMZN 1%: total B-edge ≈ 0 → share ratio explodes to nonsense.)
EDGE_ROWS = [
    ("TSLA", "1%"),
    ("NVDA", "1%"),
    ("NVDA", "3%"),   # headline footnote case: 93%
]
HIGHLIGHT = {"TSLA", "NVDA"}


def _fmt_share(b_total: float, share: float) -> str:
    """Share = top-5 D / total D. Meaningless when total B-edge ≈ 0."""
    if not np.isfinite(share) or not np.isfinite(b_total):
        return "—"
    if abs(b_total) < 15:          # cumulative B-edge under ~15% → ratio unstable
        return "—"
    if share > 200:                # other months net so negative the ratio is misleading
        return "—"
    return f"{share:.0f}%"


def _parse_months_up(months_str: str, up_str: str) -> tuple[str, str]:
    months = months_str.split()
    ups = up_str.split()
    month_txt = "  ·  ".join(months)
    up_txt = "  ·  ".join(u.replace("%", "") for u in ups) + " %"
    return month_txt, up_txt


def _draw_table(
    fig: plt.Figure,
    y_top: float,
    headers: list[str],
    rows: list[list[str]],
    *,
    col_weights: list[float],
    row_h: float = 0.072,
    header_h: float = 0.058,
    left: float = 0.06,
    right: float = 0.94,
    font_size: float = 10.0,
    header_size: float = 9.5,
    col_align: list[str] | None = None,
    cell_styles: list[list[tuple[str, str, str]]] | None = None,
) -> float:
    """Draw a table; return y coordinate below the table."""
    ax = fig.add_axes([0, 0, 1, 1], frameon=False)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    total_w = right - left
    w_sum = sum(col_weights)
    col_ws = [total_w * w / w_sum for w in col_weights]
    n_cols = len(headers)
    if col_align is None:
        col_align = ["left"] * n_cols

    # header
    x = left
    for j, (hdr, cw) in enumerate(zip(headers, col_ws)):
        ax.add_patch(Rectangle(
            (x, y_top - header_h), cw, header_h,
            transform=ax.transAxes, facecolor=NAVY, edgecolor=NAVY, clip_on=False,
        ))
        ax.text(
            x + (0.04 * cw if col_align[j] == "left" else cw / 2),
            y_top - header_h / 2,
            hdr,
            ha="left" if col_align[j] == "left" else "center",
            va="center",
            fontsize=header_size,
            color="#ffffff",
            fontweight="600",
            transform=ax.transAxes,
        )
        x += cw

    y = y_top - header_h
    for i, row in enumerate(rows):
        y -= row_h
        stripe = STRIPE if i % 2 == 0 else "#ffffff"
        x = left
        for j, (cell, cw) in enumerate(zip(row, col_ws)):
            style = (stripe, INK, "normal")
            if cell_styles and i < len(cell_styles) and j < len(cell_styles[i]):
                style = cell_styles[i][j]
            bg, txt, fw = style
            ax.add_patch(Rectangle(
                (x, y), cw, row_h,
                transform=ax.transAxes, facecolor=bg, edgecolor=GRID,
                linewidth=0.6, clip_on=False,
            ))
            ax.text(
                x + (0.04 * cw if col_align[j] == "left" else cw / 2),
                y + row_h / 2,
                cell,
                ha="left" if col_align[j] == "left" else "center",
                va="center",
                fontsize=font_size,
                color=txt,
                fontweight=fw,
                transform=ax.transAxes,
            )
            x += cw

    return y - 0.012


def plot_tests_table() -> None:
    fig = plt.figure(figsize=(12.8, 5.2), facecolor=SURFACE)
    fig.text(
        0.06, 0.93,
        "Can you switch on some indicator, within a single name?",
        fontsize=15.5, color=NAVY, fontweight="bold", va="top",
    )
    fig.text(
        0.06, 0.875,
        "Essentially no — 56 cells tested (4 signals × 7 names × 2 income targets)",
        fontsize=10.5, color=INK2, va="top",
    )

    styles = []
    for i, row in enumerate(TESTS):
        row_styles = []
        for j, cell in enumerate(row):
            bg = STRIPE if i % 2 == 0 else "#ffffff"
            txt, fw = INK, "normal"
            if j == 1 and "−" in cell:
                txt, fw = NEG, "bold"
            if j == 1 and "±" in cell:
                fw = "bold"
            row_styles.append((bg, txt, fw))
        styles.append(row_styles)

    y = _draw_table(
        fig, 0.82,
        ["Test", "Result", "Reading"],
        [list(r) for r in TESTS],
        col_weights=[2.2, 1.2, 1.6],
        row_h=0.088,
        font_size=10.2,
        col_align=["left", "left", "left"],
        cell_styles=styles,
    )

    # callout box
    box_h = 0.11
    ax = fig.axes[0]
    ax.add_patch(Rectangle(
        (0.06, y - box_h), 0.88, box_h,
        transform=ax.transAxes, facecolor=GOLD_BG, edgecolor=GOLD_BORDER,
        linewidth=0, clip_on=False,
    ))
    ax.plot([0.06, 0.06], [y - box_h, y], color=GOLD_BORDER, linewidth=4,
            transform=ax.transAxes, clip_on=False, solid_capstyle="butt")
    ax.text(
        0.075, y - box_h / 2,
        "Not passing.  Nothing survives once pooled.",
        ha="left", va="center", fontsize=13, color=NAVY, fontweight="bold",
        transform=ax.transAxes,
    )

    fig.text(
        0.06, 0.04,
        "Source: results/06_skew_switch_results.md · wing_z uses Garage Cap/Call Yield (no compliance issue)",
        fontsize=8.5, color=MUTED, va="bottom",
    )

    out = ROOT / "results" / "mag7_switch_tests_table.png"
    fig.savefig(out, dpi=200, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"wrote {out}")


def plot_edge_concentration_table() -> None:
    df = pd.read_csv(ROOT / "results" / "06_edge_concentration.csv")
    rows: list[list[str]] = []
    styles: list[list[tuple[str, str, str]]] = []

    for i, (ticker, target) in enumerate(EDGE_ROWS):
        sub = df[(df["ticker"] == ticker) & (df["target"] == target)]
        if not len(sub):
            continue
        r = sub.iloc[0]
        month_txt, up_txt = _parse_months_up(str(r["months"]), str(r["up"]))
        share = r["share"]
        share_txt = _fmt_share(r["B_total"], share)
        label = f"{ticker}  ({target})"
        rows.append([label, month_txt, up_txt, share_txt])

        bg = STRIPE if i % 2 == 0 else "#ffffff"
        row_st = []
        for j in range(4):
            txt, fw = INK, "normal"
            if ticker in HIGHLIGHT:
                fw = "bold"
            if j == 0 and ticker in HIGHLIGHT:
                txt = NAVY
            if j == 2 and ticker in HIGHLIGHT:
                txt = NAVY
            if j == 3 and share_txt != "—":
                if float(share_txt.rstrip("%")) >= 100:
                    txt, fw = WARN, "bold"
                else:
                    txt, fw = NAVY, "bold"
            row_st.append((bg, txt, fw))
        styles.append(row_st)

    fig = plt.figure(figsize=(13.6, 4.8), facecolor=SURFACE)
    fig.text(
        0.06, 0.93,
        "B's edge concentrates in a handful of gap-up months",
        fontsize=15.5, color=NAVY, fontweight="bold", va="top",
    )
    fig.text(
        0.06, 0.875,
        "Premium-matched B vs A · 5 months with largest B−A spread · "
        "only names where B's total edge is material",
        fontsize=10.5, color=INK2, va="top",
    )

    _draw_table(
        fig, 0.80,
        [
            "Name",
            "5 months where B wins biggest",
            "Underlying that month",
            "Share of\nB's total edge",
        ],
        rows,
        col_weights=[0.65, 2.0, 1.35, 0.65],
        row_h=0.095,
        header_h=0.062,
        font_size=10.0,
        header_size=9.0,
        col_align=["left", "left", "left", "center"],
        cell_styles=styles,
    )

    fig.text(
        0.06, 0.04,
        "Share = cumulative edge in these 5 months ÷ total B−A edge.  "
        "NVDA >100% means the other ~200 months net negative.  "
        "Not shown for flat-vol names (GOOGL/MSFT/AMZN at 1%: total B-edge ≈ 0, ratio undefined).  "
        "Source: results/06_edge_concentration.csv",
        fontsize=8.5, color=MUTED, va="bottom",
    )

    out = ROOT / "results" / "mag7_edge_concentration_table.png"
    fig.savefig(out, dpi=200, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"wrote {out}")


def main() -> None:
    plot_tests_table()
    plot_edge_concentration_table()


if __name__ == "__main__":
    main()
