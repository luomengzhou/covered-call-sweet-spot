"""Chart the wing_z audit: pooled equity curves + per-name rule-minus-B edge.

Reads results/*/panel_monthly.csv, recomputes the wing_z rule exactly as
tools/audit_wing_signal.py does, and writes results/06_wing_signal_audit.png.

Usage: python tools/plot_wing_signal_audit.py
"""
from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# Figure text is English (reporting language); DejaVu carries the true minus sign.
plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from _config import _CONFIGS, target_label

_v = import_module("06_skew_switch_variants")
_s5 = import_module("05_switch_signals")
matched_BD, perf = _s5.matched_BD, _s5.perf

# palette (dataviz reference instance, light surface) --------------------------
SURFACE = "#fcfcfb"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"
S_A, S_B, S_RULE = "#2a78d6", "#eb6834", "#1baf7a"   # cat slots 1,2,3
POS, NEG, NEUTRAL = "#2a78d6", "#e34948", "#f0efec"  # diverging blue<->red

HEADLINE = ("1%", "3%")   # targets drawn in the figure; the CSV covers the full ladder


def build_cells() -> dict:
    cells = {}
    for t, cfg in _CONFIGS.items():
        p = pd.read_csv(ROOT / "results" / t / "panel_monthly.csv", parse_dates=["date"])
        wing = _v.monthly_wing(p)
        wz = pd.Series(_v.expanding_z(wing.to_numpy()), index=wing.index)
        for tgt in cfg.switch_targets:
            if tgt not in set(p["index_name"]):
                continue
            g = matched_BD(p, tgt)
            if len(g) < 60:
                continue
            z = g["date"].map(wz).to_numpy()
            m = np.isfinite(z)
            if m.sum() < 60:
                continue
            cells[(t, target_label(tgt))] = dict(
                z=z[m], rA=g["r_A"].values[m], rB=g["r_B"].values[m],
                rf=g["rf"].values[m], dates=pd.DatetimeIndex(g["date"].values[m]))
    return cells


def pooled(cells: dict, tgt: str) -> dict:
    rows = [(k, c) for k, c in cells.items() if k[1] == tgt]
    fr = {}
    for kind in ("rule", "rA", "rB", "rf"):
        ser = [pd.Series(np.where(c["z"] > 0, c["rA"], c["rB"]) if kind == "rule" else c[kind],
                         index=c["dates"], name=k[0]) for k, c in rows]
        fr[kind] = pd.concat(ser, axis=1, sort=True).sort_index()
    live = fr["rule"].notna().sum(axis=1) >= 3
    P = {k: x[live].mean(axis=1) for k, x in fr.items()}
    d = P["rule"].index
    out = {k: perf(P[k].values, P["rf"].values, d) for k in ("rA", "rB", "rule")}
    dB = (P["rule"] - P["rB"]).values
    half = len(d) // 2
    return dict(dates=d, paths={k: np.cumprod(1 + P[k].values) for k in ("rA", "rB", "rule")},
                sharpe={k: out[k]["sharpe"] for k in out}, n=int(live.sum()),
                dB=dB, dB_t=stats.ttest_1samp(dB, 0).statistic,
                halves=[(d[0], d[half - 1], dB[:half].mean(),
                         stats.ttest_1samp(dB[:half], 0).statistic),
                        (d[half], d[-1], dB[half:].mean(),
                         stats.ttest_1samp(dB[half:], 0).statistic)])


