"""Step 2 — metrics layer and frontier.

Input results/panel_monthly.csv, output:
  results/metrics_summary.csv   full metrics table for each index x each subperiod
  results/frontier_<period>.png income vs risk-adjusted return frontier (families A/B, only meaningful once data is complete)
Usage: .venv/bin/python 02_metrics_frontier.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _config import get_config

CFG = get_config()
OUT = CFG.out_dir

SUBPERIODS = {
    "full": ("2008-01-01", "2026-12-31"),
    "2008-2015": ("2008-01-01", "2015-12-31"),
    "2016-2021": ("2016-01-01", "2021-12-31"),
    "2022_bear": ("2022-01-01", "2022-12-31"),
    "2023-2026_ai": ("2023-01-01", "2026-12-31"),
}


def perf_stats(ret: pd.Series, rf: pd.Series, bench: pd.Series, ppy: float = 12.0) -> dict:
    """rebalance-period returns -> annualized metrics. ret/rf/bench share the same index, rf is an annualized rate, ppy=periods per year (monthly 12/weekly 52/quarterly 4)."""
    n = len(ret)
    if n < 6:
        return {}
    rf_m = rf / ppy
    ex = ret - rf_m
    ann = ppy
    cum = (1 + ret).cumprod()
    cagr = cum.iloc[-1] ** (ann / n) - 1
    vol = ret.std() * np.sqrt(ann)
    wealth = np.r_[1.0, cum.to_numpy()]
    dd = (wealth / np.maximum.accumulate(wealth) - 1).min()
    down = np.sqrt(np.mean(np.minimum(ex.to_numpy(), 0.0) ** 2)) * np.sqrt(ann)
    up_mask, dn_mask = bench > 0, bench < 0
    stats = {
        "n_months": n,
        "cagr": cagr,
        "ann_vol": vol,
        "sharpe": ex.mean() / ret.std() * np.sqrt(ann) if ret.std() > 0 else np.nan,
        "sortino": ex.mean() * ann / down if down > 0 else np.nan,
        "max_dd": dd,
        "calmar": cagr / abs(dd) if dd < 0 else np.nan,
        "skew": ret.skew(),
        "up_capture": ret[up_mask].mean() / bench[up_mask].mean() if up_mask.any() else np.nan,
        "down_capture": ret[dn_mask].mean() / bench[dn_mask].mean() if dn_mask.any() else np.nan,
    }
    return stats


def strategy_rows(panel: pd.DataFrame) -> list[dict]:
    rows = []
    # the underlying benchmark is built from the monthly-expiry tier (all monthly indices share the same Benchmark, take any one)
    bench_bh = panel[panel["ppy"] == 12].groupby("date").first().sort_index()
    for period, (lo, hi) in SUBPERIODS.items():
        nv = bench_bh.loc[lo:hi]
        if len(nv) < 6:
            continue
        # benchmark 1: underlying full-notional (monthly)
        rows.append({"index_name": CFG.bench_name, "family": "bench", "param": np.nan,
                     "period": period, "income_pa": 0.0,
                     **perf_stats(nv["bench_ret"], nv["rf_3m"], nv["bench_ret"], 12)})
        # each strategy index
        for name, g in panel.groupby("index_name"):
            g = g.set_index("date").sort_index().loc[lo:hi].dropna(subset=["y_used"])
            if len(g) < 6:
                continue
            f = g["coverage"].iloc[0]          # payoff coverage ratio (full-notional=1.0)
            ppy = g["ppy"].iloc[0]             # periods per year for annualization
            income_pa = (g["y_used"] * f).mean() * ppy
            capped = g["bench_ret"] > (g["cap_used"] - 1)
            giveup = ((g["bench_ret"] - (g["cap_used"] - 1)) * f)[capped]
            rows.append({"index_name": name, "family": g["family"].iloc[0],
                         "param": g["param"].iloc[0], "coverage": f,
                         "delta": g["delta"].iloc[0], "expiry": g["expiry"].iloc[0],
                         "ppy": ppy, "period": period,
                         "income_pa": income_pa,
                         "pct_capped": capped.mean(),
                         "avg_giveup_when_capped": giveup.mean() if capped.any() else 0.0,
                         **perf_stats(g["index_ret"], g["rf_3m"], g["bench_ret"], ppy)})
            # benchmark 2: underlying+cash vol-matched to this index (honest benchmark, same frequency)
            bench_vol = g["bench_ret"].std()
            w = min(1.0, g["index_ret"].std() / bench_vol) if bench_vol > 0 else 0.0
            mix = w * g["bench_ret"] + (1 - w) * g["rf_3m"] / ppy
            rows.append({"index_name": f"{name}_volmatch_mix", "family": "bench",
                         "param": w, "period": period, "income_pa": 0.0,
                         **perf_stats(mix, g["rf_3m"], g["bench_ret"], ppy)})
    return rows


# strategy family -> (legend label, line style); only plot families with comparable coordinates
FAM_STYLE = {
    "B": ("B: coverage axis (partial ATM, 10-100%)", "s--"),
    "A_delta": ("A_delta: full cover, delta-strike", "o-"),
    "A": ("A: full cover OTM (premium target)", "^-"),
    "BD": ("BD: coverage x delta (2D)", "D:"),
    # Disabled: only NVDA has Weekly/Quarterly, thin sample, not Mag7-comparable.
    # "E_Weekly": ("full cover, weekly expiry", "P-"),
    # "E_Quarterly": ("full cover, quarterly expiry", "X-"),
}


def plot_frontier(m: pd.DataFrame, period: str, ycol: str = "calmar") -> None:
    sub = m[(m["period"] == period) & (m["family"].isin(FAM_STYLE))]
    fams = [f for f in FAM_STYLE if (sub["family"] == f).any()]
    if not fams:
        return
    fig, ax = plt.subplots(figsize=(9, 6))
    for fam in fams:
        label, style = FAM_STYLE[fam]
        g = sub[sub["family"] == fam].sort_values("income_pa")
        ax.plot(g["income_pa"], g[ycol], style, label=label)
        for _, r in g.iterrows():
            ax.annotate(r["index_name"].replace(f"{CFG.cc}_", ""), (r["income_pa"], r[ycol]), fontsize=7)
    nv = m[(m["period"] == period) & (m["index_name"] == CFG.bench_name)]
    if len(nv):
        ax.axhline(nv[ycol].iloc[0], color="gray", ls=":", label=f"{CFG.ticker} buy&hold")
    ax.set_xlabel("annualized premium income")
    ax.set_ylabel(ycol)
    ax.set_title(f"Income vs {ycol} frontier — {period}")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / f"frontier_{period}_{ycol}.png", dpi=150)
    plt.close(fig)


def main() -> None:
    panel = pd.read_csv(OUT / "panel_monthly.csv", parse_dates=["date"])
    m = pd.DataFrame(strategy_rows(panel))
    m.to_csv(OUT / "metrics_summary.csv", index=False)
    cols = ["index_name", "period", "income_pa", "cagr", "ann_vol", "sharpe", "sortino",
            "max_dd", "calmar", "skew", "up_capture", "down_capture", "pct_capped"]
    full = m[m["period"] == "full"][[c for c in cols if c in m.columns]]
    print("== full sample ==")
    print(full.round(3).to_string(index=False))
    for p in SUBPERIODS:
        plot_frontier(m, p, "calmar")
        plot_frontier(m, p, "sharpe")
    print(f"\nwrote {OUT / 'metrics_summary.csv'} + frontier_*.png")


if __name__ == "__main__":
    main()
