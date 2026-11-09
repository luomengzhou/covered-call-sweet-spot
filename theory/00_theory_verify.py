"""Numerical checks for core formulas in the en/zh derivation documents.

Run:  .venv/bin/python theory/00_theory_verify.py
Checked identities print PASS/FAIL plus the quoted toy-model numbers.
"""
from __future__ import annotations
import numpy as np
from scipy.stats import norm

rng = np.random.default_rng(7)
N = 4_000_000
FAILURES = 0


def OK(value):
    global FAILURES
    if not bool(value):
        FAILURES += 1
        return "**FAIL**"
    return "PASS"


# ---------- BS building blocks (S0 = 1, so K = k, price quoted per spot) ----------
def d12(k, sig, tau, m):
    """m = total drift of R = S_T/S_0 under the measure (E[R] = e^{m tau})."""
    s = sig * np.sqrt(tau)
    d1 = (-np.log(k) + (m + 0.5 * sig**2) * tau) / s
    return d1, d1 - s


def exp_intrinsic(k, sig, tau, m):
    """E[(R-k)^+] under lognormal with drift m, vol sig."""
    d1, d2 = d12(k, sig, tau, m)
    return np.exp(m * tau) * norm.cdf(d1) - k * norm.cdf(d2)


def call_yield(k, sig, tau, rf, q_annual):
    """BS call price / spot = e^{-rf tau} E^Q[(R-k)^+]."""
    return np.exp(-rf * tau) * exp_intrinsic(k, sig, tau, rf - q_annual)


def bs_delta(k, sig, tau, rf, q_annual):
    d1, _ = d12(k, sig, tau, rf - q_annual)
    return np.exp(-q_annual * tau) * norm.cdf(d1)


def bs_vega(k, sig, tau, rf, q_annual):
    d1, _ = d12(k, sig, tau, rf - q_annual)
    return np.exp(-q_annual * tau) * norm.pdf(d1) * np.sqrt(tau)


# ---------- scenario ----------
sig_iv, sig_rv = 0.45, 0.40          # IV > RV : positive VRP
tau, rf, q_annual = 1 / 12, 0.04, 0.0
mu_price = 0.15                      # annual physical drift of the ex-dividend price
d_T = 0.0                            # single-period cash dividend / S_0 (not q_annual*tau)
c, f = 0.05, 1.0                     # cap 5% OTM, full overwrite
k = 1 + c
y = call_yield(k, sig_iv, tau, rf, q_annual)
y_tilde = y * np.exp(rf * tau)

print(f"scenario: sig_IV={sig_iv} sig_RV={sig_rv} tau=1M rf={rf} "
      f"q_annual={q_annual} mu_price={mu_price} d_T={d_T} c={c:.2%}")
print(f"          ATM call yield y(0)={call_yield(1,sig_iv,tau,rf,q_annual):.4%}  y(c)={y:.4%}\n")


# ================================================================ 1. master formula
print("--- 1. master formula  R_cc = (1-f)r + f*min(r,c) + f*y*exp(rf*tau) + d_T ---")
R = np.exp((mu_price - 0.5 * sig_rv**2) * tau + sig_rv * np.sqrt(tau) * rng.standard_normal(N))
r = R - 1
for ff in (1.0, 0.6, 0.3):
    direct = r + d_T + ff * y * np.exp(rf * tau) - ff * np.maximum(R - k, 0)
    master = (1 - ff) * r + ff * np.minimum(r, c) + ff * y * np.exp(rf * tau) + d_T
    print(f"  f={ff}: max|direct-master| = {np.abs(direct-master).max():.2e}  {OK(np.allclose(direct,master))}")

