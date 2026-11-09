"""Step 1 — unified monthly panel.

Read all *_attribution_report.csv under data/, output:
  results/panel_monthly.csv        long-format panel (with derived market-state variables)
  results/reconciliation_report.csv  reconciliation of payoff-formula reconstruction vs reported returns
Usage: .venv/bin/python 01_build_panel.py
"""
from __future__ import annotations

import io
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from _config import DATA, get_config

CFG = get_config()
OUT = CFG.out_dir
SQRT_T = np.sqrt(1 / 12)  # monthly expiry

# Benchmark = total return (with dividends), Underlying = price return; a 1-70bp gap between them is a dividend month.
# A gap >10% is a stock-split garbage value (Underlying is a garbage value in the split month). Always use Benchmark for returns.
DIV_TOL, SPLIT_TOL = 1e-4, 0.10
RECON_MAX_ABS_BP = 100.0


def parse_name(path: Path) -> dict:
    """Parse the file name into structured fields.

    family : family label (for plotting/grouping), A=full-notional OTM (income axis), B=partial-notional (coverage axis),
             A_delta=full-notional with strike chosen by delta, BD=coverage×delta 2D.
    param  : the family's main-axis value (Income: premium target; Exposure/2D: coverage ratio; Delta: delta), used for frontier sorting/labeling.
    coverage(f) : option coverage ratio, the only position quantity needed for payoff reconstruction (full-notional=1.0).
    ppy    : rebalance periods per year, used for annualization (monthly=12).
    delta/expiry : optional secondary parameters, default None.
    Returns None for intentionally skipped files (e.g. Weekly/Quarterly).
    """
    n = path.name

    def out(index_name, family, param, coverage, ppy, delta=None, expiry=None):
        return {"index_name": index_name, "family": family, "param": param,
                "coverage": coverage, "ppy": ppy, "delta": delta, "expiry": expiry}

    pre, cc = CFG.prefix, CFG.cc
    m = re.match(rf"{pre}_(\d+)_(Income|Exposure)_attribution", n)
    if m:
        raw, fam = m.group(1), m.group(2)
        num = int(raw)
        if fam == "Income":  # full-notional OTM, param=premium target rate
            # 1-2 digit names are whole percents per month (3 -> 3%/mo = 0.03).
            # 4-digit zero-padded names are thousandths of a percent per month
            # (0083 -> 0.083%/mo = 1%/yr), the sub-1%/mo grid.
            return out(f"{cc}_{raw}_Income", "A", num / (100000.0 if len(raw) == 4 else 100.0), 1.0, 12)
        return out(f"{cc}_{num}_Exposure", "B", num / 100.0, num / 100.0, 12)  # partial-notional, param=coverage ratio
    m = re.match(rf"{pre}_Delta_(\d+)_attribution", n)
    if m:  # full-notional, strike chosen by delta
        d = int(m.group(1))
        return out(f"{cc}_Delta_{d}", "A_delta", d / 100.0, 1.0, 12, delta=d / 100.0)
    m = re.match(rf"{pre}_(\d+)Exp_Delta_(\d+)_attribution", n)
    if m:  # 2D: coverage ratio × delta
        cov, d = int(m.group(1)), int(m.group(2))
        return out(f"{cc}_{cov}Exp_Delta_{d}", "BD", cov / 100.0, cov / 100.0, 12, delta=d / 100.0)
    # Disabled: only NVDA has Weekly/Quarterly (thin Mag7 coverage). Re-enable when data is complete:
    # m = re.match(rf"{pre}_(\d+)Exp_(Weekly|Quarterly)_attribution", n)
    # if m:  # full-notional (coverage=cov%), different expiry frequency
    #     cov, freq = int(m.group(1)), m.group(2)
    #     return out(f"{cc}_{cov}Exp_{freq}", f"E_{freq}", cov / 100.0, cov / 100.0,
    #                52 if freq == "Weekly" else 4, expiry=freq)
    if re.match(rf"{pre}_(\d+)Exp_(Weekly|Quarterly)_attribution", n):
        return None
    raise ValueError(f"unrecognized file name: {n}")


