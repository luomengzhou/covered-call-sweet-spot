# Dashboard 的桌面语言与分布视角 — 推导笔记

**日期**: 2026-08-10 ｜ **配套代码**: `ab_core.py`（`desk_view` / `call_prob_q` / `wing_bounds` / `strike_tenor_grid`，全部命题在 `self_check()` 里有数值验证）｜ **配套页面**: `AB_explorer.html`

本笔记是 2026-08-07 会议对 dashboard 提出的四项增补（notional 计价、被行权概率、strike × maturity 表格、"sell different part of the distribution" 的显性化）以及 wing 滑块可行域钳制的理论依据。记号沿用 `00_theory_derivation_en.md`：单期、期限 $\tau$，价格收益 $r = S_T/S_0 - 1$，覆盖比例 $f$，cap $c$（$K = S_0(1+c)$），权利金比例 $y(c) = C(K)/S_0$，复利到期值 $\tilde y = y\,e^{r_f \tau}$，权利金匹配约束 $f_A\,\tilde y_A = f_B\,\tilde y_B$，差额 $D(r) = f_B (r-c_B)^+ - f_A (r-c_A)^+$。

---

## 1. 命题 1（Notional 翻译）：模型对头寸规模一阶齐次

**命题**：设投资组合为 $W$ 美元的标的多头，按策略 $(f, c)$ 卖出 call。则组合等于 $W/S_0$ 份"单位现货问题"，一切以现货比例表示的量乘以 $W$ 即为美元量；$f_B$ 与 $W$ 无关。

**证明**：单期美元损益为

$$P\&L(W) = W\Big[r + d_T + f\,\tilde y - f\,(r-c)^+\Big],$$

方括号内不含 $W$——payoff 对头寸规模是正一阶齐次的。$f_B = f_A\,y_A / y_B$ 是两个权利金比例之比，规模在分子分母同时出现并消去。∎

由此得**桌面字典**（合约乘数 $M = 100$）：

| 桌面量 | 公式 | 基准参数、$W$ = \$10mm 的数值 |
|---|---|---|
| 股数 | $W/S_0$ | 100,000 股（$S_0=100$） |
| ATM 行权价 | $K_B = S_0(1+c_B)$，$c_B=0$ 时即现价 | \$100.00 |
| OTM 行权价 | $K_A = S_0(1+c_A)$ | \$105.00 |
| 卖出合约数（A 腿） | $f_A \cdot W/(S_0 M)$ | 1,000 张 |
| 卖出合约数（B 腿） | $f_B \cdot W/(S_0 M)$ | 617.2 张 |
| 收到权利金（美元） | $f\,y\,W$（两腿相等，这就是匹配约束） | \$329,455 |
| 到期口径权利金 | $f\,\tilde y\,W$ | \$330,555 |
| A 的最大优势（美元） | $W f_B (c_A - c_B)$，出现在 $r = c_A$ | \$308,580 |

基准参数：$\sigma_{\mathrm{ATM}}=45\%$、$\tau=1M$、$r_f=4\%$、$q=b=0$、wing $=0$、$c_A=5\%$、$c_B=0$、$f_A=1$。代码 `Solution.desk_view()`；`self_check` 里验证两腿美元权利金相等及上表锚点。

---

## 2. 命题 2（切片的 Q 值恒等式）：你收到的权利金 = 你卖掉的那片分布的 Q 期望值

**命题（model-free）**：设 $Q$ 为定价测度（以货币市场账户计价），则对任意 cap $c$

$$y(c) = e^{-r_f\tau}\,\mathbb{E}^Q\big[(r-c)^+\big], \qquad\text{即}\qquad \tilde y(c) = \mathbb{E}^Q\big[(r-c)^+\big].$$

**证明**：风险中性定价给出 $C(K) = e^{-r_f\tau}\,\mathbb{E}^Q[(S_T-K)^+]$。两边除以 $S_0$，用 $K = S_0(1+c)$、$r = S_T/S_0-1$ 即得。∎

