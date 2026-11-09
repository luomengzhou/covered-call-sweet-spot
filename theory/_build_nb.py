import pathlib
import nbformat as nbf

nb = nbf.v4.new_notebook()
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip("\n")))
co = lambda s: C.append(nbf.v4.new_code_cell(s.strip("\n")))

md(r"""
# Covered Call A vs B — interactive explorer

Companion to `AB_explorer.html` (same math, cross-checked to 8 decimals) and to
`00_theory_derivation_en.md`.

**Setup.** Hold 1 unit of the underlying, sell a fraction $f$ of calls struck at
$K = S_0(1+c)$. With $r$ the underlying *price* return and $y(c)=C(K)/S_0$ the
premium as a fraction of spot, banked at the risk-free rate to $\tilde y = y e^{r_f\tau}$:

$$R(r) = r + \text{div} + f\tilde y - f\,(r-c)^+$$

- **A**: $f_A$ (default 1, full notional) at $c_A$ (default 5% OTM)
- **B**: $c_B$ (default 0, ATM), with $f_B$ pinned by the **equal-premium constraint**
  $f_A\tilde y_A = f_B \tilde y_B$, i.e. $f_B = f_A\,y_A/y_B$.

Here $q$ is an annualized yield used **only in option pricing**. If no actual single-period
cash dividend is supplied, the toy return view uses $d_q=e^{q\tau}-1$ as a deterministic
period-dividend proxy; `Params(dividend_return=...)` overrides that proxy with an actual
period return. Under the equal-premium constraint the premium terms cancel exactly, and so do the dividends
(both legs are long 1 unit of the underlying), leaving a **zero-cost ratio call spread**:

$$D(r) = R_A(r) - R_B(r) = f_B(r-c_B)^+ - f_A(r-c_A)^+$$

$$D_{\text{peak}} = f_B(c_A-c_B)\ \text{at } r=c_A, \qquad
r^{**} = \frac{f_Ac_A - f_Bc_B}{f_A-f_B}$$

$f_A=1,\,c_B=0$ recovers $r^{**}=c_A/(1-f_B)$. These peak/crossover statements require
$c_A\ge c_B$, strictly positive raw wing volatilities and option premia, $f_B\in[0,1]$,
and (when $c_A>c_B$) $f_B<f_A$. Outside that feasible region the comparison is invalid;
it is not a reversed or extrapolated peak. Within it, $D>0$ means A is ahead: **A's edge
is capped at $D_{\text{peak}}$, B's is unbounded** because the $r>c_B$ leg keeps slope $1-f_B>0$.

**Skew.** In Black–Scholes, $\sigma_{IV}(c)=\sigma_{ATM}$ for every $c$. Markets break
that, so the explorer uses a first-order call-wing tilt quoted in **vol points per 5% OTM**
(desk language), not a multiplicative ratio:

$$\sigma_{IV}(c) = \sigma_{ATM} + \texttt{wing}\cdot\frac{c}{5\%}$$

| wing | meaning |
|---|---|
| $0$ | flat (BS) |
| $-0.0052$ | NVDA measured, single growth stock (~0.52 vol lower per 5% OTM) |
| $-0.02$ | SPX-style broad index anchor, persistent put skew (2 vol lower per 5% OTM) |
| $+0.045$ | commodity-style positive wing (supply-shock fear), $k=1.10\times$ at a 45% ATM anchor |

This is a sensitivity knob, not an SVI surface. See §1's "What wing value should I actually
try?" note below for the market intuition behind each shape.

**Carry.** Forward $= S_0 e^{(r_f-q-\text{borrow})\tau}$. `borrow` is a
**stock-borrow / carry adjustment used only in option pricing**; it enters the pricing
forward like an extra dividend yield, but is not a portfolio funding cash flow.
""")

co(r"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd()))          # ab_core.py lives next to this notebook

import numpy as np
import matplotlib.pyplot as plt
from ab_core import (
    Params, solve, scenario_grid, self_check,
    WING_FLAT, WING_NVDA, WING_INDEX, WING_COMMODITY_45,
)

%matplotlib inline
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 200, "font.size": 9,
    "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False,
    "axes.spines.right": False, "figure.autolayout": True,
})

