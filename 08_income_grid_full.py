"""Step 8 — one complete Income-grid table per ticker, sub-1%/mo tiers included.

Everything the study computes about an Income tier used to live in separate files
(descriptive/metrics per ticker, premium-matched A-vs-B per ticker and on the
common window, the AQR delta-matched benchmark, the wing_z rule audit), and the
add-on analyses only ever ran the 1%/3% pair. This step joins them into a single
row per (ticker, Income tier) across the whole grid — 0.083%/mo up to 15%/mo —
and adds the one number that was previously computed ad hoc: the paired
bootstrap CI on Sharpe vs buy-and-hold.

Inputs (all committed, no network):
  results/<T>/panel_monthly.csv        monthly returns, for the bootstrap
  results/<T>/metrics_summary.csv      income_pa, pct_capped, risk/return (period=full)
  results/<T>/premium_matched_comparison.csv   A-vs-B, own full sample
  results/mag7_premium_matched.csv     A-vs-B, common window (2014-05 -> 2026-07)
  results/delta_matched_benchmark.csv  AQR delta-matched net edge
  results/06_wing_signal_audit_bynames.csv     wing_z rule vs always-B
  results/<T>/switch_signal_screen.csv momentum A<->B switch screen (step 05)

Outputs:
  results/mag7_income_grid_full.csv    the joined grid, one row per ticker x tier
  results/mag7_income_grid_full.png    heatmaps of the three headline columns
  (the Markdown write-up is results/MAG7_INCOME_GRID.md, kept by hand)

Run after 01-05 for every ticker, plus 06_delta_matched_benchmark.py and
tools/plot_wing_signal_audit.py, which supply three of the joined columns.

Usage: .venv/bin/python 08_income_grid_full.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from _config import _CONFIGS, income_pct, target_label

# Figure text is English (reporting language); DejaVu carries the true minus sign.
plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = True

ROOT = Path(__file__).parent
RES = ROOT / "results"
N_BOOT = 4000
SEED = 0

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"


# ------------------------------------------------------------------ bootstrap
def sharpe(r: np.ndarray, rf_m: np.ndarray) -> float:
    sd = r.std(ddof=1)
    return float((r - rf_m).mean() / sd * np.sqrt(12)) if sd > 0 else np.nan


def sharpe_vs_bench(
    r: np.ndarray, bench: np.ndarray, rf_m: np.ndarray, rng: np.random.Generator
) -> dict:
    """Paired iid bootstrap on the Sharpe difference (strategy - buy&hold)."""
    diff = sharpe(r, rf_m) - sharpe(bench, rf_m)
    n = len(r)
    draws = np.empty(N_BOOT)
    for i in range(N_BOOT):
        idx = rng.integers(0, n, n)          # same months for both legs
        draws[i] = sharpe(r[idx], rf_m[idx]) - sharpe(bench[idx], rf_m[idx])
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return dict(d_sharpe_vs_bh=diff, d_sharpe_ci_lo=lo, d_sharpe_ci_hi=hi,
                p_better_than_bh=float(np.nanmean(draws > 0)))


# ------------------------------------------------------------------ the join
def build() -> pd.DataFrame:
    common = pd.read_csv(RES / "mag7_premium_matched.csv")
    delta = pd.read_csv(RES / "delta_matched_benchmark.csv")
    wing = pd.read_csv(RES / "06_wing_signal_audit_bynames.csv")
    wing[["w_ticker", "w_tgt"]] = wing["cell"].str.split(" ", expand=True)

    rows = []
    for ticker, cfg in _CONFIGS.items():
        panel = pd.read_csv(RES / ticker / "panel_monthly.csv", parse_dates=["date"])
        met = pd.read_csv(RES / ticker / "metrics_summary.csv")
        met_full = met[met["period"] == "full"].set_index("index_name")
        own = pd.read_csv(RES / ticker / "premium_matched_comparison.csv")
        screen_path = RES / ticker / "switch_signal_screen.csv"
        screen = pd.read_csv(screen_path) if screen_path.exists() else pd.DataFrame()
        bench_row = met_full.loc[cfg.bench_name]

        # buy&hold monthly path and the risk-free leg, shared by every tier
        bench_m = (panel.groupby("date")
                   .agg(bench_ret=("bench_ret", "first"), rf=("rf_3m", "first")))
        rng = np.random.default_rng(SEED)

        for tgt in cfg.switch_targets:
            g = panel[panel["index_name"] == tgt].set_index("date").sort_index()
            if g.empty or tgt not in met_full.index:
                print(f"[skip] {ticker} {tgt}: absent from panel/metrics")
                continue
            m = met_full.loc[tgt]
            pair = g[["index_ret"]].join(bench_m, how="inner").dropna()
            # rf is quoted annually at month start; the return row it prices is the next one
            rf_m = (pair["rf"].shift(1) / 12).to_numpy()
            ok = np.isfinite(rf_m)
            boot = sharpe_vs_bench(pair["index_ret"].to_numpy()[ok],
                                   pair["bench_ret"].to_numpy()[ok], rf_m[ok], rng)

            pct = income_pct(tgt)
            o = own[np.isclose(own["income_target_pct"], pct)]
            c = common[(common["ticker"] == ticker)
                       & np.isclose(common["income_target_pct"], pct)]
            d = delta[(delta["ticker"] == ticker) & np.isclose(delta["target_pct"], pct)]
            w = wing[(wing["w_ticker"] == ticker) & (wing["w_tgt"] == target_label(tgt))]
            sc = (screen[np.isclose(screen["target_pct"], pct)] if len(screen)
                  else pd.DataFrame(columns=["sharpe_mom_switch", "sharpe_always_B"]))
            pick = lambda df, col: float(df[col].iloc[0]) if len(df) and pd.notna(df[col].iloc[0]) else np.nan

            rows.append(dict(
                ticker=ticker, target=target_label(tgt), target_pct=pct,
                n_months=int(m["n_months"]),
                income_pa=m["income_pa"], pct_capped=m["pct_capped"],
                cagr=m["cagr"], ann_vol=m["ann_vol"], sharpe=m["sharpe"],
                calmar=m["calmar"], skew=m["skew"], max_dd=m["max_dd"],
                bh_cagr=bench_row["cagr"], bh_sharpe=bench_row["sharpe"],
                **{k: round(v, 4) for k, v in boot.items()},
                edge_A_over_B_bp_own=pick(o, "mean_edge_A_over_B_bp"),
                A_win_rate_own=pick(o, "A_monthly_win_rate"),
                pct_B_feasible_own=pick(o, "pct_B_feasible"),
                edge_A_over_B_bp_common=pick(c, "mean_edge_A_over_B_bp"),
                pct_B_feasible_common=pick(c, "pct_B_feasible"),
                delta_matched_net_edge_B_bp=pick(d, "net_edge_B_bp"),
                wing_rule_minus_B_bp=pick(w, "rule_minus_alwaysB_bp_per_month"),
                wing_rule_t=pick(w, "t_vs_alwaysB"),
                mom_switch_sharpe_minus_B=round(
                    pick(sc, "sharpe_mom_switch") - pick(sc, "sharpe_always_B"), 3),
            ))
    out = pd.DataFrame(rows).sort_values(["ticker", "target_pct"]).reset_index(drop=True)
    return out


# ------------------------------------------------------------------ heatmaps
def heatmaps(grid: pd.DataFrame, path: Path) -> None:
    panels = [
        ("d_sharpe_vs_bh", "Sharpe − buy&hold", "{:+.3f}", 0.10),
        ("edge_A_over_B_bp_own", "A − B edge (bp/mo, own sample)", "{:+.0f}", 60),
        ("wing_rule_minus_B_bp", "wing rule − always B (bp/mo)", "{:+.0f}", 30),
    ]
    tickers = sorted(grid["ticker"].unique())
    cols = sorted(grid["target_pct"].unique())
    labels = [grid.loc[grid["target_pct"] == c, "target"].iloc[0] for c in cols]

    fig, axes = plt.subplots(len(panels), 1, figsize=(1.05 * len(cols) + 3.2, 12.6),
                             facecolor=SURFACE)
    fig.subplots_adjust(left=0.085, right=0.985, top=0.915, bottom=0.075, hspace=0.42)
    fig.text(0.085, 0.964, "The complete Income grid, sub-1%/mo tiers included",
             fontsize=16, color=INK, weight="bold")
    fig.text(0.085, 0.937,
             "Blank = tier not in that name's data set, or the add-on analysis needs "
             "more months than the tier has.",
             fontsize=9.5, color=INK2)

    for ax, (col, title, fmt, vmax) in zip(axes, panels):
        M = np.full((len(tickers), len(cols)), np.nan)
        for i, t in enumerate(tickers):
            for j, c in enumerate(cols):
                v = grid[(grid["ticker"] == t) & (grid["target_pct"] == c)][col]
                if len(v) and pd.notna(v.iloc[0]):
                    M[i, j] = v.iloc[0]
        ax.set_facecolor(SURFACE)
        ax.imshow(M, cmap="RdBu", vmin=-vmax, vmax=vmax, aspect="auto")
        ax.set_xticks(range(len(cols)), labels, fontsize=8.5, color=INK2, rotation=45,
                      ha="right")
        ax.set_yticks(range(len(tickers)), tickers, fontsize=9, color=INK)
        ax.set_title(title, fontsize=11.5, color=INK, loc="left", pad=7)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(length=0)
        for i in range(len(tickers)):
            for j in range(len(cols)):
                if np.isfinite(M[i, j]):
                    ax.text(j, i, fmt.format(M[i, j]), ha="center", va="center",
                            fontsize=7.4,
                            color=INK if abs(M[i, j]) < vmax * 0.55 else SURFACE)
    axes[-1].set_xlabel("Monthly premium target", fontsize=9.5, color=MUTED, labelpad=8)
    fig.savefig(path, dpi=170, facecolor=SURFACE)
    print(f"wrote {path}")


def main() -> None:
    grid = build()
    out = RES / "mag7_income_grid_full.csv"
    grid.round(6).to_csv(out, index=False)
    print(f"wrote {out}  ({len(grid)} ticker x tier rows, "
          f"{(grid['target_pct'] < 1).sum()} of them sub-1%/mo)")
    heatmaps(grid, RES / "mag7_income_grid_full.png")

    pd.set_option("display.width", 250)
    show = ["ticker", "target", "income_pa", "pct_capped", "cagr", "sharpe",
            "d_sharpe_vs_bh", "d_sharpe_ci_lo", "d_sharpe_ci_hi",
            "edge_A_over_B_bp_own", "edge_A_over_B_bp_common",
            "delta_matched_net_edge_B_bp", "wing_rule_minus_B_bp"]
    print(grid[show].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
