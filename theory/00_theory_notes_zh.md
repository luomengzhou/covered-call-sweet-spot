# Step 0 — Covered Call 理论笔记（A vs B 的先验）

> 2026-07-14 · NVDA sweet spot 分析的立论基础。所有结论后续都要用数据验证。

## 1. A−B 胜负区间：解析推导

**记号**：r = NVDA 当月净收益；A 套目标权利金 y（占组合名义的比例）；A 的 cap c = strike/spot − 1 > 0（由 y 反推）；B 套卖 f 比例仓位的 ATM call，权利金匹配 f·y_ATM = y。

**月度收益**（忽略现金利息，attribution 数据已验证此式到 ~1bp）：

- A（满仓 OTM）: `r_A = min(r, c) + y`
- B（部分 ATM）: `r_B = (1−f)·r + f·min(r, 0) + f·y_ATM = (1−f)·r + f·min(r, 0) + y`

**做差** `D = r_A − r_B = min(r, c) − (1−f)·r − f·min(r, 0)`：

| 区间 | D | 谁赢 |
|---|---|---|
| r ≤ 0 | 0 | **精确打平**（都全额吃跌幅 + 收同样权利金） |
| 0 < r ≤ c | f·r（斜率 +f） | A 赢，r=c 时优势最大 = f·c |
| r > c | c − (1−f)·r（斜率 −(1−f)） | r < r* 时 A 仍赢；**r > r\* = c/(1−f) 后 B 赢，且优势无上界** |

**结构解读**：premium 匹配后，"持有 A 而非 B" 等价于一个**零成本 call spread**：多 f 张 ATM call、空 1 张 strike=c 的 OTM call。A 的优势有顶（f·c），B 的优势无顶。风险中性定价下 E[D]≈0——**谁赢取决于真实分布 vs 隐含分布的差异，也就是 vol surface 哪一段更贵**。

**推论（数据要验证的）**：
1. 逐月胜负几乎是 r 落点的机械映射 → "切换规则"本质 = 预测 P(r > r*)，即大涨概率。
2. NVDA 上涨月多 → A 胜率高；但 NVDA 右尾极肥（财报 gap +15~25%）→ B 赢的月份赢得多。均值层面谁占优是实证问题。
3. r* = c/(1−f)：目标收益率越高 → c 越小 → r* 越低 → B 更容易赢。sweet spot 会随目标档位移动。
4. Skew 角度：A 卖的是 OTM call 翼（通常 IV 低于 ATM），同样权利金要卖掉更多"张数"的上行；若右尾被系统性低估（NVDA 很可能），A 结构性吃亏。

## 2. Israelov & Nielsen (AQR 2015)《Covered Calls Uncovered》框架

把 covered call 收益分解为三个暴露：
1. **被动 equity beta** — 贡献大部分风险和收益；
2. **short volatility**（VRP）— Sharpe 接近 1.0，但只占约 10% 风险 → 这是策略唯一的"结构性 alpha"；
3. **equity timing/reversal**（short call 的 delta 随价格动态变化）— 占约 25% 风险却**几乎无补偿**。

他们的 risk-managed 版本对冲掉第 3 项后 Sharpe 更高、回撤更小。**对我们的意义**：A 和 B 的差异可以用这套语言讲——B(部分 ATM) 的 timing 暴露更小更线性；A(满仓 OTM) 在接近 cap 时 delta 骤降，timing 暴露最大。memo 里用这个框架立论。

## 3. 行业界标

- **CBOE BXM**：S&P 500 满仓卖 1 个月 ATM call（第三个周五滚动，欧式，VWAP 成交价）≈ 我们 A 家族的极限档（目标收益率最高档）。**BXY** = 2% OTM 版 ≈ A 家族中间档。我们的 Income 家族本质是"yield-target 参数化的 BXM/BXY 族"。
- 注意我们的指数用**美式**期权（rebal report 确认），但 NVDA 近乎零股息 → 提前行权价值≈0，可当欧式近似。

## 4. 商业侧警示案例：YieldMax NVDY

真实存在的 NVDA covered call 收入产品（synthetic covered call）。关键教训：**distribution yield ≠ total return**——2022–2025 年化 −11.2%，同期 NVDA 大涨；2025-08~12 派息 $11.91/share 但 NAV 跌 21%（派息大量来自本金）。高目标收益率档（13%、15%）如果做成产品，客户拿到的"收入"很大程度是自己的本金换的。memo 里必须有这一段——这正是 target-yield 档位扫描的商业含义。