# Non-zero dividend convention: q_annual prices the option; d_T is the realised
# single-period cash dividend added to both stock and covered-call returns.
q_test, d_test = 0.027, 0.011
y_test = call_yield(k, sig_iv, tau, rf, q_test)
direct_test = r + d_test + f * y_test * np.exp(rf * tau) - f * np.maximum(R - k, 0)
master_test = (1 - f) * r + f * np.minimum(r, c) + f * y_test * np.exp(rf * tau) + d_test
dividend_ok = np.allclose(direct_test, master_test) and np.allclose(
    direct_test - (r + d_test), master_test - (r + d_test)
)
print(f"  nonzero dividend convention: q_annual={q_test:.2%}, d_T={d_test:.2%}, "
      f"max diff={np.max(np.abs(direct_test-master_test)):.2e}  {OK(dividend_ok)}")

# MerQube attribution identity (rf=q_annual=d_T=0 convention)
merqube = r - f * np.maximum(r - (k - 1), 0) + f * y
mine = (1 - f) * r + f * np.minimum(r, c) + f * y
print(f"  MerQube attribution identity: max diff = {np.abs(merqube-mine).max():.2e}  {OK(np.allclose(merqube,mine))}\n")


# ================================================================ 2. breakpoints
print("--- 2. breakpoints ---")
print(f"  cap (f=1)       = c + y_tilde      = {c + y_tilde:.4%}")
print(f"  crossover vs stock r* = c + y_tilde= {c + y_tilde:.4%}  (f-independent)")
print(f"  downside cushion (f=1, d_T=0)      = {y_tilde:.4%}")

# A(f=1, cap cA) vs B(f_B, cap cB) premium matched
cA, cB = 0.05, 0.0
yA, yB = call_yield(1 + cA, sig_iv, tau, rf, q_annual), call_yield(1 + cB, sig_iv, tau, rf, q_annual)
fB = yA / yB
r_star = (1 * cA - fB * cB) / (1 - fB)
print(f"  A(f=1,c={cA:.0%}) vs B(ATM, f={fB:.4f}) premium-matched:")
print(f"    r* = (fA*cA - fB*cB)/(fA-fB) = {r_star:.4%}   vs  c/(1-f) = {cA/(1-fB):.4%}  {OK(abs(r_star-cA/(1-fB))<1e-12)}")
rg = np.array([-0.20, -0.01, 0.0, 0.03, cA, 0.08, r_star, 0.30])
RA = np.minimum(rg, cA) + yA * np.exp(rf * tau)
RB = ((1 - fB) * rg + fB * np.minimum(rg, cB)
      + fB * yB * np.exp(rf * tau))
D = RA - RB
print("    r      :", "  ".join(f"{x:+7.2%}" for x in rg))
print("    D=A-B  :", "  ".join(f"{x:+7.2%}" for x in D))
print(f"    D(r=cA) = fB*(cA-cB) = {fB*(cA-cB):.4%} {OK(abs(D[4]-fB*(cA-cB))<1e-12)};  D(r*) = 0 {OK(abs(D[6])<1e-12)}\n")


# ================================================================ 3. alpha identity
print("--- 3. alpha = f*(E^Q[(R-k)^+] - E^P[(R-k)^+]) ---")
EQ = exp_intrinsic(k, sig_iv, tau, rf - q_annual)
EP = exp_intrinsic(k, sig_rv, tau, mu_price)
alpha_exact = f * (EQ - EP)
E_stock = np.exp(mu_price * tau) - 1 + d_T
E_cc = E_stock + f * y * np.exp(rf * tau) - f * EP
print(f"  E^Q = {EQ:.6f}   E^P = {EP:.6f}")
print(f"  alpha (identity)      = {alpha_exact:.6%}")
print(f"  E[R_cc] - E[R_stock]  = {E_cc-E_stock:.6%}   {OK(abs(alpha_exact-(E_cc-E_stock))<1e-12)}")
mc = (f * y * np.exp(rf * tau) - f * np.maximum(R - k, 0)).mean()
mc_se = (f * np.maximum(R-k, 0)).std() / np.sqrt(N)
print(f"  Monte-Carlo           = {mc:.6%}  (MC se ~ {mc_se:.6%})  "
      f"{OK(abs(mc-alpha_exact) < 5*mc_se)}\n")