这一步**不依赖 Black–Scholes**——它是 $Q$ 测度的定义。BS 只在玩具模型里用来生成 $y$ 的数值；恒等式对任何市场权利金都成立。`self_check` 用对数正态密度做数值积分验证到 $10^{-7}$（基准参数下 $\tilde y_A = 3.3056\%$、$\tilde y_B = 5.3561\%$）。

覆盖 call 的放弃项 $f\,(r-c)^+$ 正是"分布在 $c$ 以右的一片"。所以恒等式的读法是：

> **卖 covered call = 卖掉收益分布的一个切片；你收到的（到期口径）权利金，恰好等于这个切片在定价分布下的期望值。不多，不少。**

三个直接推论：

**推论 2.1（等权利金 = 等 Q 值切片）**：匹配约束 $f_A \tilde y_A = f_B \tilde y_B$ 等价于

$$f_A\,\mathbb{E}^Q\big[(r-c_A)^+\big] = f_B\,\mathbb{E}^Q\big[(r-c_B)^+\big],$$

即 **A 和 B 卖掉的是 Q 值完全相同的两片，区别只在切片摆在分布的什么位置**：A 的切片从 $c_A$ 起、面额 $f_A$（远而全）；B 的从 $c_B$ 起、面额 $f_B$（近而薄）。

**推论 2.2（$\mathbb{E}^Q[D] = 0$）**：由 $D$ 的定义与推论 2.1，

$$\mathbb{E}^Q[D] = f_B \tilde y_B - f_A \tilde y_A = 0.$$

**在定价分布自己看来，A 对 B 是精确的平局。** 所以"选 A 还是选 B"这个问题在 $Q$ 下没有内容——它只能是一个关于真实分布 $P$ 与定价分布 $Q$ 差异的判断。这就是把 dashboard 和"different probability distribution"连起来的那根轴。

**推论 2.3（与 $\rho$ 判据的连接）**：记 richness ratio $\rho(c) = \mathbb{E}^P[(r-c)^+] / \mathbb{E}^Q[(r-c)^+]$（`00_theory_derivation` §5），$\tilde Y = f_A \tilde y_A$ 为匹配后的共同权利金。则

$$\mathbb{E}^P[D] = f_B \tilde y_B\,\rho(c_B) - f_A \tilde y_A\,\rho(c_A) = \tilde Y\big(\rho(c_B) - \rho(c_A)\big).$$

**期望层面 A 赢 ⟺ $\rho(c_A) < \rho(c_B)$** ——与 §5 的 sweet spot 判据完全一致，这里是它的一行重推。方向判读：若相信右尾比定价的更肥（$P$ 的远端质量 > $Q$ 的，NVDA/TSLA 式），则 $\rho(c_A)$ 相对被抬得更高——**远处那片切给你的价钱低于你自己对它的估值，别卖，选 B**；反之（META 式左偏）选 A。

---

## 3. 命题 3（被行权概率）：两个数，一个平滑面修正

### 3.1 平面版（逐 strike 自身对数正态）

以该 strike 自身的 $\sigma_{IV}(c)$ 为参数、carry $= r_f - q - b$，$\ln(S_T/S_0) \sim N\big((\text{carry} - \tfrac12\sigma^2)\tau,\ \sigma^2\tau\big)$，故

$$\mathbb{P}^Q(S_T > K) = N(d_2), \qquad d_2 = \frac{\ln(F/K) - \tfrac12\sigma^2\tau}{\sigma\sqrt\tau},\quad F = S_0 e^{(r_f-q-b)\tau}.$$

`self_check` 验证 $N(d_2)$ 与对数正态尾概率解析一致（基准参数：$N(d_{2,A}) = 0.3391$，$N(d_{2,B}) = 0.4843$）。

### 3.2 Smile 一致版（dashboard 采用的口径）

有 skew 时，"从市场价格读出的行权概率"是 digital call 的无贴现价格，等于 $C(K, \sigma(K))$ 对 $K$ 的**全导数**（链式法则带上 smile 的斜率）：

