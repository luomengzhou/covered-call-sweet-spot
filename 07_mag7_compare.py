"""Mag7 cross-section on a *common* sample window.

Per-ticker full samples start at different dates (GOOGL binds at 2014-05), so
stitching results/<TICKER>/descriptive_stats.csv etc. is not apples-to-apples.
This script takes the intersection of monthly dates across all Mag7 panels and
recomputes buy&hold descriptives, premium-matched A vs B, and CC skew on that
window only.

Outputs under results/:
  mag7_buyhold_descriptive.csv
  mag7_premium_matched.csv
  mag7_reconciliation.csv          (still full-sample — formula QA, not timed)
  mag7_common_window.txt           start/end + n_months
  mag7_skew_buyhold.png
  mag7_skew_distribution.png
  mag7_skew_vs_selling.png

Usage: .venv/bin/python 07_mag7_compare.py
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _config import DATA, OUT, _CONFIGS

TICKERS = list(_CONFIGS)  # NVDA AAPL GOOGL MSFT AMZN META TSLA
COLORS = {
    "TSLA": "#d62728", "NVDA": "#2ca02c", "MSFT": "#1f77b4", "GOOGL": "#ff7f0e",
    "AMZN": "#9467bd", "META": "#8c564b", "AAPL": "#7f7f7f",
}


def skew_biased(r: np.ndarray) -> float:
    d = r - r.mean()
    m2 = (d ** 2).mean()
    return float((d ** 3).mean() / m2 ** 1.5) if m2 > 0 else np.nan


def kurt_excess(r: np.ndarray) -> float:
    d = r - r.mean()
    m2 = (d ** 2).mean()
    return float((d ** 4).mean() / m2 ** 2 - 3.0) if m2 > 0 else np.nan


def load_rf() -> pd.Series:
    """TB3MS annualized decimal, indexed by month-start Timestamp."""
    rf = pd.read_csv(DATA / "TB3MS.csv")
    rf.columns = ["date", "tb3ms"]
    rf["date"] = pd.to_datetime(rf["date"])
    rf["tb3ms"] = pd.to_numeric(rf["tb3ms"], errors="coerce") / 100.0
    return rf.set_index("date")["tb3ms"].sort_index()


def describe(returns: np.ndarray, rf_annual: np.ndarray, ppy: int = 12) -> dict:
    r = np.asarray(returns, dtype=float)
    n = len(r)
    excess = r - rf_annual / ppy
    downside = math.sqrt(np.mean(np.minimum(excess, 0.0) ** 2)) * math.sqrt(ppy)
    cum = np.r_[1.0, np.cumprod(1 + r)]
    drawdown = float((cum / np.maximum.accumulate(cum) - 1).min())
    cagr = float(np.prod(1 + r) ** (ppy / n) - 1)
    vol = float(r.std(ddof=1) * math.sqrt(ppy))
    return dict(
        n_months=n,
        cagr=cagr,
        ann_vol=vol,
        sharpe=float(excess.mean() / r.std(ddof=1) * math.sqrt(ppy)),
        sortino=float(excess.mean() * ppy / downside) if downside > 0 else np.nan,
        skew=skew_biased(r),
        excess_kurtosis=kurt_excess(r),
        max_drawdown=drawdown,
        calmar=cagr / abs(drawdown) if drawdown != 0 else np.nan,
        pct_positive=float((r > 0).mean()),
        worst_month=float(r.min()),
        best_month=float(r.max()),
    )


def common_dates() -> pd.DatetimeIndex:
    sets = []
    for t in TICKERS:
        p = pd.read_csv(OUT / t / "panel_monthly.csv", parse_dates=["date"])
        mon = p[p["ppy"] == 12]
        s = mon.groupby("date")["bench_ret"].first().dropna()
        sets.append(set(s.index))
    common = sorted(set.intersection(*sets))
    return pd.DatetimeIndex(common)


def bench_on_window(ticker: str, dates: pd.DatetimeIndex) -> pd.Series:
    p = pd.read_csv(OUT / ticker / "panel_monthly.csv", parse_dates=["date"])
    mon = p[p["ppy"] == 12]
    s = mon.groupby("date")["bench_ret"].first().dropna().sort_index()
    return s.reindex(dates).dropna()


def strategy_on_window(ticker: str, index_name: str, dates: pd.DatetimeIndex) -> pd.Series | None:
    p = pd.read_csv(OUT / ticker / "panel_monthly.csv", parse_dates=["date"])
    g = p[(p["index_name"] == index_name) & (p["ppy"] == 12) & (~p["split_artifact"])]
    if not len(g):
        return None
    s = g.set_index("date").sort_index()["index_ret"]
    out = s.reindex(dates).dropna()
    return out if len(out) else None


def rf_for(dates: pd.DatetimeIndex, rf: pd.Series) -> np.ndarray:
    """Forward-fill the latest published monthly rate; never substitute zero."""
    return rf.reindex(pd.DatetimeIndex(dates), method="ffill").to_numpy()


def buyhold_table(dates: pd.DatetimeIndex, rf: pd.Series) -> pd.DataFrame:
    rows = []
    for t in TICKERS:
        s = bench_on_window(t, dates)
        rows.append({"ticker": t, "sample_start": dates.min().strftime("%Y-%m"),
                     "sample_end": dates.max().strftime("%Y-%m"),
                     **describe(s.values, rf_for(s.index, rf))})
    return pd.DataFrame(rows).sort_values("skew", ascending=False).reset_index(drop=True)


def premium_table(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Recompute A vs B premium-match on the common window (logic mirrors 04)."""
    rows = []
    date_set = set(dates)
    for t in TICKERS:
        cfg = _CONFIGS[t]
        panel = pd.read_csv(OUT / t / "panel_monthly.csv", parse_dates=["date"])
        exposure = panel[(panel["family"] == "B") & (~panel["split_artifact"])]
        atm = (exposure.groupby("date")
               .agg(atm_yield=("y_used", "mean"), atm_cap=("cap_used", "mean"))
               .dropna())
        income = panel[(panel["family"] == "A") & (~panel["split_artifact"])]
        for name, g in income.groupby("index_name"):
            g = g.dropna(subset=["y_used", "cap_used"]).merge(atm, on="date")
            g = g[g["date"].isin(date_set)]
            if not len(g):
                continue
            f = g["y_used"] / g["atm_yield"]
            r_B = (1 - f) * g["bench_ret"] + f * (
                np.minimum(g["bench_ret"], g["atm_cap"] - 1) + g["atm_yield"])
            r_A = g["index_ret"]
            feasible = f <= 1.0
            D = (r_A - r_B)[feasible]
            target = round(g["param"].iloc[0] * 100, 3)  # %/mo; 3dp keeps the sub-1% grid distinct
            rows.append(dict(
                ticker=t,
                income_target_pct=target,
                months=len(g),
                months_B_feasible=int(feasible.sum()),
                pct_B_feasible=float(feasible.mean()),
                A_monthly_win_rate=float((D > 0).mean()) if len(D) else np.nan,
                mean_edge_A_over_B_bp=float(D.mean() * 1e4) if len(D) else np.nan,
                cum_return_A=float(np.prod(1 + r_A[feasible])) if feasible.any() else np.nan,
                cum_return_B=float(np.prod(1 + r_B[feasible])) if feasible.any() else np.nan,
            ))
    return (pd.DataFrame(rows)
            .sort_values(["ticker", "income_target_pct"])
            .reset_index(drop=True))


