# Covered Call A vs B — Call Yield、\(f_B\)、与 flat \(\sigma\) 的比较静态

> 符号与设定对齐：`00_theory_derivation.pdf`  
> 图示对齐：`00_theory_A_vs_B_en.png`  
> 本文范围：**只讨论 flat \(\sigma_{IV}\)**（ATM / OTM 共用同一条 IV）。  
> **不在本文**：skew / anchor IV ≠ OTM IV（下一节再开）。

---

## 0. 结构设定（报幕）

| 结构 | 含义 | 典型 toy |
|------|------|----------|
| **A** | full overwrite，**OTM** | \(f_A = 1\)，\(c_A = 5\%\)（\(k_A = 1.05\)） |
| **B** | partial overwrite，**ATM** | \(c_B = 0\)（\(k_B = 1\)），\(f_B\) 由 premium-match 决定 |

约定（与文档一致）：

\[
c_A > c_B
\]

Toy 公共参数（flat smile）：

\[
\sigma_{IV}=45\%,\quad \tau=1/12,\quad r_f=4\%,\quad q=0
\]

> 注意：这里的 \(k = K/S_0\) 是 **strike 倍数**，不是 skew 参数。

---

## 1. 符号（只用文档里的）

| 符号 | 含义 |
|------|------|
| \(S_0, S_T\) | 期初 / 到期 spot |
| \(R = S_T/S_0\) | gross price return |
| \(r = R - 1\) | net price return |
| \(K\) | strike |
| \(k = K/S_0\) | strike 相对 spot |
| \(c = k - 1\) | cap（net-return 空间里的 strike 位置）；OTM \(c>0\)，ATM \(c=0\) |
| \(y(c)\) | **Call Yield**（见下节） |
| \(\tilde{y} = y\,e^{r_f\tau}\) | 权利金按无风险利率持有到 \(T\) 后的有效率 |
| \(f \in [0,1]\) | overwrite ratio = 卖出期权份数 / 持有股数 |
| \(Y = f\,y(c)\) | 组合层面实际收到的 premium rate |
| \(\sigma_{IV}\) | implied vol（本文：**对所有 strike 相同**） |
| \(\tau, r_f, q\) | 期限、无风险利率、股息率 |

单期收益（文档 (1a)(1b)）：

\[
R_{cc}
= r + q + f\,\tilde{y} - f\,(r - c)^+
= (1-f)\,r + f\bigl[\min(r,c) + \tilde{y}\bigr] + q
\]

要点：

- \(f=1\)：有硬 cap，\(r>c\) 后收益封顶在 \(c+\tilde{y}\)
- \(f<1\)：**无硬 cap**，\(r>c\) 后斜率仍为 \(1-f>0\)（B 类结构在大涨里继续吃到 upside 的来源）

---

## 2. Call Yield 的定义

文档 §0：

\[
\boxed{
y(c) \;=\; \frac{C_0}{S_0}
}
\]

即：**每覆盖 1 单位标的、在该 strike 上卖出 1 份 call 所收到的权利金 / 期初 spot**。  
这就是 Call Yield；不是 \(\pi\)，也不是组合层面的 \(Y\)。

组合实际收到：

\[
Y = f\,y(c)
\]

Black–Scholes（\(S_0=1\) 时 \(y\) 就是 call 价格本身）：

\[
y(k)
= e^{-q\tau}N(d_1) - k\,e^{-r_f\tau}N(d_2)
\]

\[
d_1
= \frac{-\ln k + \bigl(r_f - q + \tfrac12\sigma_{IV}^2\bigr)\tau}{\sigma_{IV}\sqrt{\tau}},
\qquad
d_2 = d_1 - \sigma_{IV}\sqrt{\tau}
\]

其中 \(k = 1+c\)。

Toy 数值（flat \(45\%\)，1M，…）：

\[
y(c_A)=y(5\%)=3.294550\%,
\qquad
y(0)=y_{\mathrm{ATM}}=5.338\%\ \text{（量级；以你 verify 脚本为准）}
\]

---

## 3. Premium-match 与 \(f_B\)

Uday 口径：两个结构收到的 **组合 premium rate 相同**

\[
f_A\,y(c_A) = f_B\,y(c_B)
\]

主设定 \(f_A = 1\)，\(c_B = 0\)：

\[
\boxed{
f_B
= \frac{y(c_A)}{y(0)}
= \frac{y_{\mathrm{OTM}}}{y_{\mathrm{ATM}}}
}
\]

Toy：

\[
f_B = \frac{3.294550\%}{5.338\%} \approx 0.617
\]