# first-order decomposition
print("--- 3b. first-order with full Q growth factor ---")
sig_mid = 0.5 * (sig_iv + sig_rv)
drift_gap = mu_price - (rf - q_annual)
vrp_term = np.exp(rf * tau) * bs_vega(k, sig_mid, tau, rf, q_annual) * (sig_iv - sig_rv)
erp_term = tau * np.exp(rf * tau) * bs_delta(k, sig_mid, tau, rf, q_annual) * drift_gap
d1_mid, _ = d12(k, sig_mid, tau, rf - q_annual)
q_growth = np.exp((rf - q_annual) * tau)
vrp_full = q_growth * norm.pdf(d1_mid) * np.sqrt(tau) * (sig_iv - sig_rv)
erp_full = q_growth * norm.cdf(d1_mid) * tau * drift_gap
print(f"  VRP term  = vega*(IV-RV)      = {vrp_term:+.4%}")
print(f"  drift term= tau*delta*gap     = {erp_term:+.4%}")
print(f"  full factor exp((rf-q_annual)tau)={q_growth:.8f}: "
      f"raw sum={vrp_full-erp_full:+.4%}, Greeks sum={vrp_term-erp_term:+.4%}  "
      f"{OK(abs(vrp_full-vrp_term)<1e-14 and abs(erp_full-erp_term)<1e-14)}")
print(f"  sum       = {vrp_term-erp_term:+.4%}   exact = {alpha_exact:+.4%}   rel.err = {abs((vrp_term-erp_term)/alpha_exact-1):.1%}")

lam = lambda d1: norm.pdf(d1) / norm.cdf(d1)
print("\n--- 3c. inverse-Mills lambda(d1)=phi/N is decreasing => deeper OTM more vega per delta ---")
for cc in (-0.05, 0.0, 0.03, 0.05, 0.10, 0.20):
    kk = 1 + cc
    d1, _ = d12(kk, sig_iv, tau, rf - q_annual)
    v, dl = bs_vega(kk, sig_iv, tau, rf, q_annual), bs_delta(kk, sig_iv, tau, rf, q_annual)
    print(f"  c={cc:+.0%}: d1={d1:+.3f} lambda={lam(d1):.3f}  vega/delta={v/dl:.4f}  "
          f"lambda*sqrt(tau)={lam(d1)*np.sqrt(tau):.4f}  y={call_yield(kk,sig_iv,tau,rf,q_annual):.3%}")

print("\n--- 3d. premium-matched A vs B: risk exposures ---")
dA, vA = bs_delta(1 + cA, sig_iv, tau, rf, q_annual), bs_vega(1 + cA, sig_iv, tau, rf, q_annual)
dB, vB = bs_delta(1 + cB, sig_iv, tau, rf, q_annual), bs_vega(1 + cB, sig_iv, tau, rf, q_annual)
print(f"  A: f=1     short delta={1*dA:.4f}  short vega={1*vA:.4f}  vega/delta={vA/dA:.4f}")
print(f"  B: f={fB:.4f} short delta={fB*dB:.4f}  short vega={fB*vB:.4f}  vega/delta={vB/dB:.4f}")
print(f"  => A sells MORE delta ({1*dA/(fB*dB):.2f}x) and MORE vega ({1*vA/(fB*vB):.2f}x), "
      f"and is {(vA/dA)/(vB/dB):.2f}x more vega-efficient per unit delta")
# E^Q[D] = 0 check
DQ = fB * exp_intrinsic(1 + cB, sig_iv, tau, rf - q_annual) - exp_intrinsic(1 + cA, sig_iv, tau, rf - q_annual)
print(f"  E^Q[D] = {DQ:.2e}  {OK(abs(DQ)<1e-12)}   (premium-matched => zero-cost under Q)\n")

# A concrete flat-IV counterexample: sufficiently high physical price drift makes
# the farther-OTM full overwrite lose to the premium-matched partial ATM overwrite.
mu_high = 0.50
ED_high = (fB * exp_intrinsic(1 + cB, sig_rv, tau, mu_high)
           - exp_intrinsic(1 + cA, sig_rv, tau, mu_high))