def per_name(cells: dict) -> pd.DataFrame:
    recs = []
    for (t, tgt), c in cells.items():
        rule = np.where(c["z"] > 0, c["rA"], c["rB"])
        sA = perf(c["rA"], c["rf"], c["dates"])["sharpe"]
        sB = perf(c["rB"], c["rf"], c["dates"])["sharpe"]
        best = c["rB"] if sB >= sA else c["rA"]
        dB, dBest = rule - c["rB"], rule - best
        chose_a = c["z"] > 0
        D = c["rA"] - c["rB"]
        recs.append(dict(
            cell=f"{t} {tgt}", ticker=t, tgt=tgt, n=len(rule),
            D_when_A_bp=D[chose_a].mean() * 1e4,
            D_when_B_bp=D[~chose_a].mean() * 1e4,
            sharpe_A=sA, sharpe_B=sB, sharpe_rule=perf(rule, c["rf"], c["dates"])["sharpe"],
            dB_bp=dB.mean() * 1e4, t_B=stats.ttest_1samp(dB, 0).statistic,
            dBest_bp=dBest.mean() * 1e4, t_best=stats.ttest_1samp(dBest, 0).statistic,
            pct_A=np.mean(c["z"] > 0) * 100))
    return pd.DataFrame(recs).sort_values("dB_bp")


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(BASELINE)
        ax.spines[s].set_linewidth(1)
    ax.tick_params(colors=MUTED, labelsize=8, length=3)