$$\mathbb{P}^Q(S_T > K) = -\frac{1}{\mathrm{disc}}\frac{dC}{dK} = N(d_2) - \frac{\nu}{\mathrm{disc}}\,\frac{d\sigma}{dK}, \qquad \nu = S_0 e^{-(q+b)\tau} n(d_1)\sqrt\tau.$$

对线性 wing tilt $\sigma(c) = \sigma_{\mathrm{ATM}} + \mathrm{wing}\cdot(c/0.05)$ 有 $d\sigma/dK = \mathrm{wing}/(0.05\,S_0)$，$S_0$ 消去：

$$\boxed{\ \mathbb{P}^Q(S_T > K) = N(d_2) - e^{(r_f-q-b)\tau}\, n(d_1)\sqrt{\tau}\ \frac{\mathrm{wing}}{0.05}\ }$$

wing $= 0$ 时退化为 $N(d_2)$。**负 wing（常规 call wing）使真实被行权概率高于按该 strike 自身 IV 算的 $N(d_2)$**，量级不小：指数级 wing $=-0.02$ 时，基准参数下 A 腿 $0.3342 \to 0.3784$（+4.4 个概率点）、B 腿 $0.4843 \to 0.5304$（+4.6 个点）。`self_check` 用平滑面上 $C(K)$ 的中心差分验证到 $10^{-6}$。

结果按定义截断在 $[0,1]$；**触到截断意味着线性 tilt 在该 strike 违反了密度正性（butterfly 无套利）**——线性外推的又一个失效信号，与 §4 的可行域是同一件事的两面。代码 `call_prob_q()`；`solve()` 同时给出 `prob_bs`（平面版）与 `prob`（smile 一致版），页面显示后者。

### 3.3 Q 还是 P？——为什么页面标"priced (Q)"

$N(d_2)$ 是**定价分布**下的概率。真实（$P$）概率把 carry 换成标的价格漂移 $\mu$：$\Delta d_2 = (\mu - r_f + q + b)\sqrt\tau/\sigma$。量级：$\mu - \mathrm{carry} = 11\%$、$\tau = 1M$、$\sigma = 45\%$ 时 $\Delta d_2 \approx 0.071$，ATM 附近约 **±3 个概率点**——方向上 $P$ 概率更高（正漂移），但一个月尺度上是二阶量。页面不设 $\mu$ 输入（那会把工具变成收益预测器），统一报 Q 概率并标注；$P$ 与 $Q$ 的差异整体交给 §2 推论 2.3 的 $\rho$ 通道去说。

---

## 4. 命题 4（wing 的可行域）：滑块钳制的依据

模型对 wing 的合法区间 $[\mathrm{lo}, \mathrm{hi}]$ 由两个约束决定，两端性质不同：

**下界（vol 正性 / 权利金存在性）**。tilt 后的波动率须为正：$\sigma_{\mathrm{ATM}} + \mathrm{wing}\cdot(c/0.05) > \sigma_{\min}$ 对使用中的每个 strike 成立，绑定在最宽的 cap 上：

$$\mathrm{wing} > -\big(\sigma_{\mathrm{ATM}} - \sigma_{\min}\big)\frac{0.05}{c_{\max}}.$$

这是理论包络；**实际绑定的约束更紧、而且是有意为之的**：`solve()` 要求两腿权利金都超过经济地板 $y > \mathrm{MIN\_PREMIUM} = 10^{-8}$（\$10mm 名义上不足 \$0.10 的权利金——等权利金构造在此之下已退化，B 腿趋于纯持股）。不用浮点下溢当边界还有一个工程原因：Python 与 JS 两个镜像的 erfc 尾部精度不同（numpy 在 $y \sim 10^{-18}$ 处相消归零，JS 的 Numerical-Recipes 级数能算到 $10^{-215}$），若以"价格算成 0"为界，两边会给出不同的可行域；以显式地板为界后两镜像的边界一致到 $2\times 10^{-6}$。锚点（记录于 `self_check` / `qa/_jscheck.mjs`）：$\sigma_{\mathrm{ATM}}=20\%$、$c_A=20\%$ 时理论包络为 $-0.0500$，**权利金地板边界为 $-0.0171$**。因此**边界用对 `solve()` 合法性的二分来找，不用闭式**（`wing_bounds()`，公差 $10^{-5}$）。