ED_high_pa = ED_high / tau
print(f"  high-drift flat-IV counterexample (mu_price={mu_high:.0%}): "
      f"E[A-B] annualised={ED_high_pa:+.3%} (target about -0.63%)  "
      f"{OK(abs(ED_high_pa - (-0.0063)) < 0.0001)}\n")


# ================================================================ 4. closed forms
print("--- 4. closed forms vs Monte Carlo ---")
m = mu_price
d1P, d2P = d12(k, sig_rv, tau, m)
checks = [
    ("E[(R-k)^+]", exp_intrinsic(k, sig_rv, tau, m), np.maximum(R - k, 0).mean()),
    ("P(R>k)", norm.cdf(d2P), (R > k).mean()),
    ("E[R*1_{R<=k}]", np.exp(m * tau) * norm.cdf(-d1P), (R * (R <= k)).mean()),
    ("E[R^2*1_{R<=k}]", np.exp((2 * m + sig_rv**2) * tau) * norm.cdf(-d2P - 2 * sig_rv * np.sqrt(tau)),
     (R**2 * (R <= k)).mean()),
    ("E[min(R,k)]", np.exp(m * tau) - exp_intrinsic(k, sig_rv, tau, m), np.minimum(R, k).mean()),
    ("E[min(R,k)^2]", np.exp((2 * m + sig_rv**2) * tau) * norm.cdf(-d2P - 2 * sig_rv * np.sqrt(tau)) + k**2 * norm.cdf(d2P),
     (np.minimum(R, k) ** 2).mean()),
]
for name, ana, num in checks:
    print(f"  {name:18s} analytic={ana:.6f}  MC={num:.6f}  diff={abs(ana-num):.2e}  {OK(abs(ana-num)<3e-4)}")

# variance / Sharpe of the package
for ff in (1.0, 0.5):
    Emin = np.exp(m * tau) - exp_intrinsic(k, sig_rv, tau, m)
    E2min = np.exp((2 * m + sig_rv**2) * tau) * norm.cdf(-d2P - 2 * sig_rv * np.sqrt(tau)) + k**2 * norm.cdf(d2P)
    ERmin = np.exp((2 * m + sig_rv**2) * tau) * norm.cdf(-d2P - 2 * sig_rv * np.sqrt(tau)) + k * np.exp(m * tau) * norm.cdf(d1P)
    ER, ER2 = np.exp(m * tau), np.exp((2 * m + sig_rv**2) * tau)
    var = ((1 - ff) ** 2 * (ER2 - ER**2) + ff**2 * (E2min - Emin**2)
           + 2 * ff * (1 - ff) * (ERmin - ER * Emin))
    num = ((1 - ff) * R + ff * np.minimum(R, k)).var()
    print(f"  Var(R_cc) f={ff}    analytic={var:.6f}  MC={num:.6f}  {OK(abs(var-num)<3e-4)}")
    print(f"      -> sd_cc={np.sqrt(var/tau):.2%} p.a. vs sd_stock={sig_rv:.2%} p.a.")
sk = ((1 - 1.0) * R + 1.0 * np.minimum(R, k))
sk = (sk - sk.mean()) / sk.std()
print(f"  skew(R_cc, f=1) = {(sk**3).mean():+.3f}   skew(R_stock) = {(((R-R.mean())/R.std())**3).mean():+.3f}\n")


# ================================================================ 5. compounding
print("--- 5. compounding: same terminal stock return, different monthly vol ---")
paths = {"(+10%, +10%)": (0.10, 0.10), "(+21%, 0%)": (0.21, 0.0),
         "(+33%, -9.02%)": (0.33, -0.0902), "(+50%, -19.33%)": (0.50, -0.1933)}
