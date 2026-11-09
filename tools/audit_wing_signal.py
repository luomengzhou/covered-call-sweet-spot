"""Independent audit of the wing_z signal (results/06_wing_signal_audit.md).

Recomputes the IV-wing slope and its z-score straight from
results/*/panel_monthly.csv -- no yfinance needed, since the wing is backed out
of the Income ladder's own (Cap, Call Yield) terms -- and adds the tests
06_skew_switch_variants.py does not run: HAC t-stats, month-clustered pooled
regressions, split-half stability, AR(1)-matched placebo correlations, partial
regressions against vol level, and paired t-tests of the rule against
always-A / always-B / best-in-hindsight.

Usage: python tools/audit_wing_signal.py
Prints only; writes nothing.
"""
import sys, math
from importlib import import_module
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from _config import _CONFIGS, income_pct, target_label
_v = import_module("06_skew_switch_variants")
_s5 = import_module("05_switch_signals")
matched_BD, perf = _s5.matched_BD, _s5.perf


def wing_detail(panel):
    """Same construction as monthly_wing, but keep fit diagnostics."""
    rows = panel[(panel["ppy"] == 12) & panel["family"].isin(["A", "B"])].dropna(
        subset=["cap_used", "y_used", "rf_3m"])
    rf_at_sale = panel[panel["ppy"] == 12].groupby("date")["rf_3m"].first().sort_index().shift(1)
    recs = []
    for d, grp in rows.groupby("date"):
        rate = rf_at_sale.get(d, np.nan)
        if not np.isfinite(rate):
            continue
        pts = {}
        for _, row in grp.iterrows():
            c = row["cap_used"] - 1
            if not (-0.05 <= c <= 0.60) or not (0 < row["y_used"] < 0.5):
                continue
            iv = _v._implied_vol(row["y_used"], row["cap_used"], rate)
            if np.isfinite(iv):
                pts.setdefault(round(c / 0.05, 10), []).append(iv)
        if len(pts) >= 3:
            x = np.array(sorted(pts)); y = np.array([np.mean(pts[k]) for k in sorted(pts)])
            sl, ic, r, p, se = stats.linregress(x, y)
            recs.append(dict(date=d, wing=sl, r2=r**2, npts=len(x),
                             atm_iv=ic, xmax=x.max(), xmin=x.min(),
                             nquotes=sum(len(v) for v in pts.values())))
    return pd.DataFrame(recs).set_index("date")


