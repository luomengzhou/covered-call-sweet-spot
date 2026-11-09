# -*- coding: utf-8 -*-
"""
Theory charts: A vs B (premium-matched) payoff comparison and the shape of D(r)=R_A-R_B.
Formulas from 00_theory_derivation_zh.md  Sec 1.2 (1b) / Sec 3.1 / Sec 3.3 eqs (3)(4)
    R_cc(f,c) = (1-f)r + f*min(r,c) + f*y(c)*e^{r_f tau} + d_T
    D(r)      = f_B (r-c_B)^+ - f_A (r-c_A)^+        <- zero-cost ratio call spread
    r**       = (f_A c_A - f_B c_B) / (f_A - f_B)
"""
from pathlib import Path

import numpy as np
from scipy.stats import norm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
plt.rcParams["mathtext.fontset"] = "dejavusans"
plt.rcParams["axes.unicode_minus"] = False

# ---------- Parameters (same numerical example as Sec 3.1) ----------
SIG, TAU, RF = 0.45, 1/12, 0.04
Q_ANNUAL, D_T = 0.0, 0.0       # toy case: q prices options; returns use period dividend d_T

def call_yield(c, sig=SIG, tau=TAU, rf=RF, q_annual=Q_ANNUAL):
    """Black-Scholes premium per unit spot, y(c), with k = 1+c."""
    k = 1.0 + c
    d1 = (-np.log(k) + (rf - q_annual + 0.5*sig**2)*tau) / (sig*np.sqrt(tau))
    d2 = d1 - sig*np.sqrt(tau)
    return np.exp(-q_annual*tau)*norm.cdf(d1) - k*np.exp(-rf*tau)*norm.cdf(d2)

def R_cc(r, f, c):
    return (1-f)*r + f*np.minimum(r, c) + f*call_yield(c)*np.exp(RF*TAU) + D_T

def D_exact(r, fA, cA, fB, cB):
    """Eq (3). Equals R_A - R_B only under premium matching."""
    return fB*np.maximum(r-cB, 0) - fA*np.maximum(r-cA, 0)

def r_star_star(fA, cA, fB, cB):
    return (fA*cA - fB*cB) / (fA - fB)

# ---------- Baseline A / B ----------
cA, fA = 0.05, 1.00          # A: fully covered 5% OTM (Income family)
cB      = 0.00               # B: ATM
yA, yB  = call_yield(cA), call_yield(cB)
fB      = fA*yA/yB           # premium matching: f_A y(c_A) = f_B y(c_B)
Y       = fA*yA
yt      = np.exp(RF*TAU)     # e^{r_f tau}
r_ss    = r_star_star(fA, cA, fB, cB)
r_st    = cA + yA*yt         # Sec 3.1 crossover vs underlying (A, f=1)

r = np.linspace(-0.30, 0.30, 1201)
CA, CB, CS = "#c0392b", "#2471a3", "#7f8c8d"

fig, axes = plt.subplots(2, 2, figsize=(15.5, 11))
pf = PercentFormatter(1.0, decimals=0)

# ===== Panel 1: return comparison =====
ax = axes[0, 0]
ax.plot(r, r+D_T, color=CS, lw=1.6, ls="--", label="Underlying buy & hold:  r + d_T")
ax.plot(r, R_cc(r, fA, cA), color=CA, lw=2.4,
        label=f"A: f={fA:.2f}, c={cA:.0%} (fully covered OTM), y={yA:.2%}")
ax.plot(r, R_cc(r, fB, cB), color=CB, lw=2.4,
        label=f"B: f={fB:.3f}, c=0% (partial ATM), y={yB:.2%}")
ax.axhline(0, color="k", lw=.6); ax.axvline(0, color="k", lw=.6)
for x, lab, col in [(cB, "$c_B=0$", CB), (cA, "$c_A$=5%", CA),
                    (r_ss, f"$r^{{**}}$={r_ss:.2%}", "#8e44ad")]:
    ax.axvline(x, color=col, lw=.9, ls=":", alpha=.8)
    ax.text(x, -0.295, lab, color=col, fontsize=9.5,
            rotation=90, va="bottom", ha="right")
ax.plot([cA], [R_cc(cA, fA, cA)], "o", color=CA, ms=6)
ax.plot([cB], [R_cc(cB, fB, cB)], "o", color=CB, ms=6)
ax.annotate("A is capped at c+$\\tilde y$ = %.2f%%" % ((cA+yA*yt)*100),
            xy=(0.235, cA+yA*yt), xytext=(0.045, cA+yA*yt+0.085),
            color=CA, fontsize=10,
            arrowprops=dict(arrowstyle="->", color=CA, lw=.9))