CHARTS = pathlib.Path("charts"); CHARTS.mkdir(exist_ok=True)   # relative, not /sessions/...
self_check()
""")

md(r"""
## 1 · Interactive dashboard

Every parameter that shows up anywhere in the derivation gets a control: spot, ATM vol,
tenor, risk-free, annualized pricing yield $q$, optional actual period dividend,
stock-borrow/carry, call-wing `wing` (vol pts / 5% OTM), both caps, and $f_A$.
$f_B$ is **not** a slider — it is solved from the equal-premium constraint.

Requires `ipywidgets` (`pip install ipywidgets`). If it is unavailable, skip to §2,
which needs nothing but matplotlib.
""")

co(r"""
import ipywidgets as W
from IPython.display import display

def _pct(desc, val, lo, hi, step):
    return W.FloatSlider(value=val, min=lo, max=hi, step=step, description=desc,
                         readout_format=".2%", continuous_update=False,
                         style={"description_width": "150px"},
                         layout=W.Layout(width="380px"))

w = dict(
    S0     = W.FloatSlider(value=100, min=10, max=1000, step=1, description="spot S₀",
                           readout_format=".0f", continuous_update=False,
                           style={"description_width":"150px"}, layout=W.Layout(width="380px")),
    sigma_atm = _pct("σ_ATM",            0.45, 0.10, 0.60, 0.005),
    tau_m  = W.IntSlider(value=1, min=1, max=12, step=1, description="tenor (months)",
                         continuous_update=False, style={"description_width":"150px"},
                         layout=W.Layout(width="380px")),
    rf     = _pct("risk-free r_f",       0.04, 0.00, 0.08, 0.0025),
    q      = _pct("pricing yield q",     0.00, 0.00, 0.06, 0.0025),
    use_actual_dividend = W.Checkbox(value=False, description="use actual period dividend",
                                     indent=False, layout=W.Layout(width="380px")),
    dividend_return = _pct("actual period dividend", 0.00, 0.00, 0.03, 0.0005),
    borrow = _pct("stock-borrow / carry", 0.00, 0.00, 0.05, 0.0025),
    wing   = W.FloatSlider(value=0.0, min=-0.05, max=0.05, step=0.001,
                           description="wing (vol / 5% OTM)", readout_format=".3f",
                           continuous_update=False, style={"description_width":"150px"},
                           layout=W.Layout(width="380px")),
    c_A    = _pct("A cap c_A (OTM)",     0.05, 0.00, 0.25, 0.0025),
    c_B    = _pct("B cap c_B (0 = ATM)", 0.00, 0.00, 0.15, 0.0025),
    f_A    = W.FloatSlider(value=1.00, min=0.20, max=1.00, step=0.01, description="f_A",
                           readout_format=".2f", continuous_update=False,
                           style={"description_width":"150px"}, layout=W.Layout(width="380px")),
    r_max  = _pct("return axis max",     0.40, 0.15, 1.00, 0.05),
)