def main() -> None:
    cells = build_cells()
    pool = {t: pooled(cells, t) for t in HEADLINE}
    pn_all = per_name(cells)
    # The figure keeps the 1%/3% headline pair (the bar panel stays readable);
    # the exported CSV covers every Income tier, sub-1%/mo grid included.
    pn = pn_all[pn_all["tgt"].isin(HEADLINE)].reset_index(drop=True)

    fig = plt.figure(figsize=(13.5, 10.4), facecolor=SURFACE)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.25], hspace=0.40, wspace=0.16,
                          left=0.065, right=0.965, top=0.845, bottom=0.10)

    fig.text(0.065, 0.958, "IV-wing timing signal (wing_z): does it actually work?",
             fontsize=17, color=INK, weight="bold")
    fig.text(0.065, 0.922,
             "Rule: wing_z > 0 (call wing richer than its own history) -> strategy A, "
             "else B.   Recomputed from the current results/*/panel_monthly.csv.",
             fontsize=10, color=INK2)

    # --- row 1: pooled equity curves -----------------------------------------
    for i, tgt in enumerate(HEADLINE):
        ax = fig.add_subplot(gs[0, i]); style(ax)
        P = pool[tgt]
        ax.set_yscale("log")
        ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
        ax.set_axisbelow(True)
        for key, col, lab in (("rA", S_A, "Always A"), ("rB", S_B, "Always B"),
                              ("rule", S_RULE, "Wing rule")):
            ax.plot(P["dates"], P["paths"][key], color=col, lw=2, zorder=3,
                    solid_capstyle="round")
            ax.annotate(f"{lab}  {P['paths'][key][-1]:.1f}x",
                        xy=(P["dates"][-1], P["paths"][key][-1]),
                        xytext=(6, 0), textcoords="offset points",
                        fontsize=9, color=INK, va="center", weight="bold")
        ax.set_xlim(P["dates"][0], P["dates"][-1] + pd.Timedelta(days=1900))
        ax.set_title(f"MAG7 equal-weight pooled growth \u2014 Income {tgt} target\n"
                     f"n={P['n']} months, log scale",
                     fontsize=11, color=INK, loc="left", pad=8, linespacing=1.45)
        ax.set_ylabel("Cumulative growth (\u00d7)", fontsize=9, color=INK2)
        sh = P["sharpe"]
        ax.text(0.02, 0.96,
                f"Sharpe   Always A {sh['rA']:.2f}   Always B {sh['rB']:.2f}   "
                f"Rule {sh['rule']:.2f}\nRule \u2212 Always B   "
                f"{P['dB'].mean()*1e4:+.0f} bp/mo  (t={P['dB_t']:+.2f})",
                transform=ax.transAxes, fontsize=9, color=INK2, va="top",
                linespacing=1.6)
        seg = "   ".join(
            f"{a.year}–{b.year}: {m*1e4:+.0f}bp (t={t_:+.2f})" for a, b, m, t_ in P["halves"])
        ax.text(0.02, -0.155, "Split-half, rule \u2212 Always B:   " + seg, transform=ax.transAxes,
                fontsize=8.5, color=MUTED)

    # --- row 2: per-name diverging bars --------------------------------------
    ax = fig.add_subplot(gs[1, :]); style(ax)
    y = np.arange(len(pn))
    cols = [POS if v > 0 else NEG for v in pn["dB_bp"]]
    ax.axvspan(-1e9, 1e9, color=SURFACE, zorder=0)
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.barh(y, pn["dB_bp"], color=cols, height=0.62, zorder=3,
            edgecolor=SURFACE, linewidth=2)
    ax.axvline(0, color=BASELINE, lw=1.4, zorder=4)
    ax.set_yticks(y)
    ax.set_yticklabels(pn["cell"], fontsize=9, color=INK)
    ax.set_xlabel("Rule \u2212 Always B   (bp / month)", fontsize=9.5, color=INK2)
    ax.set_title("Per name and target: the rule's mean monthly edge   \u2014   "
                 "blue = beats Always B, red = loses to Always B\n"
                 "Grey: edge over the better-in-hindsight baseline (bp/mo) and its "
                 "t-stat, plus how often the rule picked A",
                 fontsize=11, color=INK, loc="left", pad=8, linespacing=1.5)
    lo, hi = pn["dB_bp"].min(), pn["dB_bp"].max()
    ax.set_xlim(lo * 1.46, hi + (hi - lo) * 1.15)
    lim = ax.get_xlim()[1]
    for yi, r in zip(y, pn.itertuples()):
        off = 7 if r.dB_bp > 0 else -7
        ha = "left" if r.dB_bp > 0 else "right"
        star = " *" if abs(r.t_B) >= 2 else ""
        ax.text(r.dB_bp + off, yi, f"{r.dB_bp:+.0f}  t={r.t_B:+.2f}{star}",
                fontsize=8.5, color=INK, va="center", ha=ha,
                weight="bold" if abs(r.t_B) >= 2 else "normal")
        ax.text(lim * 0.985, yi,
                f"vs best baseline {r.dBest_bp:+.0f}  t={r.t_best:+.2f}   picked A {r.pct_A:.0f}%",
                fontsize=8.5, color=MUTED, va="center", ha="right")
    ax.legend(handles=[Line2D([], [], color=POS, lw=7, label="Rule beats Always B"),
                       Line2D([], [], color=NEG, lw=7, label="Rule loses to Always B")],
              loc="upper left", bbox_to_anchor=(0.01, 0.60), frameon=False,
              fontsize=9.5, labelcolor=INK2, handlelength=1.6)
    ax.text(0.0, -0.215,
            "*  |t| \u2265 2.   Note: of the three cells that significantly beat Always B, none "
            "is significant against the better-in-hindsight baseline (max t = 1.33)\n"
            "\u2014 the edge is a constant tilt toward A on names where A already beats B, "
            "not timing.",
            transform=ax.transAxes, fontsize=8.5, color=MUTED, linespacing=1.7)

    out = ROOT / "results" / "06_wing_signal_audit.png"
    fig.savefig(out, dpi=170, facecolor=SURFACE)
    print(f"wrote {out}")
    cols_out = {"cell": "cell", "n": "months", "sharpe_A": "sharpe_always_A",
                "sharpe_B": "sharpe_always_B", "sharpe_rule": "sharpe_wing_rule",
                "D_when_A_bp": "D_in_months_rule_chose_A_bp",
                "D_when_B_bp": "D_in_months_rule_chose_B_bp",
                "dB_bp": "rule_minus_alwaysB_bp_per_month", "t_B": "t_vs_alwaysB",
                "dBest_bp": "rule_minus_best_baseline_bp_per_month",
                "t_best": "t_vs_best_baseline", "pct_A": "pct_months_chose_A"}
    # Figure sorts bars by magnitude; the table groups each name's targets together
    # (_CONFIGS order, then ascending premium target) so a name's rows read side by side.
    order = {t: i for i, t in enumerate(_CONFIGS)}
    tbl = pn_all.sort_values(
        ["ticker", "tgt"],
        key=lambda c: c.map(order) if c.name == "ticker"
        else c.str.rstrip("%").astype(float))
    table = tbl[list(cols_out)].rename(columns=cols_out).round(2)
    table.to_csv(ROOT / "results" / "06_wing_signal_audit_bynames.csv", index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
