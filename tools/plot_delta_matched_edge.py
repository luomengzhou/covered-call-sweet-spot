"""Gross vs net B-edge after delta matching — structural or just beta?

Reads results/delta_matched_benchmark.csv (written by 06_delta_matched_benchmark.py)
and writes results/mag7_delta_matched_edge.png.

Usage: .venv/bin/python tools/plot_delta_matched_edge.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = [
    "Noto Sans CJK SC",
    "WenQuanYi Zen Hei",
    "Source Han Sans SC",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent

SURFACE = "#fcfcfb"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"
GROSS, NET = "#c3c2b7", "#14213d"
POS = "#2a78d6"

TICKERS = ["TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "AAPL", "META"]
TARGET = "1%"


def main() -> None:
    df = pd.read_csv(ROOT / "results" / "delta_matched_benchmark.csv")
    row = df[df["target"] == TARGET].set_index("ticker").reindex(TICKERS)

    gross = row["gross_edge_B_bp"].to_numpy()
    net = row["net_edge_B_bp"].to_numpy()

    fig, ax = plt.subplots(figsize=(12.5, 6.8), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    x = np.arange(len(TICKERS))
    w = 0.36
    ax.bar(x - w / 2, gross, width=w, color=GROSS, edgecolor=SURFACE, linewidth=1.4,
           label="Gross B-edge (r_B − r_A)", zorder=3)
    bars = ax.bar(x + w / 2, net, width=w, color=NET, edgecolor=SURFACE, linewidth=1.4,
                  label="Net B-edge (delta-matched)", zorder=3)

    ax.axhline(0, color=BASELINE, linewidth=1.2, zorder=2)
    ax.yaxis.grid(True, color=GRID, linewidth=0.9, zorder=0)
    ax.set_axisbelow(True)

    ax.set_xticks(x)
    ax.set_xticklabels(TICKERS, fontsize=12, color=INK)
    ax.set_ylabel("bp / month", fontsize=12, color=INK2)
    ax.set_xlim(-0.6, len(TICKERS) - 0.4)

    ymax = max(gross.max(), net.max()) * 1.22
    ymin = min(gross.min(), net.min(), 0) * 1.15
    ax.set_ylim(ymin, ymax)

    for i, t in enumerate(TICKERS):
        g, n = gross[i], net[i]
        if t == "NVDA" and g > 0:
            ax.annotate(
                f"59% beta\n({g:.0f}→{n:.0f})",
                xy=(i + w / 2, n),
                xytext=(i + 0.55, n + 18),
                fontsize=9.5,
                color=INK2,
                ha="left",
                va="bottom",
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.9),
            )
        elif t == "TSLA" and n > 0:
            ax.annotate(
                "convexity\nsurvives",
                xy=(i + w / 2, n),
                xytext=(i - 0.15, n + 22),
                fontsize=9.5,
                color=POS,
                ha="center",
                va="bottom",
                fontweight="bold",
            )
        elif n <= 0 and g > 0:
            ax.annotate(
                "beta only",
                xy=(i, (g + n) / 2),
                fontsize=8.5,
                color=MUTED,
                ha="center",
                va="center",
                rotation=90,
            )

    fig.text(
        0.09,
        0.96,
        "Is B's edge structural, or just more stock exposure?",
        fontsize=17,
        color=INK,
        fontweight="bold",
    )
    fig.text(
        0.09,
        0.905,
        f"Income {TARGET} target · monthly mean · B benchmarked to δ_B stock + cash "
        f"(δ̄_A ≈ {row['mean_delta_A'].mean():.2f}, δ̄_B ≈ {row['mean_delta_B'].mean():.2f})",
        fontsize=10.5,
        color=INK2,
    )

    ax.legend(loc="upper right", frameon=False, fontsize=10.5, labelcolor=INK2)

    out = ROOT / "results" / "mag7_delta_matched_edge.png"
    fig.savefig(out, dpi=180, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