因此：

- \(f_B\) **就是两个 call yield 的比值**
- strike / vol / \(\tau\) / \(r_f\) 等一切定价输入，都是通过 \(y(\cdot)\) 进入 \(f_B\)，再进入后面的 \(D(r)\)

Premium-match 后，带利息的常数项抵消（\(\tilde{y}\) 共用同一 \(e^{r_f\tau}\) 因子时）：

\[
f_A\tilde{y}_A = f_B\tilde{y}_B
\]

---

## 4. 差额 \(D(r)\)（几何由 \(c,f\) 决定）

文档 (3)：

\[
\boxed{
D(r)
\equiv R_A - R_B
= f_B\,(r-c_B)^+ - f_A\,(r-c_A)^+
}
\]

即：零成本 ratio call spread——多 \(f_B\) 份在 \(c_B\)，空 \(f_A\) 份在 \(c_A\)。

分段：

| 区域 | \(D(r)\) | 斜率 |
|------|----------|------|
| \(r \le c_B\) | \(0\) | \(0\) |
| \(c_B < r \le c_A\) | \(f_B(r-c_B)\) | \(+f_B\) |
| \(r > c_A\) | \(f_B(r-c_B)-f_A(r-c_A)\) | \(-(f_A-f_B)\) |

峰（A 的最大优势）在斜率变号点 \(r=c_A\)：

\[
\boxed{D(c_A) = f_B\,(c_A - c_B)}
\tag{4a}
\]

再穿零点 \(r^{**}\)（\(r>c_A\) 处令 \(D=0\)）：

\[
\boxed{
r^{**}
= \frac{f_A c_A - f_B c_B}{f_A - f_B}
}
\tag{4}
\]

特例 \(f_A=1\)，\(c_B=0\)：

\[
D(c_A)=f_B\,c_A,
\qquad
r^{**}=\frac{c_A}{1-f_B}
\]

Toy（\(c_A=5\%\)，\(f_B=0.617\)）：

\[
D(c_A)=3.09\%,
\qquad
r^{**}=13.06\%
\]

**结构含义：** \(f_A>f_B\) 时，在 \(c_A\) 以上净空 call —— A 的优势有顶，B 的优势在大涨里无顶。

---

## 5. Flat \(\sigma_{IV}\) 的比较静态（本文核心）

### 5.1 什么在动、什么不动

固定 \(c_A,c_B,f_A,\tau,r_f,q\)，只动 **同一条** \(\sigma_{IV}\)（ATM 与 OTM 共用）。

则：

- \(c_A,c_B\) 不变 → \(D\) 的 **折点位置**不变
- \(y(c_A;\sigma)\)、\(y(0;\sigma)\) 变 → \(f_B(\sigma)\) 变 → \(D\) 的 **高度与部分斜率**变

通道：

\[
\sigma
\;\longrightarrow\;
\bigl(y(c_A),\,y(0)\bigr)
\;\longrightarrow\;
f_B=\frac{y(c_A)}{y(0)}
\;\longrightarrow\;
\bigl(D(c_A),\,r^{**},\,\text{斜率}\bigr)
\]

### 5.2 Yield 对 \(\sigma\) 的导数（vega / \(S_0\)）

普通 BS call 的 vega：

\[
\frac{\partial C_0}{\partial\sigma}
= S_0\,e^{-q\tau}\,n(d_1)\,\sqrt{\tau}
\]

因此对 Call Yield：

\[
\boxed{
\nu(c)
\;\equiv\;
\frac{\partial y(c)}{\partial\sigma}
= e^{-q\tau}\,n\bigl(d_1(c)\bigr)\,\sqrt{\tau}
}
\]

记：

\[
y_A=y(c_A),\quad y_B=y(0),
\qquad
\nu_A=\nu(c_A),\quad \nu_B=\nu(0)
\]

### 5.3 \(f_B\) 对 \(\sigma\) 的导数

\[
f_B=\frac{y_A}{y_B}
\]

\[
\boxed{
\frac{\partial\log f_B}{\partial\sigma}
=
\frac{\nu_A}{y_A}-\frac{\nu_B}{y_B}
}
\]

等价地：

\[
\boxed{
\frac{\partial f_B}{\partial\sigma}
=
f_B\left(
\frac{\nu_A}{y_A}-\frac{\nu_B}{y_B}
\right)
}
\]

解读：