y5 = call_yield(1.05, sig_iv, tau, rf, q_annual)
yt5 = y5 * np.exp(rf * tau)
print(f"  f=1, c=5%, y={y5:.3%}, y_tilde={yt5:.3%}")
for nm, (a, b) in paths.items():
    st = (1 + a) * (1 + b) - 1
    cc = (1 + min(a, c) + yt5) * (1 + min(b, c) + yt5) - 1
    print(f"  {nm:16s} stock={st:+7.3%}  covered call={cc:+7.3%}  gap={cc-st:+7.3%}")

print("\n  geometric growth: E[ln(1+g)] exact vs mu_g - sd_g^2/2")
g = (1 - 1.0) * r + 1.0 * np.minimum(r, c) + 1.0 * y * np.exp(rf * tau)
for nm, x in (("stock", r), ("covered call f=1 c=5%", g)):
    ex = np.log1p(x).mean() * 12
    ap = (x.mean() - 0.5 * x.var()) * 12
    print(f"  {nm:22s} E[ln(1+x)]*12={ex:+.3%}  (mu-var/2)*12={ap:+.3%}  arith*12={x.mean()*12:+.3%}")
print("  -> variance-drag saving (annualised) = "
      f"{0.5*(r.var()-g.var())*12:+.3%}; alpha = {alpha_exact*12:+.3%}; "
      f"net geometric edge = {(np.log1p(g).mean()-np.log1p(r).mean())*12:+.3%}")

print("\n  premium scaling: N x 1M premium vs 1 x N-month premium")
for nm, t in (("1M", 1 / 12), ("3M", 0.25), ("12M", 1.0)):
    print(f"  {nm:4s} ATM yield={call_yield(1,sig_iv,t,rf,q_annual):.3%}  "
          f"annualised roll-count x yield = {call_yield(1,sig_iv,t,rf,q_annual)/t:.3%}")

print("\n--- 5b. how much of the geometric edge is VRP vs variance drag? ---")
for iv in (0.40, 0.45, 0.50, 0.35):
    yy = call_yield(k, iv, tau, rf, q_annual)
    a = f * (exp_intrinsic(k, iv, tau, rf - q_annual) - exp_intrinsic(k, sig_rv, tau, mu_price))
    gg = np.minimum(r, c) + yy * np.exp(rf * tau)
    geo = (np.log1p(gg).mean() - np.log1p(r).mean()) * 12
    print(f"  IV={iv:.0%} (RV=40%): y={yy:.3%}  alpha*12={a*12:+.3%}  "
          f"drag-saving={0.5*(r.var()-gg.var())*12:+.3%}  geometric edge={geo:+.3%}")
print("  NB: lognormal RV. A fat right tail (NVDA earnings gaps) makes E^P[(R-k)^+] larger")
print("      than lognormal => alpha and geometric edge both shrink. Model artefact warning.")

print("\n--- 5c. iso-premium slice of the (f, c) plane: target premium = ATM-at-f (Uday's basis) ---")
target = call_yield(1.05, sig_iv, tau, rf, q_annual)   # = A's premium, 3.29%
print(f"  target premium Y={target:.3%}, RV={sig_rv:.0%}, IV flat={sig_iv:.0%}, mu_price={mu_price:.0%}")
print(f"  {'c':>6} {'f':>7} {'delta_sold':>11} {'vega_sold':>10} {'v/d':>7} {'alpha p.a.':>11} {'sd p.a.':>8} {'geo edge':>9}")
for cc in (0.0, 0.02, 0.05, 0.08, 0.12, 0.20):
    kk = 1 + cc
    ycc = call_yield(kk, sig_iv, tau, rf, q_annual)
    ff = target / ycc
    if ff > 1:
        print(f"  {cc:+6.0%} {ff:7.3f}   -- infeasible (f>1: premium target unreachable) --")
        continue
    a = ff * (exp_intrinsic(kk, sig_iv, tau, rf - q_annual) - exp_intrinsic(kk, sig_rv, tau, mu_price))
    gg = (1 - ff) * r + ff * np.minimum(r, cc) + ff * ycc * np.exp(rf * tau)
    geo = (np.log1p(gg).mean() - np.log1p(r).mean()) * 12
    print(f"  {cc:+6.0%} {ff:7.3f} {ff*bs_delta(kk,sig_iv,tau,rf,q_annual):11.4f} "
          f"{ff*bs_vega(kk,sig_iv,tau,rf,q_annual):10.4f} {bs_vega(kk,sig_iv,tau,rf,q_annual)/bs_delta(kk,sig_iv,tau,rf,q_annual):7.3f} "
          f"{a*12:+11.3%} {np.sqrt(gg.var()/tau):8.2%} {geo:+9.3%}")

