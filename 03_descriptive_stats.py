"""Step 3 — descriptive statistics.

Read all *_attribution_report.csv under data/, and for each strategy's monthly Index Return compute
a full set of descriptive statistics (return/volatility/risk-adjusted/distribution shape/drawdown), plus an NVDA buy-and-hold benchmark.

Usage:
    .venv/bin/python 03_descriptive_stats.py
Output:
    results/descriptive_stats.csv

Convention notes:
- Monthly return taken directly from attribution's `Index Return` (verified = payoff-formula reconstruction, see 00_theory_notes.md section 10).
- NVDA benchmark uses the `Benchmark` column (total return with dividends), avoiding the garbage values of `Underlying Asset Return` in
  the 2021-08 / 2024-06 split months.
- Risk-free rate from TB3MS (3M Treasury, annualized %), per-period deduction = TB3MS/100/ppy (by each family's rebalance frequency).
- Annualization: geometric CAGR for return, sqrt(ppy) for volatility/Sharpe/Sortino. Monthly family ppy=12,
  weekly ppy=52, quarterly ppy=4 — different frequencies are not directly cross-comparable, only for their own annualization.
- ⚠️ Transaction costs not included; the weekly family's rolling costs erode significantly, interpret with caution.
"""
from __future__ import annotations

import csv
import glob
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from _config import DATA, get_config

CFG = get_config()
OUT = CFG.out_dir


def load_rf() -> pd.Series:
    """TB3MS annualized decimal, forward-fillable by observation date."""
    rf = pd.read_csv(DATA / "TB3MS.csv")
    rf.columns = ["date", "tb3ms"]
    rf["date"] = pd.to_datetime(rf["date"])
    rf["tb3ms"] = pd.to_numeric(rf["tb3ms"], errors="coerce") / 100
    return rf.dropna().set_index("date")["tb3ms"].sort_index()


def skew_kurt(r: np.ndarray) -> tuple[float, float]:
    """skewness + excess kurtosis (matches scipy.stats.skew/kurtosis default convention, biased moment estimation)."""
    d = r - r.mean()
    m2 = (d ** 2).mean()
    return (d ** 3).mean() / m2 ** 1.5, (d ** 4).mean() / m2 ** 2 - 3.0


def parse(name: str):
    """file name -> (label, family, ppy, param). Unrecognized returns None."""
    pre = CFG.prefix
    rules = [
        (rf"{pre}_(\d+)_Income_attribution", "A", 12, "Income_{0}"),
        (rf"{pre}_(\d+)_Exposure_attribution", "B", 12, "Exposure_{0}"),
        (rf"{pre}_Delta_(\d+)_attribution", "A_delta", 12, "Delta_{0}"),
        (rf"{pre}_(\d+)Exp_Delta_(\d+)_attribution", "BD", 12, "{0}Exp_D{1}"),
        # Disabled: only NVDA has Weekly/Quarterly; re-enable when Mag7 coverage exists.
        # (rf"{pre}_(\d+)Exp_Weekly_attribution", "E", 52, "Weekly_{0}"),
        # (rf"{pre}_(\d+)Exp_Quarterly_attribution", "E", 4, "Quarterly_{0}"),
    ]
    for pat, fam, ppy, tmpl in rules:
        m = re.match(pat, name)
        if m:
            label = tmpl.format(*m.groups())
            param = m.group(1) if m.group(1).isdigit() else None  # raw digits: "3", "0083"
            return label, fam, ppy, param
    return None


def describe(returns: list[float], ppy: int, rf_annual: list[float]) -> dict:
    r = np.asarray(returns, dtype=float)
    n = len(r)
    excess = r - np.asarray(rf_annual) / ppy
    downside = math.sqrt(np.mean(np.minimum(excess, 0.0) ** 2)) * math.sqrt(ppy)
    cum = np.r_[1.0, np.cumprod(1 + r)]
    drawdown = (cum / np.maximum.accumulate(cum) - 1).min()
    cagr = np.prod(1 + r) ** (ppy / n) - 1
    vol = r.std(ddof=1) * math.sqrt(ppy)
    return dict(
        n_months=n,
        cagr=cagr,
        ann_vol=vol,
        sharpe=excess.mean() / r.std(ddof=1) * math.sqrt(ppy),
        sortino=excess.mean() * ppy / downside if downside > 0 else np.nan,
        skew=skew_kurt(r)[0],             # skewness: <0 = long left tail (negative skew)
        excess_kurtosis=skew_kurt(r)[1],  # excess kurtosis: >0 = fatter tails than normal
        max_drawdown=drawdown,
        calmar=cagr / abs(drawdown),
        pct_positive=(r > 0).mean(),
        worst_month=r.min(),
        best_month=r.max(),
    )


def main() -> None:
    rf = load_rf()
    rows, bench_done = [], False
    for f in sorted(glob.glob(str(CFG.data_dir / "*attribution_report.csv"))):
        parsed = parse(Path(f).name)
        if not parsed:
            continue
        label, family, ppy, param = parsed
        data = list(csv.DictReader(open(f)))
        idx = [float(x["Index Return"]) for x in data]
        dates = pd.DatetimeIndex(pd.to_datetime([x["Date"] for x in data]))
        rf_m = rf.reindex(dates, method="ffill").to_numpy()
        rec = describe(idx, ppy, rf_m)
        rec.update(strategy=label, family=family, param=param, ppy=ppy)
        rows.append(rec)
        # build the underlying buy-and-hold benchmark from the first monthly family's Benchmark
        if not bench_done and ppy == 12:
            bench = [float(x["Benchmark"]) for x in data]
            b = describe(bench, 12, rf_m)
            b.update(strategy=CFG.bench_name, family="bench", param="", ppy=12)
            rows.insert(0, b)
            bench_done = True

    cols = ["strategy", "family", "param", "ppy", "n_months", "cagr", "ann_vol",
            "sharpe", "sortino", "skew", "excess_kurtosis", "max_drawdown",
            "calmar", "pct_positive", "worst_month", "best_month"]
    OUT.mkdir(exist_ok=True)
    with open(OUT / "descriptive_stats.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})

    # console preview
    hdr = f"{'strategy':16}{'CAGR':>8}{'Vol':>8}{'Sharpe':>7}{'Skew':>7}{'Kurt':>7}{'MaxDD':>8}{'%pos':>6}"
    print(hdr, "\n" + "-" * len(hdr))
    for r in rows:
        print(f"{r['strategy']:16}{r['cagr']:>8.1%}{r['ann_vol']:>8.1%}"
              f"{r['sharpe']:>7.2f}{r['skew']:>7.2f}{r['excess_kurtosis']:>7.2f}"
              f"{r['max_drawdown']:>8.1%}{r['pct_positive']:>6.0%}")
    print(f"\nwrote {OUT/'descriptive_stats.csv'}  ({len(rows)} strategies)")


if __name__ == "__main__":
    main()
