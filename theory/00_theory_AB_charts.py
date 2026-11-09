# -*- coding: utf-8 -*-
"""
理论图：A vs B(权利金匹配) 的收益率对比 与 D(r)=R_A-R_B 的形状
公式来源: 00_theory_derivation_zh.md  §1.2 (1b) / §3.1 / §3.3 式(3)(4)
    R_cc(f,c) = (1-f)r + f*min(r,c) + f*y(c)*e^{r_f tau} + d_T
    D(r)      = f_B (r-c_B)^+ - f_A (r-c_A)^+          <- 零成本比例价差
    r**       = (f_A c_A - f_B c_B) / (f_A - f_B)
"""
from pathlib import Path

import numpy as np
from scipy.stats import norm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

plt.rcParams["font.sans-serif"] = [
    "PingFang SC", "Arial Unicode MS", "Noto Sans CJK JP", "DejaVu Sans"
]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["mathtext.fontset"] = "dejavusans"
plt.rcParams["axes.unicode_minus"] = False

# ---------- 参数（与 00_theory_derivation_zh.md §3.1 数值算例一致） ----------
SIG, TAU, RF = 0.45, 1/12, 0.04
Q_ANNUAL, D_T = 0.0, 0.0       # toy：q 仅用于定价；收益使用单期股息 d_T

def call_yield(c, sig=SIG, tau=TAU, rf=RF, q_annual=Q_ANNUAL):
    """BS 单位 spot 权利金率 y(c), k = 1+c"""
    k = 1.0 + c
    d1 = (-np.log(k) + (rf - q_annual + 0.5*sig**2)*tau) / (sig*np.sqrt(tau))
    d2 = d1 - sig*np.sqrt(tau)
    return np.exp(-q_annual*tau)*norm.cdf(d1) - k*np.exp(-rf*tau)*norm.cdf(d2)

def R_cc(r, f, c):
    return (1-f)*r + f*np.minimum(r, c) + f*call_yield(c)*np.exp(RF*TAU) + D_T

def D_exact(r, fA, cA, fB, cB):
    """式(3)。仅当权利金匹配时 D = R_A - R_B"""
    return fB*np.maximum(r-cB, 0) - fA*np.maximum(r-cA, 0)

def r_star_star(fA, cA, fB, cB):
    return (fA*cA - fB*cB) / (fA - fB)

# ---------- 基准 A / B ----------
cA, fA = 0.05, 1.00          # A: 满仓 5% OTM (Income family)
cB      = 0.00               # B: ATM
yA, yB  = call_yield(cA), call_yield(cB)
fB      = fA*yA/yB           # 权利金匹配 f_A y(c_A) = f_B y(c_B)
Y       = fA*yA
yt      = np.exp(RF*TAU)     # e^{r_f tau}
r_ss    = r_star_star(fA, cA, fB, cB)
r_st    = cA + yA*yt         # §3.1 相对标的转负点 (A, f=1)

r = np.linspace(-0.30, 0.30, 1201)
CA, CB, CS = "#c0392b", "#2471a3", "#7f8c8d"

fig, axes = plt.subplots(2, 2, figsize=(15.5, 11))
pf = PercentFormatter(1.0, decimals=0)

# ===== 图1: 收益率对比 =====
ax = axes[0, 0]
ax.plot(r, r+D_T, color=CS, lw=1.6, ls="--", label="标的 buy & hold:  r + d_T")
ax.plot(r, R_cc(r, fA, cA), color=CA, lw=2.4,
        label=f"A: f={fA:.2f}, c={cA:.0%} (满仓 OTM), y={yA:.2%}")
ax.plot(r, R_cc(r, fB, cB), color=CB, lw=2.4,
        label=f"B: f={fB:.3f}, c=0% (部分 ATM), y={yB:.2%}")
ax.axhline(0, color="k", lw=.6); ax.axvline(0, color="k", lw=.6)
for x, lab, col in [(cB, "$c_B=0$", CB), (cA, "$c_A$=5%", CA),
                    (r_ss, f"$r^{{**}}$={r_ss:.2%}", "#8e44ad")]:
    ax.axvline(x, color=col, lw=.9, ls=":", alpha=.8)
    ax.text(x, -0.295, lab, color=col, fontsize=9.5,
            rotation=90, va="bottom", ha="right")
