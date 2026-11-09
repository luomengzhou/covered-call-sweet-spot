"""Phase 6 add-on — delta-matched equity+cash benchmarks for A and B.

Motivated by Israelov & Nielsen (AQR), "Covered Call Strategies: One Fact and
Eight Myths" (FAJ 2014): a covered call's expected excess return equals that of
delta x stock + (1-delta) x cash unless implied vol is rich — everything else
is beta. So the honest question for "B beats A on NVDA" is: does B still win
AFTER each structure is benchmarked against its own month-start-delta
equity+cash mix? If not, B's edge is just retained beta, not skew alpha.

Per month, per structure:
  delta_A = 1 - N(d1) at A's cap (f_A = 1)
  delta_B = 1 - f * N(d1_ATM)
  bench_X = delta_X * stock_ret + (1 - delta_X) * rf_monthly
  excess_X = r_X - bench_X          (the VRP + timing residual)

Usage: .venv/bin/python 06_delta_matched_benchmark.py
"""
from __future__ import annotations

import math
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd

from _config import _CONFIGS, income_pct, target_label

_step5 = import_module("05_switch_signals")
_var = import_module("06_skew_switch_variants")
matched_BD, perf = _step5.matched_BD, _step5.perf
_implied_vol, TAU = _var._implied_vol, _var.TAU

ROOT = Path(__file__).parent


def call_delta(y: float, cap: float, r: float) -> float:
    sigma = _implied_vol(y, cap, r)
    if not np.isfinite(sigma):
        return np.nan
    st = sigma * math.sqrt(TAU)
    d1 = (-math.log(cap) + (r + 0.5 * sigma**2) * TAU) / st
    return 0.5 * (1 + math.erf(d1 / math.sqrt(2)))


def main() -> None:
    rows = []
    for ticker, cfg in _CONFIGS.items():
        panel = pd.read_csv(ROOT / "results" / ticker / "panel_monthly.csv", parse_dates=["date"])
        for tgt in cfg.switch_targets:
            if tgt not in set(panel["index_name"]):
                print(f"[skip] {ticker} {tgt}: target absent from panel")
                continue
            g = matched_BD(panel, tgt, with_signals=False)
            if len(g) < 60:
                continue
            g = g.dropna(subset=["rf"]).reset_index(drop=True)
            f = (g["y_used"] / g["atm_yield"]).values
            dA = np.array([1 - call_delta(y, c, r)
                           for y, c, r in zip(g["y_used"], g["cap_used"], g["rf"])])
            dB = 1 - f * np.array([call_delta(y, c, r)
                                   for y, c, r in zip(g["atm_yield"], g["atm_cap"], g["rf"])])
            rf_m = (1 + g["rf"].values) ** TAU - 1
            m = np.isfinite(dA) & np.isfinite(dB)
            stock = g["bench_ret"].values
            exA = g["r_A"].values - (dA * stock + (1 - dA) * rf_m)
            exB = g["r_B"].values - (dB * stock + (1 - dB) * rf_m)
            rows.append(dict(
                ticker=ticker, target=target_label(tgt),
                target_pct=income_pct(tgt), n=int(m.sum()),
                mean_delta_A=round(float(np.nanmean(dA[m])), 2),
                mean_delta_B=round(float(np.nanmean(dB[m])), 2),
                gross_edge_B_bp=round(float(-np.mean((g["r_A"].values - g["r_B"].values)[m])) * 1e4, 1),
                excess_A_bp=round(float(np.mean(exA[m])) * 1e4, 1),
                excess_B_bp=round(float(np.mean(exB[m])) * 1e4, 1),
                net_edge_B_bp=round(float(np.mean(exB[m] - exA[m])) * 1e4, 1),
                sharpe_exA=round(float(np.mean(exA[m]) / np.std(exA[m], ddof=1) * np.sqrt(12)), 2),
                sharpe_exB=round(float(np.mean(exB[m]) / np.std(exB[m], ddof=1) * np.sqrt(12)), 2),
            ))
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "results" / "delta_matched_benchmark.csv", index=False)
    pd.set_option("display.width", 200)
    print(out.to_string(index=False))
    print("\nwrote results/delta_matched_benchmark.csv")
    print("\nreading guide: gross_edge_B = plain mean(r_B - r_A); net_edge_B = same after each"
          "\nstructure is measured against its own delta-matched equity+cash benchmark."
          "\nIf net << gross, B's edge was mostly retained beta (AQR's point), not option alpha.")


if __name__ == "__main__":
    main()
