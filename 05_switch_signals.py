"""Step 5 — Does a z-score switch between A and B add value? (Uday's z-score idea, tested.)

Question: at the start of each month, can an observable signal (momentum, implied vol,
realized vol, VRP, rate), z-scored, tell us whether to run strategy A (full-notional OTM)
or B (matched partial-ATM) that month — and does switching beat just always-B?

Two tests:
  (1) SIGNAL SCREEN: corr(signal_z, D) and corr(signal_z, next NVDA return), plus mean D
      by signal tertile. A useful signal must actually separate A-win from B-win months.
  (2) SWITCH BACKTEST: a momentum rule (expanding, lagged z -> no lookahead) vs always-A,
      always-B, and an ORACLE (hindsight best) that bounds the achievable prize.

Key context (theory §11): the A<->B choice is an equity-timing overlay, which AQR shows is
largely uncompensated. If no signal predicts, a switch just adds risk.

Usage: python 05_switch_signals.py   (reads results/panel_monthly.csv)
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from _config import get_config, income_pct, target_label

CFG = get_config()
OUT = CFG.out_dir


def matched_BD(
    panel: pd.DataFrame, income_name: str, *, with_signals: bool = True
) -> pd.DataFrame:
    """Return feasible premium-matched A/B months, optionally with signals."""
    atm = (panel[(panel["family"] == "B") & (~panel["split_artifact"])]
           .groupby("date").agg(atm_yield=("y_used", "mean"), atm_cap=("cap_used", "mean")).dropna())
    monthly_dates = (
        panel.loc[panel["ppy"] == 12, "date"].drop_duplicates().sort_values().reset_index(drop=True)
    )
    prior_rebalance = dict(zip(monthly_dates.iloc[1:], monthly_dates.iloc[:-1]))
    g = (panel[panel["index_name"] == income_name]
         .dropna(subset=["y_used", "cap_used"]).merge(atm, on="date"))
    rate = (
        panel[panel["ppy"] == 12].groupby("date")["rf_3m"].first().sort_index().shift(1)
        .rename("rf")
    )
    g = g.merge(rate.dropna().reset_index(), on="date")
    if with_signals:
        state = (panel[panel["ppy"] == 12].groupby("date")
                 .agg(mom=("mom_12_1", "first"), real_vol=("real_vol_12m", "first"),
                      sigma_impl=("sigma_impl_next", "first")))
        # On row t, D is realized over (t-1,t]. Momentum is already lagged;
        # the other month-end values must move to the next return row.
        state[["real_vol", "sigma_impl"]] = state[["real_vol", "sigma_impl"]].shift(1)
        g = g.merge(state.dropna().reset_index(), on="date")
    g["rebalance_date"] = g["date"].map(prior_rebalance)
    f = g["y_used"] / g["atm_yield"]
    g["r_A"] = g["index_ret"]
    g["r_B"] = (1 - f) * g["bench_ret"] + f * (np.minimum(g["bench_ret"], g["atm_cap"] - 1) + g["atm_yield"])
    g["D"] = g["r_A"] - g["r_B"]
    return g[f <= 1].reset_index(drop=True)


def perf(
    r: np.ndarray,
    rf_annual: np.ndarray | None = None,
    dates: np.ndarray | pd.Series | None = None,
) -> dict:
    """Monthly performance using excess returns and calendar-aware gaps.

    When dates are provided and the sample skips months, omitted calendar months
    are treated as flat (0 return) for CAGR, volatility, and Sharpe, while the
    cumulative product still reflects only the realized active months.
    """
    r = np.asarray(r, dtype=float)
    if len(r) == 0:
        return dict(cagr=np.nan, vol=np.nan, sharpe=np.nan, cum=np.nan)
    cum = np.prod(1 + r)
    rf = np.zeros(len(r)) if rf_annual is None else np.asarray(rf_annual, dtype=float) / 12
    if dates is None:
        active_r, active_rf, n_months = r, rf, len(r)
    else:
        d = pd.DatetimeIndex(pd.to_datetime(np.asarray(dates))).sort_values()
        if len(d) != len(r):
            raise ValueError("dates must align 1:1 with returns")
        # Rebuild a contiguous monthly path so gaps enter vol/Sharpe as flat months.
        order = np.argsort(pd.DatetimeIndex(pd.to_datetime(np.asarray(dates))))
        r_ord, rf_ord, d_ord = r[order], rf[order], d
        month_index = pd.period_range(d_ord[0].to_period("M"), d_ord[-1].to_period("M"), freq="M")
        active = pd.DataFrame({"r": r_ord, "rf": rf_ord}, index=d_ord.to_period("M"))
        active = active[~active.index.duplicated(keep="last")]
        filled = active.reindex(month_index, fill_value=0.0)
        active_r = filled["r"].to_numpy(dtype=float)
        active_rf = filled["rf"].to_numpy(dtype=float)
        n_months = len(active_r)
    std = active_r.std(ddof=1) if len(active_r) > 1 else np.nan
    return dict(
        cagr=cum ** (12 / n_months) - 1,
        vol=std * np.sqrt(12) if std == std else np.nan,
        sharpe=(active_r - active_rf).mean() / std * np.sqrt(12) if std and std > 0 else np.nan,
        cum=cum,
    )


def main() -> None:
    panel = pd.read_csv(OUT / "panel_monthly.csv", parse_dates=["date"])
    screen = []

    for tgt in CFG.switch_targets:
        g = matched_BD(panel, tgt)
        if len(g) < 24:
            print(f"\n===== {tgt}  (skipped: only {len(g)} feasible months, need >=24 for rolling z) =====")
            continue
        print(f"\n===== {tgt}  (n={len(g)} feasible months) =====")
        # (1) signal screen  (full-sample z: exploratory only; real rule uses rolling z below)
        signals = {"momentum": g["mom"], "implied_vol": g["sigma_impl"], "realized_vol": g["real_vol"],
                   "VRP(impl-real)": g["sigma_impl"] - g["real_vol"], "rate": g["rf"]}
        print(f"{'signal':16}{'corr(z,D)':>10}{'corr(z,'+CFG.ticker+')':>13}   mean D by tertile bp (lo/mid/hi)")
        for name, x in signals.items():
            z = (x - x.mean()) / x.std()
            cD, cN = np.corrcoef(z, g["D"])[0, 1], np.corrcoef(z, g["bench_ret"])[0, 1]
            q1, q2 = z.quantile([1 / 3, 2 / 3])
            lo, mid, hi = (g["D"][z <= q1].mean(), g["D"][(z > q1) & (z <= q2)].mean(), g["D"][z > q2].mean())
            print(f"{name:16}{cD:>10.2f}{cN:>13.2f}     {lo*1e4:>6.0f} /{mid*1e4:>5.0f} /{hi*1e4:>5.0f}")

        # (2) switch backtest with expanding, lagged momentum z on the full calendar
        calendar = (
            panel.loc[panel["ppy"] == 12, "date"].drop_duplicates().sort_values().reset_index(drop=True)
        )
        mom_calendar = (
            panel[panel["ppy"] == 12].groupby("date")["mom_12_1"].first().reindex(calendar)
        )
        mom_vals = mom_calendar.to_numpy(dtype=float)
        z_full = np.array([
            (mom_vals[i] - np.nanmean(mom_vals[:i])) / np.nanstd(mom_vals[:i], ddof=1)
            if np.sum(~np.isnan(mom_vals[:i])) >= 24 else np.nan
            for i in range(len(mom_vals))
        ])
        z = g["date"].map(pd.Series(z_full, index=calendar)).to_numpy()
        m = ~np.isnan(z)
        rA, rB = g["r_A"].values, g["r_B"].values
        rule = np.where(z > 0, rB, rA)
        print("\nswitch backtest (feasible months, z defined):")
        stats = {}
        for label, r in [("always A", rA[m]), ("always B", rB[m]),
                         ("momentum switch z>0->B", rule[m]),
                         ("ORACLE hindsight best", np.maximum(rA, rB)[m]),
                         ("ANTI-ORACLE worst", np.minimum(rA, rB)[m])]:
            s = perf(r, g["rf"].values[m], g["date"].values[m])
            stats[label] = s
            print(f"  {label:24} CAGR={s['cagr']:6.1%}  vol={s['vol']:5.1%}  Sharpe={s['sharpe']:4.2f}  cum={s['cum']:6.1f}x")

        D = rA - rB
        total = D.sum()
        top = np.argsort(D)[:5]
        # A share is only meaningful when the tier has a net B-edge to concentrate;
        # on the sub-1%/mo tiers A and B nearly cancel, so the ratio explodes.
        share = (D[top].sum() / total * 100
                 if abs(total) > 0.20 * np.abs(D).sum() else np.nan)
        print(f"  concentration: 5 most extreme months = {share:.0f}% of total B-edge; "
              f"their {CFG.ticker} returns = {np.round(g['bench_ret'].values[top]*100,0)}%  (earnings gaps, unpredictable)")

        z_mom = (g["mom"] - g["mom"].mean()) / g["mom"].std()
        screen.append(dict(
            target=target_label(tgt), target_pct=income_pct(tgt), n_months=int(m.sum()),
            corr_mom_D=round(float(np.corrcoef(z_mom, g["D"])[0, 1]), 3),
            sharpe_always_A=round(stats["always A"]["sharpe"], 3),
            sharpe_always_B=round(stats["always B"]["sharpe"], 3),
            sharpe_mom_switch=round(stats["momentum switch z>0->B"]["sharpe"], 3),
            sharpe_oracle=round(stats["ORACLE hindsight best"]["sharpe"], 3),
            cum_always_A=round(stats["always A"]["cum"], 2),
            cum_always_B=round(stats["always B"]["cum"], 2),
            cum_mom_switch=round(stats["momentum switch z>0->B"]["cum"], 2),
            pct_B_chosen=round(float(np.mean(z[m] > 0)), 3),
            top5_share_of_B_edge_pct=round(float(share), 1) if share == share else np.nan,
        ))

    # One row per Income tier (sub-1%/mo grid included) so the screen is reviewable
    # without rereading the console log.
    if screen:
        path = OUT / "switch_signal_screen.csv"
        pd.DataFrame(screen).to_csv(path, index=False)
        print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