ax.plot([cA], [R_cc(cA, fA, cA)], "o", color=CA, ms=6)
ax.plot([cB], [R_cc(cB, fB, cB)], "o", color=CB, ms=6)
ax.annotate(f"A 上限 = c+$\\tilde{{y}}$ = {cA+yA*yt:.2%}", xy=(0.235, cA+yA*yt),
            xytext=(0.055, cA+yA*yt+0.085), color=CA, fontsize=9.5,
            arrowprops=dict(arrowstyle="->", color=CA, lw=.9))
ax.annotate("B 无上限，斜率 $1-f_B$", xy=(0.265, R_cc(0.265, fB, cB)),
            xytext=(0.145, R_cc(0.265, fB, cB)-0.115), color=CB, fontsize=9.5,
            arrowprops=dict(arrowstyle="->", color=CB, lw=.9))
ax.set_title("① 单期收益率：A（满仓 OTM）vs B（部分 ATM），权利金匹配", fontsize=12.5, pad=10)
ax.set_xlabel("标的净价格收益 $r$"); ax.set_ylabel("组合收益 $R_{cc}$")
ax.legend(loc="upper left", fontsize=9.5, framealpha=.95)
ax.xaxis.set_major_formatter(pf); ax.yaxis.set_major_formatter(pf)
ax.grid(alpha=.25)

# ===== 图2: D(r) =====
ax = axes[0, 1]
d = D_exact(r, fA, cA, fB, cB)
ax.plot(r, d, color="#1e8449", lw=2.6, label="$D(r)=R_A-R_B$")
ax.fill_between(r, 0, d, where=d >= 0, color=CA, alpha=.16)
ax.fill_between(r, 0, d, where=d < 0, color=CB, alpha=.16)
ax.axhline(0, color="k", lw=.6); ax.axvline(0, color="k", lw=.6)
Dmax = fB*(cA-cB)
ax.plot([cA], [Dmax], "o", color="#1e8449", ms=7, zorder=5)
ax.annotate("A 最大优势 = $f_B(c_A-c_B)$ = %.2f%%\n（在 r = $c_A$ 处）" % (Dmax*100),
            xy=(cA, Dmax), xytext=(-0.275, Dmax-0.004), fontsize=9.5, va="top",
            arrowprops=dict(arrowstyle="->", lw=.9,
                            connectionstyle="arc3,rad=-0.12")) 
ax.plot([r_ss], [0], "o", color="#8e44ad", ms=7, zorder=5)
ax.annotate("$r^{**}=\\dfrac{f_Ac_A-f_Bc_B}{f_A-f_B}$ = %.2f%%" % (r_ss*100),
            xy=(r_ss, 0), xytext=(r_ss-0.005, 0.0175), fontsize=10, color="#8e44ad",
            arrowprops=dict(arrowstyle="->", color="#8e44ad", lw=.9))
ax.text(-0.22, -0.035, "r $\\leq c_B$ :  $D\\equiv 0$\n（精确打平）", fontsize=9.5, color="#555")
ax.text(0.155, -0.028, "斜率 $-(f_A-f_B)$ = $-$%.3f\nB 的优势无顶" % (fA-fB),
        fontsize=9.5, color=CB, va="top")
ax.text(0.004, 0.0175, "斜率 $+f_B$\n= %.3f" % fB, fontsize=9.5, color=CA)
ax.set_ylim(-0.072, 0.042)
ax.set_title("② $D(r)=f_B(r-c_B)^+-f_A(r-c_A)^+$ —— 零成本比例价差（式3）",
             fontsize=12.5, pad=10)
ax.set_xlabel("标的净价格收益 $r$"); ax.set_ylabel("$D=R_A-R_B$")
ax.legend(loc="upper left", fontsize=10)
ax.xaxis.set_major_formatter(pf); ax.yaxis.set_major_formatter(pf)
ax.grid(alpha=.25)

# ===== 图3: D(r) 随 c_A 变化（B 恒为权利金匹配的 ATM） =====
ax = axes[1, 0]
cmap = plt.cm.viridis(np.linspace(.12, .88, 5))
rows = []
for col, cA_i in zip(cmap, [0.02, 0.05, 0.08, 0.12, 0.20]):
    yA_i = call_yield(cA_i)
    fB_i = 1.0*yA_i/yB
    d_i  = D_exact(r, 1.0, cA_i, fB_i, cB)
    rss  = r_star_star(1.0, cA_i, fB_i, cB)
    ax.plot(r, d_i, color=col, lw=2.1,
            label=f"$c_A$={cA_i:.0%} → $f_B$={fB_i:.3f},  $r^{{**}}$={rss:.1%}")
    ax.plot([cA_i], [fB_i*cA_i], "o", color=col, ms=5)
    ax.plot([rss], [0], "v", color=col, ms=6)
    rows.append((cA_i, yA_i, fB_i, fB_i*cA_i, rss))