print("\n--- 5d. what breaks 'A dominates'? (a) call skew  (b) fat right tail ---")
# (a) downward call skew: IV(c) = IV_atm - s*c
for s in (0.0, 0.20, 0.40, 0.60):
    row = []
    for cc in (0.0, 0.02, 0.05):
        kk, ivc = 1 + cc, sig_iv - s * cc
        ycc = call_yield(kk, ivc, tau, rf, q_annual)
        ff = min(target / ycc, 1.0) if cc > 0 else target / ycc
        a = ff * (exp_intrinsic(kk, ivc, tau, rf - q_annual) - exp_intrinsic(kk, sig_rv, tau, mu_price))
        row.append(f"c={cc:+.0%}: f={ff:.2f} a={a*12:+.2%}")
    print(f"  skew slope {s:.2f} vol/moneyness ({s*0.05*100:.1f}vol pts per 5% OTM):  " + "  ".join(row))

# (b) fat right tail: lognormal + earnings gap, each spec recalibrated to ~40% annual vol
print("  (b) fat right tail: lognormal + earnings gap, all specs ~= 40% annual vol")
print(f"  {'spec':28} {'sd':>6} {'skew':>6} {'kurt':>6} | {'a(ATM)':>8} {'a(c=5%)':>8} | winner")
for nm, (p, jm, js, bv) in {
    "no jump (lognormal 40%)": (0.0, 0, 0, 0.40),
    "5% chance of +25% gap": (0.05, 0.25, 0.05, 0.315),
    "8% chance of +30% gap": (0.08, 0.30, 0.06, 0.24),
    "20% chance of +35% gap": (0.20, 0.35, 0.06, 0.10),
    "12% chance of +/-18% gap": (0.12, 0.0, 0.18, 0.30),
}.items():
    base = np.exp((mu_price - 0.5 * bv**2) * tau + bv * np.sqrt(tau) * rng.standard_normal(N))
    Rfat = base * (np.where(rng.random(N) < p, 1 + jm + js * rng.standard_normal(N), 1.0) if p else 1.0)
    rfat = Rfat - 1
    z = (rfat - rfat.mean()) / rfat.std()
    al = {}
    for cc in (0.0, 0.05):
        kk, ycc = 1 + cc, call_yield(1 + cc, sig_iv, tau, rf, q_annual)
        ff = min(target / ycc, 1.0)
        al[cc] = ff * (ycc * np.exp(rf * tau) - np.maximum(Rfat - kk, 0).mean()) * 12
    print(f"  {nm:28} {rfat.std()/np.sqrt(tau):6.1%} {(z**3).mean():+6.2f} {(z**4).mean():6.2f} | "
          f"{al[0.0]:+8.2%} {al[0.05]:+8.2%} | {'A' if al[0.05] > al[0.0] else 'B'}")

print("\n--- 6. package greeks (f=1, c=5%) ---")
gam = lambda kk, s, t: norm.pdf(d12(kk, s, t, rf - q_annual)[0]) / (s * np.sqrt(t))
print(f"  delta = 1 - f*N(d1) = {1 - bs_delta(k, sig_iv, tau, rf, q_annual):.4f}")
print(f"  gamma = -f*Gamma_c  = {-gam(k, sig_iv, tau):.4f}")
print(f"  vega  = -f*Vega_c   = {-bs_vega(k, sig_iv, tau, rf, q_annual):.4f}")
print("  effective equity exposure beta(S) = 1 - f*N(d1(S)) :")
for s in (0.85, 0.95, 1.0, 1.05, 1.15):
    print(f"    S/S0={s:.2f} -> beta={1-bs_delta(k/s, sig_iv, tau, rf, q_annual):.3f}")


