# -*- coding: utf-8 -*-
"""
k 口径 skew：sigma_IV(c_A) = k * sigma_ATM，B 在 ATM 上不动。

回答"如果 OTM 和 ATM 的 IV 不一致、一个是另一个的 k 倍，会有什么影响"。
复用 ab_core 的 wing 参数化（wing = (k-1)*sigma_ATM*(0.05/c_A) 使
sigma_A = k*sigma_ATM 精确成立），不引入第二个模型。

输出：
  charts/03_k_ratio_skew.png     三联图：smile / f_B & r** vs k / D(r) 分 k
  charts/03_k_ratio_table.csv    k 扫描表
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from scipy.optimize import brentq

import ab_core as ab

plt.rcParams["font.sans-serif"] = [
    "PingFang SC", "Arial Unicode MS", "Noto Sans CJK JP", "DejaVu Sans"
]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["mathtext.fontset"] = "dejavusans"
plt.rcParams["axes.unicode_minus"] = False

OUT = Path(__file__).resolve().parent / "charts"
BASE = ab.Params()          # sigma_ATM=45%, tau=1M, rf=4%, c_A=5%, c_B=0, f_A=1


def wing_for_k(k, p=BASE):
    """wing such that sigma_IV(c_A) == k * sigma_ATM exactly."""
    return (k - 1.0) * p.sigma_atm * (ab.SKEW_REF_MONEYNESS / p.c_A)


def solve_k(k, p=BASE):
    return ab.solve(p.with_(wing=wing_for_k(k, p)))


# ---------------------------------------------------------------------------
# 1. no-arb ceiling on k: call price must fall with strike, i.e. y_A < y_B.
#    Same inequality as ab_core's feasibility check f_B < f_A.
# ---------------------------------------------------------------------------
def k_max(p=BASE):
    """Largest k with y_A(k*sigma_ATM) = y_B(sigma_ATM); above it A's OTM call
    prices above B's ATM call -> vertical-spread arbitrage, f_B > 1."""
    y_B = ab.bs_call(p.S0, p.S0 * (1 + p.c_B), p.sigma_atm, p.tau,
                     p.rf, p.q, p.borrow)["price"] / p.S0

    def gap(k):
        y_A = ab.bs_call(p.S0, p.S0 * (1 + p.c_A), k * p.sigma_atm, p.tau,
                         p.rf, p.q, p.borrow)["price"] / p.S0
        return float(y_A - y_B)

    return brentq(gap, 1.0, 20.0, xtol=1e-10)


# ---------------------------------------------------------------------------
# 2. analytic semi-elasticity, checked against finite difference
#    dsigma_A/dk = sigma_ATM  =>  dlog f_B/dk = sigma_ATM * nu_A / y_A
# ---------------------------------------------------------------------------
def elasticity_check(k=1.0, p=BASE, h=1e-5):
    s = solve_k(k, p)
    nu_A = s.greeks_A["vega"] / p.S0          # d(y_A)/d(sigma)
    analytic = p.sigma_atm * nu_A / s.y_A
    fd = (np.log(solve_k(k + h, p).f_B) - np.log(solve_k(k - h, p).f_B)) / (2 * h)
    return analytic, fd, s


# ---------------------------------------------------------------------------
# 3. k sweep
# ---------------------------------------------------------------------------
def sweep(ks, p=BASE):
    rows = []
    for k in ks:
        try:
            s = solve_k(k, p)
        except ValueError as exc:
            rows.append(dict(k=k, sigma_A=k * p.sigma_atm, note=str(exc)[:40]))
            continue
        g = s.portfolio_greeks()
        rows.append(dict(
            k=k, sigma_A=s.sigma_A, wing=s.p.wing,
            y_A=s.y_A, y_B=s.y_B, f_B=s.f_B,
            D_peak=s.D_peak, r_star_star=s.r_star_star, slope_B=s.slope_B,
            delta_A=g["A"]["delta"], delta_B=g["B"]["delta"],
            vega_A=g["A"]["vega"], vega_B=g["B"]["vega"],
            note="",
        ))
    return pd.DataFrame(rows)