ax.axhline(0, color="k", lw=.6); ax.axvline(0, color="k", lw=.6)
ax.set_title("③ 把 A 的 strike 推远：优势峰值先升后降（非单调），翻转点 $r^{**}$ 右移", fontsize=12.5, pad=10)
ax.set_xlabel("标的净价格收益 $r$"); ax.set_ylabel("$D=R_A-R_B$")
ax.legend(loc="lower left", fontsize=9)
ax.xaxis.set_major_formatter(pf); ax.yaxis.set_major_formatter(pf)
ax.set_ylim(-0.13, 0.05); ax.grid(alpha=.25)

# ===== 图4: 各自相对标的 =====
ax = axes[1, 1]
ax.plot(r, R_cc(r, fA, cA)-(r+D_T), color=CA, lw=2.4, label="A $-$ 标的")
ax.plot(r, R_cc(r, fB, cB)-(r+D_T), color=CB, lw=2.4, label="B $-$ 标的")
ax.axhline(0, color="k", lw=.6); ax.axvline(0, color="k", lw=.6)
for f_, c_, col, nm in [(fA, cA, CA, "A"), (fB, cB, CB, "B")]:
    rs = c_ + call_yield(c_)*yt
    ax.axvline(rs, color=col, lw=.9, ls=":")
    ax.plot([rs], [0], "o", color=col, ms=6)
    lab4 = "%s 的 $r^*$ = c+$\\tilde{y}$ = %.2f%%" % (nm, rs*100)
    ax.annotate(lab4, xy=(rs, 0), xytext=(rs+0.045, -0.045 if nm == "A" else -0.105),
                color=col, fontsize=10,
                arrowprops=dict(arrowstyle="->", color=col, lw=.9))
ax.text(-0.29, 0.020, "r $\\leq$ 0 段两线完全重合\n（权利金匹配 $\\Rightarrow$ 下行缓冲同为 %.2f%%）" % (Y*yt*100),
        fontsize=9.5, color="#555", va="top")
ax.set_title("④ 相对 buy & hold 的超额：转负点 $r^*$ = c+$\\tilde{y}$ 与 f 无关（§3.1）",
             fontsize=12.5, pad=10)
ax.set_xlabel("标的净价格收益 $r$"); ax.set_ylabel("$R_{cc}-R_{stock}$")
ax.legend(loc="lower left", fontsize=10)
ax.xaxis.set_major_formatter(pf); ax.yaxis.set_major_formatter(pf)
ax.grid(alpha=.25)

fig.suptitle("Covered Call 理论图 · A vs B（权利金匹配 Y=%.3f%%）    $\\sigma_{IV}$=%.0f%%,  $\\tau$=1M,  $r_f$=%.0f%%,  q=0, d_T=0" % (Y*100, SIG*100, RF*100),
             fontsize=14.5, y=0.985)
fig.tight_layout(rect=[0, 0.02, 1, 0.965])
out = Path(__file__).resolve().parent / "charts" / "00_theory_A_vs_B.png"
out.parent.mkdir(exist_ok=True)
fig.savefig(out, dpi=170)
fig.savefig(out.with_suffix(".pdf"))

# ---------- 数值自检（对账 md §3.3） ----------
print(f"y(cA)={yA:.4%}  y(0)={yB:.4%}  fB={fB:.4f}  Y={Y:.4%}")
print(f"A cap = c+yt = {cA+yA*yt:.4%}   r*(A) = {r_st:.4%}")
print(f"r** = {r_ss:.4%}   (md 记录 13.06%)")
print(f"D(cA) = {D_exact(cA,fA,cA,fB,cB):.4%}  (= fB*cA = {fB*cA:.4%})")
print(f"D(r**) = {D_exact(r_ss,fA,cA,fB,cB):.2e}")
chk = np.max(np.abs((R_cc(r,fA,cA)-R_cc(r,fB,cB)) - D_exact(r,fA,cA,fB,cB)))
print(f"max |(R_A-R_B) - D(r)| = {chk:.2e}   <- 权利金匹配下应为 0")
print("\ncA     y(cA)    fB      D_max    r**")
for a,b,c,d,e in rows: print(f"{a:5.0%} {b:7.3%} {c:7.3f} {d:7.3%} {e:7.2%}")
print("saved:", out)
