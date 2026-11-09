"""Phase 6 — run the remaining skew-switch signal variants across the Mag7.

Extends 06_skew_switch_pilot.py (realized skew, own-history, NVDA) to the rest
of the design matrix in results/06_skew_switch_signal_design.md:

  signals, all month-start observable:
    skew_own      trailing 126d realized skew of the underlying (lagged 1 row)
    skew_vs_SPY   same, minus SPY's trailing skew  (cross-sectional relative)
    skew_vs_QQQ   same, minus QQQ's
    wing_z        IV-wing backed out each month from the Income ladder's
                  (Cap, Call Yield) pairs + the Exposure family's ATM anchor,
                  BS-inverted to sigma_IV(c), slope fitted per month, then
                  expanding z-score.  cap_used/y_used are already the terms
                  sold at the PRIOR rebalance, so no extra lag is needed.
  rules (sign priors fixed ex ante, nothing fitted):
    skew rules:   signal > 0 -> B   (fat right tail -> keep upside)
    wing rule:    z > 0 -> A       (richer OTM calls help A: theory/ab_core.py)
  scope: every Income tier each name has (TickerConfig.switch_targets), plus a
  pooled equal-weight Mag7 panel (>=3 names live per month).

DATA SOURCE for the three realized-skew signals: daily adjusted-close prices
from data/prices/<TICKER>_daily.csv (the approved daily OHLCV source), one file
per Mag7 name plus SPY/QQQ for the cross-sectional variants.

Every run builds/refreshes data/daily_close.csv (wide, one adjusted-close column
per ticker) from those files, with data/daily_close_source.json recording the
build date and per-ticker coverage. Commit the cache: it is what makes these
rows reproducible without re-reading data/prices/. `--refresh` rebuilds it even
if a cache already exists (e.g. after data/prices/ gets new trading days).

FALLBACK when data/prices/ lacks a Mag7 name and no cache exists (`--source
panel`, or automatically): the monthly panel's own `bench_ret` — the underlying's
total return per rebalance period, already in data/. That yields a *different*
signal, not a cheaper route to the same one: 126 daily observations become 36
monthly ones, so the skew is a multi-year monthly-return skew. Those runs are
named `skew_own_m36`, carry source=panel_monthly, and land in a separate file
(results/skew_switch_variants_panel_monthly.csv) so they can never be read as the
daily numbers. skew_vs_SPY / skew_vs_QQQ have no fallback at all — if
data/prices/ lacks SPY or QQQ, those two variants are simply skipped.

Splits in the fallback path: `bench_ret` is the split-adjusted total return, so
nothing needs recomputing. The unadjusted `Underlying Asset Return` column is a
garbage value in each split month, which is what step 01's `split_artifact` flag
marks and why this script never touches that column; audit_splits() prints the
eight events (AAPL 7:1/4:1, NVDA 4:1/10:1, TSLA 5:1/3:1, AMZN 20:1, GOOGL 20:1)
with the ratio implied by the two columns, so the claim is checkable per run.

Caveat on the pooled panel: the 7 names share one market factor; treat the
pooled row as one diversified backtest, not as 7 independent samples.

Usage: .venv/bin/python 06_skew_switch_variants.py [--refresh] [--source auto|daily|panel]
       --refresh rebuilds data/daily_close.csv from data/prices/ even if a cache exists
Writes: results/skew_switch_variants_summary.csv           (daily source)
        results/skew_switch_variants_panel_monthly.csv     (panel fallback)
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd

from _config import DATA, _CONFIGS, target_label

_step5 = import_module("05_switch_signals")
matched_BD, perf = _step5.matched_BD, _step5.perf

ROOT = Path(__file__).parent
WINDOW = 126           # headline window; sensitivity was covered in the pilot
SKEW_MONTHS = 36       # fallback window, in months: the shortest sample a monthly skew is worth reading
MIN_DAILY_ROWS = 1000  # ~4y; every name in the study has >=12y, so less means a failed fetch
TAU = 1 / 12
DAILY_CACHE = DATA / "daily_close.csv"
DAILY_META = DATA / "daily_close_source.json"
PRICES_DIR = DATA / "prices"
MARKET = ["SPY", "QQQ"]        # cross-sectional anchors, daily source only; optional


# ---------------------------------------------------------------- daily data
def load_local_prices(tickers: list[str]) -> dict[str, pd.Series]:
    """Adjusted daily closes from data/prices/<TICKER>_daily.csv (the approved source).

    Only tickers with a file on disk are returned; callers treat the rest as missing.
    """
    out = {}
    for t in tickers:
        p = PRICES_DIR / f"{t}_daily.csv"
        if not p.exists():
            continue
        s = (pd.read_csv(p, parse_dates=["Date"]).set_index("Date")["Adj Close"]
             .sort_index())
        out[t] = s[~s.index.duplicated(keep="last")]
    return out


def save_daily_cache(px: pd.DataFrame) -> None:
    # %.10g, not a fixed number of decimals: split-adjusted early closes are cents
    # (NVDA 2008 divided by 40), where fixed decimals would quantize the returns.
    px.rename_axis("Date").to_csv(DAILY_CACHE, float_format="%.10g")
    DAILY_META.write_text(json.dumps({
        "source": "data/prices/<TICKER>_daily.csv (approved daily OHLCV, adjusted close)",
        "built": date.today().isoformat(),
        "tickers": {t: [str(s.first_valid_index().date()), str(s.last_valid_index().date()),
                        int(s.notna().sum())] for t, s in px.items()},
    }, indent=2) + "\n")
    print(f"cached {len(px)} daily rows x {px.shape[1]} tickers -> {DAILY_CACHE.name}")


def load_daily_cache(required: list[str], optional: list[str] = ()) -> pd.DataFrame | None:
    """The on-disk cache, or None if it is missing or short of a required ticker."""
    if not DAILY_CACHE.exists():
        return None
    px = pd.read_csv(DAILY_CACHE, index_col="Date", parse_dates=["Date"])
    missing = [t for t in required if t not in px.columns]
    if missing:
        print(f"[cache] {DAILY_CACHE.name} lacks required {missing}; rebuilding")
        return None
    thin = {t: int(px[t].notna().sum()) for t in required if px[t].notna().sum() < MIN_DAILY_ROWS}
    if thin:  # e.g. a file left behind by a build that came back empty
        print(f"[cache] {DAILY_CACHE.name} too thin {thin}; rebuilding")
        return None
    present = [t for t in list(required) + list(optional) if t in px.columns]
    return px[present]


def daily_returns(
    required: list[str], optional: list[str] = (), *, refresh: bool
) -> dict[str, pd.Series] | None:
    """Daily return series per ticker: cache first, data/prices/ otherwise.

    Returns None when a required (Mag7) ticker has no data at all, which is the
    caller's cue to fall back to the monthly panel. Missing optional (SPY/QQQ)
    tickers just drop those columns — callers skip the signals that need them.
    """
    px = None if refresh else load_daily_cache(required, optional)
    if px is not None:
        meta = json.loads(DAILY_META.read_text()) if DAILY_META.exists() else {}
        print(f"[daily] cache {DAILY_CACHE.name}, built {meta.get('built', '?')} "
              f"({len(px)} rows, {px.index.min().date()} -> {px.index.max().date()}, "
              f"cols={list(px.columns)})")
        return {t: px[t].dropna().pct_change().dropna() for t in px.columns}

    local = load_local_prices(list(required) + list(optional))
    missing_required = [t for t in required if t not in local]
    if missing_required:
        print(f"[daily] data/prices/ lacks required {missing_required}")
        return None
    if [t for t in optional if t not in local]:
        print(f"[daily] data/prices/ lacks optional {[t for t in optional if t not in local]}; "
              "skipping the cross-sectional variants that need them")
    px = pd.concat(local, axis=1, sort=True)
    save_daily_cache(px)
    return {t: px[t].dropna().pct_change().dropna() for t in px.columns}


def trailing_skew(dates: pd.Series, ret: pd.Series, window: int = WINDOW) -> np.ndarray:
    out = np.full(len(dates), np.nan)
    for i, d in enumerate(dates):
        w = ret.loc[:d].tail(window)
        if len(w) == window:
            out[i] = w.skew()
    return out


# ------------------------------------------------- fallback: monthly panel skew
def audit_splits(panel: pd.DataFrame, ticker: str) -> None:
    """Print the split months and the ratio implied by the panel's two return columns.

    `bench_ret` is the split-adjusted total return; `underlying_ret_raw` divides the
    post-split price by the pre-split one, so (1+bench)/(1+raw) recovers the split
    ratio exactly. A clean integer (or 3:2-style) ratio is the evidence that only the
    raw column is damaged and bench_ret needs no repair.
    """
    rows = (panel[panel["split_artifact"]].drop_duplicates("date")
            .sort_values("date")[["date", "bench_ret", "underlying_ret_raw"]])
    for _, r in rows.iterrows():
        ratio = (1 + r["bench_ret"]) / (1 + r["underlying_ret_raw"])
        print(f"[split] {ticker} {r['date']:%Y-%m-%d}  implied {ratio:.4f}:1  "
              f"(bench {r['bench_ret']:+.4f} kept, raw {r['underlying_ret_raw']:+.4f} discarded)")
    if not len(rows):
        print(f"[split] {ticker}: no split month in sample")


def monthly_bench(panel: pd.DataFrame) -> pd.Series:
    """The underlying's total return per rebalance period, one value per date."""
    return (panel[panel["ppy"] == 12].groupby("date")["bench_ret"].first().sort_index())


