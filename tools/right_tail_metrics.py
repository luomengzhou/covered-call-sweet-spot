"""Right-tail metrics for the Mag7 underlyings, on the common window.

Excess kurtosis is symmetric, so on its own it says nothing about the right
tail -- MSFT carries the highest excess kurtosis of the seven names and one of
the smallest right tails. These are the measures that actually separate the
names on "does it gap up", which is what decides whether B's convexity
survives delta matching (see delta_matched_benchmark.csv).

Window and series construction mirror 07_mag7_compare.py exactly (monthly rows
only, intersected across the seven names), so the skew column here reproduces
mag7_buyhold_descriptive.csv.

Usage: python3 tools/right_tail_metrics.py
Writes: results/mag7_righttail_metrics.csv
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _config import _CONFIGS  # noqa: E402

TICKERS = list(_CONFIGS)
OUT = ROOT / "results"
DECILE = 0.10


def monthly_bench(ticker: str) -> pd.Series:
    p = pd.read_csv(OUT / ticker / "panel_monthly.csv", parse_dates=["date"])
    mon = p[p["ppy"] == 12]
    return mon.groupby("date")["bench_ret"].first().dropna()


def skew_biased(r: np.ndarray) -> float:
    """Population skew, matching skew_biased() in 07_mag7_compare.py.

    pandas' .skew() applies the bias correction, which shifts TSLA from 0.946
    to 0.96 and would not reconcile with mag7_buyhold_descriptive.csv.
    """
    d = r - r.mean()
    m2 = (d ** 2).mean()
    return float((d ** 3).mean() / m2 ** 1.5) if m2 > 0 else np.nan


def metrics(r: np.ndarray) -> dict:
    k = int(np.ceil(len(r) * DECILE))
    top, bot = np.sort(r)[-k:], np.sort(r)[:k]
    dev = r - r.mean()
    up = np.sqrt(np.mean(np.maximum(dev, 0) ** 2))
    dn = np.sqrt(np.mean(np.minimum(dev, 0) ** 2))
    return dict(
        n=len(r),
        pct_months_gt20=100 * np.mean(r > 0.20),
        pct_months_gt30=100 * np.mean(r > 0.30),
        mean_top_decile=100 * top.mean(),
        mean_bottom_decile=100 * bot.mean(),
        tail_ratio=top.mean() / abs(bot.mean()),
        upside_semidev=100 * up,
        downside_semidev=100 * dn,
        semidev_ratio=up / dn,
        best_month=100 * r.max(),
        skew=skew_biased(r),
    )


def main() -> None:
    series = {t: monthly_bench(t) for t in TICKERS}
    common = pd.DatetimeIndex(sorted(set.intersection(*(set(s.index) for s in series.values()))))
    print(f"common window {common.min():%Y-%m} -> {common.max():%Y-%m}  n={len(common)}\n")

    rows = [dict(ticker=t, **metrics(series[t].loc[common].to_numpy())) for t in TICKERS]
    out = pd.DataFrame(rows).sort_values("tail_ratio", ascending=False)
    out.round(4).to_csv(OUT / "mag7_righttail_metrics.csv", index=False)
    print(out.round(2).to_string(index=False))
    print("\nwrote results/mag7_righttail_metrics.csv")


if __name__ == "__main__":
    main()