def main():
    kmax = k_max()
    analytic, fd, s0 = elasticity_check()

    print(f"anchor: sigma_ATM={BASE.sigma_atm:.0%}, tau=1M, c_A={BASE.c_A:.0%}, c_B=0")
    print(f"  f_B(k=1) = {s0.f_B:.6f}   D_peak = {s0.D_peak:.4%}   "
          f"r** = {s0.r_star_star:.4%}")
    print(f"  dlog f_B/dk  analytic {analytic:+.6f}  finite-diff {fd:+.6f}  "
          f"(diff {abs(analytic - fd):.2e})")
    print(f"  dD_peak/dk   = {BASE.c_A * s0.f_B * analytic:+.4%} per 1.00 of k")
    print(f"  dr**/dk      = "
          f"{BASE.c_A / (1 - s0.f_B) ** 2 * s0.f_B * analytic:+.4%} per 1.00 of k")
    print(f"  no-arb ceiling k_max = {kmax:.4f} "
          f"(sigma_A = {kmax * BASE.sigma_atm:.2%})")

    print("\nk_max is not a constant -- it moves with sigma_ATM / tau / c_A:")
    grid = []
    for sig in (0.20, 0.30, 0.45, 0.60):
        for tau in (1 / 12, 3 / 12, 1.0):
            p = BASE.with_(sigma_atm=sig, tau=tau)
            grid.append(dict(sigma_atm=sig, tau_m=round(tau * 12),
                             k_max=k_max(p), sigma_A_max=k_max(p) * sig))
    for c_A in (0.02, 0.05, 0.10, 0.20):
        p = BASE.with_(c_A=c_A)
        grid.append(dict(sigma_atm=0.45, tau_m=1, c_A=c_A, k_max=k_max(p),
                         sigma_A_max=k_max(p) * 0.45))
    gdf = pd.DataFrame(grid)
    print(gdf.to_string(index=False, float_format=lambda x: f"{x:8.4f}"))

    ks = np.round(np.arange(0.70, 1.45, 0.05), 4)
    tbl = sweep(ks)
    print("\nk sweep at the toy anchor:")
    cols = ["k", "sigma_A", "wing", "y_A", "f_B", "D_peak", "r_star_star",
            "slope_B", "delta_A", "vega_A", "note"]
    print(tbl[cols].to_string(index=False,
                              float_format=lambda x: f"{x:9.5f}"))

    OUT.mkdir(exist_ok=True)
    tbl.to_csv(OUT / "03_k_ratio_table.csv", index=False)

    # market anchors expressed in k
    print("\nwhere real markets sit in k units (at sigma_ATM=45%, c_A=5%):")
    for name, wing in (("flat (BS)", ab.WING_FLAT),
                       ("NVDA measured", ab.WING_NVDA),
                       ("SPX-style index", ab.WING_INDEX),
                       ("commodity stress", ab.WING_COMMODITY_45)):
        k = ab.k_from_wing(wing, BASE.sigma_atm)
        s = solve_k(k)
        print(f"  {name:18s} wing={wing:+.4f}  k={k:.4f}  f_B={s.f_B:.4f}  "
              f"D_peak={s.D_peak:.3%}  r**={s.r_star_star:.3%}")

    # ---------------- charts ----------------
    fig, ax = plt.subplots(1, 3, figsize=(16.5, 4.8))
    k_show = [0.80, 0.90, 1.00, 1.10, 1.20]
    colors = plt.cm.coolwarm(np.linspace(0.05, 0.95, len(k_show)))

    # (a) the smile slices
    c = np.linspace(-0.02, 0.12, 200)
    for k, col in zip(k_show, colors):
        ax[0].plot(c, ab.skew_vol(BASE.sigma_atm, wing_for_k(k), c),
                   color=col, label=f"k={k:.2f}")
    ax[0].axvline(BASE.c_A, ls=":", c="grey", lw=1)
    ax[0].axvline(0, ls=":", c="grey", lw=1)
    ax[0].scatter([0], [BASE.sigma_atm], c="k", zorder=5, s=25)
    ax[0].annotate("B 坐在锚点上，不受 k 影响", (0, BASE.sigma_atm),
                   textcoords="offset points", xytext=(8, -18), fontsize=8)
    ax[0].set_title(r"(a) $\sigma_{IV}(c)$：k 绕 ATM 锚点转动，"
                    r"在 $c_A$ 处取到 $k\sigma_{ATM}$")
    ax[0].set_xlabel("moneyness c"); ax[0].set_ylabel(r"$\sigma_{IV}$")
    ax[0].xaxis.set_major_formatter(PercentFormatter(1.0))
    ax[0].yaxis.set_major_formatter(PercentFormatter(1.0))
    ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)

    # (b) f_B and r** vs k
    kk = np.linspace(0.55, kmax * 0.999, 400)
    fb, rss = [], []
    for k in kk:
        try:
            s = solve_k(k)
            fb.append(s.f_B); rss.append(s.r_star_star)
        except ValueError:
            fb.append(np.nan); rss.append(np.nan)
    ax[1].plot(kk, fb, c="C0", label=r"$f_B$（B 的覆盖比例）")
    ax[1].axvline(1.0, ls=":", c="grey", lw=1)
    ax[1].axvline(kmax, ls="--", c="crimson", lw=1.2)
    ax[1].annotate(f"no-arb 上限 k={kmax:.2f}\n（$y_A=y_B$, $f_B=1$）",
                   (kmax, 0.5), textcoords="offset points", xytext=(-108, 0),
                   fontsize=8, color="crimson")
    ax[1].set_xlabel("k"); ax[1].set_ylabel(r"$f_B$", color="C0")
    ax[1].set_title(r"(b) $f_B$ 与 $r^{**}$ 对 k 单调上升，且有硬上限")
    ax2 = ax[1].twinx()
    ax2.plot(kk, rss, c="C3", label=r"$r^{**}$（A/B 交叉点）")
    ax2.set_ylabel(r"$r^{**}$", color="C3")
    ax2.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax2.set_yscale("log")
    ax[1].grid(alpha=.3)
    lines = ax[1].get_lines()[:1] + ax2.get_lines()[:1]
    ax[1].legend(lines, [l.get_label() for l in lines], fontsize=8, loc="upper left")

    # (c) D(r) for a few k
    r = np.linspace(-0.05, 0.45, 600)
    for k, col in zip(k_show, colors):
        s = solve_k(k)
        ax[2].plot(r, s.D(r), color=col,
                   label=f"k={k:.2f}: $r^{{**}}$={s.r_star_star:.1%}, "
                         f"peak {s.D_peak:.2%}")
    ax[2].axhline(0, c="k", lw=.8)
    ax[2].set_title(r"(c) $D(r)=R_A-R_B$：k 抬高 A 的整条优势曲线")
    ax[2].set_xlabel("标的期间价格回报 r"); ax[2].set_ylabel("D(r)")
    ax[2].xaxis.set_major_formatter(PercentFormatter(1.0))
    ax[2].yaxis.set_major_formatter(PercentFormatter(1.0))
    ax[2].legend(fontsize=7.5); ax[2].grid(alpha=.3)

    fig.suptitle(
        r"OTM/ATM 隐含波动率之比 $k=\sigma_{IV}(c_A)/\sigma_{ATM}$ 的影响"
        f"（$\\sigma_{{ATM}}$=45%, $\\tau$=1M, $c_A$=5%, $c_B$=0, $f_A$=1）",
        y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / "03_k_ratio_skew.png", dpi=160, bbox_inches="tight")
    print(f"\nwrote {OUT/'03_k_ratio_skew.png'}")
    print(f"wrote {OUT/'03_k_ratio_table.csv'}")


if __name__ == "__main__":
    main()
