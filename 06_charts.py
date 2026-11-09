"""Step 6 — the seven summary charts (reproducible, ticker-parametrized).

Reads results/<TICKER>/panel_monthly.csv (+ metrics_summary.csv) and writes:
  cumulative_growth.png     Growth of $1, log scale
  risk_return_scatter.png   ann-vol vs CAGR, every variant on one ray from buy&hold
  skew_distribution.png     return histogram + skew-vs-parameter (the +→− flip)
  by_market_state.png       return by underlying-move bucket + drag by IV tertile
  by_era_cagr.png           CAGR by era, grouped bars
  correlation_heatmap.png   monthly-return correlation among variants
  call_spread_shape.png     premium-matched A−B vs underlying return (the payoff shape)

These were previously produced by ad-hoc code that was never saved; this script
regenerates them for any ticker. Usage:
    .venv/bin/python 06_charts.py                 # NVDA
    TICKER=AAPL .venv/bin/python 06_charts.py      # Apple
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _config import get_config

CFG = get_config()
OUT = CFG.out_dir
BENCH = CFG.ticker  # label for the underlying buy&hold

# fixed era windows (match 02_metrics_frontier.SUBPERIODS)
ERAS = [("2008-01-01", "2015-12-31", "2008-2015"),
        ("2016-01-01", "2021-12-31", "2016-2021"),
        ("2022-01-01", "2022-12-31", "2022 bear"),
        ("2023-01-01", "2026-12-31", "2023-2026 AI")]


def skew_biased(r: np.ndarray) -> float:
    """Biased moment skewness (matches 03_descriptive_stats)."""
    d = r - r.mean()
    m2 = (d ** 2).mean()
    return (d ** 3).mean() / m2 ** 1.5 if m2 > 0 else np.nan


def load():
    panel = pd.read_csv(OUT / "panel_monthly.csv", parse_dates=["date"])
    monthly = panel[panel["ppy"] == 12].copy()
    bench = monthly.groupby("date")["bench_ret"].first().sort_index()  # underlying total return
    return panel, monthly, bench


def series(monthly: pd.DataFrame, name: str) -> pd.Series | None:
    """Monthly index_ret series for one strategy, or None if absent."""
    g = monthly[monthly["index_name"] == name]
    return g.set_index("date").sort_index()["index_ret"] if len(g) else None


def income(n: int) -> str:
    return f"{CFG.cc}_{n}_Income"


def exposure(n: int) -> str:
    return f"{CFG.cc}_{n}_Exposure"


# ----------------------------------------------------------------------------- charts
def chart_cumulative(monthly, bench):
    picks = [(income(1), "Income_1", "wheat"), (income(5), "Income_5", "tab:orange"),
             (income(12), "Income_12", "tab:red"), (exposure(50), "Exposure_50", "tab:blue"),
             (exposure(100), "Exposure_100", "navy")]
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(bench.index, (1 + bench).cumprod(), color="tab:green", lw=2.5, label=BENCH)
    for name, label, color in picks:
        s = series(monthly, name)
        if s is not None:
            ax.plot(s.index, (1 + s).cumprod(), color=color, lw=1.2, label=label)
    ax.set_yscale("log")
    ax.set_title(f"Growth of $1 (log scale), {bench.index.min():%Y}-{bench.index.max():%Y}")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout(); fig.savefig(OUT / "cumulative_growth.png", dpi=150); plt.close(fig)


def chart_risk_return(metrics):
    m = metrics[metrics["period"] == "full"]
    fam = {"A": ("Income", "tab:orange"), "B": ("Exposure", "tab:blue"),
           "A_delta": ("Delta", "tab:purple"), "BD": ("Coverage×Delta", "tab:brown")}
    fig, ax = plt.subplots(figsize=(11, 8))
    for f, (label, color) in fam.items():
        g = m[m["family"] == f]
        if not len(g):
            continue
        ax.scatter(g["ann_vol"], g["cagr"], s=90, color=color, label=label, zorder=3)
        for _, r in g.iterrows():
            ax.annotate(f"{int(round(r['param'] * 100))}", (r["ann_vol"], r["cagr"]),
                        fontsize=7, xytext=(4, -2), textcoords="offset points")
    bh = m[m["index_name"] == CFG.bench_name]
    if len(bh):
        ax.scatter(bh["ann_vol"], bh["cagr"], marker="*", s=350, color="tab:green",
                   edgecolor="k", label=BENCH, zorder=4)
        ax.annotate(BENCH, (bh["ann_vol"].iloc[0], bh["cagr"].iloc[0]), fontweight="bold",
                    fontsize=12, xytext=(-55, 2), textcoords="offset points")
    ax.set_xlabel("annualized volatility"); ax.set_ylabel("CAGR")
    ax.set_title(f"Risk-Return: every covered call sits BELOW & LEFT of {BENCH}\n"
                 "(less vol, but less return — roughly same Sharpe ray)")
    ax.grid(True, alpha=0.3); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "risk_return_scatter.png", dpi=150); plt.close(fig)


def chart_skew(monthly, bench):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 6.5))
    # left: return distribution
    bh = bench.values
    ax1.hist(bh, bins=40, density=True, alpha=0.5, color="tab:green",
             label=f"{BENCH} buy&hold  (skew={skew_biased(bh):+.2f})")
    for name, label, color in [(income(5), "Income 5%", "tab:orange"),
                               (income(12), "Income 12%", "tab:red")]:
        s = series(monthly, name)
        if s is not None:
            ax1.hist(s.values, bins=40, density=True, alpha=0.5, color=color,
                     label=f"{label}  (skew={skew_biased(s.values):+.2f})")
    ax1.axvline(bh.mean(), color="tab:green", ls="--", lw=1)
    ax1.annotate("crash months\nleft intact", (bh.min(), 0.3), fontsize=9,
                 xytext=(bh.min() + 0.05, 3), arrowprops=dict(arrowstyle="->", color="gray"))
    ax1.annotate("big up-months\nchopped off", (bh.max() * 0.7, 0.3), color="tab:red", fontsize=9,
                 xytext=(bh.max() * 0.55, 3), arrowprops=dict(arrowstyle="->", color="tab:red"))
    ax1.set_xlabel("monthly return"); ax1.set_ylabel("density")
    ax1.set_title("Monthly return distribution: selling calls shaves the\n"
                  "right tail, keeps the left tail -> negative skew")
    ax1.legend()
    # right: skew vs parameter
    for fam_fn, fam_vals, label, color, mk in [
            (income, (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 15), "Income (target yield %)", "tab:orange", "o"),
            (exposure, (10, 20, 30, 40, 50, 60, 70, 80, 90, 100), "Exposure (coverage %)", "tab:blue", "s")]:
        xs, ys = [], []
        for n in fam_vals:
            s = series(monthly, fam_fn(n))
            if s is not None:
                xs.append(n); ys.append(skew_biased(s.values))
        if xs:
            ax2.plot(xs, ys, mk + "-", color=color, label=label)
    ax2.axhline(skew_biased(bh), color="tab:green", ls="--", label=f"{BENCH} buy&hold ({skew_biased(bh):+.2f})")
    ax2.axhline(0, color="gray", lw=0.8)
    ax2.set_xlabel("parameter (Income target% / Exposure coverage%)"); ax2.set_ylabel("skewness")
    ax2.set_title("More selling -> more negative skew:\nthe positive->negative flip")
    ax2.legend()
    fig.tight_layout(); fig.savefig(OUT / "skew_distribution.png", dpi=150); plt.close(fig)


def chart_market_state(panel, monthly, bench):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 6.5))
    # left: mean return by underlying-move bucket
    edges = [-1, -0.10, 0.0, 0.10, 0.20, 10]
    labels = ["< -10%", "-10~0%", "0~10%", "10~20%", ">20%"]
    buckets = pd.cut(bench, edges, labels=labels)
    picks = [(None, BENCH, "tab:green", bench), (income(5), "Income_5", "tab:orange", None),
             (exposure(100), "Exposure_100", "navy", None)]
    for name, label, color, override in picks:
        s = override if override is not None else series(monthly, name)
        if s is None:
            continue
        s = s.reindex(bench.index)
        means = s.groupby(buckets, observed=False).mean()
        ax1.plot(range(len(labels)), [means.get(l, np.nan) for l in labels], "o-", color=color, label=label)
    ax1.axhline(0, color="k", lw=0.8); ax1.set_xticks(range(len(labels))); ax1.set_xticklabels(labels)
    ax1.set_xlabel(f"{BENCH} return bucket that month"); ax1.set_ylabel("mean monthly return")
    ax1.set_title(f"Return by {BENCH}-move bucket: covered calls track {BENCH}\n"
                  "downside fully, but cap the upside (esp. >20% months)")
    ax1.legend()
    # right: drag vs underlying by implied-vol tertile
    iv = monthly.groupby("date")["atm_yield_next"].first().reindex(bench.index)
    iv_prev = iv.shift(1)  # month-start observable
    tert = pd.qcut(iv_prev.dropna(), 3, labels=["low IV", "mid IV", "high IV"])
    bars = {}
    for name, label in [(income(5), "Income_5"), (exposure(100), "Exposure_100")]:
        s = series(monthly, name)
        if s is None:
            continue
        drag = (s.reindex(bench.index) - bench)
        bars[label] = drag.groupby(tert, observed=False).mean()
    if bars:
        x = np.arange(3); w = 0.38
        for i, (label, vals) in enumerate(bars.items()):
            color = "tab:orange" if "Income" in label else "navy"
            ax2.bar(x + (i - 0.5) * w, [vals.get(t, np.nan) for t in ["low IV", "mid IV", "high IV"]],
                    w, color=color, label=label)
        ax2.set_xticks(x); ax2.set_xticklabels(["low IV", "mid IV", "high IV"])
    ax2.set_xlabel("implied-vol regime (ATM call yield tertiles)")
    ax2.set_ylabel(f"avg monthly return  minus {BENCH}")
    ax2.set_title("Relative drag vs underlying by IV regime")
    ax2.legend()
    fig.tight_layout(); fig.savefig(OUT / "by_market_state.png", dpi=150); plt.close(fig)


def chart_by_era(metrics):
    picks = [(CFG.bench_name, BENCH, "tab:green"), (income(5), "Income_5", "tab:orange"),
             (income(12), "Income_12", "tab:red"), (exposure(50), "Exposure_50", "tab:blue"),
             (exposure(100), "Exposure_100", "navy")]
    key = {"2008-2015": "2008-2015", "2016-2021": "2016-2021",
           "2022 bear": "2022_bear", "2023-2026 AI": "2023-2026_ai"}
    era_labels = [e[2] for e in ERAS]
    fig, ax = plt.subplots(figsize=(14, 7))
    x = np.arange(len(era_labels)); w = 0.16
    present = [(n, l, c) for n, l, c in picks if len(metrics[metrics["index_name"] == n])]
    for i, (name, label, color) in enumerate(present):
        vals = []
        for el in era_labels:
            row = metrics[(metrics["index_name"] == name) & (metrics["period"] == key[el])]
            vals.append(row["cagr"].iloc[0] if len(row) else np.nan)
        ax.bar(x + (i - (len(present) - 1) / 2) * w, vals, w, color=color, label=label)
    ax.axhline(0, color="k", lw=0.8); ax.set_xticks(x); ax.set_xticklabels(era_labels)
    ax.set_ylabel("CAGR (annualized)")
    ax.set_title("By era: covered calls keep up in flat/bear years,\nfall behind in the bull")
    ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "by_era_cagr.png", dpi=150); plt.close(fig)


def chart_correlation(monthly):
    names = [(CFG.bench_name, BENCH)]
    wide = {}
    bench_s = monthly.groupby("date")["bench_ret"].first()
    wide[BENCH] = bench_s
    for n in (1, 5, 9, 12):
        s = series(monthly, income(n))
        if s is not None:
            wide[f"Income_{n}"] = s
    for n in (10, 20, 50, 100):
        s = series(monthly, exposure(n))
        if s is not None:
            wide[f"Exposure_{n}"] = s
    for d in (30, 50, 70):
        s = series(monthly, f"{CFG.cc}_Delta_{d}")
        if s is not None:
            wide[f"Delta_{d}"] = s
    df = pd.DataFrame(wide).dropna()
    corr = df.corr()
    fig, ax = plt.subplots(figsize=(1.1 * len(corr) + 2, 1.0 * len(corr) + 1))
    im = ax.imshow(corr, cmap="RdYlGn", vmin=0.5, vmax=1.0)
    ax.set_xticks(range(len(corr))); ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr))); ax.set_yticklabels(corr.index)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title(f"Monthly return correlation (all high: same {BENCH} beta engine)")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout(); fig.savefig(OUT / "correlation_heatmap.png", dpi=150); plt.close(fig)


def chart_call_spread(panel):
    """Premium-matched A-B (Income 1%) vs underlying return — the payoff shape."""
    exp = panel[(panel["family"] == "B") & (~panel["split_artifact"])]
    atm = exp.groupby("date").agg(atm_yield=("y_used", "mean"), atm_cap=("cap_used", "mean")).dropna()
    g = panel[(panel["index_name"] == income(1)) & (~panel["split_artifact"])]
    g = g.dropna(subset=["y_used", "cap_used"]).merge(atm, on="date")
    if not len(g):
        return
    f = g["y_used"] / g["atm_yield"]
    r_A = g["index_ret"]
    r_B = (1 - f) * g["bench_ret"] + f * (np.minimum(g["bench_ret"], g["atm_cap"] - 1) + g["atm_yield"])
    feasible = f <= 1.0
    x = g["bench_ret"][feasible].values * 100
    D = (r_A - r_B)[feasible].values * 100
    order = np.argsort(x); x, D = x[order], D[order]
    # binned mean
    bins = np.array([-100, -20, -10, -3, 0, 3, 8, 13, 18, 25, 35, 100])
    idx = np.clip(np.digitize(x, bins) - 1, 0, len(bins) - 2)
    centers, bmean = [], []
    for b in range(len(bins) - 1):
        sel = idx == b
        if sel.sum() >= 2:
            centers.append(x[sel].mean()); bmean.append(D[sel].mean())
    # crossover: last up-side bin center where binned mean is still >= 0
    rstar = next((c for c, m in zip(centers, bmean) if c > 0 and m < 0), 15.0)
    fig, ax = plt.subplots(figsize=(14, 7.5))
    ax.axhline(0, color="k", lw=0.8); ax.axvline(0, color="gray", ls=":", lw=1)
    ax.axvspan(x.min() - 2, 0, color="gray", alpha=0.08)
    ax.axvspan(0, rstar, color="tab:green", alpha=0.08)
    ax.axvspan(rstar, x.max() + 2, color="tab:red", alpha=0.08)
    ax.axvline(rstar, color="tab:red", ls="--", lw=1)
    ax.scatter(x, D, s=14, color="tab:blue", alpha=0.5)
    ax.plot(centers, bmean, "o-", color="tab:orange", lw=2, label="binned mean D")
    ax.annotate(f"crossover r* ~ {rstar:.0f}%", (rstar, 0), color="tab:red", fontsize=9,
                xytext=(rstar + 5, D.max() * 0.5), arrowprops=dict(arrowstyle="->", color="tab:red"))
    ax.text(x.min() * 0.5, D.max() * 0.9, f"tie\n({BENCH} down)", color="gray", ha="center", fontweight="bold")
    ax.text(rstar / 2, D.max() * 0.9, "A wins\n(moderate up)", color="tab:green", ha="center", fontweight="bold")
    ax.text(x.max() * 0.7, D.min() * 0.7, "B wins big\n(huge up)", color="tab:red", ha="center", fontweight="bold")
    ax.set_xlabel(f"{BENCH} monthly return (%)")
    ax.set_ylabel("D = full-OTM(A) minus partial-ATM(B), monthly (%)")
    ax.set_title(f"The zero-cost call spread, in data (Income 1%, premium-matched)\n"
                 "A beats B in moderate-up months; B wins big in huge-up months; tie on downside")
    ax.legend(loc="lower left")
    fig.tight_layout(); fig.savefig(OUT / "call_spread_shape.png", dpi=150); plt.close(fig)


def main():
    panel, monthly, bench = load()
    metrics = pd.read_csv(OUT / "metrics_summary.csv")
    chart_cumulative(monthly, bench)
    chart_risk_return(metrics)
    chart_skew(monthly, bench)
    chart_market_state(panel, monthly, bench)
    chart_by_era(metrics)
    chart_correlation(monthly)
    chart_call_spread(panel)
    print(f"[{CFG.ticker}] wrote 7 charts to {OUT}/")


if __name__ == "__main__":
    main()
