# Covered Call — Full Theoretical Derivation

> 2026-07-29 · Derived from the payoff up. Every formula is cross-checked in `theory/00_theory_verify.py` via 4M-path Monte Carlo vs. closed form (all PASS); the numbers quoted below come directly from that script.
> Relation to `00_theory_notes_zh.md`: that note's §1 (the A-vs-B win/lose region) is a special case of §3.3 here ($f_A=1,\ c_B=0$).

---

## 0. Notation

Following the data panel / attribution convention, **everything is normalized by spot** (equivalently $S_0=1$, all quantities expressed as a fraction of notional).

| Symbol | Meaning | Data source |
|---|---|---|
| $S_0,\ S_T$ | Spot at inception, spot at expiry | garage |
| $R=S_T/S_0$ | Gross price return; $r=R-1$ is the net price return | `Underlying Asset Return` |
| $K$ | Strike; $k=K/S_0$ | `Cap` column = $k$ |
| $c=k-1$ | **cap** (the strike's location in net-return space). OTM: $c>0$; ATM: $c=0$; ITM: $c<0$ | `Cap` − 1 |
| $y(c)$ | **Per-unit-of-overwrite** premium rate at that strike $=C_0/S_0$ | `Call Yield` |
| $f\in[0,1]$ | **Overwrite ratio** = option shares sold ÷ shares held | share-count ratio in the rebal report |
| $Y=f\\,y(c)$ | Portfolio-level premium rate actually received | — |
| $\tau$ | Time to expiry (years) | 1M ≈ 1/12 |
| $r_f,\ q$ | Annualized continuously compounded risk-free rate and pricing dividend yield | TB3MS / per-underlier |
| $d_T=D_{0\to T}/S_0$ | Realized single-period cash-dividend return | actual dividends over the holding period |
| $\sigma_{IV},\ \sigma_{RV}$ | Implied vol, realized vol | — |
| $\mu$ | Underlier's true (real-world / $\mathbb{P}$) expected total return | — |
| $\mathbb{P},\ \mathbb{Q}$ | Real-world measure, risk-neutral measure | — |

**Two knobs.** The entire strategy space is the two-dimensional plane $(f,\ c)$. The Income family is $f=1$ with $c$ backed out from a target yield; the Exposure family is $c\approx0$ with $f$ fixed. They are two lines on the same plane, not two different "strategies."

---

## 1. Single-period return: the general formula

### 1.1 Derived from the payoff

At $t=0$: buy 1 share with $S_0$ (notional $S_0$), sell a call struck at $K$ against a fraction $f$ of it, collect premium $f\\,y\\,S_0$, and earn interest $r_f$ on the cash.

Portfolio value at $t=T$:

$$V_T=\underbrace{S_T}_ {\text{stock held}}+\underbrace{D_{0\to T}}_ {\text{realized cash dividends}}-\underbrace{f\\,(S_T-K)^+}_ {\text{assignment payout}}+\underbrace{f\\,y\\,S_0\\,e^{r_f\tau}}_ {\text{premium + interest}}$$

Divide by $S_0$ and subtract 1, noting $(S_T-K)/S_0=R-k=r-c$:

$$\boxed{\\;R_{cc}=r+d_T+f\\,y\\,e^{r_f\tau}-f\\,(r-c)^+\\;}\tag{1}$$

Here $q$ and $d_T$ are deliberately different objects: $q$ is an annualized continuous yield used in option pricing, whereas $d_T$ is the realized simple dividend return entering the payoff. In a toy calculation with no dividend observations, one may approximate $d_T$ by $e^{q\tau}-1$; that approximation is not a payoff identity.

### 1.2 Three equivalent forms (each useful for something different)

$$R_{cc}\\;=\\;\underbrace{r+d_T}_ {\text{underlier total return}}\\;+\\;f\big[\\,y\\,e^{r_f\tau}-(r-c)^+\\,\big]\tag{1a}$$

$$R_{cc}\\;=\\;\underbrace{(1-f)\\,r}_ {\text{uncovered piece}}\\;+\\;\underbrace{f\big[\min(r,\\,c)+y\\,e^{r_f\tau}\big]}_ {\text{covered piece}}\\;+\\;d_T\tag{1b}$$

$$1+R_{cc}\\;=\\;\underbrace{(1-f)\\,R}_ {\text{uncovered}}\\;+\\;\underbrace{f\\,\min(R,\\,k)}_ {\text{capped stock}}\\;+\\;f\\,y\\,e^{r_f\tau}+d_T\tag{1c}$$

- (1a) is for **attribution**: underlier return + option-leg contribution.
- (1b) is the rigorous version of the informal "$f\cdot(\text{stock+premium})+(1-f)\cdot\text{stock}$" idea — note the covered piece is *not* `stock+premium`, it's `min(r,c)+premium`, which equals `stock+premium` only when $r\le c$.
- (1c) is for **pricing and change-of-measure**: $\min(R,k)$ is a "capped asset."

**Reconciling with MerQube's attribution report**: setting $d_T=r_f=0$, (1) becomes
$$\texttt{Index Return}=r-f\cdot\max\big(r-(\texttt{Cap}-1),0\big)+f\cdot\texttt{Call Yield}$$
which is exactly the identity verified month-by-month in the earlier note's §10 (median error 0.00000 across 220 months). **(Script check: max diff = 2.8e-17)**

### 1.3 The key identity: covered call = cash-secured short put

$$\min(S_T,K)=K-(K-S_T)^+$$

So **the expiry payoff of a full overwrite ($f=1$) is identical to "holding a bond with face value $K$ + selling a put struck at $K$"** (the expiry form of put-call parity). Corollary:

> The whole $(f,c)$ plane is just **a menu of "how big and how far OTM a put to sell."**
> - ITM overwrite ($c<0$) = mostly cash + sell a deep-OTM put → a near-cash asset.
> - ATM overwrite ($c=0$) = sell an at-the-money put → roughly 50% delta.
> - Deep-OTM overwrite ($c\gg0$) = almost naked stock + sell a tiny put.
>
> This is why "writing covered calls" is never an independent source of risk: it's just **equity beta + a short put (= short vol + short skew)** repackaged. It maps directly onto AQR's three-way decomposition.

---

## 2. All six cases enumerated

From (1b), let $\tilde y\equiv y\\,e^{r_f\tau}$ and suppress $d_T$ in the case table:

### 2.1 Full overwrite $f=1$: $R_{cc}=\min(r,c)+\tilde y$

| Strike choice | Not assigned ($r\le c$) | Assigned ($r>c$) | Max return (cap) | Downside buffer | Structural meaning |
|---|---|---|---|---|---|
| **OTM** $c>0$ | $r+\tilde y$ | $c+\tilde y$ | $c+\tilde y>0$ | $\tilde y$ | Keeps the upside up to $c$ + premium; this is "when $k>s$, return = stock return + premium, and once assigned, = (K−S)/S + premium" |
| **ATM** $c=0$ | $r+\tilde y$ ($r<0$) | $\tilde y$ | $\tilde y$ | $\tilde y$ | **Upside return is always exactly the premium, regardless of how much the stock is up**; downside is fully absorbed |
| **ITM** $c<0$ | $r+\tilde y$ ($r<c<0$) | $c+\tilde y$ | $c+\tilde y$ = strike component + premium future value | $\tilde y$ | The pre-collected intrinsic value helps fund protection over the same region; the assigned-state return must not be labeled inception time value |

**Key decomposition for ITM.** At inception the spot-normalized extrinsic value is
$$x_0\equiv y-(-c)=y+c\ge0,$$
for an American call (or when the immediate-exercise bound applies). For a European call with continuous dividend yield, the sharper no-arbitrage lower bound is
$$y\ge\max\!\left(e^{-q\tau}-k e^{-r_f\tau},0\right),$$
which need not equal spot intrinsic value when rates or dividends are nonzero. At expiry, however, the premium cash has grown to $\tilde y$; hence the assigned-state cap is $c+\tilde y$ (or $c+d_T+\tilde y$ including dividends), **not** $x_0$. Since a nonnegative stock implies $r\ge-1$, the full-overwrite return range is the finite interval $[-1+d_T+\tilde y,\ c+d_T+\tilde y]$. Economically, the structure is prepaid downside protection rather than free yield enhancement.

### 2.2 Partial overwrite $f<1$: linear interpolation between naked stock and full overwrite

$$R_{cc}(f,c)=(1-f)\\,r+f\cdot R_{cc}(1,c)$$

There is exactly one structural difference, but it matters enormously:

> **When $f<1$, the return has no cap.** Above $r>c$ the slope is $(1-f)>0$, not 0. This is the entire source of B-type structures (partial ATM) "capturing everything in a big rally."

| Strike | $r\le c$ | $r>c$ | Cap | Note |
|---|---|---|---|---|
| OTM $c>0$, $f<1$ | $r+f\tilde y$ | $(1-f)r+fc+f\tilde y$ | None | Kinked line: slope $1\to(1-f)$, kink at $r=c$ |
| ATM $c=0$, $f<1$ | $r+f\tilde y$ | $(1-f)r+f\tilde y$ | None | Kink at 0; the downside is fully linear |
| ITM $c<0$, $f<1$ | $r+f\tilde y$ | $(1-f)r+fc+f\tilde y$ | None | Kink at $r=c<0$; the downside gets "partially capped" too (because part of the ITM downside has already been sold) |

### 2.3 Multi-strike ladders

Generalizing is trivial: sell $J$ tranches, overwrite ratio $f_j$, cap $c_j$, $\sum_j f_j\le1$,

$$R_{cc}=r+d_T+\sum_{j=1}^{J}f_j\Big[\\,y(c_j)\\,e^{r_f\tau}-(r-c_j)^+\\,\Big]\tag{2}$$

$R_{cc}(r)$ is a **piecewise-linear, concave, non-decreasing function of $r$**, with initial slope 1 and nonnegative downward slope jumps $f_j$, ending at $1-\sum f_j\ge0$. Conversely, a finite piecewise-linear payoff has representation (2), up to its cash/dividend constant, only if it is continuous and concave, has initial slope exactly 1, terminal slope in $[0,1]$, and nonnegative slope drops at the chosen strikes. Under those conditions (2) parametrizes the covered-call ladder family; the weaker condition “non-decreasing with slope at most 1” alone is insufficient.

---

## 3. Every breakpoint

### 3.1 Relative to buy & hold

From (1a), $R_{cc}-R_{stock}=f\big[\tilde y-(r-c)^+\big]$:

| Breakpoint | Formula | Note |
|---|---|---|
| **Assignment begins** | $r=c$ | Every point of further upside after this gives up $f$ points |
| **Turns negative relative to underlier** | $\\;r^{\*}=c+\tilde y\\;$ | **Independent of $f$!** $f$ only sets how much is given up ($-f(r-c-\tilde y)$), not when the losing starts |
| **Absolute breakeven** | see the branch conditions below | Depends on whether $r\le c$ or $r>c$ |
| **Full-overwrite cap** | $c+\tilde y$ (only for $f=1$) | No cap when $f<1$ |

Numbers ($\sigma_{IV}=45\\%,\ \tau=1M,\ r_f=4\\%,\ c=5\\%\Rightarrow y=3.2945\\%$ and $\tilde y=3.3056\\%$, $f=1$): cap $=8.3056\\%$, $r^\*=8.3056\\%$, downside buffer $3.3056\\%$.

The absolute breakeven must be solved branch by branch. For $r\le c$, it is $r_0=-(d_T+f\tilde y)$, provided $-1\le r_0\le c$. For $r>c$ and $f<1$, it is
$$r_0=-\frac{fc+d_T+f\tilde y}{1-f},\qquad r_0>c.$$
For $f=1$ the assigned branch is the constant $c+d_T+\tilde y$, so it has no isolated breakeven unless that constant is exactly zero.

### 3.2 Relative to cash / relative to a put

- Let the simple cash return be $h_f=e^{r_f\tau}-1$. The covered call beats cash under the following branch conditions:
  - if $r\le c$: $r>h_f-d_T-f\tilde y$;
  - if $r>c$ and $f<1$: $r>(h_f-fc-d_T-f\tilde y)/(1-f)$;
  - if $r>c$ and $f=1$: $c+d_T+\tilde y>h_f$, independently of how far $r$ exceeds $c$.
- By §1.3, a full ($f=1$) overwrite vs. directly selling a put(K): identical expiry payoff; the only differences are **funding cost, dividend entitlement, early-exercise risk, and transaction costs** — not the payoff structure.

### 3.3 Comparing the two structures (general form of A vs B)

Let $A=(f_A,c_A)$, $B=(f_B,c_B)$, with $c_A>c_B$, $0\le f_B<f_A\le1$, and **premium-matched** $f_A\\,y(c_A)=f_B\\,y(c_B)$ (this is the convention Uday set). The premium terms cancel:

$$D(r)\equiv R_A-R_B=f_B\\,(r-c_B)^+-f_A\\,(r-c_A)^+\tag{3}$$

i.e. **a zero-cost ratio call spread: long $f_B$ units at $c_B$, short $f_A$ units at $c_A$**. Piecewise:

| Region | $D$ | Slope |
|---|---|---|
| $r\le c_B$ | 0 | 0 (**exactly flat**) |
| $c_B<r\le c_A$ | $f_B(r-c_B)$ | $+f_B$ |
| $r>c_A$ | $f_B(r-c_B)-f_A(r-c_A)$ | $-(f_A-f_B)$ |

Under $0\le f_B<f_A\le1$,
$$\text{max advantage of A}=f_B\\,(c_A-c_B)\quad\text{(at }r=c_A\text{)},\qquad\boxed{\\;r^{\*\*}=\frac{f_Ac_A-f_Bc_B}{f_A-f_B}\\;}\tag{4}$$

Setting $f_A=1,\ c_B=0$ recovers the earlier note's $r^{\*\*}=c/(1-f_B)$. **(Script check: $r^{\*\*}=13.06\\%$ both ways; $D(c_A)=f_Bc_A=3.09\\%$; $D(r^{\*\*})=0$)**

When $f_A>f_B$, (3) is net short calls above $c_A$ → **A's advantage is capped, B's advantage is uncapped** — the fatter the right tail, the more this favors B.

---

## 4. Expected return and alpha: the one rigorous decomposition

### 4.1 The exact identity

For a European call—or a call that is not exercised early and is held through expiry—take $\mathbb{P}$-expectations of (1) and use **premium = the risk-neutral discounted expiry payoff**:

$$y\\,e^{r_f\tau}=\mathbb{E}^{\mathbb{Q}}\big[(R-k)^+\big]$$

so the excess return relative to the underlier (overwrite ratio $f$, single period) is:

$$\boxed{\\;\alpha\\;\equiv\\;\mathbb{E}^{\mathbb{P}}[R_{cc}]-\mathbb{E}^{\mathbb{P}}[R_{stock}]\\;=\\;f\Big(\mathbb{E}^{\mathbb{Q}}\big[(R-k)^+\big]-\mathbb{E}^{\mathbb{P}}\big[(R-k)^+\big]\Big)\\;}\tag{5}$$

**Within that European/held-to-expiry setup, this is the entire arithmetic source of covered-call alpha:** the call's risk-neutral expected expiry payout minus its real-world expected expiry payout. American early exercise or an interim close/roll requires replacing the expiry payoff identity by the realized stopping/mark-to-market cash flows. When $\mathbb{E}^{\mathbb{Q}}=\mathbb{E}^{\mathbb{P}}$, $\alpha=0$. **(Script check: both sides of the identity = 0.196250%, MC = 0.196571%, MC s.e. = 0.003%)**

### 4.2 Rewritten as something estimable: the richness ratio $\rho$

Define the **richness ratio** of a given strike:

$$\rho(c)\\;\equiv\\;\frac{\mathbb{E}^{\mathbb{P}}\big[(R-k)^+\big]}{\mathbb{E}^{\mathbb{Q}}\big[(R-k)^+\big]}\\;=\\;\frac{\text{average real-world payout}}{\text{premium received (future value)}}$$

then (5) becomes, under the same European/no-early-exercise and held-to-expiry conditions,

$$\boxed{\\;\alpha=f\\,y\\,e^{r_f\tau}\big(1-\rho(c)\big)=\underbrace{Y\\,e^{r_f\tau}}_ {\text{premium received}}\times\big(1-\rho(c)\big)\\;}\tag{6}$$

Three implications:

1. **Alpha exists only when $\rho<1$**, and scales with premium size. $\rho$ is the *only* quantity that needs to be estimated, and it **can be estimated directly from the existing panel**: $\hat\rho(c)=\dfrac{\overline{\max(r-c,\\,0)}}{\overline{\texttt{Call Yield}\cdot e^{r_f\tau}}}$, bucketed by cap.
2. **A premium-matched pairwise comparison is, at its core, purely a comparison of $\rho$'s** (distribution-free, model-free): taking expectations of (3), $\mathbb{E}[D]=f_B\mathbb{E}^\mathbb{P}_B-f_A\mathbb{E}^\mathbb{P}_A$, combined with $f_A\mathbb{E}^\mathbb{Q}_A=f_B\mathbb{E}^\mathbb{Q}_B$:

$$\boxed{\\;A\succ B\iff \rho(c_A)<\rho(c_B)\\;}\tag{7}$$

   i.e. **“sell the strike with the lower payout-to-premium ratio”** within this expiry framework. Delta, volatility, and rally probabilities matter through the strike-specific $\rho$ rather than as separate sufficient ranking rules. **(Script verifies (7)'s direction against the sign of $\mathbb{E}[D]$ across 5 different real-world distributions — all PASS.)**
3. This is the quantitative version of the earlier note's "$\mathbb{E}[D]\approx0$, all edge comes from real ≠ implied distribution."

### 4.3 First-order decomposition: VRP harvest minus ERP giveback

In the **lognormal toy model**, $\mathbb{Q}$ and $\mathbb{P}$ are parameterized here only by drift ($r_f-q$ vs. $\mu-q$) and volatility ($\sigma_{IV}$ vs. $\sigma_{RV}$). Let $G(\sigma,m)=\mathbb{E}[(R-k)^+]$; (5) becomes $\alpha/f=G(\sigma_{IV},r_f-q)-G(\sigma_{RV},\mu-q)$. Expanding around a common $(\bar\sigma,\bar m)$ gives

$$\boxed{\\;\frac{\alpha}{f}\\;\approx\\;\underbrace{e^{\bar m\tau}\phi(\bar d_1)\sqrt{\tau}\,(\sigma_{IV}-\sigma_{RV})}_ {\text{VRP term}}\\;-\\;\underbrace{\tau e^{\bar m\tau}N(\bar d_1)(\mu-r_f)}_ {\text{ERP term}}\\;}\tag{8}$$

Thus the expectation sensitivities are $\mathcal V_G=e^{\bar m\tau}\phi(\bar d_1)\sqrt{\tau}$ and $\Delta_G=e^{\bar m\tau}N(\bar d_1)$; omitting the $e^{\bar m\tau}$ factor is only a near-zero-drift approximation. **(Script check: VRP term +0.551%, ERP term −0.348%, sum +0.203%, exact value +0.196%, relative error 3.2%.)**

**Corollary A — tenor: shorter-dated is more efficient.** Annualized, the VRP term $\propto\phi(d_1)(\sigma_{IV}-\sigma_{RV})/\sqrt{\tau}$ (rises as $\tau$ shrinks), while the ERP term $\propto\Delta(\mu-r_f)$ (roughly independent of $\tau$). Numbers: at the same IV, a 1M ATM premium of 5.34% compounds to a nominal 64.1% annualized if rolled 12x; a single 12M option only collects 19.5% ($\approx\sqrt{12}\times$ relationship). **But** transaction costs scale the same way ($1/\tau$), and gamma is nastier at the short end (§6) — the net effect has to be measured empirically.

**Corollary B — strike in this first-order lognormal comparison.** Let the inverse Mills ratio be $\lambda(d_1)=\phi(d_1)/N(d_1)$ (monotonically decreasing). $\mathcal{V}_G/\Delta_G=\lambda(d_1)\sqrt\tau$. Budgeting by “expected-payoff delta given up $=\delta^\*$” ($f=\delta^\*/\Delta_G$):

$$\alpha\approx\delta^\*\Big[\lambda(d_1)\sqrt{\tau}\\,(\sigma_{IV}-\sigma_{RV})-\tau(\mu-r_f)\Big]$$

The common $e^{\bar m\tau}$ factor cancels in this ratio. **Within the local lognormal expansion**, the ERP cost is locked in by that delta budget while the VRP term rises as the strike moves further OTM. This is not a distribution-free global optimum. Measured $\mathcal{V}_G/\Delta_G$:

| $c$ | −5% | 0% | +3% | +5% | +10% | +20% |
|---|---|---|---|---|---|---|
| $d_1$ | +0.485 | +0.091 | −0.137 | −0.285 | −0.643 | −1.313 |
| $\lambda(d_1)$ | 0.517 | 0.741 | 0.887 | 0.988 | 1.247 | 1.781 |
| vega/delta | 0.149 | 0.214 | 0.256 | 0.285 | 0.360 | 0.514 |
| $y(c)$ | 8.14% | 5.34% | 4.03% | 3.30% | 1.92% | 0.55% |

**Corollary C — testing the claim that "A structurally dominates B."** Premium-matched ($c_A=5\\%,f_A=1$ vs. ATM $f_B=0.617$):

| | delta sold | vega sold | vega/delta |
|---|---|---|---|
| A (full overwrite, 5% OTM) | 0.388 | 0.1106 | 0.285 |
| B (61.7% ATM) | 0.331 | 0.0708 | 0.214 |

A sells **both** more delta (1.17×) and more vega (1.56×) in this calibration, with 1.33× more vega per unit of delta. This explains why A wins in the current lognormal toy calibration; it is not a theorem implied by “flat IV + positive VRP.” The general premium-matched ranking remains (7). For example, with flat IV 45%, RV 40%, and annual drift $\mu=50\%$, the same toy setup gives annualized $A-B\approx-0.63\%$: high drift raises the OTM real-world payout enough for B to win even with positive VRP.

---

## 5. The design problem: optimizing over the $(f,c)$ plane

Using (6) as the objective, $\alpha(f,c)=f\\,y(c)\\,e^{r_f\tau}\big(1-\rho(c)\big)$. Three budget constraints give three different solutions:

| Constraint | Optimization problem | Result |
|---|---|---|
| **Premium budget** $f\\,y(c)=Y$ | $\alpha=Y e^{r_f\tau}(1-\rho(c))$ | **Degenerates to one dimension**: just pick the strike with the smallest $\rho(c)$; $f$ is backed out from $Y/y(c)$. **This is the rigorous definition of the sweet spot.** |
| **Delta budget** $f\Delta(c)=\delta^\*$ | $\max_c\ \dfrac{y(c)}{\Delta(c)}\big(1-\rho(c)\big)$ | In the baseline local-lognormal calibration it rises with OTM depth; generally the result depends on $\rho(c)$ and feasibility |
| **Unconstrained (arithmetic alpha)** | $\alpha$ is linear in $f$ | $\rho(c)<1\Rightarrow f=1$; a corner solution, no interior optimum |
| **Geometric / utility (§7)** | $\max\ \mu_{cc}-\tfrac12\sigma_{cc}^2$ | May have an interior optimum; depending on parameters it can also remain a boundary solution |

> **"The sweet spot is a range, not a point"** has a theoretical explanation here: on the iso-premium curve, the objective depends only on $\rho(c)$, and $\rho(c)$ is flat over a range of strikes (plus sample estimation noise) → a flat optimum. This is a structural feature of the problem, not dirty data.

**Iso-premium slice, measured** (target premium 3.295% = A's premium, $\sigma_{IV}$ flat at 45%, $\sigma_{RV}$=40%, $\mu$=15%, 1M):

| $c$ | $f$ | delta sold | vega sold | annualized alpha | annualized vol | annualized geometric edge |
|---|---|---|---|---|---|---|
| 0% (B) | 0.617 | 0.331 | 0.0708 | +0.50% | 26.92% | +4.80% |
| +2% | 0.743 | 0.353 | 0.0854 | +1.17% | 26.52% | +5.55% |
| +5% (A) | 1.000 | 0.388 | 0.1106 | +2.36% | 26.46% | +6.72% |
| +8% | 1.375 | — | — | infeasible ($f>1$; can't reach the premium target) | — | — |

**Conclusion for this calibration:** on a flat vol surface with IV 45%, RV 40%, and $\mu=15\%$, the optimum is “push the strike out until $f=1$ is fully used.” This is a numerical toy result, not a structural flat-vol theorem; a sufficiently high drift already reverses A/B without skew or non-lognormal tails.

### 5.1 Mechanisms that can reverse the baseline A win

**(a) Call skew — the primary driver, and the threshold is low.** Let $\sigma_{IV}(c)=\sigma_{ATM}-s\cdot c$:

| Skew slope $s$ | Vol pts lower per 5% OTM | $\alpha_{\text{ATM}}$ | $\alpha_{c=5\\%}$ | Winner |
|---|---|---|---|---|
| 0.0 | 0.0 | +0.50% | +2.35% | A |
| 0.2 | 1.0 | +0.50% | +1.03% | A |
| 0.4 | 2.0 | +0.50% | −0.30% | **B** |
| 0.6 | 3.0 | +0.50% | −1.62% | **B** |

> **Once the call wing's IV is only about 2 vol points below ATM (per 5% OTM), A's advantage is wiped out.** This is exactly the typical shape of the equity-options vol surface. **Skew is the first-order driver of the A/B contest.**

**(b) A fat right tail — moves the level, doesn't easily flip the ranking.** Using a "lognormal + earnings gap" mixture distribution (IV held flat at 45%):

| Real-world distribution | Annualized vol | Skew | Kurtosis | $\alpha_{\text{ATM}}$ | $\alpha_{c=5\\%}$ | Winner |
|---|---|---|---|---|---|---|
| Lognormal | 40.6% | +0.35 | 3.21 | +0.51% | +2.37% | A |
| 5% chance of a +25% gap | 37.8% | +0.92 | 5.10 | −0.49% | +2.03% | A |
| 8% chance of a +30% gap | 38.4% | +1.69 | 7.16 | −2.56% | −0.88% | A (both lose, A loses less) |
| 12% chance of a ±18% gap (symmetric) | 37.5% | +0.29 | 5.80 | +4.95% | +9.35% | A |
| 20% chance of a +35% gap | 51.1% | +1.56 | 3.92 | −25.8% | −37.7% | **B** |

> Three points:
> 1. In this particular calibrated mixture, the symmetric-gap case raises seller alpha. Symmetric excess kurtosis by itself has no universal sign for call-selling alpha: the result depends on how probability mass is redistributed relative to each strike and on how IV is held/calibrated.
> 2. A fatter right tail **simultaneously depresses alpha for both** (it lifts the whole $\rho(c)$ curve); only an extreme right tail (a 20%-of-months +35% gap, annualized vol spiking to 51%) flips the ranking.
> 3. So the intuition "NVDA's earnings gaps are fat → pick B" **points the right direction but isn't nearly enough magnitude**; what actually makes B win is **skew**, or a tail fat enough that $\rho(c_A)>\rho(c_B)$. **Phase 4/5 needs to test these two hypotheses separately, not conflate them.**

**Unified diagnostic (script §7)**: across five settings, the direction predicted by (7) matches the sign of the actual $\mathbb{E}[D]$ exactly —

| Real-world distribution / surface | $\rho(5\\%)$ | $\rho(\text{ATM})$ | (7) predicts | Actual $\mathbb{E}[D]\times12$ |
|---|---|---|---|---|
| Lognormal 40% | 0.9394 | 0.9867 | A | +1.88% ✓ |
| 5% × +25% gap | 0.9491 | 1.0124 | A | +2.51% ✓ |
| 8% × +30% gap | 1.0234 | 1.0660 | A | +1.69% ✓ |
| 20% × +35% gap | 1.9575 | 1.6556 | **B** | −11.98% ✓ |
| Lognormal + 3-vol call skew | 1.0458 | 0.9875 | **B** | −2.08% ✓ |

> $\rho$ is a **single scalar diagnostic** that compresses "how steep is the skew," "how fat is the right tail," and "how thick is the VRP" all into one number. **Phase 4 only needs to estimate this one curve, $\hat\rho(c)$.**

---

## 6. Greeks and the AQR three-way decomposition

At the portfolio level (per unit notional), with remaining maturity $u=T-t$ and continuous dividend yield $q$:

$$\Delta_{cc}=1-f\\,e^{-qu}N(d_1),\qquad \Gamma_{cc}=-f\\,\Gamma_{c}<0,\qquad \mathcal{V}_ {cc}=-f\\,\mathcal{V}_ {c}<0,\qquad \Theta_{cc}=-f\\,\Theta_c$$

Here $\Gamma_c=e^{-qu}\phi(d_1)/(S\sigma\sqrt u)$ and $\mathcal V_c/S=e^{-qu}\phi(d_1)\sqrt u$. The option-leg theta is positive only when the long call's theta is negative; with nonzero dividends/rates its sign is not universal.

For $f=1,c=5\\%$: $\Delta=0.612$, $\Gamma=-2.95$, $\mathcal{V}=-0.111$.

**The effective equity exposure moves automatically with price** — this is the key point:

$$\beta_\Delta(S)=1-f\\,e^{-qu}N\\!\big(d_1(K/S)\big),\qquad \frac{\partial\beta_\Delta}{\partial S}=-f\\,\Gamma_c<0$$

| $S/S_0$ | 0.85 | 0.95 | 1.00 | 1.05 | 1.15 |
|---|---|---|---|---|---|
| $\beta_\Delta$ | 0.938 | 0.752 | 0.612 | 0.464 | 0.214 |

> De-risking on rallies, re-risking on selloffs = **mechanical "sell into strength / buy into weakness" (short momentum / long reversal)**. This is exactly the Israelov–Nielsen "equity-timing" leg that carries ~25% of the risk with almost no compensation. It's a mechanical consequence of $\Gamma_{cc}<0$, not an execution flaw.
>
> **Warning for A↔B switching rules**: switching stacks another layer of active timing on top of this already-uncompensated timing exposure. If the rule can't genuinely predict the right tail, it's pure noise added on top.

Mapping the three-way decomposition onto this document: ① equity beta = the linear part of $(1-f)R+f\min(R,k)$ in (1c); ② short vol = the VRP term in (8); ③ equity timing = the $\beta_\Delta(S)$ drift caused by $\Gamma_{cc}<0$, which is not a separate term in the held-to-expiry arithmetic identity (5)/(8), though it affects the payoff distribution and multi-period outcomes.

---

## 7. Multi-period compounding and path dependence

### 7.1 Compounding with a rolling relative strike

Each period the strike resets to $K_t=(1+c)S_{t}$ with the overwrite ratio $f$ fixed, so each period's return is just a function $g(r_t)$ of that period's $r_t$ (given by (1b)), and the index is

$$I_N=I_0\prod_{t=1}^{N}\big(1+g(r_t)\big),\qquad g(r)=(1-f)r+f\min(r,c)+f\tilde y_t$$

**Path order doesn't matter, but the outcome is extremely sensitive to how dispersed $\\{r_t\\}$ is** (because $g$ is concave). For the same two-period cumulative underlier return of +21%:

| Monthly path | Underlier cumulative | Covered call cumulative | Gap |
|---|---|---|---|
| (+10%, +10%) | +21.00% | +17.28% | −3.72% |
| (+21%, 0%) | +21.00% | +11.86% | −9.14% |
| (+33%, −9.0%) | +21.00% | +2.09% | −18.91% |
| (+50%, −19.3%) | +21.00% | −9.07% | −30.08% |

> This is a clean demonstration of how **rolling/resetting turns single-period short-gamma concavity into multi-period path dependence**: for the examples shown, the same underlier endpoint with more dispersed monthly returns hurts the covered call. Short gamma is already present in each single-period payoff; compounding makes its sequence-level consequence visible.

### 7.2 Variance drag: the second (often overlooked) source of edge

Second-order expansion uses $\mathbb{E}[\ln(1+x)]\approx\mu_x-\tfrac12\mathbb{E}[x^2]=\mu_x-\tfrac12(\sigma_x^2+\mu_x^2)$:

$$\underbrace{G_{cc}-G_{stock}}_ {\text{geometric excess}}\\;\approx\\;\underbrace{\alpha}_ {\text{arithmetic alpha, (6)}}\\;+\\;\underbrace{\tfrac12\big(\sigma_{stock}^2-\sigma_{cc}^2\big)}_ {\text{variance-drag saving}}\\;+\\;\underbrace{\tfrac12\big(\mu_{stock}^2-\mu_{cc}^2\big)}_ {\text{mean-square correction}}\tag{9}$$

Measured ($f=1,c=5\\%,\sigma_{RV}=40\\%,\mu=15\\%$):

| | Annualized arithmetic | Annualized vol | $\mathbb{E}[\ln(1+x)]\times12$ |
|---|---|---|---|
| Underlier | +15.08% | 40.0% | **+6.98%** |
| Covered call (IV=45%) | +17.44% | 26.5% | **+13.71%** |

The second-order approximation gives alpha +2.36% + variance-drag saving +4.76% + mean-square correction about −0.03% = **+7.09%**; the directly computed geometric excess is **+6.72%**, leaving about −0.37% of higher-order residual.

**VRP sensitivity (RV fixed at 40%):**

| $\sigma_{IV}$ | Annualized alpha | Drag saving | Geometric excess |
|---|---|---|---|
| 35% | −10.74% | +4.76% | −6.33% |
| 40% (zero VRP) | −4.25% | +4.76% | **+0.15%** |
| 45% | +2.36% | +4.76% | +6.72% |
| 50% | +9.05% | +4.76% | +13.35% |

**At zero VRP ($\sigma_{IV}=\sigma_{RV}$), is the geometric excess positive or negative?** By (9), it is approximately the variance-drag saving minus ERP giveback plus the mean-square correction. The drag saving grows with $\sigma^2$, while ERP giveback grows roughly linearly with $\mu$; the correction and higher-order terms prevent a universal sign. $f=1,c=5\\%$, measured annualized:

| $\sigma_{RV}$ \\ $\mu$ | 5% | 10% | 15% | 25% |
|---|---|---|---|---|
| **25%** | +1.01% | −0.37% | −1.83% | −5.09% |
| **40%** | +3.71% | +1.99% | +0.19% | −3.72% |
| **60%** | +10.14% | +7.95% | +5.96% | +1.77% |

> **Three things to remember:**
> 1. The earlier claim that "geometric excess ≈ 0 at zero VRP" was just a coincidence of the $\sigma=40\\%,\mu=15\\%$ cell landing near zero — **not a general rule**. The real pattern is: **higher volatility and lower drift make it easier for the variance-drag saving to overcome the ERP giveback**; low vol + high drift always loses at zero VRP (−5.1%).
> 2. **NVDA happens to be "high volatility + high drift,"** landing right on the diagonal boundary in this table where the outcome is genuinely contested — which is exactly why the A/B/buy-hold ranking for NVDA has to be settled empirically; the formula alone can't sign it. **Switch to a low-volatility name (e.g. MSFT/AAPL) and the "zero VRP can still win" conclusion in the upper-left of the table reverses** — this is one theoretical source of the cross-sectional differences across the Mag7.
> 3. The table above is computed entirely under a **lognormal** assumption. A fatter real-world right tail → $\mathbb{E}^\mathbb{P}[(R-k)^+]$ is larger → both alpha and geometric excess shrink together (§5.1b: with an 8%-probability +30% gap, $\alpha_{c=5\\%}$ drops from +2.37% to −0.88%). **The Gaussian approximation in (9) is unreliable under heavy truncation + strong skewness — always compute the sample $\overline{\ln(1+g)}$ directly, don't rely on $\mu-\sigma^2/2$.**

### 7.3 Skewness and Sharpe distortion

$f=1,c=5\\%$: $\text{skew}(R_{cc})=-0.99$ vs. $\text{skew}(R_{stock})=+0.35$. Annualized vol 26.5% vs. 40.0%.

> Selling strategies cut off the right tail while keeping the left tail → skewness flips from positive to negative. Sharpe only looks at the first two moments and will **systematically overstate** this class of strategy. The primary metrics should be Calmar / Sortino / month-by-month win rate + max drawdown; Sharpe is reference only (this maps onto the earlier note's §5.3).

### 7.4 Term structure: rolling N short-dated options ≠ one long-dated option

$y_{ATM}(\tau)\approx0.4\\,\sigma\sqrt{\tau}$, so the annualized premium collected by rolling $\approx\sqrt{N}\times$ the premium of a single $N$-period option:

| Tenor | ATM premium | Annualized (by roll count) |
|---|---|---|
| 1M | 5.34% | 64.1% |
| 3M | 9.42% | 37.7% |
| 12M | 19.48% | 19.5% |

Under $\mathbb{Q}$, this extra collected premium is exactly offset by "being capped repeatedly" (no-arbitrage). The difference only shows up under $\mathbb{P}$: short-dated VRP is richer (Corollary A) but gamma cost, transaction costs, and path dependence are also heavier.

---

## 8. Index implementation (daily mark-to-market)

At inception $t_0$: $n=I_{t_0}/S_{t_0}$ shares, short $f\\,n$ calls, cash $=f\\,n\\,C_{t_0}$. For any $t\in(t_0,T]$:

$$\frac{I_t}{I_{t_0}}=\frac{S_t}{S_{t_0}}-f\cdot\frac{C_t-C_{t_0}e^{r_f(t-t_0)}}{S_{t_0}}+\frac{D_{t_0\to t}}{S_{t_0}}\tag{10}$$

where $C_t$ is the **option's daily mark** (includes time value pre-expiry). At expiry, $C_T=(S_T-K)^+$ and (10) collapses exactly to (1). **(Script check: at $f=1$ and $f=0.4$, $|(10)@T-(1)|_ {\max}=1.1\times10^{-16}$.)**

Three implementation notes:

1. **The daily path ≠ the expiry path.** (10) implies the daily-frequency index will first reflect the decay/inflation of time value. If the underlier spikes mid-month and pulls back by month-end, the index will dip intra-month first (option MTM loss) before recovering — drawdown stats will look worse at daily frequency than at monthly. State clearly which frequency any drawdown/vol statistic uses.
2. **At inception, equity value = base is correct** (covered call = full position in the underlier + selling calls against part of it); the premium goes into a cash account. This maps onto the earlier note's §9.
3. **`Cap`/`Call Yield` are properties of "that specific option," not of the portfolio.** They're identical across Exposure tranches and different across Income tranches. To distinguish different $f$'s, look only at `Index Return`.

---

## 9. Real-world frictions (downgrading (5) from "alpha exists" to "net alpha")

$$\alpha_{\text{net}}=\underbrace{f\\,y\\,e^{r_f\tau}(1-\rho)}_ {(6)}-\underbrace{\frac{f\cdot\text{spread}/2}{\tau}\Big|_ {\text{annualized}}}_ {\text{bid-ask spread}}-\text{assignment/settlement costs}-\text{taxes}-\text{discrete-strike slippage}$$

| Friction | Mechanism | Magnitude / handling |
|---|---|---|
| **Bid-ask spread** | Half the spread paid on every roll, scaled up by $1/\tau$ annualized | 12 rolls/year at monthly tenor; a half-point spread of 0.5% of premium eats a meaningful fraction. This **directly offsets Corollary A (shorter-dated is better)** |
| **Listed-strike discreteness** | Only integer listed strikes available → the actual $c$ jitters (earlier note: strike% jitters 94–109%) | Makes target-yield back-solving inexact; when the theoretical $c^\*$ falls between two listed strikes, interpolate or round to the nearest |
| **American early exercise** | Exercise is an optimal-stopping decision, concentrated just before ex-dividend dates for calls | Compare immediate exercise $S-K$ with the call's continuation value using the actual discrete dividend, financing benefit on $K$, borrow constraints, and remaining optionality. “Dividend exceeds remaining time value” is only a rule of thumb, not the general criterion. NVDA's tiny dividend makes the European approximation plausible, but it still should be checked against actual contract/date inputs |
| **Target-yield endogeneity trap** | To hit the target, low-vol periods force the strike near ATM (tight $c$); high-vol periods allow it far away (loose $c$) → $c$ positively correlated with IV | Follows locally from the option-price relation: fixing $Y$ generally makes $c$ move with $\sigma$. **A low-vol bull market can be unfavorable because the cap tightens while the stock rises; the severity depends on the realized return path. Fixed-delta selection reduces this target-yield channel** |
| **Taxes** | Premium and assigned capital gains are mostly short-term | An after-tax lens can significantly shift the A/B ranking (A is assigned more often) |
| **Cash drag** | Premium sits at the short end; a benefit when $r_f$ is high, a drag when low | Already captured in (1)'s $e^{r_f\tau}$ |
| **Crowding** | Rising seller AUM compresses VRP → $\rho\uparrow$ | A slow-moving variable, used to judge "is this strategy still worth doing at all" (earlier note's §4 on NVDY) |

---

## 10. Appendix: lognormal closed forms (all cross-checked against MC)

Let $R=\exp\big((m-\tfrac12\sigma^2)\tau+\sigma\sqrt{\tau}Z\big)$, $Z\sim N(0,1)$, where $m$ = total drift of $R$ under that measure ($\mathbb{Q}$: $m=r_f-q$; $\mathbb{P}$: $m=\mu-q$);

$$d_1=\frac{-\ln k+(m+\tfrac12\sigma^2)\tau}{\sigma\sqrt{\tau}},\qquad d_2=d_1-\sigma\sqrt{\tau}$$

| Quantity | Closed form | MC check |
|---|---|---|
| $\mathbb{E}[(R-k)^+]$ | $e^{m\tau}N(d_1)-k\\,N(d_2)$ | 0.031093 / 0.031090 ✓ |
| Premium $y$ | $e^{-q\tau}N(d_1^{\mathbb{Q}})-k\\,e^{-r_f\tau}N(d_2^{\mathbb{Q}})$ (BS, using $\sigma_{IV}$) | — |
| Assignment probability $\mathbb{P}(R>k)$ | $N(d_2)$ | 0.354940 / 0.354758 ✓ |
| $\mathbb{E}[R\\,\mathbf{1}_ {R\le k}]$ | $e^{m\tau}N(-d_1)$ | 0.608798 / 0.608979 ✓ |
| $\mathbb{E}[R^2\mathbf{1}_ {R\le k}]$ | $e^{(2m+\sigma^2)\tau}N(-d_2-2\sigma\sqrt{\tau})$ | 0.577826 / 0.578009 ✓ |
| $\mathbb{E}[\min(R,k)]$ | $e^{m\tau}-\mathbb{E}[(R-k)^+]$ | 0.981485 / 0.981476 ✓ |
| $\mathbb{E}[\min(R,k)^2]$ | $e^{(2m+\sigma^2)\tau}N(-d_2-2\sigma\sqrt{\tau})+k^2N(d_2)$ | 0.969148 / 0.969130 ✓ |
| $\mathbb{E}[R\min(R,k)]$ | $e^{(2m+\sigma^2)\tau}N(-d_2-2\sigma\sqrt{\tau})+k\\,e^{m\tau}N(d_1)$ | ✓ |

**Portfolio variance** (from (1c); the constant term doesn't affect variance):

$$\mathrm{Var}(R_{cc})=(1-f)^2\mathrm{Var}(R)+f^2\mathrm{Var}\big(\min(R,k)\big)+2f(1-f)\mathrm{Cov}\big(R,\min(R,k)\big)$$

**(Check: $f=1$ closed form 0.005834 / MC 0.005836; $f=0.5$ closed form 0.008881 / MC 0.008884.)**

This lets you plot the **mean-variance frontier** on the $(f,c)$ plane analytically without backtesting, to locate the feasible region — then swap in the historical $\hat\rho(c)$ for the model $\rho(c)$ to get the empirical frontier.

---

## 11. One-page summary: what this theory says

1. **The single-period return is a single formula**: $R_{cc}=(1-f)r+f\min(r,c)+f\tilde y+d_T$. The OTM/ATM/ITM × full/partial six cases are all special cases of it (§2), as is any admissible multi-tranche ladder (§2.3). Pricing uses annualized $q$; realized payoff uses $d_T$.
2. **Covered-call writing = equity beta + a cash-secured short put** (§1.3). It is not an independent risk source; $(f,c)$ is simply "how big and how far OTM a put to sell."
3. **The break-even point relative to the underlier, $r^\*=c+\tilde y$, is independent of $f$**; $f$ only sets the slope of the win/loss (§3.1).
4. **For European/no-early-exercise calls held to expiry, arithmetic alpha $=Y e^{r_f\tau}(1-\rho(c))$**, where $\rho(c)=$ real-world average expiry payout / premium (§4.2). Within that framework, the key object to estimate is $\rho$, directly from the panel by cap bucket.
5. **A premium-matched comparison reduces to a pure comparison of $\rho$'s**: $A\succ B\iff\rho(c_A)<\rho(c_B)$ (eq. 7, distribution-free).
6. **A vs. B is always a $\rho$ ranking in the held-to-expiry framework.** A wins in the baseline flat-IV lognormal calibration, but flat IV + positive VRP is not sufficient: at IV 45%, RV 40%, and $\mu=50\%$, the toy gives annualized $A-B\approx-0.63\%$. Skew, right-tail shape, and high drift are all mechanisms that can make B win.
7. **The sweet spot degenerates to a one-dimensional problem on the iso-premium curve** (pick $\min\rho(c)$), and because $\rho$ is flat plus estimation noise, it is naturally a **range, not a point** (§5).
8. **Compounding adds a potential geometric benefit**: variance-drag saving, together with the mean-square correction in (9) (§7.2). Whether it overcomes ERP giveback at zero VRP depends on the vol/drift ratio—high vol + low drift can win on this approximation; high drift + low vol tends to lose. NVDA (high vol + high drift) sits in a contested region that must be measured empirically.
9. **$\Gamma_{cc}<0$ forces "de-risk on rallies, re-risk on selloffs"** (§6), which is exactly AQR's uncompensated timing leg. An A↔B switching rule stacks another layer of timing on top of it — the burden of proof is on the rule.
10. **Short-dated VRP is richer, but frictions scale up the same way** ($1/\tau$) (§4.3 Corollary A + §9); the net effect can only be measured.

---

## To do: connecting the theory back to the data

| # | Task | Formula used |
|---|---|---|
| 1 | Estimate $\hat\rho(c)$ bucketed by cap (monthly $\max(r-c,0)$ against `Call Yield`); plot $\hat\rho$ vs. $c$ | (6)(7) |
| 2 | Use $\hat\rho$ to directly predict A/B wins and compare against the actual monthly $D$ — this is the empirical test of eq. (7) | (7) |
| 3 | Back out monthly $\sigma_{IV}(c)$ and $\sigma_{IV}(0)$ from `Cap`+`Call Yield`, estimate the skew slope $s$, check whether it exceeds the ~0.4 threshold from §5.1 | §5.1a |
| 4 | Estimate NVDA's monthly return skewness/kurtosis and compare against the four scenarios in §5.1b to judge whether the right tail is "extreme enough" | §5.1b |
| 5 | Plot the $(f,c)$ mean-variance frontier analytically and overlay historical realized points | §10 |
| 6 | Check the correlation between the target-yield-implied $c$ and an IV proxy (direct evidence of the endogeneity trap) | §9 |

## Sources

- Israelov & Nielsen, *Covered Calls Uncovered* (AQR) — three-way exposure decomposition, the timing leg is uncompensated: [PDF](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Covered-Calls-Uncovered.pdf) · [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2444999)
- [Cboe BuyWrite Indices Methodology (PDF)](https://cdn.cboe.com/api/global/us_indices/governance/Cboe_BuyWrite_Indices_Methodology.pdf) — BXM/BXY rolling and pricing rules
- Local: `theory/00_theory_notes_zh.md` (priors and experiment design) · `theory/00_theory_verify.py` (executable checks for the core identities and quoted toy numbers). The 2026-07-08 stakeholder discussion establishing the premium-matching convention is not stored in this repository.