## 5. 三个分析前登记的理论预期（Step 2–4 验证）

1. **VRP 存在性**：Call Yield 反推的隐含 vol（σ ≈ call_yield/(0.4·√T)）应长期高于随后实现 vol；差值收窄/转负的时期，所有卖 call 策略都难看。
2. **Target-yield 的内生性陷阱**：低波期 strike 被迫贴近 ATM（cap 紧）、高波期远（cap 松）→ Cap 列与隐含 vol 代理应正相关；意味着 Income 家族在低波慢牛（2016–21 型）被系统性打爆——是设计使然不是 bug。fixed-delta 选 strike 无此问题，memo 可提为改进方向。
3. **Sharpe 虚高**：卖方策略收益负偏（小赢多、偶尔大输给基准）→ 主口径用 Calmar/Sortino + 逐月胜负，Sharpe 只作参考。

## 6. Desk 定的实验设计（2026-07 stakeholder discussion；原始纪要不在本仓库）

**对比基准 = 权利金相等（= 同 target yield）。** 这是 desk 明确定的，不是推测。原话："instead of selling a 107 strike call which is 100% notional, I will sell 20% of at-the-money call... **essentially I'm just saying that the same premium** I'm getting by selling a bit of the at-the-money." → 所以 `f·y_ATM = y` 的口径来自这里；他**没有**要求"风险相等"。风险归一化版是我们自己的扩展方向（见下），不冲突，但排在权利金版之后。

**他要的两组回测（26:37–27:00）：**
1. **第一组 = Strategy A**：满仓 covered call（卖 100% notional 的 OTM cap），target yield 从 **1% 扫到 15%**，每 **1–2%** 一档，1 个月到期滚动。
2. **第二组 = Strategy B**：**同一 target yield、同一 expiry**，改成卖部分参与（partial ATM）。

**从回测里要抽的统计**：每月 cap 被打中几次、每月实际收益（NVDA 无股息，price return 即可）、逐月哪个策略赢。

**switch / sweet spot 的驱动因素**（他点名的）：target yield（premium level）、利率、到期时间，还有波动率——他说 vol 是 "another hidden parameter"，且"**there may not always be one answer, there may be a range**"（sweet spot 很可能是一个**区间**不是一个点）。

**终局路线**：NVDA 先做通 → 拟一个 **Z-score 规则**（月初已知 cap 和参与率，用 NVDA 及各股月度表现的 z-score 预判该月选 A 还是 B）→ 再推广到其余 6 个 Mag7 → 最后定成一篮子 covered call 的选券规则。

## 7. 为什么解出了 r\* 还要跑回测（给自己留的备注）

`r* = c/(1−f)` 只是**机械分界线**：给定某月的 r 就知道谁赢。它**不告诉你两件事**——(1) r 实际会落在哪、r\* 一年被越过几次（NVDA 的真实分布）；(2) 赢多少（A 赢有顶 = f·c，B 赢无顶）。这两件只能靠**历史数据**。

`E[D]≈0`（风险中性下）的含义：若 NVDA 未来分布 = 期权隐含分布，则两策略长期打平。**所有 edge 都来自"真实分布 ≠ 隐含分布"**——即 vol surface 哪一段被定价得太贵/太便宜。NVDA 右尾极肥（财报 gap），市场可能低估 → 只能实证，公式算不出。**所以 r\* 是解析层，回测是实证层，两个都要。**

**"零成本 call spread"白话版**：把 D = r_A − r_B 画成 r 的函数——r≤0 时平、0<r≤c 时以斜率 f 上爬（到 r=c 顶点 f·c）、r>c 后以斜率 −(1−f) 下坡并转负。这个形状 = **买 f 张 ATM call + 卖 1 张 strike=c 的 OTM call**。因为两边权利金已拉平，组合净成本≈0，故"零成本"。一句话：**选 A 不选 B ≈ 持有一个牛市价差**。A "小赢常赢"（有顶），B "大涨通吃"（无顶）。

## 8. 数据面板规格 + 现有数据盘点 + 缺口

**目标面板**（逐月一行 = 标的 × target yield 档 × 月份）：