def trailing_skew_monthly(
    dates: pd.Series, monthly: pd.Series, window: int = SKEW_MONTHS
) -> np.ndarray:
    """Skew of the last `window` monthly returns realized up to and including each date.

    Same observability convention as trailing_skew: `dates` are rebalance dates, and
    the return on panel row t is realized over (t-1, t], so a row dated <= the
    rebalance date is known when the option is sold.
    """
    out = np.full(len(dates), np.nan)
    for i, d in enumerate(dates):
        w = monthly.loc[:d].tail(window)
        if len(w) == window:
            out[i] = w.skew()
    return out


# ---------------------------------------------------------------- IV wing
def _bs_call_yield(sigma: float, k: float, r: float) -> float:
    """C/S for spot 1, strike k, tenor TAU, rate r, q=0."""
    if sigma <= 0:
        return max(0.0, 1 - k * math.exp(-r * TAU))
    st = sigma * math.sqrt(TAU)
    d1 = (-math.log(k) + (r + 0.5 * sigma**2) * TAU) / st
    d2 = d1 - st
    N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    return N(d1) - k * math.exp(-r * TAU) * N(d2)


def _implied_vol(y: float, k: float, r: float) -> float:
    lo, hi = 1e-4, 5.0
    if not (_bs_call_yield(lo, k, r) < y < _bs_call_yield(hi, k, r)):
        return np.nan
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _bs_call_yield(mid, k, r) < y:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def monthly_wing(panel: pd.DataFrame) -> pd.Series:
    """Per-date wing slope (vol pts per 5% OTM) from the A ladder + B's ATM anchor."""
    rows = panel[(panel["ppy"] == 12) & panel["family"].isin(["A", "B"])].dropna(
        subset=["cap_used", "y_used", "rf_3m"])
    rf_at_sale = (
        panel[panel["ppy"] == 12].groupby("date")["rf_3m"].first().sort_index().shift(1)
    )
    out = {}
    for d, grp in rows.groupby("date"):
        pts_by_strike: dict[float, list[float]] = {}
        rate = rf_at_sale.get(d, np.nan)
        if not np.isfinite(rate):
            continue
        for _, row in grp.iterrows():
            c = row["cap_used"] - 1
            if not (-0.05 <= c <= 0.60) or not (0 < row["y_used"] < 0.5):
                continue  # deep-ITM ladder points are put-side, off the call wing
            iv = _implied_vol(row["y_used"], row["cap_used"], rate)
            if np.isfinite(iv):
                pts_by_strike.setdefault(round(c / 0.05, 10), []).append(iv)
        if len(pts_by_strike) >= 3:
            pts = [(x, float(np.mean(ivs))) for x, ivs in pts_by_strike.items()]
            x, y = np.array(pts).T
            out[d] = np.polyfit(x, y, 1)[0]
    return pd.Series(out, name="wing")