def dashboard(S0, sigma_atm, tau_m, rf, q, use_actual_dividend, dividend_return,
              borrow, wing, c_A, c_B, f_A, r_max):
    p = Params(S0=S0, sigma_atm=sigma_atm, tau=tau_m/12, rf=rf, q=q,
               dividend_return=dividend_return if use_actual_dividend else None,
               borrow=borrow, wing=wing, c_A=c_A, c_B=c_B, f_A=f_A)
    try:
        s = solve(p)
    except ValueError as exc:
        print(f"INVALID — {exc}")
        print("No return curves, D_peak, or r** are drawn for this parameter combination.")
        return

    fig, ax = plt.subplots(1, 2, figsize=(11.2, 3.9))

    # --- panel 1: single-period return -------------------------------------
    r = np.linspace(-0.30, r_max, 700)
    ax[0].plot(r, 100*s.R_bh(r), color="#8b93a1", ls="--", lw=1.2, label="buy & hold")
    ax[0].plot(r, 100*s.R_A(r),  color="#1f77b4", lw=2,
               label=f"A  f={f_A:.2f} @ {c_A:.2%} OTM")
    ax[0].plot(r, 100*s.R_B(r),  color="#ff7f0e", lw=2,
               label=f"B  f={s.f_B:.3f} @ {c_B:.2%}")
    if np.isfinite(s.ceiling_A):
        ax[0].axhline(100*s.ceiling_A, color="#1f77b4", lw=.7, ls=":")
        ax[0].annotate(f"ceiling $c_A+\\tilde y_A$ = {s.ceiling_A:.2%}",
                       (r_max, 100*s.ceiling_A), ha="right", va="bottom",
                       fontsize=7.5, color="#1f77b4")
    if np.isfinite(s.r_star_star):
        ax[0].axvline(s.r_star_star, color="#7c5cff", lw=.8, ls=":")
    ax[0].set_title("1 · single-period return", fontsize=9.5, loc="left")
    ax[0].set_xlabel("underlying price return $r$"); ax[0].set_ylabel("return (%)")
    ax[0].legend(fontsize=7.5, frameon=False, loc="upper left")

    # --- panel 2: D(r) ------------------------------------------------------
    d = 100*s.D(r)
    ax[1].axhline(0, color="#888", lw=.8)
    ax[1].plot(r, d, color="#2ca02c", lw=2)
    ax[1].fill_between(r, 0, d, where=d > 0, color="#1f77b4", alpha=.13)
    ax[1].fill_between(r, 0, d, where=d < 0, color="#ff7f0e", alpha=.13)
    ax[1].plot([c_A], [100*s.D_peak], "o", ms=4.5, color="#2ca02c")
    ax[1].annotate(f"peak $f_B(c_A-c_B)$ = {s.D_peak:.2%}\nat $r=c_A$={c_A:.2%}",
                   (c_A, 100*s.D_peak), textcoords="offset points", xytext=(8, -2),
                   fontsize=7.5, color="#2ca02c")
    if np.isfinite(s.r_star_star):
        ax[1].axvline(s.r_star_star, color="#7c5cff", lw=.8, ls=":")
        ax[1].annotate(f"$r^{{**}}$ = {s.r_star_star:.2%}", (s.r_star_star, 0),
                       textcoords="offset points", xytext=(5, 8),
                       fontsize=7.5, color="#7c5cff")
    ax[1].set_title(r"2 · $D(r)=R_A-R_B$   (zero-cost ratio call spread)",
                    fontsize=9.5, loc="left")
    ax[1].set_xlabel("$r$"); ax[1].set_ylabel("A − B (%)")
    plt.show()

    g = s.portfolio_greeks()
    print(f"σ_IV(c_A) = {s.sigma_A:7.4%}   σ_IV(c_B) = {s.sigma_B:7.4%}"
          f"   ({100*(s.sigma_A - sigma_atm):+.2f} vol pts vs ATM at c_A)"
          f"   wing={100*wing:+.2f} vol / 5% OTM")
    print(f"y_A = {s.y_A:7.4%}   y_B = {s.y_B:7.4%}   ->  f_B = {s.f_B:.6f}"
          f"   (slope above c_B = 1-f_B = {s.slope_B:.4f})")
    print(f"D_peak = {s.D_peak:7.4%}   r** = {s.r_star_star:7.4%}"
          f"   r* vs buy&hold = {s.r_star_A:7.4%}  (independent of f_A)")
    source = "actual dividend_return" if use_actual_dividend else "toy proxy exp(q·τ)−1"
    print(f"K_A = {s.K_A:.2f}   K_B = {s.K_B:.2f}   period dividend = {s.dq:.4%}"
          f"  ({source}; cancels in D)")
    print("\nportfolio Greeks (long 1 unit underlying, short f calls):")
    print(f"{'':4s}{'Δ':>10s}{'Γ':>12s}{'ν /vol pt':>12s}{'Θ /day':>10s}{'ρ /1%':>10s}")
    for tag in ("A", "B"):
        v = g[tag]
        print(f"{tag:4s}{v['delta']:10.4f}{v['gamma']:12.2e}"
              f"{v['vega']:12.4f}{v['theta']:10.4f}{v['rho']:10.3f}")
    print("\n" + s.verdict())