| 字段 | 含义 | 来源 |
|---|---|---|
| `month` | 1 个月到期滚动 | — |
| `underlier` | NVDA，之后扩到其余 6 个 | — |
| `spot` | 月初现价 | garage |
| `r` | 当月实际收益率 | NVDA 收益指数（无股息） |
| `target_yield y` | 目标权利金档（1%→15%） | 设定 |
| `c` | cap = strike/spot−1，由 y 反推 | 期权价/IV |
| `y_ATM` | ATM call 权利金率 | 期权价/IV |
| `f` | = y / y_ATM（B 卖的仓位比例） | 计算 |
| `r_A, r_B, D` | 三条收益 | 公式 |
| `winner, cap_hit` | A/B、r 是否 > c | 计算 |
| `iv_atm, realized_vol` | 隐含波 vs 已实现波 | 切换驱动 |
| `rate` | 利率 | TB3MS |

**现有数据（`data/`）盘点：**
- **Exposure family（20/30/40/50）= Strategy B。** 已验证：rebal 里 期权股数/股票股数 = f（20%/30%/40%/50%），卖的是 ATM call（strike%≈99.6%）。attribution 报告给逐月 2008–2026 的 `Underlying Asset Return`(=r)、`Cap`、`Call Yield`(=y_ATM)、`Index Return`。⚠️ 注意这是**固定 f**，不是每月按权利金匹配的 B；严格按 desk 口径需重跑 premium-matched（f 每月 = y/y_ATM），或用固定 f 先看趋势。
- **Income family = Strategy A**，用户确认数据下载中（此前 `data-explorer` 只有一条 `NV_CoveredCall_1_Income`、日频、1 年，不够）。校验点：**Income 各档的 Cap 列应彼此不同**（strike 随 target yield 变）；若又都一样 = 真有问题。
- **TB3MS.csv** = 3M 国债利率，逐月，利率驱动用。✅

**缺口**：realized vol / IV 干净序列（可用 r 与 Call Yield 代理）；其余 6 个 Mag7（后期）。

## 9. Rebal 报告字段 / 单位说明（避免再被 ×100 绊住）

以 `NV_CoveredCall_20_Exposure_rebal_report.csv` 2008-02-15 建仓为例：

- **base=1000 → 满仓标的**：Equity 44.90 股 × 22.27 = 1000。covered call 结构是"满仓持标的 + 在其中一部分上卖 call"，所以 **equity 价值 = base 是对的**。
- **exposure 藏在"股数比"，不在金额**：|Option shares 8.98| ÷ |Equity shares 44.90| = **20%** = f。期权 Shares 与股票 Shares 是**同一"股"单位**，直接相除即 exposure。
- **Cash = 卖 call 收的权利金**：|opt_sh| × opt_px = 8.98 × 1.7 = 15.27 = f × CallYield × eqVal。
- **`Strategy` 列是空的**（663 行 0 个非空值）。之前截图里的 −1526.7 是手动乘出来的（= 15.27 × 100，即权利金 × 合约乘数），**不是文件里的数**。别去依赖这列。
- **Cap 列是"那张期权"的属性，不是组合有效上限**：跨 Exposure 档（10/20/30/40/50）的 `Cap` 与 `Call Yield` **完全相同**（已核对 221 个月，0 处不同），因为都卖同一张 ATM strike；差异只体现在 `Index Return`。**区分不同 Exposure 档要看 Index Return，别看 Cap/Call Yield。**

## 10. 指数构造逻辑（从 attribution + rebal 逐月反推验证）

**建仓（rebal report）：**
- **Equity**：满仓，base 全买 NVDA，`eqVal = 股数 × spot`。
- **Strike**：取**离 spot 最近的挂牌行权价**（整数档）→ **≈ATM，非 delta target、非 yield target**。strike% 在 94–109% 抖只是挂牌档离散所致；期权 delta 天然≈0.5 但没主动锁。
- **f (exposure)** = |期权股数| ÷ 股票股数 = **固定 20/30/40/50%**，是**唯一设计旋钮**。
- **Cash** = 权利金 = |期权股数| × 期权价 = f × CallYield × eqVal。

**attribution 各列（全部验证过）：**
- `Cap` = **strike / spot**（>1 OTM，<1 ITM）。
- `Call Yield` = **期权价 / spot**（满仓口径 ATM 权利金率）。
- `Underlying Asset Return` = r = NVDA 当期收益。⚠️ **2021-08、2024-06 两个月是拆股假数据**（−71%、−86%，未复权），用前须剔除/修正。
- `Index Return` = **`r − f·max(r − (Cap−1), 0) + f·CallYield`**，其中 Cap、CallYield 取**上一 rebal 日卖出的那张期权**（当期真正在仓的那张，非同一行）。
  - 220 个月逐月验证：除上述 2 个拆股月外，**误差≈0（中位数 0.00000）**。这就是指数真实构造。

