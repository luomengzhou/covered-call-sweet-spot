# -*- coding: utf-8 -*-
"""
IV 曲线所编码的 Q 定价信息图解，配合 §4/§5.1 的对话推导。
方法：Breeden-Litzenberger —— 给定 IV(K)，逐 K 用 BS 定价 C(K)，
      对 K 求一/二阶数值导数近似恢复 Q 的生存函数 / 密度。
      (对 K 求导，K 是标签不是状态变量，不是希腊字母。)
参数对齐 NVDA 实测：sigma_ATM=43.5%, skew slope 实测 s=0.104（每5%OTM降0.52vol），
文档 §5.1 的翻转阈值 s~0.4 作对比；真实世界 sigma_RV=40%, mu=15%。
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

TAU, RF = 1/12, 0.04
SIG_ATM, SIG_RV, MU = 0.435, 0.40, 0.15   # 对齐 NVDA 实测量级
CA = 0.05

def bs_call(K, sig, tau=TAU, rf=RF):
    d1 = (np.log(1.0/K) + (rf+0.5*sig**2)*tau)/(sig*np.sqrt(tau))
    d2 = d1 - sig*np.sqrt(tau)
    return norm.cdf(d1) - K*np.exp(-rf*tau)*norm.cdf(d2)

def sigma_skew(c, s, sig_atm=SIG_ATM, floor=0.05):
    return np.maximum(sig_atm - s*c, floor)

def expected_payoff(c, sig, m, tau=TAU):
    """E[(R-k)^+]，任意测度下总漂移 m、波动 sig 的对数正态。"""
    k = 1+c
    d1 = (-np.log(k) + (m+0.5*sig**2)*tau) / (sig*np.sqrt(tau))
    d2 = d1 - sig*np.sqrt(tau)
    return np.exp(m*tau)*norm.cdf(d1) - k*norm.cdf(d2)

def lognorm_pdf_R(R, m, sig, tau=TAU):
    return norm.pdf((np.log(R)-(m-0.5*sig**2)*tau)/(sig*np.sqrt(tau))) / (R*sig*np.sqrt(tau))

def lognorm_surv_R(R, m, sig, tau=TAU):
    return 1 - norm.cdf((np.log(R)-(m-0.5*sig**2)*tau)/(sig*np.sqrt(tau)))

# ---------- Breeden-Litzenberger: 由 IV(K) 反出 Q 的密度/生存函数 ----------
K = np.linspace(0.55, 1.65, 6001)
c_grid = K - 1.0
MONOTONICITY_TOL = 1e-10
CONVEXITY_TOL = 1e-8
NEGATIVE_MASS_TOL = 1e-8
SURVIVAL_BOUND_TOL = 1e-10

def Q_density_survival(s):
    sig = sigma_skew(c_grid, s)
    C = bs_call(K, sig)
    dC = np.gradient(C, K, edge_order=2)
    d2C = np.gradient(dC, K, edge_order=2)
    discount_inverse = np.exp(RF * TAU)
    surv_raw = -discount_inverse * dC
    dens_raw = discount_inverse * d2C

    max_upward_slope = max(float(np.max(np.diff(C) / np.diff(K))), 0.0)
    min_convexity = float(np.min(d2C))
    negative_mass = float(np.trapezoid(np.maximum(-dens_raw, 0.0), K))
    survival_violation = max(
        float(np.max(-surv_raw)), float(np.max(surv_raw - 1.0)), 0.0
    )
    print(
        f"BL diagnostics s={s:.3f}: max positive call slope={max_upward_slope:.3e}, "
        f"min call convexity={min_convexity:.3e}, negative density mass={negative_mass:.3e}, "
        f"survival bound violation={survival_violation:.3e}"
    )
    violations = []
    if max_upward_slope > MONOTONICITY_TOL:
        violations.append(f"call monotonicity {max_upward_slope:.3e} > {MONOTONICITY_TOL:.1e}")
    if min_convexity < -CONVEXITY_TOL:
        violations.append(f"call convexity {-min_convexity:.3e} > {CONVEXITY_TOL:.1e}")
    if negative_mass > NEGATIVE_MASS_TOL:
        violations.append(f"negative mass {negative_mass:.3e} > {NEGATIVE_MASS_TOL:.1e}")
    if survival_violation > SURVIVAL_BOUND_TOL:
        violations.append(
            f"survival bounds {survival_violation:.3e} > {SURVIVAL_BOUND_TOL:.1e}"
        )
    if violations:
        raise ValueError(f"invalid IV slice s={s:.3f}: " + "; ".join(violations))

    # Only tolerance-qualified finite-difference noise is zeroed.  Build the
    # plotted survival from the same cleaned density, retaining both grid-tail
    # masses, then normalize the numerical distribution once.
    dens = np.where(dens_raw < 0.0, 0.0, dens_raw)
    left_tail = max(1.0 - float(surv_raw[0]), 0.0)
    right_tail = max(float(surv_raw[-1]), 0.0)
    segment_mass = 0.5 * (dens[:-1] + dens[1:]) * np.diff(K)
    right_integral = np.zeros_like(dens)
    right_integral[:-1] = np.cumsum(segment_mass[::-1])[::-1]
    total_mass = left_tail + float(np.sum(segment_mass)) + right_tail
    if not np.isfinite(total_mass) or total_mass <= 0:
        raise ValueError(f"invalid numerical Q mass for s={s:.3f}: {total_mass}")
    dens = dens / total_mass
    surv = (right_tail + right_integral) / total_mass
    return dens, surv

S_FLAT, S_MEAS, S_THRESH = 0.0, 0.104, 0.40
dens_flat,  surv_flat  = Q_density_survival(S_FLAT)
dens_meas,  surv_meas  = Q_density_survival(S_MEAS)
dens_thr,   surv_thr   = Q_density_survival(S_THRESH)

dens_P = lognorm_pdf_R(K, MU, SIG_RV)
surv_P = lognorm_surv_R(K, MU, SIG_RV)

r = c_grid
CQF, CQM, CQT, CP = "#7f8c8d", "#c0392b", "#8e44ad", "#2471a3"

fig, axes = plt.subplots(2, 2, figsize=(15.5, 11))
pf = PercentFormatter(1.0, decimals=0)

# ===== 图1: IV(c) 三条曲线 =====
ax = axes[0, 0]
cc = np.linspace(-0.15, 0.30, 400)
ax.plot(cc, sigma_skew(cc, S_FLAT)*100, color=CQF, lw=2.2, ls="--", label=f"平坦 (s=0)")
ax.plot(cc, sigma_skew(cc, S_MEAS)*100, color=CQM, lw=2.4, label=f"NVDA 实测 skew (s={S_MEAS:.3f})")
ax.plot(cc, sigma_skew(cc, S_THRESH)*100, color=CQT, lw=2.4, label=f"文档翻转阈值 (s={S_THRESH:.2f})")
ax.axvline(0, color="k", lw=.6); ax.axvline(CA, color="#555", lw=.9, ls=":")
ax.text(CA, ax.get_ylim()[1] if False else 44.6, " $c_A$=5%", color="#555", fontsize=9.5)
ax.set_title("① 三种 IV(c) 曲面：平坦 / NVDA 实测斜率 / 文档翻转阈值", fontsize=12.5, pad=10)
ax.set_xlabel("cap $c=K/S_0-1$"); ax.set_ylabel("隐含波动率 $\\sigma_{IV}$ (%)")
ax.legend(loc="upper right", fontsize=10)
ax.xaxis.set_major_formatter(pf); ax.grid(alpha=.25)

# ===== 图2: Q 密度 vs P 密度 =====
ax = axes[0, 1]
ax.plot(r, dens_flat, color=CQF, lw=2.0, ls="--", label="$\\mathbb{Q}$ 数值密度（平坦 IV，纯对数正态）")
ax.plot(r, dens_meas, color=CQM, lw=2.4, label="$\\mathbb{Q}$ 数值密度（NVDA 实测 skew）")
ax.plot(r, dens_P,    color=CP,  lw=2.4, label="$\\mathbb{P}$ 密度（真实世界，$\\mu$=15%, $\\sigma_{RV}$=40%）")
ax.axvline(0, color="k", lw=.6)
ax.axvline(CA, color="#555", lw=.9, ls=":")
ax.fill_between(r, dens_meas, dens_P, where=(r>=CA), color=CQM, alpha=.12)
ax.text(0.14, ax.get_ylim()[1]*0.55 if False else 2.3,
        "$c\\geq c_A$ 这一段：\n$\\mathbb{Q}$ 和 $\\mathbb{P}$ 谁厚决定 alpha 符号", fontsize=9.5, color="#444")
ax.set_xlim(-0.25, 0.30)
ax.set_title("② 密度对比：同一 payoff，两套分布去积分", fontsize=12.5, pad=10)
ax.set_xlabel("到期净收益 $r=R-1$"); ax.set_ylabel("概率密度")
ax.legend(loc="upper left", fontsize=9.5)
ax.xaxis.set_major_formatter(pf); ax.grid(alpha=.25)

# ===== 图3: 右尾生存函数差 S_Q - S_P（决定逐 strike 的 alpha 符号）=====
ax = axes[1, 0]
diff_flat = surv_flat - surv_P
diff_meas = surv_meas - surv_P
diff_thr  = surv_thr  - surv_P
ax.plot(r, diff_flat*100, color=CQF, lw=2.0, ls="--", label="平坦 IV")
ax.plot(r, diff_meas*100, color=CQM, lw=2.4, label="NVDA 实测 skew")
ax.plot(r, diff_thr*100,  color=CQT, lw=2.4, label="翻转阈值 s=0.4")
ax.axhline(0, color="k", lw=.6); ax.axvline(0, color="k", lw=.6)
ax.axvline(CA, color="#555", lw=.9, ls=":")
ax.fill_between(r, 0, diff_meas*100, where=(diff_meas>=0), color=CA and "#1e8449", alpha=.10)
ax.fill_between(r, 0, diff_meas*100, where=(diff_meas<0),  color="#c0392b", alpha=.10)
ax.text(0.02, 0.85, "$S_Q>S_P \\Rightarrow$ 该 strike 边际 alpha>0\n（市场高估了越过它的概率）",
        transform=ax.transAxes, fontsize=9, color="#1e8449", va="top")
ax.text(0.02, 0.12, "$S_Q<S_P \\Rightarrow$ 该 strike 边际 alpha<0", transform=ax.transAxes,
        fontsize=9, color="#c0392b", va="bottom")
ax.set_xlim(-0.05, 0.30)
ax.set_title("③ $S_{\\mathbb{Q}}(k)-S_{\\mathbb{P}}(k)$：逐 strike 的 alpha 符号（式子 $E[(R-k)^+]=\\int_k^\\infty S(x)dx$）",
             fontsize=11.5, pad=10)
ax.set_xlabel("strike 位置 $c=k-1$"); ax.set_ylabel("$S_Q-S_P$  (百分点)")
ax.legend(loc="upper right", fontsize=9.5)
ax.xaxis.set_major_formatter(pf); ax.grid(alpha=.25)

# ===== 图4: rho(c) 三条曲线 =====
ax = axes[1, 1]
cc2 = np.linspace(-0.02, 0.20, 300)
def rho_curve(s):
    sig = sigma_skew(cc2, s)
    yQ = expected_payoff(cc2, sig, RF)
    yP = expected_payoff(cc2, SIG_RV, MU)
    return yP/yQ
def rho_at(s, c=CA):
    yv = expected_payoff(c, sigma_skew(c, s), RF); pv = expected_payoff(c, SIG_RV, MU)
    return pv/yv

ax.plot(cc2, rho_curve(S_FLAT), color=CQF, lw=2.2, ls="--",
        label=f"平坦 IV (s=0)，$\\rho(c_A)$={rho_at(S_FLAT):.3f}")
ax.plot(cc2, rho_curve(S_MEAS), color=CQM, lw=2.4,
        label=f"NVDA 实测 (s={S_MEAS:.3f})，$\\rho(c_A)$={rho_at(S_MEAS):.3f}")
ax.plot(cc2, rho_curve(S_THRESH), color=CQT, lw=2.4,
        label=f"翻转阈值 (s={S_THRESH:.2f})，$\\rho(c_A)$={rho_at(S_THRESH):.3f}")
ax.axhline(1.0, color="k", lw=.8)
ax.axvline(CA, color="#555", lw=.9, ls=":")
for s, col in [(S_FLAT, CQF), (S_MEAS, CQM), (S_THRESH, CQT)]:
    ax.plot([CA], [rho_at(s)], "o", color=col, ms=7, zorder=5,
            markeredgecolor="white", markeredgewidth=1)
ax.text(0.001, 1.72, "$\\rho>1 \\Rightarrow$ 真实赔付 > 权利金 $\\Rightarrow$ alpha<0", fontsize=9.5, color="#555")
ax.text(0.001, 1.60, "$\\rho<1 \\Rightarrow$ alpha>0", fontsize=9.5, color="#555")
ax.set_title("④ $\\rho(c)=\\mathbb{E}^{\\mathbb{P}}[(R-k)^+]/\\mathbb{E}^{\\mathbb{Q}}[(R-k)^+]$：把①②③压缩成一条曲线",
             fontsize=12, pad=10)
ax.set_xlabel("cap $c$"); ax.set_ylabel("$\\rho(c)$")
ax.legend(loc="upper left", fontsize=9.5, framealpha=.95)
ax.xaxis.set_major_formatter(pf); ax.grid(alpha=.25)

fig.suptitle("IV 曲线编码的 $\\mathbb{Q}$ 定价信息：skew 斜率如何改写 $\\rho(c)$ 与 alpha 符号"
             "   ($\\sigma_{ATM}$=%.1f%%, $\\sigma_{RV}$=%.0f%%, $\\mu$=%.0f%%, $\\tau$=1M)"
             % (SIG_ATM*100, SIG_RV*100, MU*100), fontsize=14, y=0.985)
fig.tight_layout(rect=[0, 0.02, 1, 0.965])
out = Path(__file__).resolve().parent / "charts" / "00_theory_IV_Q.png"
out.parent.mkdir(exist_ok=True)
fig.savefig(out, dpi=170)
fig.savefig(out.with_suffix(".pdf"))

# ---------- 自检 ----------
for s in [S_FLAT, S_MEAS, S_THRESH]:
    yQ = expected_payoff(CA, sigma_skew(CA, s), RF)
    yP = expected_payoff(CA, SIG_RV, MU)
    print(f"s={s:.3f}  sigma_IV(cA)={sigma_skew(CA,s):.3%}  yQ={yQ:.4%}  yP={yP:.4%}  "
          f"rho={yP/yQ:.4f}  alpha/f(月)={yQ-yP:.4%}  alpha/f(年化)={  (yQ-yP)*12:.4%}")
print("saved:", out)