out = W.interactive_output(dashboard, w)
left  = W.VBox([w["S0"], w["sigma_atm"], w["tau_m"], w["rf"], w["q"],
                w["use_actual_dividend"], w["dividend_return"], w["borrow"]])
right = W.VBox([w["wing"], w["c_A"], w["c_B"], w["f_A"], w["r_max"]])
display(W.HBox([left, right]), out)
""")

md(r"""
### What wing value should I actually try?

No fixed scenario set — drag the slider using market intuition instead:

- **Broad index (SPX-style):** persistent, steep put skew (leverage effect + structural
  put-buying demand). wing is clearly negative, typically −0.02 to −0.03 per 5% OTM — the
  most stable skew shape in equities.
- **Single growth/momentum stock (NVDA-like):** same sign, much shallower — upside tail
  hope (M&A, earnings pops) partly offsets the crash-fear put skew. NVDA measured ≈
  −0.0052, right direction but ~4× flatter than the index case.
- **Commodities (oil etc.):** sometimes flips the other way (wing > 0) — fear of a supply
  shock spiking price. One of the few asset classes where a positive wing has real market
  grounding.
- **FX:** closer to a symmetric double-sided smile; direction depends on which way the
  pair's tail risk runs. This single-slope `wing` knob doesn't really apply to FX.

Sign convention: **wing > 0 helps A, wing < 0 helps B.** Richer OTM calls raise $y_A$, which
raises $f_B$ through the premium match, which shrinks B's uncapped slope $1-f_B$.
""")

md(r"""
## 2 · Scenario grid — the static deliverable

IV 10–45%, tenor 1M–1Y, rate around 4%, plus the call-wing parameter in vol points.
This is the same object as §1, just tabulated and rendered rather than dragged.
""")

co(r"""
grid = scenario_grid(
    sigma_atm=[0.10, 0.20, 0.30, 0.45],
    tau=[1/12, 3/12, 6/12, 1.0],
    wing=[WING_INDEX, WING_FLAT, WING_COMMODITY_45],  # index anchor / flat / commodity-style
)
grid.to_csv("scenario_grid.csv", index=False)

view = grid.assign(
    tenor=lambda d: (12*d.tau).round().astype(int).astype(str) + "M",
    IV=lambda d: (100*d.sigma_atm).round(0).astype(int).astype(str) + "%",
    wing_label=lambda d: (100*d.wing).round(1).astype(str) + "vol",
).pivot_table(index=["IV", "tenor"], columns="wing_label", values="r_star_star")
print("r** by (IV, tenor) x call wing (vol pts / 5% OTM)\n")
print((100*view).round(2).to_string())
""")

co(r"""
wings = [WING_INDEX, WING_FLAT, WING_COMMODITY_45]
titles = ["wing = −2.0 vol / 5%  (SPX-style index anchor)",
          "wing =  0    (flat surface)",
          "wing = +4.5 vol / 5%  (commodity-style, k=1.10× @ 45% ATM)"]
sig_ax = np.linspace(0.10, 0.45, 60)
tau_ax = np.array([1, 2, 3, 4, 6, 9, 12]) / 12

fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.6), sharey=True)
for ax, wing, ttl in zip(axes, wings, titles):
    for tau in tau_ax:
        vals = [solve(Params(sigma_atm=s, tau=tau, wing=wing)).r_star_star for s in sig_ax]
        ax.plot(100*sig_ax, 100*np.array(vals), lw=1.6,
                label=f"{round(12*tau)}M")
    ax.set_title(ttl, fontsize=8.5, loc="left")
    ax.set_xlabel("σ_ATM (%)")
    ax.set_yscale("log")             # +4.5vol x 12M x 45% blows up: f_B -> f_A
    ax.set_yticks([5, 10, 20, 50, 100, 300])
    ax.set_yticklabels(["5", "10", "20", "50", "100", "300"])
    ax.grid(True, which="minor", alpha=.12)