def hac_t(x, y, lags=6):
    """t-stat on slope of y ~ x with Newey-West HAC errors."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    X = np.column_stack([np.ones(len(x)), x])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtX_inv = np.linalg.inv(X.T @ X)
    S = (X * e[:, None]).T @ (X * e[:, None])
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None])
        S += w * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    return b[1], b[1] / math.sqrt(V[1, 1]), len(x)


print("=" * 100)
print("PART 1 — is the wing measure itself well identified?")
print("=" * 100)
print(f"{'ticker':8}{'n_months':>9}{'wing med':>10}{'wing sd':>9}{'R2 med':>8}"
      f"{'npts med':>9}{'xmax med':>9}{'AR(1)':>7}{'first':>9}{'last':>9}")
details, panels = {}, {}
for t in _CONFIGS:
    p = pd.read_csv(ROOT / "results" / t / "panel_monthly.csv", parse_dates=["date"])
    panels[t] = p
    d = wing_detail(p)
    details[t] = d
    ar1 = d["wing"].autocorr(1)
    print(f"{t:8}{len(d):>9}{d['wing'].median():>10.3f}{d['wing'].std():>9.3f}"
          f"{d['r2'].median():>8.2f}{d['npts'].median():>9.0f}{d['xmax'].median():>9.1f}"
          f"{ar1:>7.2f}{str(d.index[0].date()):>11}{str(d.index[-1].date()):>11}")

print("\n" + "=" * 100)
print("PART 2 — does wing_z predict D = r_A - r_B?  (HAC t-stats, sign prior: wing high -> A)")
print("=" * 100)
print(f"{'ticker':7}{'tgt':>5}{'n':>5}{'corr':>7}{'HACt':>7}{'D|lo tert':>11}{'D|hi tert':>11}"
      f"{'t(hi-lo)':>10}{'h1 corr':>9}{'h2 corr':>9}")
allrows = []
for t, cfg in _CONFIGS.items():
    p = panels[t]
    wz = pd.Series(_v.expanding_z(details[t]["wing"].to_numpy()), index=details[t].index)
    for tgt in cfg.switch_targets:
        if tgt not in set(p["index_name"]):
            continue
        g = matched_BD(p, tgt)
        if len(g) < 60:
            continue
        rA, rB, D = g["r_A"].values, g["r_B"].values, (g["r_A"] - g["r_B"]).values
        z = g["date"].map(wz).to_numpy()
        m = np.isfinite(z)
        if m.sum() < 60:
            continue
        zz, DD = z[m], D[m]
        _, tt, n = hac_t(zz, DD)
        c = np.corrcoef(zz, DD)[0, 1]
        q1, q2 = np.quantile(zz, [1/3, 2/3])
        lo, hi = DD[zz <= q1], DD[zz > q2]
        tw = stats.ttest_ind(hi, lo, equal_var=False)
        half = len(zz) // 2
        c1 = np.corrcoef(zz[:half], DD[:half])[0, 1]
        c2 = np.corrcoef(zz[half:], DD[half:])[0, 1]
        lbl = target_label(tgt)
        print(f"{t:7}{lbl:>5}{n:>5}{c:>7.3f}{tt:>7.2f}{lo.mean()*1e4:>11.0f}"
              f"{hi.mean()*1e4:>11.0f}{tw.statistic:>10.2f}{c1:>9.3f}{c2:>9.3f}")
        allrows.append(dict(t=t, tgt=lbl, z=zz, D=DD, rA=rA[m], rB=rB[m],
                            rf=g["rf"].values[m], dates=g["date"].values[m],
                            atm_iv=g["date"].map(details[t]["atm_iv"]).to_numpy()[m],
                            sig_impl=g["sigma_impl"].to_numpy()[m],
                            real_vol=g["real_vol"].to_numpy()[m], corr=c, hact=tt))

print("\n" + "=" * 100)
print("PART 3 — does the RULE monetize it?  paired t-tests of rule vs always-A / always-B")
print("=" * 100)
print(f"{'ticker':7}{'tgt':>5}{'ShA':>6}{'ShB':>6}{'ShRule':>8}{'d(r-B) bp':>11}{'t':>7}"
      f"{'d(r-best) bp':>14}{'t':>7}{'%A':>6}")
for r in allrows:
    rule = np.where(r["z"] > 0, r["rA"], r["rB"])
    sA = perf(r["rA"], r["rf"], r["dates"])["sharpe"]
    sB = perf(r["rB"], r["rf"], r["dates"])["sharpe"]
    sR = perf(rule, r["rf"], r["dates"])["sharpe"]
    best = r["rB"] if sB >= sA else r["rA"]
    dB, dBest = rule - r["rB"], rule - best
    tB = stats.ttest_1samp(dB, 0); tBest = stats.ttest_1samp(dBest, 0)
    print(f"{r['t']:7}{r['tgt']:>5}{sA:>6.2f}{sB:>6.2f}{sR:>8.2f}{dB.mean()*1e4:>11.0f}"
          f"{tB.statistic:>7.2f}{dBest.mean()*1e4:>14.0f}{tBest.statistic:>7.2f}"
          f"{np.mean(r['z'] > 0)*100:>6.0f}")

print("\n" + "=" * 100)
print("PART 4 — is wing_z distinct from plain vol level, or a proxy for it?")
print("=" * 100)
print(f"{'ticker':7}{'tgt':>5}{'r(wz,atmIV)':>13}{'r(wz,sigImp)':>14}{'r(wz,realVol)':>15}"
      f"{'HACt wz|ctrl':>14}")
for r in allrows:
    z, D = r["z"], r["D"]
    ctrl = np.column_stack([r["atm_iv"], r["sig_impl"], r["real_vol"]])
    m = np.isfinite(ctrl).all(1)
    # partial: residualize z on controls, then HAC t on D
    X = np.column_stack([np.ones(m.sum()), ctrl[m]])
    zr = z[m] - X @ np.linalg.lstsq(X, z[m], rcond=None)[0]
    Dr = D[m] - X @ np.linalg.lstsq(X, D[m], rcond=None)[0]
    _, tp, _ = hac_t(zr, Dr)
    print(f"{r['t']:7}{r['tgt']:>5}{np.corrcoef(z[m], r['atm_iv'][m])[0,1]:>13.2f}"
          f"{np.corrcoef(z[m], r['sig_impl'][m])[0,1]:>14.2f}"
          f"{np.corrcoef(z[m], r['real_vol'][m])[0,1]:>15.2f}{tp:>14.2f}")

print("\n" + "=" * 100)
print("PART 5 — multiple-testing context: how good is corr=0.15-0.30 vs random signals?")
print("=" * 100)
rng = np.random.default_rng(0)
for r in allrows:
    if r["t"] not in ("AMZN", "MSFT", "NVDA"):
        continue
    D = r["D"]
    # AR(1)-matched random signals (wing_z is persistent), 5000 draws
    rho = pd.Series(r["z"]).autocorr(1)
    n = len(D); cs = []
    for _ in range(5000):
        e = rng.standard_normal(n); s = np.empty(n); s[0] = e[0]
        for i in range(1, n):
            s[i] = rho * s[i-1] + math.sqrt(max(1e-9, 1 - rho**2)) * e[i]
        cs.append(np.corrcoef(s, D)[0, 1])
    cs = np.abs(np.array(cs))
    print(f"{r['t']:7}{r['tgt']:>5} rho(z)={rho:.2f}  |corr| obs={abs(r['corr']):.3f}  "
          f"placebo |corr| 90/95/99pct = {np.percentile(cs,90):.3f}/"
          f"{np.percentile(cs,95):.3f}/{np.percentile(cs,99):.3f}  "
          f"-> p_emp={np.mean(cs >= abs(r['corr'])):.3f}")


ROOT = Path(__file__).resolve().parent.parent
v = import_module("06_skew_switch_variants"); s5 = import_module("05_switch_signals")
matched_BD, perf = s5.matched_BD, s5.perf

cells = {}
for t, cfg in _CONFIGS.items():
    p = pd.read_csv(ROOT / "results" / t / "panel_monthly.csv", parse_dates=["date"])
    w = v.monthly_wing(p)
    wz = pd.Series(v.expanding_z(w.to_numpy()), index=w.index)
    for tgt in cfg.switch_targets:
        if tgt not in set(p["index_name"]): continue
        g = matched_BD(p, tgt)
        if len(g) < 60: continue
        z = g["date"].map(wz).to_numpy(); m = np.isfinite(z)
        if m.sum() < 60: continue
        cells[(t, target_label(tgt))] = dict(
            z=z[m], rA=g["r_A"].values[m], rB=g["r_B"].values[m],
            rf=g["rf"].values[m], dates=pd.DatetimeIndex(g["date"].values[m]))

# Every Income tier with >=3 live names, ascending: the sub-1%/mo grid included.
TARGET_LABELS = [
    lbl for lbl in sorted({k[1] for k in cells}, key=lambda s: float(s.rstrip("%")))
    if sum(1 for k in cells if k[1] == lbl) >= 3
]

print("=" * 92)
print("A. POOLED cross-sectional predictive test (all names stacked, clustered by month)")
print("=" * 92)
for tgtsel in TARGET_LABELS:
    rows = [(k, c) for k, c in cells.items() if k[1] == tgtsel]
    z = np.concatenate([c["z"] for _, c in rows])
    D = np.concatenate([c["rA"] - c["rB"] for _, c in rows])
    mo = np.concatenate([c["dates"].to_period("M").astype(str) for _, c in rows])
    X = np.column_stack([np.ones(len(z)), z])
    b = np.linalg.lstsq(X, D, rcond=None)[0]; e = D - X @ b
    XtXi = np.linalg.inv(X.T @ X); S = np.zeros((2, 2))
    for g_ in pd.unique(mo):
        i = mo == g_; Xg = X[i]; eg = e[i]
        S += np.outer(Xg.T @ eg, Xg.T @ eg)
    V = XtXi @ S @ XtXi
    print(f"  {tgtsel}: N={len(z)}  {len(rows)} names  slope={b[1]*1e4:7.1f} bp per 1z  "
          f"clustered t={b[1]/math.sqrt(V[1,1]):5.2f}   corr={np.corrcoef(z,D)[0,1]:.3f}")

print("\n" + "=" * 92)
print("B. POOLED equal-weight BACKTEST: wing rule (z>0 -> A) vs always-A / always-B")
print("=" * 92)
for tgtsel in TARGET_LABELS:
    rows = [(k, c) for k, c in cells.items() if k[1] == tgtsel]
    fr = {}
    for kind in ("rule", "rA", "rB", "rf"):
        ser = []
        for k, c in rows:
            val = np.where(c["z"] > 0, c["rA"], c["rB"]) if kind == "rule" else c[kind]
            ser.append(pd.Series(val, index=c["dates"], name=k[0]))
        fr[kind] = pd.concat(ser, axis=1, sort=True).sort_index()
    live = fr["rule"].notna().sum(axis=1) >= 3
    P = {k: x[live].mean(axis=1) for k, x in fr.items()}
    d = P["rule"].index
    out = {k: perf(P[k].values, P["rf"].values, d) for k in ("rA", "rB", "rule")}
    dB = (P["rule"] - P["rB"]).values
    tB = stats.ttest_1samp(dB, 0)
    print(f"  {tgtsel} (n={live.sum()} months): SharpeA={out['rA']['sharpe']:.2f} "
          f"SharpeB={out['rB']['sharpe']:.2f} SharpeRule={out['rule']['sharpe']:.2f} | "
          f"cumA={out['rA']['cum']:.1f}x cumB={out['rB']['cum']:.1f}x cumRule={out['rule']['cum']:.1f}x")
    print(f"       rule-minus-B: {dB.mean()*1e4:+.0f} bp/mo, t={tB.statistic:+.2f}, p={tB.pvalue:.2f}")
    # subperiod
    half = len(d) // 2
    for lbl, sl in (("H1", slice(0, half)), ("H2", slice(half, None))):
        db = dB[sl]
        print(f"       {lbl} {d[sl][0].date()}..{d[sl][-1].date()}: rule-B {db.mean()*1e4:+.0f} bp/mo, "
              f"t={stats.ttest_1samp(db,0).statistic:+.2f}")

print("\n" + "=" * 92)
print("C. Is the sign prior earned, or is 'z>0 -> A' just picking A more in the good-for-A era?")
print("=" * 92)
for tgtsel in TARGET_LABELS:
    rows = [(k, c) for k, c in cells.items() if k[1] == tgtsel]
    for k, c in rows:
        D = c["rA"] - c["rB"]
        yr = c["dates"].year
        early = yr < 2018; late = ~early
        print(f"  {k[0]:6}{tgtsel:>4}  %A-chosen early={np.mean(c['z'][early]>0)*100:3.0f}% "
              f"late={np.mean(c['z'][late]>0)*100:3.0f}%   meanD early={D[early].mean()*1e4:+5.0f}bp "
              f"late={D[late].mean()*1e4:+5.0f}bp")
