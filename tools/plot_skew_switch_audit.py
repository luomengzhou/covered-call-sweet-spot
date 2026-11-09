"""Chart the realized-skew switch signals: pooled outcome + per-name edge vs always-B.

Reads results/skew_switch_variants_summary.csv (written by
06_skew_switch_variants.py) and writes results/06_skew_switch_audit.png.

Companion to tools/plot_wing_signal_audit.py: that one covers the wing_z
signal, this one covers the three realized-skew variants (own history /
relative to SPY / relative to QQQ). Same palette so the pair reads as one
system.

Usage: python tools/plot_skew_switch_audit.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# CJK labels: fall back to whatever CJK-capable sans is installed.
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "WenQuanYi Zen Hei",
                                   "Source Han Sans SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent

# palette (dataviz reference instance, light surface; validated) ---------------
SURFACE = "#fcfcfb"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"   # cat slots 1,2,3
POS, NEG = "#2a78d6", "#e34948"                # diverging blue <-> red

# Ordered by common-window buy&hold skew, fat right tail -> thin. Same order as
# every other exhibit in the deck.
TICKERS = ["TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "AAPL", "META"]
SKEW = {"TSLA": 0.95, "NVDA": 0.31, "MSFT": 0.24, "GOOGL": 0.08,
        "AMZN": 0.02, "AAPL": -0.26, "META": -0.47}
SIGNALS = ["skew_own", "skew_vs_SPY", "skew_vs_QQQ"]
SIGLABEL = {"skew_own": "自身历史", "skew_vs_SPY": "相对 SPY", "skew_vs_QQQ": "相对 QQQ"}
SIGCOLOR = dict(zip(SIGNALS, (S1, S2, S3)))
TARGETS = ["1%", "3%"]


def main() -> None:
    df = pd.read_csv(ROOT / "results" / "skew_switch_variants_summary.csv")
    df = df[df["signal"].isin(SIGNALS)]

    fig = plt.figure(figsize=(15.5, 12.4), facecolor=SURFACE)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.5],
                          hspace=0.36, wspace=0.16,
                          left=0.085, right=0.975, top=0.893, bottom=0.155)

    fig.text(0.085, 0.955, "Realized-skew 择时信号 —— 三个参照系全部失败",
             fontsize=19, color=INK, fontweight="bold")
    fig.text(0.085, 0.925,
             "规则:月初滚动 realized skew 转正(右尾变肥)→ 选 B,否则选 A。"
             "窗口 126 交易日(headline);63/252 已测,不改变结论。",
             fontsize=11, color=INK2)

    # ---- row 1: pooled equal-weight cumulative -----------------------------
    for j, tgt in enumerate(TARGETS):
        ax = fig.add_subplot(gs[0, j])
        p = df[(df["ticker"] == "MAG7_pooled") & (df["target"] == tgt)]
        pv = {r["signal"]: r for _, r in p.iterrows()}
        base = pv[SIGNALS[0]]

        labels = ["一直 A\n(满仓OTM)", "一直 B\n(部分ATM)"] + \
                 [f"规则\n{SIGLABEL[s]}" for s in SIGNALS]
        vals = [base["cum_A"], base["cum_B"]] + [pv[s]["cum_rule"] for s in SIGNALS]
        cols = [MUTED, S2] + [S1] * 3

        x = np.arange(len(vals))
        ax.bar(x, vals, width=0.62, color=cols, zorder=3,
               linewidth=1.6, edgecolor=SURFACE)
        for xi, v in zip(x, vals):
            ax.text(xi, v * 1.03, f"{v:.0f}x", ha="center", va="bottom",
                    fontsize=12, color=INK, fontweight="bold", zorder=4)

        ax.axhline(base["cum_B"], color=S2, lw=1.4, ls="--", zorder=2, alpha=0.85)
        ax.text(0.015, base["cum_B"], "一直B 基准线 ", va="bottom",
                ha="left", fontsize=9.5, color=S2,
                transform=ax.get_yaxis_transform())

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10, color=INK2)
        ax.set_ylim(0, max(vals) * 1.22)
        ax.set_ylabel("累计净值 (×)", fontsize=10.5, color=INK2)
        ax.set_title(f"MAG7 等权池化 —— Income {tgt} 档   "
                     f"(n={int(base['n'])} 个月)",
                     fontsize=13, color=INK, loc="left", pad=9)
        ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(BASELINE)
        ax.tick_params(colors=MUTED, labelsize=10)
        ax.set_facecolor(SURFACE)

        worst = min(pv[s]["cum_rule"] for s in SIGNALS)
        ax.text(0.985, 0.955,
                f"三个变体全部低于一直 B（{base['cum_B']:.0f}x）,最差 {worst:.0f}x",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=10.5, color=NEG)

    # ---- row 2: per-name rule vs always-B ---------------------------------
    for j, tgt in enumerate(TARGETS):
        ax = fig.add_subplot(gs[1, j])
        h = 0.26
        for si, sig in enumerate(SIGNALS):
            off = (1 - si) * h
            xs, ys, flips = [], [], []
            for ti, t in enumerate(TICKERS):
                r = df[(df["ticker"] == t) & (df["target"] == tgt) &
                       (df["signal"] == sig)]
                if r.empty:
                    continue
                r = r.iloc[0]
                vs_B = (r["cum_rule"] / r["cum_B"] - 1) * 100
                best = max(r["cum_A"], r["cum_B"])
                xs.append(vs_B)
                ys.append(len(TICKERS) - 1 - ti + off)
                # beats always-B only because A was simply the better line here
                flips.append(vs_B > 0 and r["cum_rule"] < best)
            ax.barh(ys, xs, height=h * 0.92, color=SIGCOLOR[sig], zorder=3,
                    linewidth=1.2, edgecolor=SURFACE)
            for xv, yv, fl in zip(xs, ys, flips):
                ax.text(xv + (1.6 if xv >= 0 else -1.6), yv, f"{xv:+.0f}%",
                        va="center", ha="left" if xv >= 0 else "right",
                        fontsize=8.6, color=NEG if fl else INK2, zorder=4)
                if fl:
                    ax.plot([xv + 8.2], [yv], marker="x", ms=6.5, mew=2.0,
                            color=NEG, zorder=5, clip_on=False)

        ax.axvline(0, color=BASELINE, lw=1.6, zorder=2)
        ax.set_yticks(range(len(TICKERS)))
        ax.set_yticklabels([f"{t}\n偏度 {SKEW[t]:+.2f}" for t in TICKERS[::-1]],
                           fontsize=10, color=INK2)
        ax.set_xlabel("规则相对「一直 B」的累计净值差 (%)   ← 输    赢 →",
                      fontsize=10.5, color=INK2)
        ax.set_title(f"单票:规则 vs 一直 B —— Income {tgt} 档",
                     fontsize=13, color=INK, loc="left", pad=9)
        ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(BASELINE)
        ax.tick_params(colors=MUTED, labelsize=10)
        ax.set_facecolor(SURFACE)
        ax.set_xlim(-78, 40)


    leg = fig.legend(handles=[Patch(facecolor=SIGCOLOR[s], label=SIGLABEL[s])
                              for s in SIGNALS],
                     loc="upper left", bbox_to_anchor=(0.085, 0.600),
                     ncol=3, fontsize=10.5, frameon=False,
                     title="滚动 skew 的参照系（每组三条,自上而下）",
                     title_fontsize=10.5, labelcolor=INK2,
                     handlelength=1.5, columnspacing=1.6)
    leg.get_title().set_color(INK2)

    fig.text(0.085, 0.103,
             "读法:上排 = 七票等权池化后的累计净值,三个变体都低于「一直 B」(-7% 到 -25%)。"
             "下排 = 每只票单独看,负值 = 规则输给「一直 B」。",
             fontsize=10.5, color=INK2)
    fig.text(0.085, 0.072,
             "红 × = 赢过「一直 B」但输给「事后更优的那个基准」——这几格的赢面来自"
             "在 A 本就优于 B 的票上常数偏向 A,不是择时。META 三个变体全部属于此类。",
             fontsize=10.5, color=NEG)
    fig.text(0.085, 0.041,
             "42 个单元格(7票×2档×3变体):输给「一直 B」28 个,输给「事后更优基准」33 个。"
             "唯一稳定为正的是 AMZN(6 格里 5 格),量级也只有 +2%~+17%。"
             "TSLA 最贵:1% 档累计从 117x 掉到 47x。",
             fontsize=10.5, color=INK2)

    out = ROOT / "results" / "06_skew_switch_audit.png"
    fig.savefig(out, dpi=140, facecolor=SURFACE)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