axes[0].set_ylabel("$r^{**}$ (%, log scale)")
axes[-1].legend(fontsize=7, frameon=False, ncol=2, title="tenor",
                title_fontsize=7, loc="lower right")
fig.suptitle("Where B takes over from A ($r^{**}$), across IV × tenor × call wing"
             "   —   $c_A$=5% OTM, $c_B$=ATM, $f_A$=1, $r_f$=4%",
             fontsize=9.5, y=1.06)
fig.savefig(CHARTS / "01_scenario_rstarstar.png", bbox_inches="tight")
plt.show()
""")

co(r"""
fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.6), sharey=True)
for ax, wing, ttl in zip(axes, wings, titles):
    for tau in tau_ax:
        vals = [solve(Params(sigma_atm=s, tau=tau, wing=wing)).D_peak for s in sig_ax]
        ax.plot(100*sig_ax, 100*np.array(vals), lw=1.6, label=f"{round(12*tau)}M")
    ax.set_title(ttl, fontsize=8.5, loc="left")
    ax.set_xlabel("σ_ATM (%)")
axes[0].set_ylabel("$D_{peak}$ (%)")
axes[-1].legend(fontsize=7, frameon=False, ncol=2, title="tenor", title_fontsize=7)
fig.suptitle("A's maximum edge $D_{peak}=f_B(c_A-c_B)$, across IV × tenor × call wing",
             fontsize=9.5, y=1.06)
fig.savefig(CHARTS / "02_scenario_Dpeak.png", bbox_inches="tight")
plt.show()
""")

md(r"""
## 3 · Reading the grid

Three comparative statics fall out, and they are the things to say out loud:

1. **Higher IV pushes $r^{**}$ out at the displayed anchor.** The relevant object is not
   dollar vega in isolation but the premium ratio $f_B/f_A=y_A/y_B$. Here the OTM call has
   the higher *relative price elasticity* to IV, so $y_A/y_B$ and $f_B$ rise, B's residual
   slope $1-f_B$ shrinks, and $r^{**}$ moves right. This is an anchor-specific numerical
   comparative static, not a global theorem for every strike/smile combination.
2. **Longer tenor has the same direction at the displayed anchor.** Extra tenor raises the
   OTM premium proportionally more than the ATM premium, so $y_A/y_B$ and $f_B$ rise and
   $r^{**}$ moves right. Again, the ratio—not the statement that ATM has more dollar
   sensitivity—is what governs the equal-premium comparison.
3. **Skew is the weakest of the three** *in the middle of the range* — but it is the only
   one that can break the comparison outright. At wing = +4.5 vol (commodity-style), long
   tenor and high vol, $y_A \to y_B$, so $f_B \to f_A$ and $r^{**}$ runs away (note the log
   axis). That is not a numerical artifact: with a steep enough upward call wing the 5% OTM
   call is worth nearly as much as the ATM call, B has to sell nearly full notional, and the
   two structures stop being distinguishable. Flag this: +4.5 vol / 5% only shows up in
   asset classes with real supply-shock fear (commodities); it is not a mild equity baseline.
4. **Skew still moves $r^{**}$ less than IV does over the realistic range.** Going from the
   index anchor (−2 vol) to the commodity-style case (+4.5 vol) moves $r^{**}$ by a few
   points; moving IV from 10% to 45% moves it by multiples. Same conclusion as the
   Breeden–Litzenberger work on 07-31 from the $\mathbb{Q}$-measure side.

### Skew grounding, revisited

An earlier version of the derivation assumed a call wing ~2 vol below ATM per 5% OTM was
"the typical shape of the equity option surface" for any single stock. NVDA measures
**0.52** vol — about 4× flatter. That −2 vol anchor is real, but it describes a broad
index (SPX-style), not a single growth stock: see `ab_core.py`'s module docstring for the
market intuition by asset class. Anything load-bearing should use IVs backed out from
`Cap`+`Call Yield` (or a real surface), not this linear knob alone.
""")

nb["cells"] = C
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}
nbf.write(nb, str(pathlib.Path(__file__).with_name("AB_explorer.ipynb")))
print("wrote AB_explorer.ipynb with", len(C), "cells")
