# Stylized scenario: premium-matched A vs B (full calculation)

> Not Mag7 / NVDA data. This is the fixed Black–Scholes toy used in `theory/00_theory_verify.py` to check eqs. (3)–(4) of `00_theory_derivation_en.md`.  
> Flat vol surface, European calls, $S_0=1$ (all prices as fractions of spot).

---

## 0. Assumptions

| Object | Value | Meaning |
|---|---|---|
| $\sigma_{IV}$ | $45\%$ | flat implied vol (same for every strike) |
| $\tau$ | $1/12$ | one-month tenor |
| $r_f$ | $4\%$ | continuous risk-free rate |
| $q$ | $0$ | dividend yield |
| Structure A | $f_A=1$, $c_A=5\%$ | full overwrite, $5\%$ OTM ($k_A=1.05$) |
| Structure B | $c_B=0$ (ATM, $k_B=1$), $f_B$ TBD | partial ATM, **premium-matched** to A |

Premium-matching (desk convention): choose $f_B$ so that

$$f_A\,y(c_A)=f_B\,y(c_B)
\quad\Longrightarrow\quad
f_B=\frac{y(c_A)}{y(0)}\qquad(f_A=1).$$

Everything below uses only these inputs.

---

## 1. Black–Scholes call yield

With $S_0=1$,

$$
y(k)=e^{-q\tau}N(d_1)-k\,e^{-r_f\tau}N(d_2),
\qquad
d_1=\frac{-\ln k+(r_f-q+\tfrac12\sigma_{IV}^2)\tau}{\sigma_{IV}\sqrt{\tau}},
\qquad
d_2=d_1-\sigma_{IV}\sqrt{\tau}.
$$

Common factor:

$$\sigma_{IV}\sqrt{\tau}=0.45\cdot\sqrt{1/12}=0.129904,\qquad
e^{-r_f\tau}=e^{-0.04/12}=0.996672.$$

### 1.1 Strike A: $k_A=1.05$

$$
d_1^A=\frac{-\ln 1.05+(0.04+\tfrac12\cdot0.45^2)/12}{0.129904}=-0.284975,
\qquad
d_2^A=-0.414879.
$$

$$
N(d_1^A)=0.387832,\qquad N(d_2^A)=0.339115.
$$

$$
y(c_A)=N(d_1^A)-1.05\cdot e^{-r_f\tau}\,N(d_2^A)
=0.387832-1.05\cdot0.996672\cdot0.339115
=\mathbf{3.294550\%}.
$$

### 1.2 Strike B: $k_B=1$ (ATM)

$$
d_1^B=\frac{(0.04+\tfrac12\cdot0.45^2)/12}{0.129904}=+0.090612,
\qquad
d_2^B=-0.039292.
$$

$$
N(d_1^B)=0.536100,\qquad N(d_2^B)=0.484329.
$$

$$
y(0)=N(d_1^B)-e^{-r_f\tau}\,N(d_2^B)
=0.536100-0.996672\cdot0.484329
=\mathbf{5.338243\%}.
$$

---

## 2. Premium-matched overwrite for B

$$
f_B=\frac{y(c_A)}{y(0)}=\frac{3.294550\%}{5.338243\%}=\mathbf{0.617160}.
$$

So the matched pair is

$$
A=(f_A,c_A)=(1,\ 5\%),\qquad
B=(f_B,c_B)=(0.617,\ 0).
$$

(Interest factor $e^{r_f\tau}$ is common and cancels under matching; for the pathwise $D(r)$ below we only need $f$ and $c$.)

---

## 3. Pathwise difference $D(r)$

From the derivation note, under premium matching,

$$D(r)=R_A-R_B=f_B\,(r-c_B)^+-f_A\,(r-c_A)^+
=0.617160\,(r)^+-1\cdot(r-0.05)^+.\tag{3}$$

### 3.1 Peak of A's advantage

Slope of $D$: $+f_B$ on $(0,c_A]$, then $-(f_A-f_B)<0$ for $r>c_A$. Maximum at the kink $r=c_A$:

$$
D(c_A)=f_B(c_A-c_B)=0.617160\cdot5\%=\mathbf{3.0858\%}\approx 3.09\%.\tag{4a}
$$

### 3.2 Second breakeven $r^{**}$

For $r>c_A$, set $D(r)=0$:

$$
f_B(r-c_B)-f_A(r-c_A)=0
\;\Longrightarrow\;
r^{**}=\frac{f_Ac_A-f_Bc_B}{f_A-f_B}.
$$

With $f_A=1$, $c_B=0$:

$$
r^{**}=\frac{c_A}{1-f_B}=\frac{0.05}{1-0.617160}=\mathbf{13.0603\%}\approx 13.06\%.\tag{4}
$$

Check both formulas agree:

$$
\frac{f_Ac_A-f_Bc_B}{f_A-f_B}
=\frac{1\cdot0.05-0.617160\cdot0}{1-0.617160}
=\frac{0.05}{0.382840}=13.0603\%.
$$

And $D(r^{**})=0$ by construction.

---

## 4. Spot-check grid

Evaluate $D(r)=f_B(r)^+-(r-0.05)^+$ at selected $r$:

| $r$ | Region | $D(r)$ | Comment |
|---|---|---|---|
| $-20\%$ | $r\le c_B$ | $0$ | identical |
| $-1\%$ | $r\le c_B$ | $0$ | identical |
| $0$ | kink at $c_B$ | $0$ | identical |
| $+3\%$ | $c_B<r\le c_A$ | $+1.85\%$ | A ahead, slope $+f_B$ |
| $+5\%$ ($=c_A$) | peak | $+3.09\%$ | max advantage of A |
| $+8\%$ | $c_A<r<r^{**}$ | $+1.94\%$ | B catching up |
| $+13.06\%$ ($=r^{**}$) | second zero | $0$ | cross again |
| $+30\%$ | $r>r^{**}$ | $-6.49\%$ | B wins; advantage uncapped |

---

## 5. One-line summary

Under this toy (flat $45\%$ IV, 1M, $r_f=4\%$, no dividend):

1. Price the two yields with BS → $y(5\%)=3.295\%$, $y(\mathrm{ATM})=5.338\%$.
2. Match premiums → $f_B=0.617$.
3. Peak gap → $D(5\%)=f_B\cdot5\%=3.09\%$.
4. Second zero → $r^{**}=5\%/(1-f_B)=13.06\%$.

Re-run anytime with:

```bash
.venv/bin/python theory/00_theory_verify.py
```

(section “2. breakpoints” prints the same numbers).