def recon_table() -> pd.DataFrame:
    """Full-sample reconciliation QA (not time-aligned — formula check only)."""
    rows = []
    for t in TICKERS:
        r = pd.read_csv(OUT / t / "reconciliation_report.csv")
        rows.append({
            "ticker": t,
            "n_indices": len(r),
            "mean_abs_bp": float(r["mean_abs_bp"].mean()),
            "median_abs_bp": float(r["mean_abs_bp"].median()),
            "max_abs_bp": float(r["max_abs_bp"].max()),
        })
    return pd.DataFrame(rows)


def cc_skew_on_window(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Buy&hold / Income_1 / Exposure_100 skew on the common window."""
    rows = []
    for t in TICKERS:
        cfg = _CONFIGS[t]
        bh = bench_on_window(t, dates).values
        row = {"ticker": t, "buyhold": skew_biased(bh)}
        for label, name in [("inc1", f"{cfg.cc}_1_Income"),
                            ("exp100", f"{cfg.cc}_100_Exposure")]:
            s = strategy_on_window(t, name, dates)
            row[label] = skew_biased(s.values) if s is not None else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def chart_skew_bars(buyhold: pd.DataFrame, dates: pd.DatetimeIndex) -> None:
    bh = buyhold.sort_values("skew", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    colors = [COLORS[t] for t in bh["ticker"]]
    bars = ax.bar(bh["ticker"], bh["skew"], color=colors, edgecolor="k", lw=0.4)
    ax.axhline(0, color="k", lw=0.8)
    for bar, v in zip(bars, bh["skew"]):
        ax.text(bar.get_x() + bar.get_width() / 2, v + (0.03 if v >= 0 else -0.06),
                f"{v:+.2f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=10)
    ax.set_ylabel("monthly return skewness (biased)")
    ax.set_title(f"Mag7 buy&hold skew — common window "
                 f"{dates.min():%Y-%m} → {dates.max():%Y-%m} (n={len(dates)})\n"
                 "A vs B preference tracks this ordering")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "mag7_skew_buyhold.png", dpi=150)
    plt.close(fig)


def chart_skew_distribution(dates: pd.DatetimeIndex, buyhold: pd.DataFrame) -> None:
    order = buyhold.sort_values("skew", ascending=False)["ticker"].tolist()
    fig, axes = plt.subplots(2, 4, figsize=(18, 8), sharex=True, sharey=True)
    axes = axes.ravel()
    for i, t in enumerate(order):
        r = bench_on_window(t, dates).values
        ax = axes[i]
        ax.hist(r, bins=35, density=True, color=COLORS[t], alpha=0.75,
                edgecolor="white", lw=0.3)
        ax.axvline(0, color="k", lw=0.6)
        ax.axvline(r.mean(), color="k", ls="--", lw=0.8)
        sk = skew_biased(r)
        ax.set_title(f"{t}  skew={sk:+.2f}\n"
                     f"best={r.max():+.0%}  worst={r.min():+.0%}", fontsize=10)
        ax.grid(True, alpha=0.25)
    axes[-1].axis("off")
    fig.suptitle(
        f"Mag7 monthly return distributions (buy&hold) — "
        f"{dates.min():%Y-%m} → {dates.max():%Y-%m}\n"
        "right-tail fatness (TSLA/NVDA) is what makes partial-ATM (B) win",
        fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT / "mag7_skew_distribution.png", dpi=150)
    plt.close(fig)


def chart_skew_vs_selling(cc_skew: pd.DataFrame, dates: pd.DatetimeIndex) -> None:
    df = cc_skew.set_index("ticker").loc[
        cc_skew.sort_values("buyhold", ascending=False)["ticker"]
    ].reset_index()
    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(df))
    w = 0.28
    ax.bar(x - w, df["buyhold"], w, color=[COLORS[t] for t in df["ticker"]],
           label="buy&hold", edgecolor="k", lw=0.3)
    ax.bar(x, df["inc1"], w, color="tab:orange", alpha=0.85,
           label="Income 1% (full OTM)", edgecolor="k", lw=0.3)
    ax.bar(x + w, df["exp100"], w, color="navy", alpha=0.85,
           label="Exposure 100% (ATM)", edgecolor="k", lw=0.3)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(df["ticker"])
    ax.set_ylabel("skewness")
    ax.set_title(f"Selling calls drives skew negative everywhere — "
                 f"{dates.min():%Y-%m} → {dates.max():%Y-%m}\n"
                 "(buy&hold → covered-call −1 to −3)")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "mag7_skew_vs_selling.png", dpi=150)
    plt.close(fig)


def main() -> None:
    dates = common_dates()
    rf = load_rf()
    (OUT / "mag7_common_window.txt").write_text(
        f"common_start={dates.min():%Y-%m-%d}\n"
        f"common_end={dates.max():%Y-%m-%d}\n"
        f"n_months={len(dates)}\n"
        f"binding_ticker=GOOGL (latest Mag7 start)\n"
        "note: buyhold/premium/skew recomputed on this intersection; "
        "reconciliation stays full-sample (formula QA).\n"
    )

    buyhold = buyhold_table(dates, rf)
    premium = premium_table(dates)
    recon = recon_table()
    cc_skew = cc_skew_on_window(dates)

    buyhold.to_csv(OUT / "mag7_buyhold_descriptive.csv", index=False)
    premium.to_csv(OUT / "mag7_premium_matched.csv", index=False)
    recon.to_csv(OUT / "mag7_reconciliation.csv", index=False)
    # drop the misleading full-sample stitch if present
    stale = OUT / "mag7_metrics_full.csv"
    if stale.exists():
        stale.unlink()

    chart_skew_bars(buyhold, dates)
    chart_skew_distribution(dates, buyhold)
    chart_skew_vs_selling(cc_skew, dates)

    print(f"common window: {dates.min():%Y-%m} → {dates.max():%Y-%m}  (n={len(dates)})")
    print("\n== Mag7 buy&hold (by skew, common window) ==")
    print(buyhold[["ticker", "skew", "sharpe", "ann_vol", "cagr", "max_drawdown"]]
          .to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("\n== premium edge A−B @ 1% (bp, common window) ==")
    p1 = premium[premium["income_target_pct"] == 1]
    # print in skew order
    order = buyhold["ticker"].tolist()
    p1 = p1.set_index("ticker").loc[[t for t in order if t in p1["ticker"].values]].reset_index()
    print(p1[["ticker", "mean_edge_A_over_B_bp", "cum_return_A", "cum_return_B"]]
          .to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    print(f"\nwrote CSVs + 3 skew charts → {OUT}/")


if __name__ == "__main__":
    main()
