"""Regenerate the current additive-wing scenario grid and its two charts."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ab_core import (
    Params,
    WING_COMMODITY_45,
    WING_FLAT,
    WING_INDEX,
    scenario_grid,
    solve,
)


HERE = Path(__file__).resolve().parent
CHARTS = HERE / "charts"
CHARTS.mkdir(exist_ok=True)

WINGS = [WING_INDEX, WING_FLAT, WING_COMMODITY_45]
TITLES = [
    "wing = −2.0 vol / 5% (index anchor)",
    "wing = 0 (flat surface)",
    "wing = +4.5 vol / 5% (positive-wing stress)",
]


def build_grid() -> None:
    grid = scenario_grid(
        sigma_atm=[0.10, 0.20, 0.30, 0.45],
        tau=[1 / 12, 3 / 12, 6 / 12, 1.0],
        wing=WINGS,
    )
    grid.to_csv(HERE / "scenario_grid.csv", index=False)


def build_charts() -> None:
    sigmas = np.linspace(0.10, 0.45, 60)
    tenors = np.array([1, 2, 3, 4, 6, 9, 12]) / 12

    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.6), sharey=True)
    for ax, wing, title in zip(axes, WINGS, TITLES):
        for tau in tenors:
            values = [
                solve(Params(sigma_atm=float(sigma), tau=float(tau), wing=wing))
                .r_star_star
                for sigma in sigmas
            ]
            ax.plot(100 * sigmas, 100 * np.asarray(values), lw=1.6,
                    label=f"{round(12 * tau)}M")
        ax.set_title(title, fontsize=8.5, loc="left")
        ax.set_xlabel("ATM implied volatility (%)")
        ax.set_yscale("log")
        ax.set_yticks([5, 10, 20, 50, 100, 300])
        ax.set_yticklabels(["5", "10", "20", "50", "100", "300"])
        ax.grid(True, which="minor", alpha=0.12)
    axes[0].set_ylabel("Second crossover r** (%, log scale)")
    axes[-1].legend(fontsize=7, frameon=False, ncol=2, title="tenor",
                    title_fontsize=7, loc="lower right")
    fig.suptitle(
        "Where B overtakes A across ATM IV × tenor × additive call wing",
        fontsize=9.5,
        y=1.03,
    )
    fig.savefig(CHARTS / "01_scenario_rstarstar.png", dpi=170,
                bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.6), sharey=True)
    for ax, wing, title in zip(axes, WINGS, TITLES):
        for tau in tenors:
            values = [
                solve(Params(sigma_atm=float(sigma), tau=float(tau), wing=wing))
                .D_peak
                for sigma in sigmas
            ]
            ax.plot(100 * sigmas, 100 * np.asarray(values), lw=1.6,
                    label=f"{round(12 * tau)}M")
        ax.set_title(title, fontsize=8.5, loc="left")
        ax.set_xlabel("ATM implied volatility (%)")
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("A edge at r=c_A (%)")
    axes[-1].legend(fontsize=7, frameon=False, ncol=2, title="tenor",
                    title_fontsize=7)
    fig.suptitle(
        "A edge at the kink across ATM IV × tenor × additive call wing",
        fontsize=9.5,
        y=1.03,
    )
    fig.savefig(CHARTS / "02_scenario_Dpeak.png", dpi=170,
                bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    build_grid()
    build_charts()
    print("wrote scenario_grid.csv and scenario charts")