ax.annotate("B uncapped, slope $1-f_B$", xy=(0.265, R_cc(0.265, fB, cB)),
            xytext=(0.115, R_cc(0.265, fB, cB)-0.115), color=CB, fontsize=10,
            arrowprops=dict(arrowstyle="->", color=CB, lw=.9))
ax.set_title("(1) Single-period return: A (fully covered OTM) vs B (partial ATM), premium-matched",
             fontsize=12, pad=10)
ax.set_xlabel("Underlying net price return $r$"); ax.set_ylabel("Portfolio return $R_{cc}$")
ax.legend(loc="upper left", fontsize=9.5, framealpha=.95)
ax.xaxis.set_major_formatter(pf); ax.yaxis.set_major_formatter(pf)
ax.grid(alpha=.25)

# ===== Panel 2: D(r) =====
ax = axes[0, 1]
d = D_exact(r, fA, cA, fB, cB)
ax.plot(r, d, color="#1e8449", lw=2.6, label="$D(r)=R_A-R_B$")
ax.fill_between(r, 0, d, where=d >= 0, color=CA, alpha=.16)
ax.fill_between(r, 0, d, where=d < 0, color=CB, alpha=.16)
ax.axhline(0, color="k", lw=.6); ax.axvline(0, color="k", lw=.6)
Dmax = fB*(cA-cB)
ax.plot([cA], [Dmax], "o", color="#1e8449", ms=7, zorder=5)
ax.annotate("A's max edge = $f_B(c_A-c_B)$ = %.2f%%\n(attained at r = $c_A$)" % (Dmax*100),
            xy=(cA, Dmax), xytext=(-0.285, Dmax-0.004), fontsize=9.5, va="top",
            arrowprops=dict(arrowstyle="->", lw=.9,
                            connectionstyle="arc3,rad=-0.12"))
ax.plot([r_ss], [0], "o", color="#8e44ad", ms=7, zorder=5)
ax.annotate("$r^{**}=\\dfrac{f_Ac_A-f_Bc_B}{f_A-f_B}$ = %.2f%%" % (r_ss*100),
            xy=(r_ss, 0), xytext=(r_ss-0.005, 0.0175), fontsize=10, color="#8e44ad",
            arrowprops=dict(arrowstyle="->", color="#8e44ad", lw=.9))
ax.text(-0.285, -0.032, "$r \\leq c_B$ :  $D \\equiv 0$\n(exact tie)", fontsize=9.5, color="#555")
ax.text(0.155, -0.028, "slope $-(f_A-f_B)$ = $-$%.3f\nB's edge is unbounded" % (fA-fB),
        fontsize=9.5, color=CB, va="top")
ax.annotate("slope $+f_B$ = %.3f" % fB, xy=(0.028, D_exact(0.028, fA, cA, fB, cB)),
            xytext=(-0.095, 0.0295), fontsize=9.5, color=CA,
            arrowprops=dict(arrowstyle="->", color=CA, lw=.9))
ax.set_ylim(-0.072, 0.042)
ax.set_title("(2) $D(r)=f_B(r-c_B)^+-f_A(r-c_A)^+$  —  a zero-cost ratio call spread (eq. 3)",
             fontsize=12, pad=10)
ax.set_xlabel("Underlying net price return $r$"); ax.set_ylabel("$D=R_A-R_B$")
ax.legend(loc="upper left", fontsize=10)
ax.xaxis.set_major_formatter(pf); ax.yaxis.set_major_formatter(pf)
ax.grid(alpha=.25)

# ===== Panel 3: D(r) as c_A moves (B always the premium-matched ATM) =====
ax = axes[1, 0]
cmap = plt.cm.viridis(np.linspace(.12, .88, 5))
rows = []
for col, cA_i in zip(cmap, [0.02, 0.05, 0.08, 0.12, 0.20]):
    yA_i = call_yield(cA_i)
    fB_i = 1.0*yA_i/yB
    d_i  = D_exact(r, 1.0, cA_i, fB_i, cB)
    rss  = r_star_star(1.0, cA_i, fB_i, cB)
    ax.plot(r, d_i, color=col, lw=2.1,
            label=f"$c_A$={cA_i:.0%} $\\to$ $f_B$={fB_i:.3f},  $r^{{**}}$={rss:.1%}")
    ax.plot([cA_i], [fB_i*cA_i], "o", color=col, ms=5)
    ax.plot([rss], [0], "v", color=col, ms=6)
    rows.append((cA_i, yA_i, fB_i, fB_i*cA_i, rss))