# ================================================================ 7. rho criterion (eq 7)
print("\n--- 7. eq(7):  A > B  <=>  rho(cA) < rho(cB),  rho(c) = E^P/E^Q  (distribution-free) ---")
EQint = lambda kk, s: np.exp(rf * tau) * call_yield(kk, s, tau, rf, q_annual)   # = E^Q[(R-k)^+]
cA, cB = 0.05, 0.0


def rho_test(name, R_, ivA=sig_iv, ivB=sig_iv):
    r_ = R_ - 1
    yA_, yB_ = call_yield(1 + cA, ivA, tau, rf, q_annual), call_yield(1 + cB, ivB, tau, rf, q_annual)
    fB_ = yA_ / yB_
    rhoA = np.maximum(R_ - (1 + cA), 0).mean() / EQint(1 + cA, ivA)
    rhoB = np.maximum(R_ - (1 + cB), 0).mean() / EQint(1 + cB, ivB)
    RA_ = np.minimum(r_, cA) + yA_ * np.exp(rf * tau)
    RB_ = (1 - fB_) * r_ + fB_ * np.minimum(r_, cB) + fB_ * yB_ * np.exp(rf * tau)
    ED = (RA_ - RB_).mean()
    # eq(6): alpha = premium_FV * (1 - rho)
    a_exact = 1.0 * (EQint(1 + cA, ivA) - np.maximum(R_ - (1 + cA), 0).mean())
    a_eq6 = yA_ * np.exp(rf * tau) * (1 - rhoA)
    print(f"  {name:30s} f_B={fB_:.3f} rho(cA)={rhoA:.4f} rho(cB)={rhoB:.4f} -> predict "
          f"{'A' if rhoA < rhoB else 'B'};  E[D]*12={ED*12:+7.3%} -> {'A' if ED > 0 else 'B'}  "
          f"{OK((rhoA < rhoB) == (ED > 0))} | eq(6) {OK(abs(a_exact-a_eq6) < 1e-12)}")


def mixture(p, jm, js, basevol):
    b = np.exp((mu_price - 0.5 * basevol**2) * tau + basevol * np.sqrt(tau) * rng.standard_normal(N))
    if p == 0:
        return b
    return b * np.where(rng.random(N) < p, 1 + jm + js * rng.standard_normal(N), 1.0)


rho_test("lognormal RV=40%", mixture(0, 0, 0, 0.40))
rho_test("5% x +25% gap", mixture(0.05, 0.25, 0.05, 0.315))
rho_test("8% x +30% gap", mixture(0.08, 0.30, 0.06, 0.24))
rho_test("20% x +35% gap", mixture(0.20, 0.35, 0.06, 0.10))
rho_test("lognormal + 3vol call skew", mixture(0, 0, 0, 0.40), ivA=sig_iv - 0.6 * cA)


# ================================================================ 8. eq(10) daily MTM index
print("\n--- 8. eq(10) daily mark-to-market index collapses to eq(1) at expiry ---")
# I_t/I_t0 = S_t/S_t0 - f*(C_t - C_t0*e^{rf dt})/S_t0 + D/S_t0 ; at T, C_T = (S_T-K)^+
C_T = np.maximum(R - k, 0)                            # option mark at expiry, per S_0
for ff in (1.0, 0.4):
    idx = (R - 1) - ff * (C_T - y * np.exp(rf * tau)) + d_T      # eq(10) at t = T
    eq1 = (R - 1) + d_T + ff * y * np.exp(rf * tau) - ff * C_T   # eq(1)
    print(f"  f={ff}: max|eq(10)@T - eq(1)| = {np.abs(idx-eq1).max():.2e}  {OK(np.allclose(idx, eq1))}")

if FAILURES:
    raise SystemExit(f"{FAILURES} numerical verification check(s) failed")