**上界（排序条件 = 垂直价差无套利）**。$c_A > c_B$ 时模型要求 $f_B < f_A$，而

$$f_B \ge f_A \iff y_A \ge y_B \iff C(K_A) \ge C(K_B),\quad K_A > K_B,$$

**恰好是 call 价格对 strike 单调性的违反，即垂直价差套利**。所以"ordering"错误不是模型的技术性挑剔，是无套利边界。$y_A/y_B$ 对 wing 单调递增（正 wing 同时抬高两腿的 IV，但 A 腿乘的是 $c_A/0.05 > c_B/0.05$，且 OTM 期权的相对价格弹性 $\nu/y$ 更大——见 `00_theory_k_ratio_skew.md` 的 $d\log f_B/dk = \sigma_{\mathrm{ATM}}\nu_A/y_A > 0$），故上边界唯一，同样二分可得。基准参数下上界在滑块范围（$+0.05$）之外，不绑定；把 $c_B$ 抬近 $c_A$ 或压低 $\sigma_{\mathrm{ATM}}$ 时会进入范围。

**对 dashboard 的含义**：wing 滑块的有效范围随 $(\sigma_{\mathrm{ATM}}, c_A, c_B, \tau, r_f, q, b)$ 动态钳制到 $[\mathrm{lo}, \mathrm{hi}]$，滑块可达状态全部合法；`INVALID` 分支保留作为纵深防御（直接改代码/极端参数仍受保护）。$f_A$ 不影响边界（$f_B \ge f_A \iff y_A \ge y_B$ 与 $f_A$ 无关）。

---

## 5. 命题 5（期限网格）：strike × maturity 表格的单元格定义

对 cap 行 $c \in \{0, 2.5\%, 5\%, 7.5\%, 10\%, 15\%, 20\%\}$、期限列 $\tau \in \{1,2,3,6,9,12\}$ 个月，每格报告：

| 量 | 公式 | 含义 |
|---|---|---|
| $y(c,\tau)$ | $C\big(S_0(1+c);\ \sigma_{IV}(c), \tau\big)/S_0$ | 权利金，占现货 |
| 权利金（美元） | $y \cdot W$（全额覆盖 $f=1$ 口径） | 桌面报价 |
| $\tilde y(c,\tau)$ | $y\,e^{r_f\tau}$ | 卖掉切片的 Q 值（命题 2） |
| $\mathbb{P}(\text{called})$ | §3.2 smile 一致 digital | 被行权概率（Q） |
| $f_B(c,\tau)$ | $f_A\,y(c,\tau)/y(c_B,\tau)$，锚 = **同期限**的 $c_B$ 腿 | 等权利金覆盖比例 |
| $r^{**}(c,\tau)$ | $(f_A c - f_B c_B)/(f_A - f_B)$ | A/B 切换点 |
| $D_{\mathrm{peak}}(c,\tau)$ | $f_B (c - c_B)$ | A 的最大优势 |

约定：每列的 ATM 锚取**同一期限**（否则 $f_B$ 混合两个期限的 vol 水平，失去"同月替代结构"的含义）；$c < c_B$ 或 wing 在该 cap 越出 §4 可行域的格子标记为不可行、报 NaN 而不是静默丢行（表形状稳定）。`strike_tenor_grid()`；`self_check` 验证 $(c_A, 1M)$ 格与 `solve()` 逐字段一致。

wing 的跨期限外推注意：tilt 系数按**收益空间 moneyness** 定义（每 5\% OTM 差 wing 个 vol 点，与 $\tau$ 无关）。真实市场里 skew 大致按 $\sqrt\tau$ 变平（delta 空间），所以长期限、宽 cap 的格子里线性 tilt 会高估 skew——网格是**比较静态工具，不是曲面模型**，与 `ab_core.py` 模块注释的定位一致。

### 5.1 附注（命题 5b）：$D_{\mathrm{peak}}(c)$ 的内部极值点——"sweet-spot cap"会随期限跑出显示窗口