- 比的不是绝对 vega \(\nu\)，而是 **yield 弹性** \(\nu/y\)
- \(\nu_A/y_A > \nu_B/y_B\) ⇒ \(\partial f_B/\partial\sigma > 0\)
- 在本设定（A=OTM，B=ATM）下：低 σ 时 OTM yield 相对 ATM 更「干」；σ 抬高后 OTM 相对补回 ⇒ **通常 \(f_B\) 随 \(\sigma\) 上升**  
  （是否在你的参数区恒为正，可用 toy 的 \(d_1\) 把 \(\nu/y\) 算出来验符号——待细化）

### 5.4 对 \(D\) 的后果（\(c_B=0,\,f_A=1\)）

由

\[
D(c_A)=f_B\,c_A,
\qquad
r^{**}=\frac{c_A}{1-f_B}
\]

| flat \(\sigma_{IV}\uparrow\) | 后果 |
|------------------------------|------|
| \(f_B\uparrow\) | 要 match 更贵的 OTM premium，ATM 侧覆盖比例升高 |
| 中间段斜率 \(+f_B\) | 更陡 |
| 峰高 \(D(c_A)=f_B c_A\) | **升高** |
| \(r^{**}=c_A/(1-f_B)\) | **右移**（B 更晚才反超） |
| 高段斜率 \(-(1-f_B)\) | 绝对值变小（B 的残余 upside 变薄） |

一句话：

> **Flat σ 抬高 ⇒ OTM 相对 ATM 不那么「白送」⇒ \(f_B\) 变大 ⇒ A 相对 B 的优势区又高又往右拖。**

对峰高的显式敏感度（\(c_A\) 固定）：

\[
\frac{\partial D(c_A)}{\partial\sigma}
= c_A\,\frac{\partial f_B}{\partial\sigma}
= c_A\,f_B\left(
\frac{\nu_A}{y_A}-\frac{\nu_B}{y_B}
\right)
\]

对 \(r^{**}\)（\(c_B=0,f_A=1\)）：

\[
\frac{\partial r^{**}}{\partial\sigma}
=
\frac{c_A}{(1-f_B)^2}\,\frac{\partial f_B}{\partial\sigma}
\]

与 \(\partial f_B/\partial\sigma\) **同号**。

---

## 6. 和「扫 \(c_A\)」实验的区别（避免混）

图 (3)「Pushing A's strike further out」动的是 **\(c_A\)**，不是 \(\sigma\)：

- \(c_A\uparrow\) ⇒ \(y(c_A)\downarrow\) ⇒ \(f_B=y(c_A)/y(0)\downarrow\)
- 同时峰的横轴位置 \(c_A\) 本身右移；\(r^{**}\) 也右移

那是 **strike 比较静态**。  
本文是 **vol 比较静态**。两条通道都进 \(f_B\)，但不要混成一个故事。

---

## 7. 本文边界（下一节再写）

当前文档 / toy 明确：

\[
\sigma_{\mathrm{ATM}} = \sigma_{\mathrm{OTM}} = \sigma_{IV}
\quad\text{（flat）}
\]

**尚未引入：**

- anchor IV 与 OTM IV 不同
- ATM IV 与 OTM IV 不同（call skew）
- 形如 \(\sigma(c)=\sigma_0\cdot\kappa(c)\) 的参数化

那些会变成：

\[
f_B
= \frac{y(c_A;\sigma_A)}{y(0;\sigma_B)}
\]

再对 \(\sigma_0\)、\(\kappa\) 分别做比较静态——**单独开文档**，不塞进本节。

---

## 8. 小考用三句话

1. \(y(c)=C_0/S_0\)；premium-match 且 \(f_A=1,c_B=0\) 时 \(f_B=y(c_A)/y(0)\)。  
2. Flat \(\sigma\) 只通过 \(f_B(\sigma)\) 改 \(D\)；\(\partial\log f_B/\partial\sigma=\nu_A/y_A-\nu_B/y_B\)。  
3. \(\sigma\uparrow\) ⇒（通常）\(f_B\uparrow\) ⇒ 峰 \(f_B c_A\) 升高，\(r^{**}=c_A/(1-f_B)\) 右移。

---

## 9. 待你追问时再细化的清单

- [ ] 用 toy 的 \(d_1^A,d_1^B\) 数值验证 \(\nu_A/y_A ?\, \nu_B/y_B\) 的符号  
- [ ] 写出 \(10\%\to 45\%\) 时 \(f_B\) 的示意路径（仍可纯公式 / 手算几点）  
- [ ] \(\tau\)、\(r_f\) 的同类比较静态（同样走 \(y\to f_B\to D\)）  
- [ ] **下一文档**：skew（\(\sigma_A\neq\sigma_B\)）下的 \(f_B\) 与 \(D\)