# ---------------------------------------------------------------- backtests
def expanding_z(x: np.ndarray, min_obs: int = 24) -> np.ndarray:
    return np.array([(x[i] - np.nanmean(x[:i])) / np.nanstd(x[:i], ddof=1)
                     if np.sum(~np.isnan(x[:i])) >= min_obs else np.nan
                     for i in range(len(x))])


def skew_signals(
    ticker: str, rebalance_dates: pd.Series, daily: dict[str, pd.Series] | None,
    monthly: pd.Series,
) -> dict[str, np.ndarray]:
    """The realized-skew signals the available data source supports.

    Daily source: the three designed signals. Panel fallback: the own-history one
    only, at monthly frequency and under a distinct name — data/ has no SPY/QQQ, so
    the two cross-sectional variants simply cannot be built from it.
    """
    if daily is not None:
        own = trailing_skew(rebalance_dates, daily[ticker])
        out = {"skew_own": own}
        for mkt in MARKET:
            if mkt in daily:
                out[f"skew_vs_{mkt}"] = own - trailing_skew(rebalance_dates, daily[mkt])
        return out
    return {f"skew_own_m{SKEW_MONTHS}": trailing_skew_monthly(rebalance_dates, monthly)}


def run_ticker(ticker: str, daily: dict[str, pd.Series] | None) -> list[dict]:
    cfg = _CONFIGS[ticker]
    panel = pd.read_csv(ROOT / "results" / ticker / "panel_monthly.csv", parse_dates=["date"])
    wing = monthly_wing(panel)
    wing_z = pd.Series(expanding_z(wing.to_numpy()), index=wing.index)
    monthly = monthly_bench(panel)
    if daily is None:
        audit_splits(panel, ticker)
    recs = []
    for tgt in cfg.switch_targets:
        if tgt not in set(panel["index_name"]):
            print(f"[skip] {ticker} {tgt}: target absent from panel")
            continue
        g = matched_BD(panel, tgt)
        if len(g) < 60:
            continue
        rA, rB = g["r_A"].values, g["r_B"].values
        D = rA - rB

        wz = g["date"].map(wing_z).to_numpy()
        skew_src = "daily_prices" if daily is not None else "panel_monthly"
        variants = {name: (sig, sig > 0, skew_src) for name, sig in
                    skew_signals(ticker, g["rebalance_date"], daily, monthly).items()}
        variants["wing_z"] = (wz, wz <= 0, "panel_monthly")  # built from the ladder, never daily
        for name, (sig, choose_b, source) in variants.items():
            m = ~np.isnan(sig)
            if m.sum() < 60:
                continue
            rule = np.where(choose_b, rB, rA)
            corr = np.corrcoef(sig[m], D[m])[0, 1]
            rf = g["rf"].values[m]
            dates = g["date"].values[m]
            recs.append(dict(
                ticker=ticker, target=target_label(tgt), signal=name, source=source,
                n=int(m.sum()), corr_sig_D=round(corr, 3),
                pct_B=round(float(np.mean(choose_b[m])), 2),
                sharpe_A=round(perf(rA[m], rf, dates)["sharpe"], 2),
                sharpe_B=round(perf(rB[m], rf, dates)["sharpe"], 2),
                sharpe_rule=round(perf(rule[m], rf, dates)["sharpe"], 2),
                cum_A=round(perf(rA[m], rf, dates)["cum"], 1),
                cum_B=round(perf(rB[m], rf, dates)["cum"], 1),
                cum_rule=round(perf(rule[m], rf, dates)["cum"], 1),
                cum_oracle=round(perf(np.maximum(rA, rB)[m], rf, dates)["cum"], 1),
                _dates=g["date"].values[m], _rule=rule[m], _rA=rA[m], _rB=rB[m],
                _rf=rf,
            ))
    return recs