ax.axhline(0, color="k", lw=.6); ax.axvline(0, color="k", lw=.6)
ax.set_title("(3) Pushing A's strike out: peak edge first rises then falls (non-monotonic); $r^{**}$ shifts right",
             fontsize=12, pad=10)
ax.set_xlabel("Underlying net price return $r$"); ax.set_ylabel("$D=R_A-R_B$")
ax.legend(loc="lower left", fontsize=9)
ax.xaxis.set_major_formatter(pf); ax.yaxis.set_major_formatter(pf)
ax.set_ylim(-0.13, 0.05); ax.grid(alpha=.25)

# ===== Panel 4: each vs the underlying =====
ax = axes[1, 1]
ax.plot(r, R_cc(r, fA, cA)-(r+D_T), color=CA, lw=2.4, label="A $-$ underlying")
ax.plot(r, R_cc(r, fB, cB)-(r+D_T), color=CB, lw=2.4, label="B $-$ underlying")
ax.axhline(0, color="k", lw=.6); ax.axvline(0, color="k", lw=.6)
for f_, c_, col, nm in [(fA, cA, CA, "A"), (fB, cB, CB, "B")]:
    rs = c_ + call_yield(c_)*yt
    ax.axvline(rs, color=col, lw=.9, ls=":")
    ax.plot([rs], [0], "o", color=col, ms=6)
    lab4 = "%s: $r^*$ = c+$\\tilde y$ = %.2f%%" % (nm, rs*100)
    ax.annotate(lab4, xy=(rs, 0), xytext=(rs+0.045, -0.045 if nm == "A" else -0.105),
                color=col, fontsize=10,
                arrowprops=dict(arrowstyle="->", color=col, lw=.9))
ax.text(-0.29, -0.012, "the two lines coincide for $r \\leq 0$\n"
        "(premium matching $\\Rightarrow$ identical\ndownside buffer of %.2f%%)" % (Y*yt*100),
        fontsize=9.5, color="#555", va="top")
ax.set_title("(4) Excess over buy & hold: the crossover $r^*$ = c+$\\tilde y$ does not depend on f (Sec 3.1)",
             fontsize=12, pad=10)
ax.set_xlabel("Underlying net price return $r$"); ax.set_ylabel("$R_{cc}-R_{stock}$")
ax.legend(loc="lower left", fontsize=10)
ax.xaxis.set_major_formatter(pf); ax.yaxis.set_major_formatter(pf)
ax.grid(alpha=.25)

fig.suptitle("Covered call theory  ·  A vs B, premium-matched at Y=%.3f%%"
             "     $\\sigma_{IV}$=%.0f%%,  $\\tau$=1M,  $r_f$=%.0f%%,  q=0, d_T=0"
             % (Y*100, SIG*100, RF*100), fontsize=14.5, y=0.985)
fig.tight_layout(rect=[0, 0.02, 1, 0.965])
out = Path(__file__).resolve().parent / "charts" / "00_theory_A_vs_B_en.png"
out.parent.mkdir(exist_ok=True)
fig.savefig(out, dpi=170)
fig.savefig(out.with_suffix(".pdf"))

# ---------- Self-checks (reconcile with Sec 3.3) ----------
print(f"y(cA)={yA:.4%}  y(0)={yB:.4%}  fB={fB:.4f}  Y={Y:.4%}")
print(f"A cap = c+yt = {cA+yA*yt:.4%}   r*(A) = {r_st:.4%}")
print(f"r** = {r_ss:.4%}   (md records 13.06%)")
print(f"D(cA) = {D_exact(cA,fA,cA,fB,cB):.4%}  (= fB*cA = {fB*cA:.4%})")
print(f"D(r**) = {D_exact(r_ss,fA,cA,fB,cB):.2e}")
chk = np.max(np.abs((R_cc(r,fA,cA)-R_cc(r,fB,cB)) - D_exact(r,fA,cA,fB,cB)))
print(f"max |(R_A-R_B) - D(r)| = {chk:.2e}   <- should be 0 under premium matching")
print("\ncA     y(cA)    fB      D_max    r**")
for a,b,c,d,e in rows: print(f"{a:5.0%} {b:7.3%} {c:7.3f} {d:7.3%} {e:7.2%}")
print("saved:", out)