固定 $c_B=0$、$f_A=1$、wing $=0$ 时 $D_{\mathrm{peak}}(c) = f_B(c)\cdot c = c\cdot y_A(c)/y_B$，$y_B$ 与 $c$ 无关，故 $D_{\mathrm{peak}}(c) \propto c\cdot y_A(c)$——形式上就是"价格 × 数量"的收入曲线。求导：

$$\frac{d}{dc}\big[c\,y_A(c)\big] = y_A(c) + c\,y_A'(c) = 0 \iff \underbrace{\frac{c\,y_A'(c)}{y_A(c)}}_{\text{弹性}} = -1.$$

**内部极大值出现在 OTM 权利金对 cap 的点弹性恰好等于 $-1$ 的地方**——与垄断定价里"边际收益为零 $\iff$ 需求弹性 $=-1$"是同一个代数结构。数值验证（`self_check`）：基准参数（$\sigma_{\mathrm{ATM}}=45\%$）下 $\tau=1M$ 时极大值在 $c\approx 9.0\%$（弹性 $-1.009$），$\tau=3M$ 时在 $c\approx 17.0\%$（弹性 $-1.002$）。

**这个极值点随 $\tau$ 单调外移，而且会跑出 dashboard 的 cap 滑块范围（$[0,25\%]$）**：期限越长，$\sigma\sqrt\tau$ 越大，$y_A(c)$ 对 $c$ 的衰减越慢（同样的 OTM 百分比在更长期限里"没那么虚值"），弹性触及 $-1$ 需要更宽的 $c$。二分求得阈值：$\tau \approx 5.49$ 个月——**低于此期限，$D_{\mathrm{peak}}(c)$ 在滑块可达范围内先升后降，有真实驼峰；高于此期限，极大值点已经超出 25% OTM，滑块范围内看到的只是驼峰左半段——单调上升、上凸减弱（12M 时中点偏离线性插值达 30%，仍有真实曲率，但不再有转折）。**

**对 dashboard 图 4（Sweep c_A）的含义**：曲线形状随期限从"驼峰"变为"单调上凸"不是渲染或坐标轴的假象，是这条弹性边界穿越了显示窗口的真实结果。图上应标出：极大值点落在窗口内时，标出该点（sweet-spot cap）；落在窗口外时，标注"最优 cap 超出 25% OTM，本图范围内仍在上升"，避免被误读为"这个位置附近已经差不多是最优"。

---

## 6. 实现与校验索引

| 命题 | 代码 | 数值验证（`self_check`） |
|---|---|---|
| 1 Notional 翻译 | `Solution.desk_view()` | \$10mm：两腿权利金相等 = \$329,455；1,000 / 617.2 张 |
| 2 切片 Q 值 | （恒等式，无新代码） | 数值积分 $\tilde y_A, \tilde y_B$ 到 $10^{-7}$；$\mathbb{E}^Q[D]$ 残差 $10^{-11}$ |
| 3 被行权概率 | `call_prob_q()`、`solve()` 的 `prob_*` | $N(d_2)$ = 解析尾概率；smile digital = 中心差分到 $10^{-6}$；负 wing 抬高两腿概率 |
| 4 wing 可行域 | `wing_bounds()` | $\sigma=20\%/c_A=20\%$：lo $=-0.0171$，边界两侧合法性翻转 |
| 5 期限网格 | `strike_tenor_grid()` | $(5\%, 1M)$ 格与 `solve()` 一致 |
| 5b sweet-spot cap | （恒等式，无新代码；见 §5.1） | 弹性 $=-1$ 于 $\tau=1M,c\approx9.0\%$ 和 $\tau=3M,c\approx17.0\%$；阈值 $\tau\approx5.49M$ 两侧内部/边界极大值翻转 |

`AB_explorer.html` 内嵌同一套数学（wing 钳制、desk 行、概率列、期限网格），由 `qa/_jscheck.mjs` 对照本页锚点数字回归、`qa/_rendercheck.mjs` 验证滑块可达状态全部合法。
