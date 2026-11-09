"""Render the Mag7 skew × A−B edge grid as a presentation-ready PNG.

Reads:
  results/mag7_premium_matched.csv   (07_mag7_compare.py, common window)
  results/mag7_buyhold_descriptive.csv

Writes:
  results/mag7_skew_edge_table.png

Usage: .venv/bin/python tools/plot_mag7_skew_edge_table.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
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
POS = "#c0392b"   # A wins (positive edge)
NEG = "#2a78d6"   # B wins (negative edge)

TARGETS = [0.083, 0.167, 0.25, 1.0, 2.0, 3.0, 4.0]
TARGET_LABELS = ["0.083%", "0.167%", "0.25%", "1%", "2%", "3%", "4%"]

# Cells shown as em-dash in the deck (low-feasibility / not worth quoting).
DASH = {
    (2.0, "MSFT"), (2.0, "GOOGL"), (2.0, "AAPL"),
}


def _fmt_target(t: float) -> str:
    if t < 1:
        return f"{t:g}%"
    return f"{int(t)}%"


def load_table() -> tuple[list[str], np.ndarray, np.ndarray, dict[str, float], str]:
    pm = pd.read_csv(ROOT / "results" / "mag7_premium_matched.csv")
    bh = pd.read_csv(ROOT / "results" / "mag7_buyhold_descriptive.csv")
    tickers = bh.sort_values("skew", ascending=False)["ticker"].tolist()
    skew = {r["ticker"]: r["skew"] for _, r in bh.iterrows()}

    n_rows, n_cols = len(TARGETS), len(tickers)
    values = np.full((n_rows, n_cols), np.nan)
    masked = np.zeros((n_rows, n_cols), dtype=bool)

    for i, tgt in enumerate(TARGETS):
        for j, t in enumerate(tickers):
            if (tgt, t) in DASH:
                masked[i, j] = True
                continue
            sub = pm[(pm["ticker"] == t) & (pm["income_target_pct"] == tgt)]
            if len(sub):
                values[i, j] = sub["mean_edge_A_over_B_bp"].iloc[0]

    window = (
        f"{bh['sample_start'].iloc[0]} → {bh['sample_end'].iloc[0]}"
        f"  (n={int(bh['n_months'].iloc[0])})"
    )
    return tickers, values, masked, skew, window


def _cell_bg(val: float, vmax: float) -> tuple[str, str]:
    """Return (background, text colour) for a numeric cell."""
    if not np.isfinite(val):
        return STRIPE, MUTED
    t = np.clip(abs(val) / vmax, 0, 1)
    if abs(val) < 0.5:
        return "#ffffff", INK
    if val < 0:
        # B wins — blue wash
        r = int(42 + (1 - t) * (253 - 42))
        g = int(33 + (1 - t) * (253 - 33))
        b = int(61 + (1 - t) * (252 - 61))
        bg = f"#{r:02x}{g:02x}{b:02x}"
        txt = NAVY if t < 0.55 else "#ffffff"
    else:
        # A wins — warm wash
        r = int(253 - t * (253 - 192))
        g = int(253 - t * (253 - 57))
        b = int(252 - t * (252 - 43))
        bg = f"#{r:02x}{g:02x}{b:02x}"
        txt = "#7b241c" if t < 0.55 else "#ffffff"
    return bg, txt


def main() -> None:
    tickers, values, masked, skew, window = load_table()
    n_rows, n_cols = values.shape
    vmax = max(150.0, np.nanmax(np.abs(values)))

    fig_w = 13.2
    fig_h = 0.72 + n_rows * 0.62 + 1.1
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=SURFACE)

    # layout constants (figure coords)
    left, right = 0.06, 0.94
    top_title = 0.93
    table_top = 0.82
    row_h = (table_top - 0.12) / (n_rows + 1)
    col_w = (right - left) / (n_cols + 1.05)
    row_label_w = col_w * 1.05

    fig.text(
        left, top_title,
        "A−B monthly edge by buy-and-hold skew (common window)",
        fontsize=16.5, color=NAVY, fontweight="bold", va="top",
    )
    fig.text(
        left, top_title - 0.045,
        f"Premium-matched · negative = B wins · {window}",
        fontsize=10.5, color=INK2, va="top",
    )

    # header row
    y_hdr = table_top - row_h
    ax_hdr = fig.add_axes([0, 0, 1, 1], frameon=False)
    ax_hdr.set_xlim(0, 1)
    ax_hdr.set_ylim(0, 1)
    ax_hdr.axis("off")

    # corner + row header background
    ax_hdr.add_patch(Rectangle(
        (left, y_hdr), row_label_w, row_h,
        transform=ax_hdr.transAxes, facecolor=NAVY, edgecolor=NAVY, clip_on=False,
    ))
    ax_hdr.text(
        left + row_label_w / 2, y_hdr + row_h / 2,
        "Monthly\nincome target",
        ha="center", va="center", fontsize=9.5, color="#ffffff",
        fontweight="600", transform=ax_hdr.transAxes,
    )

    for j, t in enumerate(tickers):
        x = left + row_label_w + j * col_w
        ax_hdr.add_patch(Rectangle(
            (x, y_hdr), col_w, row_h,
            transform=ax_hdr.transAxes, facecolor=NAVY, edgecolor=NAVY, clip_on=False,
        ))
        sk = skew[t]
        ax_hdr.text(
            x + col_w / 2, y_hdr + row_h * 0.62, t,
            ha="center", va="center", fontsize=11, color="#ffffff",
            fontweight="700", transform=ax_hdr.transAxes,
        )
        ax_hdr.text(
            x + col_w / 2, y_hdr + row_h * 0.28, f"{sk:+.2f}",
            ha="center", va="center", fontsize=8.5, color="#c8d4e8",
            transform=ax_hdr.transAxes,
        )

    # body rows
    for i, (tgt, label) in enumerate(zip(TARGETS, TARGET_LABELS)):
        y = y_hdr - (i + 1) * row_h
        stripe = STRIPE if i % 2 == 0 else "#ffffff"

        ax_hdr.add_patch(Rectangle(
            (left, y), row_label_w, row_h,
            transform=ax_hdr.transAxes, facecolor=stripe, edgecolor=GRID,
            linewidth=0.6, clip_on=False,
        ))
        ax_hdr.text(
            left + row_label_w * 0.08, y + row_h / 2, label,
            ha="left", va="center", fontsize=10.5, color=INK,
            fontweight="600" if tgt in (1.0, 2.0) else "normal",
            transform=ax_hdr.transAxes,
        )

        for j, t in enumerate(tickers):
            x = left + row_label_w + j * col_w
            if masked[i, j]:
                bg, txt = stripe, MUTED
                cell_txt = "—"
                fw = "normal"
            else:
                v = values[i, j]
                bg, txt = _cell_bg(v, vmax)
                if abs(v) < 0.5:
                    cell_txt = "0"
                else:
                    cell_txt = f"{v:+.0f}"
                fw = "bold" if abs(v) >= 50 else "normal"

            ax_hdr.add_patch(Rectangle(
                (x, y), col_w, row_h,
                transform=ax_hdr.transAxes, facecolor=bg, edgecolor=GRID,
                linewidth=0.6, clip_on=False,
            ))
            ax_hdr.text(
                x + col_w / 2, y + row_h / 2, cell_txt,
                ha="center", va="center", fontsize=11 if fw == "bold" else 10.5,
                color=txt, fontweight=fw, transform=ax_hdr.transAxes,
            )

    # footer
    fig.text(
        left, 0.04,
        "Spearman(skew, A−B edge) = −0.75 to −1.00 at every income target (p ≤ 0.05, n = 7).  "
        "Source: results/mag7_premium_matched.csv",
        fontsize=9, color=MUTED, va="bottom",
    )

    out = ROOT / "results" / "mag7_skew_edge_table.png"
    fig.savefig(out, dpi=200, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