**与理论笔记的对应**：这条公式里 `Cap−1` = 理论的 `c`，`f·CallYield` = 权利金 `y` → **Exposure family 的 Index Return 就是我们理论里的 r_B**（部分参与、卖 ATM 故 c≈0、f 固定）。等 Income family 到位，其 Index Return 应对应 **r_A**（满仓、c 由 target yield 定、f=1）——可用同一套公式反查校验。

## 11. Switch 规则的 z-score 理论(Phase 5 立论,2026-07-21)

**z-score = (x − x 的历史均值) / x 的历史标准差。** 把任意变量标准化成"相对自身历史高/低几个标准差",这样能设统一阈值(z>1 就切换)。关键不是 z 本身,而是**作用在哪个变量上**。真实规则须用**滚动/扩展窗口**算 z(只用截至上月的数据),否则有前视偏差。

**switch 的核心任务**:月初预判 NVDA 这个月会不会**冲右尾(暴涨)**。因为(第 1 节 + Phase 4 已证)跌→A/B 打平、温和涨→A 赢、暴涨→B 大赢。能预测右尾就能切。

**候选信号(月初可观测)及方向:**

| 变量 | z 高时 | 偏向 |
|---|---|---|
| 动量(过去 3-12 月收益) | 趋势强,更可能续冲右尾 | **B**(留上涨) |
| 隐含波动 / IV rank(ATM yield) | 权利金肥,卖 call 更值 | **A / 多卖** |
| VRP = 隐含波 − 已实现波 | 卖方溢价厚 | **A / 多卖** |
| 估值/乖离 | 涨过头,或回调 | **A**(封顶无妨) |
| 利率 | desk 提过(影响期权定价) | 待验证 |

**关键结论(纠正"只看动量"):** 实务主流是**波动率驱动**——active overlay 直接按 VXN 调覆盖(低波卖 25%、高波卖 50%)。动量是另一条线,且**常与波动率打架**(高动量往往伴高 IV,一个偏 B 一个偏 A)。所以需多信号、用数据定谁强。

**AQR 警告(最该记):** Israelov & Nielsen 拆解显示 covered call 里"股票择时/反转"那块占 ~25% 风险却几乎无回报(未补偿风险)。**A↔B 切换本质就是择时叠加 → 若 z-score 规则不能真正预测右尾,就只是徒增无补偿的风险。** Phase 5 必须回测:规则真的强过"一直 A / 一直 B",还是只加波动。

**资金盘/拥挤度(另一维,非月度信号):** VRP 会被卖方拥挤压缩(JEPI/QYLD/NVDY 等 AUM 越大权利金越薄,见第 4 节 NVDY)。属慢变量、结构性逆风,用于判断"策略整体还值不值得做",不进按月 z-score。

**Phase 5 做法:** 先不定规则。把 Phase 4 逐月 D(A−B)对上述各 z 信号分组,看**哪个 z 能真把"A 赢月"和"B 赢月"分开**;分得开的才进规则,分不开的淘汰。

### Sources(第 11 节)
- [Israelov & Nielsen, Covered Calls Uncovered (AQR)](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Covered-Calls-Uncovered.pdf) — 三重暴露分解,择时腿未补偿
- [How to Use Volatility to Select Covered Call Strikes (Volatility Box)](https://volatilitybox.com/research/how-to-use-volatility-to-select-covered-call-strikes/) — 按 IV 调覆盖比例的 active overlay
- [When to Sell Covered Calls (Quantwheel)](https://quantwheel.com/learn/when-to-sell-covered-calls/) · [covered call ETF 趋势市跑输 (justETF)](https://www.justetf.com/en/how-to/invest-in-covered-call-etfs.html)

## Sources

- [Israelov & Nielsen, Covered Calls Uncovered (AQR PDF)](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Covered-Calls-Uncovered.pdf) · [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2444999)
- [Cboe BuyWrite Indices Methodology (PDF)](https://cdn.cboe.com/api/global/us_indices/governance/Cboe_BuyWrite_Indices_Methodology.pdf) · [BXM Wikipedia](https://en.wikipedia.org/wiki/CBOE_S&P_500_BuyWrite_Index)
- [NVDY 概览 (stockanalysis.com)](https://stockanalysis.com/etf/nvdy/) · [NVDY NAV erosion 分析 (ainvest)](https://www.ainvest.com/news/nvdy-yield-illusion-synthetic-exposure-capital-erosion-risks-2512/)