def load_one(path: Path) -> pd.DataFrame | None:
    meta = parse_name(path)
    if meta is None:
        return None
    df = pd.read_csv(path, parse_dates=["Date"])
    required = {
        "Date", "Index Return", "Benchmark", "Underlying Asset Return", "Cap", "Call Yield",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing required columns {sorted(missing)}")
    if df["Date"].isna().any() or df["Date"].duplicated().any():
        raise ValueError(f"{path.name}: Date must be non-null and unique")
    numeric = list(required - {"Date"})
    if not np.isfinite(df[numeric].to_numpy(dtype=float)).all():
        raise ValueError(f"{path.name}: non-finite numeric input")
    if (df["Benchmark"] <= -1).any() or (df["Index Return"] <= -1).any():
        raise ValueError(f"{path.name}: returns must be greater than -100%")
    if (df["Cap"] <= 0).any() or (df["Call Yield"] < 0).any():
        raise ValueError(f"{path.name}: Cap/Call Yield outside valid range")
    df = df.sort_values("Date").reset_index(drop=True)
    out = pd.DataFrame(
        {
            "date": df["Date"],
            "index_name": meta["index_name"],
            "family": meta["family"],
            "param": meta["param"],
            "coverage": meta["coverage"],
            "ppy": meta["ppy"],
            "delta": meta["delta"],
            "expiry": meta["expiry"],
            "index_ret": df["Index Return"],
            "bench_ret": df["Benchmark"],
            "underlying_ret_raw": df["Underlying Asset Return"],
            # the Cap/Call Yield on row t are the terms of the option newly sold that day, applying to the next period's return
            "cap_next": df["Cap"],
            "call_yield_next": df["Call Yield"],
        }
    )
    out["cap_used"] = out["cap_next"].shift(1)
    out["y_used"] = out["call_yield_next"].shift(1)
    diff = (out["underlying_ret_raw"] - out["bench_ret"]).abs()
    out["split_artifact"] = diff > SPLIT_TOL
    out["dividend_month"] = (diff > DIV_TOL) & ~out["split_artifact"]
    return out


def reconstruct(row: pd.Series) -> float:
    # unified payoff: a coverage-ratio-f position sells cap-capped covered calls, the remaining (1-f) holds the underlying naked. Full-notional (f=1) degenerates to pure capped.
    r, cap, y, f = row["bench_ret"], row["cap_used"] - 1, row["y_used"], row["coverage"]
    capped = min(r, cap) + y
    return (1 - f) * r + f * capped


def fetch_tb3ms() -> pd.Series:
    """Load TB3MS; download once to a temp file then atomically replace the cache."""
    cache = DATA / "TB3MS.csv"
    if not cache.exists():
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=TB3MS"
        tmp = cache.with_suffix(".csv.tmp")
        tmp.write_bytes(urllib.request.urlopen(url, timeout=30).read())
        tmp.replace(cache)
    rf = pd.read_csv(cache)
    rf.columns = ["date", "tb3ms"]
    rf["date"] = pd.to_datetime(rf["date"])
    rf["tb3ms"] = pd.to_numeric(rf["tb3ms"], errors="coerce") / 100.0
    series = rf.dropna().set_index("date")["tb3ms"].sort_index()
    if series.empty:
        raise RuntimeError(f"TB3MS cache is empty or unreadable: {cache}")
    return series


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(CFG.data_dir.glob(f"{CFG.prefix}_*_attribution_report.csv"))
    if not files:
        sys.exit(f"no attribution files in {CFG.data_dir}/")
    frames = [df for p in files if (df := load_one(p)) is not None]
    skipped = len(files) - len(frames)
    if skipped:
        print(f"[skip] {skipped} attribution file(s) (Weekly/Quarterly disabled)")
    panel = pd.concat(frames, ignore_index=True)
    print(f"[{CFG.ticker}] loaded {len(frames)} indices, {len(panel)} rows, "
          f"{panel['date'].min():%Y-%m} → {panel['date'].max():%Y-%m}")
    missing = CFG.expected - set(panel["index_name"].unique())
    if missing:
        sys.exit(f"missing attribution for {len(missing)} indices: {sorted(missing)}")

    n_split = int(panel.groupby("date")["split_artifact"].any().sum())
    n_div = int(panel.groupby("date")["dividend_month"].any().sum())
    print(f"split artifacts: {n_split} months (option strike split adjustment, large reconciliation residual, downstream analysis should flag)")
    print(f"dividend months: {n_div} months (Benchmark includes dividends, 1-70bp gap, negligible)")

    # ---- reconciliation ----
    # NVDA returns in split months (split_artifact) are themselves garbage values → exclude from reconciliation, otherwise the residual is pulled to thousands of bp
    # and masks the formula's true precision. Split months are separately flagged, and downstream analysis should also exclude them.
    body = panel.dropna(subset=["cap_used", "y_used"]).copy()
    body["recon_ret"] = body.apply(reconstruct, axis=1)
    body["residual"] = body["index_ret"] - body["recon_ret"]
    clean = body[~body["split_artifact"]]
    rec = (
        clean.groupby("index_name")["residual"]
        .agg(n="size", mean_bp=lambda s: s.mean() * 1e4, mean_abs_bp=lambda s: s.abs().mean() * 1e4,
             max_abs_bp=lambda s: s.abs().max() * 1e4)
        .round(2)
    )
    if rec["max_abs_bp"].max() > RECON_MAX_ABS_BP:
        raise RuntimeError(
            f"reconciliation exceeded {RECON_MAX_ABS_BP:.0f}bp threshold: "
            f"{rec['max_abs_bp'].max():.2f}bp"
        )
    rec.to_csv(OUT / "reconciliation_report.csv")
    print("\n== payoff reconstruction reconciliation (bp, split months excluded) ==\n", rec.to_string())
    print(f"\nall (split excluded): median|resid|={clean['residual'].abs().median()*1e4:.3f}bp  "
          f"mean|resid|={clean['residual'].abs().mean()*1e4:.2f}bp  max|resid|={clean['residual'].abs().max()*1e4:.1f}bp")
    worst = clean.loc[clean["residual"].abs().sort_values(ascending=False).index[:5],
                      ["date", "index_name", "index_ret", "recon_ret", "residual"]]
    print("\ntop 5 largest residual rows (split excluded, mostly minor dividend-convention differences from 2012-12 on):\n", worst.to_string(index=False))

    # ---- market-state variables (known at month start, defined only on the monthly-expiry tier) ----
    # weekly/quarterly rebalance dates do not coincide with monthly; mixing them would pollute the NVDA monthly series; state variables are built only from the monthly tier (ppy==12).
    monthly = panel[panel["ppy"] == 12]
    # ATM call yield taken from the Exposure family (tiers should agree, take the mean and check divergence)
    exp = monthly[monthly["family"] == "B"]
    atm = exp.groupby("date").agg(atm_yield_next=("call_yield_next", "mean"),
                                  atm_yield_spread=("call_yield_next", lambda s: s.max() - s.min()))
    if (atm["atm_yield_spread"] > 1e-9).any():
        print("[warn] Exposure call_yield inconsistent across tiers, check!")
    state = atm[["atm_yield_next"]].copy()
    state["sigma_impl_next"] = state["atm_yield_next"] / (0.4 * SQRT_T)  # ATM approximation: c/S ≈ 0.4σ√T

    bench = monthly.groupby("date")["bench_ret"].first().sort_index()
    state["real_vol_12m"] = bench.rolling(12).std() * np.sqrt(12)
    state["mom_12_1"] = (1 + bench).rolling(12).apply(np.prod, raw=True).shift(1) - 1

    panel = panel.merge(state.reset_index(), on="date", how="left")
    # the risk-free rate is forward-filled to the nearest date per row, covering all expiry frequencies (for downstream annualized excess returns).
    rf = fetch_tb3ms().sort_index()
    panel["rf_3m"] = rf.reindex(panel["date"].sort_values().unique(), method="ffill") \
                       .reindex(panel["date"]).values
    if panel["rf_3m"].isna().any():
        raise RuntimeError("rf_3m still has NaN after TB3MS forward-fill; extend the cache")
    panel.to_csv(OUT / "panel_monthly.csv", index=False)
    print(f"\nwrote {OUT / 'panel_monthly.csv'} ({len(panel)} rows)")


if __name__ == "__main__":
    main()
