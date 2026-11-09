"""Step 4 — Strategy A vs B at matched premium (the sweet-spot / switch analysis).

Strategy A  = full-notional out-of-the-money covered call  (the "Income" family;
              strike chosen so the premium hits a target yield).
Strategy B  = partial at-the-money covered call (sell an ATM call on only a
              fraction f of the position, keeping full upside on the rest).

We compare them ON EQUAL FOOTING: for every month we force B to collect the SAME
premium A collected, by solving f = premium / atm_yield. B is built synthetically
from the panel (no separate download needed), because the downloaded Exposure
indices use a FIXED coverage and therefore do not premium-match A month to month.

Per month, per Income target level:
    r_A = official Income index return              (from panel, column index_ret)
    y   = premium A collected that month            (column y_used)
    y_atm, atm_cap = that month's ATM option        (from the Exposure family)
    f   = y / y_atm                                 (coverage B needs for equal premium)
    r_B = (1-f)*r + f*[ min(r, atm_cap-1) + y_atm ]  (matched-premium partial ATM)
    feasible = (f <= 1)   -> f>1 means B is impossible long-only (high-yield regime)
    D   = r_A - r_B       -> >0 means full-notional-OTM (A) beat partial-ATM (B)

Outputs:
    results/premium_matched_comparison.csv   summary per target level
Usage:
    python 04_premium_matched_comparison.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from _config import get_config

OUT = get_config().out_dir


def main() -> None:
    panel = pd.read_csv(OUT / "panel_monthly.csv", parse_dates=["date"])

    # ATM reference: the Exposure family sells an at-the-money call; every coverage
    # level shares the same strike, so any of them gives that month's ATM terms.
    exposure = panel[(panel["family"] == "B") & (~panel["split_artifact"])]
    atm = (exposure.groupby("date")
           .agg(atm_yield=("y_used", "mean"), atm_cap=("cap_used", "mean"))
           .dropna())

    income = panel[(panel["family"] == "A") & (~panel["split_artifact"])]
    summary = []
    for _, g in income.groupby("index_name"):
        g = g.dropna(subset=["y_used", "cap_used"]).merge(atm, on="date")
        bench = g["bench_ret"]
        premium = g["y_used"]                      # premium A collected (the match target)
        f = premium / g["atm_yield"]               # coverage B needs for equal premium
        r_B = (1 - f) * bench + f * (np.minimum(bench, g["atm_cap"] - 1) + g["atm_yield"])
        r_A = g["index_ret"]
        feasible = f <= 1.0
        D = (r_A - r_B)[feasible]                   # A's monthly edge over B (feasible months)

        target = round(g["param"].iloc[0] * 100, 3)  # %/mo; 3dp keeps the sub-1% grid distinct
        summary.append(dict(
            income_target_pct=target,
            months=len(g),
            months_B_feasible=int(feasible.sum()),
            pct_B_feasible=feasible.mean(),
            A_monthly_win_rate=(D > 0).mean() if len(D) else np.nan,
            mean_edge_A_over_B_bp=D.mean() * 1e4 if len(D) else np.nan,
            cum_return_A=np.prod(1 + r_A[feasible]) if feasible.any() else np.nan,
            cum_return_B=np.prod(1 + r_B[feasible]) if feasible.any() else np.nan,
        ))

    res = pd.DataFrame(summary).sort_values("income_target_pct").reset_index(drop=True)
    res.to_csv(OUT / "premium_matched_comparison.csv", index=False)

    fmt = {"pct_B_feasible": "{:.0%}".format, "A_monthly_win_rate": "{:.0%}".format,
           "mean_edge_A_over_B_bp": "{:.1f}".format,
           "cum_return_A": "{:.1f}x".format, "cum_return_B": "{:.1f}x".format}
    pd.set_option("display.width", 140)
    print(res.to_string(index=False, formatters=fmt))
    print(f"\nwrote {OUT / 'premium_matched_comparison.csv'}")
    print("Reading: mean_edge < 0 => partial-ATM (B) wins on average; "
          "A_win_rate > 50% => full-notional-OTM (A) wins more often month-to-month.")


if __name__ == "__main__":
    main()