def pooled_panel(recs: list[dict]) -> list[dict]:
    """Equal-weight across names, per signal x target; >=3 names live per month."""
    out = []
    df = pd.DataFrame(recs)
    for (sig, tgt, src), grp in df.groupby(["signal", "target", "source"]):
        if grp["ticker"].nunique() < 3:
            continue
        frames = {kind: pd.concat(
            [pd.Series(r[f"_{kind}"], index=pd.DatetimeIndex(r["_dates"])) for _, r in grp.iterrows()],
            axis=1, sort=True).sort_index() for kind in ("rule", "rA", "rB", "rf")}
        live = frames["rule"].notna().sum(axis=1) >= 3
        pooled = {k: v[live].mean(axis=1).values for k, v in frames.items()}
        pooled_dates = frames["rule"].index[live]
        out.append(dict(
            ticker="MAG7_pooled", target=tgt, signal=sig, source=src, n=int(live.sum()),
            corr_sig_D=np.nan, pct_B=np.nan,
            sharpe_A=round(perf(pooled["rA"], pooled["rf"], pooled_dates)["sharpe"], 2),
            sharpe_B=round(perf(pooled["rB"], pooled["rf"], pooled_dates)["sharpe"], 2),
            sharpe_rule=round(perf(pooled["rule"], pooled["rf"], pooled_dates)["sharpe"], 2),
            cum_A=round(perf(pooled["rA"], pooled["rf"], pooled_dates)["cum"], 1),
            cum_B=round(perf(pooled["rB"], pooled["rf"], pooled_dates)["cum"], 1),
            cum_rule=round(perf(pooled["rule"], pooled["rf"], pooled_dates)["cum"], 1),
            cum_oracle=np.nan,
        ))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true",
                    help="rebuild data/daily_close.csv from data/prices/, ignoring any existing cache")
    ap.add_argument("--source", choices=("auto", "daily", "panel"), default="auto",
                    help="auto: cache, then data/prices/, then the monthly-panel fallback; "
                         "daily: require the daily prices (fail if unavailable); "
                         "panel: force the monthly fallback")
    args = ap.parse_args()

    tickers = list(_CONFIGS)
    daily = None
    if args.source != "panel":
        daily = daily_returns(tickers, MARKET, refresh=args.refresh)
        if daily is None:
            if args.source == "daily":
                raise SystemExit("no daily prices: data/prices/ is missing a Mag7 name and no "
                                 f"cache at {DAILY_CACHE}. Run with --source panel for the "
                                 "monthly-panel fallback (a different signal).")
            print("[daily] falling back to the monthly panel: skew from the underlying's "
                  f"{SKEW_MONTHS}-month total returns in data/, SPY/QQQ variants dropped")

    recs = []
    for t in tickers:
        r = run_ticker(t, daily)
        recs += r
        print(f"{t}: {len(r)} variant runs")
    recs += pooled_panel(recs)

    cols = ["ticker", "target", "signal", "source", "n", "corr_sig_D", "pct_B",
            "sharpe_A", "sharpe_B", "sharpe_rule", "cum_A", "cum_B", "cum_rule", "cum_oracle"]
    summary = pd.DataFrame(recs)[cols]
    # The two skew definitions never share a file: the daily run is the canonical
    # summary, the fallback writes its own so a monthly-skew row can't be quoted as
    # the 126-day one.
    name = ("skew_switch_variants_summary.csv" if daily is not None
            else "skew_switch_variants_panel_monthly.csv")
    summary.to_csv(ROOT / "results" / name, index=False)
    pd.set_option("display.width", 200)
    print("\n", summary.to_string(index=False))
    print(f"\nwrote results/{name}")


if __name__ == "__main__":
    main()
