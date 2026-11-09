"""Phase 6 pilot — realized-skew switch signal, single name, own-history reference.

First of the 8 signal variants in results/06_skew_switch_signal_design.md:
trailing realized skew of the underlying's DAILY returns, compared against the
name's own history, deciding A (full-notional OTM) vs B (matched partial-ATM)
one month ahead. Reuses Phase 5's matched_BD/perf so the three baselines
(always-A / always-B / ORACLE) are computed identically.

Rules tested (both no-lookahead: signal on row t uses daily data up to the
PREVIOUS rebalance date, when the month's option was actually sold):
  - sign rule:  trailing skew > 0 -> B, else A   (prior from the cross-sectional
    memo: fat right tail favors B; no fitted threshold, nothing to overfit)
  - z rule:     expanding z-score of trailing skew > 0 -> B, else A

Window sensitivity is reported for 63/126/252 trading days — read it as a
range, do NOT pick the best one as the result.

⚠️ DATA SOURCE: daily prices come from yfinance, auto_adjust=True (split+dividend
adjusted). The production version read option surfaces and adjusted prices from an
internal database; this pilot uses yfinance instead so it runs end-to-end on public
data. Decision: keep yfinance, note the source. Revisit if this analysis graduates
beyond exploration.

Usage: .venv/bin/python 06_skew_switch_pilot.py   (reads results/<TICKER>/panel_monthly.csv)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from _config import get_config
from importlib import import_module

_step5 = import_module("05_switch_signals")
matched_BD, perf = _step5.matched_BD, _step5.perf

CFG = get_config()
OUT = CFG.out_dir

WINDOWS = [63, 126, 252]  # trading days; 126 is the headline, others are sensitivity


def daily_returns() -> pd.Series:
    import yfinance as yf

    px = yf.download(CFG.ticker, start="2006-01-01", auto_adjust=True, progress=False)["Close"]
    if isinstance(px, pd.DataFrame):  # yfinance returns a 1-col frame for single tickers
        px = px.iloc[:, 0]
    return px.pct_change().dropna()


def trailing_skew_at(dates: pd.Series, ret: pd.Series, window: int) -> np.ndarray:
    """Trailing skew of the `window` daily returns ending at each date (inclusive)."""
    out = np.full(len(dates), np.nan)
    for i, d in enumerate(dates):
        w = ret.loc[:d].tail(window)
        if len(w) == window:
            out[i] = w.skew()
    return out


def main() -> None:
    panel = pd.read_csv(OUT / "panel_monthly.csv", parse_dates=["date"])
    ret = daily_returns()
    calendar = (
        panel.loc[panel["ppy"] == 12, "date"].drop_duplicates().sort_values().reset_index(drop=True)
    )
    print(f"daily {CFG.ticker} returns: {ret.index[0].date()} .. {ret.index[-1].date()}  (yfinance, TEMP source)")

    for tgt in CFG.switch_targets:
        g = matched_BD(panel, tgt)
        if len(g) < 36:
            print(f"\n===== {tgt}  (skipped: only {len(g)} feasible months) =====")
            continue
        rA, rB = g["r_A"].values, g["r_B"].values
        D = rA - rB
        print(f"\n===== {tgt}  (n={len(g)} feasible months) =====")

        for window in WINDOWS:
            # Compute on the complete rebalance calendar before feasibility
            # filtering, then map the actual prior-rebalance signal to each row.
            sk_calendar = pd.Series(
                trailing_skew_at(calendar, ret, window), index=calendar
            )
            sk = g["rebalance_date"].map(sk_calendar).to_numpy()
            m0 = ~np.isnan(sk)

            corr = np.corrcoef(sk[m0], D[m0])[0, 1]
            sk_full = sk_calendar.to_numpy()
            z_full = np.array([
                (sk_full[i] - np.nanmean(sk_full[:i])) / np.nanstd(sk_full[:i], ddof=1)
                if np.sum(~np.isnan(sk_full[:i])) >= 24 else np.nan
                for i in range(len(sk_full))
            ])
            z_calendar = pd.Series(z_full, index=calendar)
            zexp = g["rebalance_date"].map(z_calendar).to_numpy()
            mz = m0 & ~np.isnan(zexp)

            sign_rule = np.where(sk > 0, rB, rA)
            z_rule = np.where(zexp > 0, rB, rA)

            print(f"\n-- window={window}d   corr(skew_lag, D)={corr:+.2f}   "
                  f"months B chosen: sign {np.mean(sk[m0] > 0):.0%}, z {np.mean(zexp[mz] > 0):.0%}")
            rows = [("always A", rA[mz]), ("always B", rB[mz]),
                    ("skew sign >0 -> B", sign_rule[mz]),
                    ("skew z >0 -> B", z_rule[mz]),
                    ("ORACLE hindsight", np.maximum(rA, rB)[mz])]
            for label, r in rows:
                s = perf(r, g["rf"].values[mz], g["date"].values[mz])
                print(f"  {label:20} CAGR={s['cagr']:6.1%}  vol={s['vol']:5.1%}  "
                      f"Sharpe={s['sharpe']:4.2f}  cum={s['cum']:6.1f}x")


if __name__ == "__main__":
    main()
