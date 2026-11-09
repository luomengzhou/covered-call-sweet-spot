"""
ab_core.py -- shared math for the Mag7 covered-call A-vs-B comparison.

Strategy definitions (single period, tenor tau)
----------------------------------------------
Hold 1 unit of the underlying, sell a fraction f of calls struck at
K = S0 * (1 + c).  Let r = S_T/S0 - 1 be the *price* return of the
underlying and let y(c) = C(K)/S0 be the call premium as a fraction of
spot.  Premium is banked at the risk-free rate, so it grows to
ytil = y * exp(rf * tau) by expiry.  The realized period dividend return
dq is supplied separately from the annualized pricing yield q; when omitted,
the toy model uses dq = exp(q*tau) - 1.

    R(r) = r + dq + f*ytil - f*(r - c)^+

Strategy A: f_A (default 1, "full notional"), cap c_A (default 5% OTM)
Strategy B: cap c_B (default 0, i.e. ATM), f_B set by the equal-premium
            constraint  f_A * ytil_A = f_B * ytil_B.

Because exp(rf*tau) is a common factor, f_B = f_A * y_A / y_B.

Under that constraint the difference collapses to a zero-cost ratio call
spread -- the premium terms cancel exactly and the dividend terms cancel
too (both strategies are long 1 unit of the underlying):

    D(r) = R_A(r) - R_B(r) = f_B*(r - c_B)^+ - f_A*(r - c_A)^+

    D_peak = f_B * (c_A - c_B)                      attained at r = c_A
    r**    = (f_A*c_A - f_B*c_B) / (f_A - f_B)      second zero of D

Setting f_A = 1, c_B = 0 recovers the earlier special case r** = c_A/(1-f_B).

D > 0 means A is ahead.  A's edge is capped at D_peak; B's edge is
unbounded to the upside because the r > c_B leg has slope (1 - f_B) > 0.

Skew parameterization
---------------------
Implied vol is a quoting convention (BS inverted through market prices),
not a second primitive next to ATM vol.  In a true Black-Scholes world
sigma_IV(c) = sigma_ATM for every c.  Markets break that, so we need a
local description of the call wing.  We use a first-order tilt in
return-space moneyness, quoted in *vol points per 5% OTM* (desk language),
not as a multiplicative ratio:

    sigma_IV(c) = sigma_ATM + wing * (c / 0.05)

wing = 0 is flat (BS), wing < 0 is the usual equity call wing (cheaper OTM
calls), wing > 0 is an upward call wing.  What wing actually looks like by
asset class:

    Broad index (SPX-style):  persistent, steep put skew (leverage effect +
        structural put-buying demand). wing clearly negative, typically
        -0.02 to -0.03 per 5% OTM -- the most stable skew shape in equities.
    Single growth/momentum stock (NVDA-like): same sign, much shallower --
        upside tail hope (M&A, earnings pops) partly offsets the crash-fear
        put skew. NVDA measured wing = -0.0052, right direction but ~4x
        flatter than the index case.
    Commodities (oil etc.): sometimes flips the other way (wing > 0) --
        fear of a supply shock spiking price. One of the few asset classes
        where a positive wing has real market grounding.
    FX: closer to a symmetric double-sided smile; direction depends on
        which way the pair's tail risk runs. This single-slope wing knob
        doesn't really apply to FX.

This is a sensitivity knob, not an SVI/SSVI surface fit.

Carry
-----
Forward = S0 * exp((rf - q - borrow) * tau).  Here ``borrow`` is a
stock-borrow / carry adjustment used only in option pricing.  It is not a
funding spread paid by the covered-call investor; any such funding cost must
be modelled as a separate portfolio cash flow.

Reference anchors (recorded 2026-07-29 / 07-31, reproduced by self_check)
------------------------------------------------------------------------
sigma_ATM=45%, tau=1M, rf=4%, q=0, borrow=0, wing=0, c_A=5%, c_B=0, f_A=1
    y_A = 3.2946%,  y_B = 5.3382%,  f_B = 0.6172
    D(5%) = 3.09%,  r** = 13.06%,  D(30%) = -6.49%
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

SKEW_REF_MONEYNESS = 0.05  # wing is quoted as vol pts per 5% OTM
MIN_VOL = 1e-4
MIN_PREMIUM = 1e-8  # smallest meaningful premium, as a fraction of spot.
# Below this the equal-premium construction is degenerate (on $10mm notional
# that is <$0.10 of premium) and, numerically, the two mirrors' erfc tails
# disagree about where the price underflows -- so feasibility is defined by
# this economic floor, not by floating-point cancellation.  The same constant
# lives in AB_explorer.html; wing_bounds() bisects against it.

# Wing anchors by asset class (vol as decimal: -0.02 = −2 vol points per 5% OTM).
# Not "presets" to pick from -- reference points for the market intuition in
# the module docstring above, and regression anchors for self_check().
WING_FLAT = 0.0        # pure BS, no skew
WING_NVDA = -0.0052    # single growth/momentum stock (measured)
WING_INDEX = -0.02     # SPX-style broad index, persistent put skew
WING_COMMODITY_45 = 0.10 * 0.45  # +4.5 vol; commodity-style positive wing,
                                  # only equivalent to k=1.10 at σ_ATM=45%



# --------------------------------------------------------------------------
# Black-Scholes with continuous dividend yield and borrow cost
# --------------------------------------------------------------------------
def _norm_cdf(x):
    x = np.asarray(x, dtype=float)
    return 0.5 * (1.0 + np.vectorize(math.erf)(x / math.sqrt(2.0)))


def _norm_pdf(x):
    x = np.asarray(x, dtype=float)
    return np.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_call(S, K, sigma, tau, rf, q=0.0, borrow=0.0):
    """European call price and Greeks. Returns a dict of scalars/arrays.

    Greeks are in natural units: delta per 1.00 of spot, gamma per 1.00^2,
    vega per 1.00 of vol (divide by 100 for "per vol point"), theta per year
    (divide by 365 for "per calendar day"), rho per 1.00 of rate.
    """
    S = np.asarray(S, dtype=float)
    K = np.asarray(K, dtype=float)
    if np.any(S <= 0) or np.any(K <= 0):
        raise ValueError("S and K must be strictly positive")
    if np.any(np.asarray(sigma) <= 0) or np.any(np.asarray(tau) <= 0):
        raise ValueError("sigma and tau must be strictly positive")
    sigma = np.maximum(np.asarray(sigma, dtype=float), MIN_VOL)
    tau = np.maximum(np.asarray(tau, dtype=float), 1e-8)

    carry = rf - q - borrow
    fwd = S * np.exp(carry * tau)
    disc = np.exp(-rf * tau)
    dfqb = np.exp(-(q + borrow) * tau)

    srt = sigma * np.sqrt(tau)
    d1 = (np.log(fwd / K) + 0.5 * sigma * sigma * tau) / srt
    d2 = d1 - srt
    nd1, nd2, pd1 = _norm_cdf(d1), _norm_cdf(d2), _norm_pdf(d1)

    price = disc * (fwd * nd1 - K * nd2)
    delta = dfqb * nd1
    gamma = dfqb * pd1 / (S * srt)
    vega = S * dfqb * pd1 * np.sqrt(tau)
    theta = (
        -S * dfqb * pd1 * sigma / (2.0 * np.sqrt(tau))
        + (q + borrow) * S * dfqb * nd1
        - rf * K * disc * nd2
    )
    rho = K * tau * disc * nd2

    return dict(
        price=price, delta=delta, gamma=gamma, vega=vega, theta=theta,
        rho=rho, d1=d1, d2=d2,
    )


def skew_vol(sigma_atm, wing, c):
    """sigma_IV(c) = sigma_atm + wing * (c / 0.05), floored at MIN_VOL.

    wing is in absolute vol units per 5% OTM (e.g. -0.02 = −2 vol points).
    """
    c = np.asarray(c, dtype=float)
    return np.maximum(
        sigma_atm + wing * (c / SKEW_REF_MONEYNESS), MIN_VOL
    )


def call_prob_q(S, K, sigma, tau, rf, q=0.0, borrow=0.0, dsigma_dK=0.0):
    """Risk-neutral P(S_T > K), i.e. the undiscounted digital-call price.

    With a flat smile (dsigma_dK = 0) this is the Black-Scholes N(d2).  With a
    smile, the digital is the full strike derivative of the call written on the
    smile, C(K, sigma(K)):

        P^Q(S_T > K) = -(1/disc) * dC/dK
                     = N(d2) - (vega/disc) * dsigma/dK
                     = N(d2) - e^{carry*tau} * n(d1) * sqrt(tau) * S * dsigma_dK

    where carry = rf - q - borrow (vega = S * e^{-(q+borrow)tau} * n(d1) * sqrt(tau)).
    For the linear wing tilt sigma(c) = sigma_ATM + wing*(c/0.05) with
    c = K/S - 1, pass dsigma_dK = wing / (0.05 * S), so the S cancels and
    adj = e^{carry*tau} * n(d1) * sqrt(tau) * wing/0.05.  The result is clamped
    to [0, 1]; hitting the clamp means the linear tilt violates density
    positivity (butterfly no-arbitrage) at that strike.
    See 00_theory_dashboard_desk_view.md §3.
    """
    g = bs_call(S, K, sigma, tau, rf, q, borrow)
    carry = rf - q - borrow
    adj = math.exp(carry * tau) * float(_norm_pdf(g["d1"])) * math.sqrt(tau) \
        * float(S) * dsigma_dK
    return float(np.clip(float(_norm_cdf(g["d2"])) - adj, 0.0, 1.0))


def wing_from_k(k, sigma_atm):
    """Convert legacy ratio k = σ_IV(5%)/σ_ATM into wing vol points."""
    return (k - 1.0) * sigma_atm


def k_from_wing(wing, sigma_atm):
    """Inverse of wing_from_k (only meaningful at the 5% OTM anchor)."""
    if sigma_atm <= 0:
        return float("nan")
    return 1.0 + wing / sigma_atm


def wing_bounds(p: "Params", wing_min=-0.05, wing_max=0.05, tol=1e-5):
    """Feasible wing interval [lo, hi] inside [wing_min, wing_max], holding
    every other field of ``p`` fixed.

    Two constraints bound the wing (00_theory_dashboard_desk_view.md §4):

    - below, vol positivity: sigma_ATM + wing*(c/0.05) must stay above
      MIN_VOL at the widest strike, i.e. wing > -(sigma_ATM - MIN_VOL)*0.05/c
      (in practice the numeric premium hits zero slightly before the floor);
    - above, the ordering condition f_B < f_A, which for c_A > c_B is exactly
      y_A < y_B, i.e. call-price monotonicity in strike -- the model's
      "ordering" error IS vertical-spread no-arbitrage.

    solve() is valid at wing = 0 for any otherwise-valid Params (flat BS has
    y_A < y_B whenever c_A > c_B), so both edges are found by bisection on
    solve-validity from that anchor.  Returns (lo, hi); every wing in the
    closed interval solves, anything outside raises.
    """

    def ok(w):
        try:
            solve(p.with_(wing=w))
            return True
        except ValueError:
            return False

    if not ok(0.0):
        raise ValueError("Params must be valid at wing = 0 to bound the wing")
    if not wing_min <= 0.0 <= wing_max:
        raise ValueError("wing_bounds expects wing_min <= 0 <= wing_max")

    def edge(good, bad):
        # invariant: ok(good) is True, ok(bad) is False
        while abs(bad - good) > tol:
            mid = 0.5 * (good + bad)
            if ok(mid):
                good = mid
            else:
                bad = mid
        return good

    lo = wing_min if ok(wing_min) else edge(0.0, wing_min)
    hi = wing_max if ok(wing_max) else edge(0.0, wing_max)
    return lo, hi


# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------
@dataclass
class Params:
    S0: float = 100.0        # spot
    sigma_atm: float = 0.45  # ATM implied vol
    tau: float = 1.0 / 12.0  # tenor in years
    rf: float = 0.04         # risk-free rate
    q: float = 0.0           # annualized continuous dividend yield (pricing)
    dividend_return: float | None = None  # realized period dividend / initial spot
    borrow: float = 0.0      # stock-borrow / carry adjustment (pricing only)
    wing: float = 0.0        # call-wing vol pts per 5% OTM (decimal)
    c_A: float = 0.05        # strategy A cap (OTM fraction)
    c_B: float = 0.00        # strategy B cap (0 = ATM)
    f_A: float = 1.00        # strategy A notional fraction

    def with_(self, **kw) -> "Params":
        return replace(self, **kw)

    def validate(self) -> None:
        numeric = (
            self.S0, self.sigma_atm, self.tau, self.rf, self.q, self.borrow,
            self.wing, self.c_A, self.c_B, self.f_A,
        )
        if not all(math.isfinite(x) for x in numeric):
            raise ValueError("all numeric parameters must be finite")
        if self.S0 <= 0 or self.sigma_atm <= 0 or self.tau <= 0:
            raise ValueError("S0, sigma_atm, and tau must be strictly positive")
        if self.c_A <= -1 or self.c_B <= -1:
            raise ValueError("caps must imply strictly positive strikes")
        if self.c_A < self.c_B:
            raise ValueError("the A-vs-B model requires c_A >= c_B")
        if not 0 <= self.f_A <= 1:
            raise ValueError("f_A must be a coverage fraction in [0, 1]")
        if self.dividend_return is not None:
            if not math.isfinite(self.dividend_return):
                raise ValueError("dividend_return must be finite")
            if self.dividend_return <= -1:
                raise ValueError("dividend_return must be greater than -1")

    def resolved_dividend_return(self) -> float:
        """Return the period dividend cash flow normalized by initial spot.

        When no realized cash dividend is supplied, use exp(q*tau)-1 as the
        deterministic toy-model proxy implied by the annualized yield q.
        """
        if self.dividend_return is not None:
            return float(self.dividend_return)
        return math.expm1(self.q * self.tau)


# --------------------------------------------------------------------------
# Core solve
# --------------------------------------------------------------------------
@dataclass
class Solution:
    p: Params
    sigma_A: float
    sigma_B: float
    K_A: float
    K_B: float
    y_A: float          # premium / spot, strategy A leg
    y_B: float
    ytil_A: float       # premium compounded to expiry, / spot
    ytil_B: float
    f_B: float
    dq: float           # dividends over the period, as a fraction of spot
    D_peak: float       # A's maximum edge, attained at r = c_A
    r_star_star: float  # second zero of D (nan if f_B >= f_A)
    r_star_A: float     # A crosses buy-and-hold
    r_star_B: float     # B crosses buy-and-hold
    ceiling_A: float    # A's terminal return ceiling (nan if f_A < 1)
    slope_B: float      # B's slope above c_B
    prob_bs_A: float = float("nan")   # P^Q(S_T > K_A), flat-smile N(d2)
    prob_bs_B: float = float("nan")
    prob_A: float = float("nan")      # same, smile-consistent digital
    prob_B: float = float("nan")
    greeks_A: dict = field(default_factory=dict)
    greeks_B: dict = field(default_factory=dict)

    # ---- curves -------------------------------------------------------
    def R_A(self, r):
        r = np.asarray(r, dtype=float)
        return (r + self.dq + self.p.f_A * self.ytil_A
                - self.p.f_A * np.maximum(r - self.p.c_A, 0.0))

    def R_B(self, r):
        r = np.asarray(r, dtype=float)
        return (r + self.dq + self.f_B * self.ytil_B
                - self.f_B * np.maximum(r - self.p.c_B, 0.0))

    def R_bh(self, r):
        return np.asarray(r, dtype=float) + self.dq

    def D(self, r):
        r = np.asarray(r, dtype=float)
        return (self.f_B * np.maximum(r - self.p.c_B, 0.0)
                - self.p.f_A * np.maximum(r - self.p.c_A, 0.0))

    # ---- portfolio Greeks (long 1 unit underlying, short f calls) ------
    def portfolio_greeks(self):
        out = {}
        for tag, f, g in (("A", self.p.f_A, self.greeks_A),
                          ("B", self.f_B, self.greeks_B)):
            out[tag] = dict(
                delta=1.0 - f * g["delta"],
                gamma=-f * g["gamma"],
                vega=-f * g["vega"] / 100.0,        # per vol point
                theta=-f * g["theta"] / 365.0,      # per calendar day
                rho=-f * g["rho"] / 100.0,          # per 1% rate
            )
        return out

    # ---- desk translation (degree-1 homogeneity in notional) -----------
    def desk_view(self, notional: float, contract_size: int = 100) -> dict:
        """Translate the per-unit-of-spot model into dollar/desk language.

        Every payoff in the model is positively homogeneous of degree 1 in
        the position size, so a W-dollar position is W/S0 units of the
        per-unit problem and every %-of-spot quantity maps to dollars by
        multiplying with W (00_theory_dashboard_desk_view.md §1).  f_B is a
        ratio of premiums and does not depend on W.
        """
        if notional <= 0:
            raise ValueError("notional must be strictly positive")
        shares = notional / self.p.S0
        return dict(
            notional=notional,
            shares=shares,
            calls_A=self.p.f_A * shares,            # underlying units sold at K_A
            calls_B=self.f_B * shares,
            contracts_A=self.p.f_A * shares / contract_size,
            contracts_B=self.f_B * shares / contract_size,
            K_A=self.K_A, K_B=self.K_B,
            premium_A=self.p.f_A * self.y_A * notional,   # equal by construction
            premium_B=self.f_B * self.y_B * notional,
            premium_at_expiry=self.p.f_A * self.ytil_A * notional,
            D_peak=self.D_peak * notional,          # A's max edge, in dollars
        )

    def verdict(self) -> str:
        if abs(self.p.c_A - self.p.c_B) < 1e-12 and abs(self.p.f_A - self.f_B) < 1e-12:
            return "A and B are identical under these parameters."
        if not np.isfinite(self.r_star_star):
            return "f_B >= f_A: B is the capped leg, roles are reversed."
        return (
            f"A leads on [{self.p.c_B:.1%}, {self.r_star_star:.2%}], "
            f"max +{self.D_peak:.2%} at r = {self.p.c_A:.1%}; "
            f"B leads above {self.r_star_star:.2%}, with no upper bound."
        )


def solve(p: Params) -> Solution:
    p.validate()
    sigma_A = p.sigma_atm + p.wing * (p.c_A / SKEW_REF_MONEYNESS)
    sigma_B = p.sigma_atm + p.wing * (p.c_B / SKEW_REF_MONEYNESS)
    if sigma_A <= MIN_VOL or sigma_B <= MIN_VOL:
        raise ValueError(
            "linear wing implies a non-positive/floored volatility; "
            "choose parameters above MIN_VOL"
        )
    K_A = p.S0 * (1.0 + p.c_A)
    K_B = p.S0 * (1.0 + p.c_B)

    gA = bs_call(p.S0, K_A, sigma_A, p.tau, p.rf, p.q, p.borrow)
    gB = bs_call(p.S0, K_B, sigma_B, p.tau, p.rf, p.q, p.borrow)
    gA = {kk: float(vv) for kk, vv in gA.items()}
    gB = {kk: float(vv) for kk, vv in gB.items()}

    y_A = gA["price"] / p.S0
    y_B = gB["price"] / p.S0
    compound = math.exp(p.rf * p.tau)
    ytil_A, ytil_B = y_A * compound, y_B * compound

    # Equal-premium constraint.  A covered-call comparison requires meaningful
    # positive premiums (>= MIN_PREMIUM of spot) and a feasible B coverage.
    if not (math.isfinite(y_A) and math.isfinite(y_B)
            and y_A > MIN_PREMIUM and y_B > MIN_PREMIUM):
        raise ValueError(
            "both option premiums must be finite and above MIN_PREMIUM of spot"
        )
    f_B = p.f_A * y_A / y_B
    if not math.isfinite(f_B) or not 0 <= f_B <= 1 + 1e-12:
        raise ValueError(f"premium match implies infeasible f_B={f_B!r}")
    if p.c_A > p.c_B and f_B >= p.f_A - 1e-12:
        raise ValueError(
            "premium match requires f_B < f_A when c_A > c_B; "
            "the supplied smile violates the model's feasible ordering"
        )

    dq = p.resolved_dividend_return()

    D_peak = f_B * (p.c_A - p.c_B)
    denom = p.f_A - f_B
    r_ss = ((p.f_A * p.c_A - f_B * p.c_B) / denom
            if denom > 1e-12 else float("nan"))

    # Q-probability of finishing above each cap.  prob_bs is the flat-smile
    # N(d2) at that strike's own IV; prob is the smile-consistent digital
    # (the tilt term dsigma/dK = wing/(0.05*S0) applies at both strikes).
    dsdK = p.wing / (SKEW_REF_MONEYNESS * p.S0)
    prob_bs_A = float(_norm_cdf(gA["d2"]))
    prob_bs_B = float(_norm_cdf(gB["d2"]))
    prob_A = call_prob_q(p.S0, K_A, sigma_A, p.tau, p.rf, p.q, p.borrow, dsdK)
    prob_B = call_prob_q(p.S0, K_B, sigma_B, p.tau, p.rf, p.q, p.borrow, dsdK)

    return Solution(
        p=p, sigma_A=sigma_A, sigma_B=sigma_B, K_A=K_A, K_B=K_B,
        y_A=y_A, y_B=y_B, ytil_A=ytil_A, ytil_B=ytil_B, f_B=f_B, dq=dq,
        D_peak=D_peak, r_star_star=r_ss,
        r_star_A=p.c_A + ytil_A,   # independent of f_A
        r_star_B=p.c_B + ytil_B,
        ceiling_A=(p.c_A + dq + p.f_A * ytil_A
                   if abs(p.f_A - 1.0) < 1e-12 else float("nan")),
        slope_B=1.0 - f_B,
        prob_bs_A=prob_bs_A, prob_bs_B=prob_bs_B,
        prob_A=prob_A, prob_B=prob_B,
        greeks_A=gA, greeks_B=gB,
    )


# --------------------------------------------------------------------------
# Scenario grid -- the static deliverable requested on 08-03
# --------------------------------------------------------------------------
def scenario_grid(base: Params | None = None, **sweeps):
    """Cartesian sweep over any Params fields. Returns a pandas DataFrame.

    >>> scenario_grid(sigma_atm=[0.10, 0.25, 0.45], tau=[1/12, 0.5, 1.0])
    """
    import itertools
    import pandas as pd

    base = base or Params()
    if not sweeps:
        sweeps = dict(
            sigma_atm=[0.10, 0.20, 0.30, 0.45],
            tau=[1 / 12, 3 / 12, 6 / 12, 1.0],
            wing=[WING_INDEX, WING_FLAT, WING_COMMODITY_45],
        )
    names = list(sweeps)
    rows = []
    for combo in itertools.product(*(sweeps[n] for n in names)):
        s = solve(base.with_(**dict(zip(names, combo))))
        rows.append(
            dict(zip(names, combo))
            | dict(y_A=s.y_A, y_B=s.y_B, f_B=s.f_B, sigma_A=s.sigma_A,
                   D_peak=s.D_peak, r_star_star=s.r_star_star,
                   slope_B=s.slope_B)
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Strike x tenor term grid -- the static table deliverable (2026-08-07 ask)
# --------------------------------------------------------------------------
def strike_tenor_grid(base: Params | None = None, caps=None, taus_m=None,
                      notional: float | None = None):
    """The desk term grid: one row per (cap, tenor) cell.

    Per cell: the full-overwrite leg at that cap (premium y, its Q-value at
    expiry ytil, smile-consistent P(called)) plus the A-vs-B quantities
    against the same-tenor anchor at base.c_B (f_B, r**, D_peak).  Cells the
    model cannot price (cap below the anchor, wing outside its feasible
    domain at that cap) come back with feasible=False and NaNs -- they are
    reported, not skipped, so the table shape is stable.

    ``notional`` adds dollar columns via degree-1 homogeneity.
    """
    import itertools
    import pandas as pd

    base = base or Params()
    caps = list(caps if caps is not None
                else (0.0, 0.025, 0.05, 0.075, 0.10, 0.15, 0.20))
    taus_m = list(taus_m if taus_m is not None else (1, 2, 3, 6, 9, 12))
    rows = []
    for c, m in itertools.product(caps, taus_m):
        row = dict(cap=c, tenor_m=m, feasible=False,
                   y=float("nan"), ytil=float("nan"), prob_called=float("nan"),
                   f_B=float("nan"), r_star_star=float("nan"),
                   D_peak=float("nan"))
        try:
            s = solve(base.with_(c_A=c, tau=m / 12.0))
            row.update(feasible=True, y=s.y_A, ytil=s.ytil_A,
                       prob_called=s.prob_A, f_B=s.f_B,
                       r_star_star=s.r_star_star, D_peak=s.D_peak)
        except ValueError:
            pass
        if notional is not None:
            row["premium_usd"] = row["y"] * notional
            row["D_peak_usd"] = row["D_peak"] * notional
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Self-checks
# --------------------------------------------------------------------------
def self_check(verbose: bool = True) -> bool:
    """Reproduce the anchors recorded on 2026-07-29 / 07-31."""
    s = solve(Params())
    checks = [
        ("y_A", s.y_A, 0.032946, 5e-6),
        ("y_B", s.y_B, 0.053382, 5e-6),
        ("f_B", s.f_B, 0.6172, 5e-4),
        ("D(5%)", float(s.D(0.05)), 0.03086, 5e-5),
        ("r**", s.r_star_star, 0.1306, 5e-4),
        ("D(30%)", float(s.D(0.30)), -0.0649, 5e-4),
    ]
    ok = True
    for name, got, want, tol in checks:
        good = abs(got - want) <= tol
        ok &= good
        if verbose:
            print(f"  [{'ok' if good else 'FAIL'}] {name:8s} "
                  f"got {got: .6f}  want {want: .6f}")

    # identity: R_A - R_B == D(r) exactly (premium + dividend terms cancel)
    r = np.linspace(-0.5, 1.0, 4001)
    resid = float(np.max(np.abs((s.R_A(r) - s.R_B(r)) - s.D(r))))
    good = resid < 1e-12
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] max|R_A-R_B-D| = {resid:.2e}")

    # D vanishes at r**
    dss = abs(float(s.D(s.r_star_star)))
    good = dss < 1e-12
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] |D(r**)|      = {dss:.2e}")

    # premium match residual
    pm = abs(s.p.f_A * s.ytil_A - s.f_B * s.ytil_B)
    good = pm < 1e-15
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] premium match  = {pm:.2e}")

    # Pricing yield q and realized period dividend return are distinct inputs.
    sd = solve(Params().with_(q=0.06, tau=1.0, dividend_return=0.025))
    good = abs(sd.dq - 0.025) < 1e-15
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] explicit dividend return = "
              f"{sd.dq:.6f}")

    sp = solve(Params().with_(q=0.06, tau=1.0))
    good = abs(sp.dq - math.expm1(0.06)) < 1e-15
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] q-to-dividend toy proxy = "
              f"{sp.dq:.6f}")

    # r* is independent of f_A (analytic claim from the derivation)
    a1 = solve(Params().with_(f_A=1.0)).r_star_A
    a2 = solve(Params().with_(f_A=0.4)).r_star_A
    good = abs(a1 - a2) < 1e-15
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] r* indep of f_A: "
              f"{a1:.6f} vs {a2:.6f}")

    # NVDA measured call wing: 0.52 vol lower per 5% OTM
    sn = solve(Params().with_(wing=WING_NVDA))
    good = abs(sn.sigma_A - (0.45 + WING_NVDA)) < 1e-12
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] NVDA wing={WING_NVDA:.4f} -> "
              f"sigma_IV(5%)={sn.sigma_A:.4%}  (f_B {sn.f_B:.4f}, "
              f"r** {sn.r_star_star:.2%})")

    # legacy k <-> wing round-trip at the 5% anchor
    k_commodity = 1.10
    w_commodity = wing_from_k(k_commodity, 0.45)
    good = abs(w_commodity - WING_COMMODITY_45) < 1e-15
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] k=1.10 @ 45% -> "
              f"wing={w_commodity:.4f} (commodity-style positive wing)")

    sm = solve(Params().with_(wing=WING_COMMODITY_45))
    good = abs(sm.sigma_A - 0.45 * 1.10) < 1e-12
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] commodity-style wing -> "
              f"sigma_IV(5%)={sm.sigma_A:.4%} (= 1.10× ATM at c=5%)")

    # ---- dashboard/desk-view pack (00_theory_dashboard_desk_view.md) ----
    s = solve(Params())

    # Slice-value identity (§2): ytil = E^Q[(r - c)^+] under the leg's own
    # lognormal.  Dense trapezoid over x = ln(S_T/S0) ~ N(m, v^2).
    def q_slice(sigma, c, p):
        carry = p.rf - p.q - p.borrow
        m = (carry - 0.5 * sigma * sigma) * p.tau
        v = sigma * math.sqrt(p.tau)
        x = np.linspace(m - 12 * v, m + 12 * v, 400_001)
        pdf = np.exp(-0.5 * ((x - m) / v) ** 2) / (v * math.sqrt(2 * math.pi))
        payoff = np.maximum(np.exp(x) - (1.0 + c), 0.0)
        return float(np.trapezoid(payoff * pdf, x))

    for tag, sigma, c, ytil in (("A", s.sigma_A, s.p.c_A, s.ytil_A),
                                ("B", s.sigma_B, s.p.c_B, s.ytil_B)):
        got = q_slice(sigma, c, s.p)
        good = abs(got - ytil) < 1e-7
        ok &= good
        if verbose:
            print(f"  [{'ok' if good else 'FAIL'}] slice value {tag}: "
                  f"E^Q[(r-c)^+]={got:.7f}  vs ytil={ytil:.7f}")

    # Equal premium == equal Q-value slices -> E^Q[D] = 0 exactly.
    eqd = abs(s.f_B * q_slice(s.sigma_B, s.p.c_B, s.p)
              - s.p.f_A * q_slice(s.sigma_A, s.p.c_A, s.p))
    good = eqd < 1e-7
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] E^Q[D] = 0 residual = {eqd:.2e}")

    # Digital identities (§3): flat-smile N(d2) matches the lognormal tail
    # probability analytically; the smile-consistent digital matches the
    # finite difference of C(K, sigma(K)) on the tilted smile.
    carry = s.p.rf - s.p.q - s.p.borrow
    m = (carry - 0.5 * s.sigma_A ** 2) * s.p.tau
    v = s.sigma_A * math.sqrt(s.p.tau)
    tail = float(_norm_cdf((m - math.log1p(s.p.c_A)) / v))
    good = abs(tail - s.prob_bs_A) < 1e-12
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] N(d2) = lognormal tail: "
              f"{s.prob_bs_A:.6f} vs {tail:.6f}")

    pw = Params().with_(wing=WING_INDEX)
    sw = solve(pw)
    h = 1e-4 * pw.S0

    def c_on_smile(K):
        c = K / pw.S0 - 1.0
        sig = pw.sigma_atm + pw.wing * (c / SKEW_REF_MONEYNESS)
        return float(bs_call(pw.S0, K, sig, pw.tau, pw.rf,
                             pw.q, pw.borrow)["price"])

    for tag, K, prob in (("A", sw.K_A, sw.prob_A), ("B", sw.K_B, sw.prob_B)):
        fd = (c_on_smile(K - h) - c_on_smile(K + h)) / (2 * h) \
            * math.exp(pw.rf * pw.tau)
        good = abs(fd - prob) < 1e-6
        ok &= good
        if verbose:
            print(f"  [{'ok' if good else 'FAIL'}] smile digital {tag}: "
                  f"analytic {prob:.6f} vs finite-diff {fd:.6f}")

    # wing < 0 raises the smile-consistent P(called) above N(d2) at both legs.
    good = sw.prob_A > sw.prob_bs_A and sw.prob_B > sw.prob_bs_B
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] index wing lifts digitals: "
              f"A {sw.prob_bs_A:.4f}->{sw.prob_A:.4f}, "
              f"B {sw.prob_bs_B:.4f}->{sw.prob_B:.4f}")

    # Wing feasibility bounds (§4): interior everywhere inside, ValueError
    # just outside, on a case whose lower edge binds inside the +-5 vol range.
    pb = Params().with_(sigma_atm=0.20, c_A=0.20)
    lo, hi = wing_bounds(pb)
    probes = [(lo, True), (lo - 1e-3, False), (hi, True)]
    if hi < 0.05:                       # upper edge binds inside the range
        probes.append((hi + 1e-3, False))
    edge_ok = []
    for w, want in probes:
        try:
            solve(pb.with_(wing=w))
            edge_ok.append(want is True)
        except ValueError:
            edge_ok.append(want is False)
    good = all(edge_ok) and -0.05 < lo < 0.0
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] wing bounds sig=20%/cap=20%: "
              f"lo={lo:.5f} hi={hi:.5f} (edges hold)")

    # Desk view (§1): dollars are the per-spot quantities x notional, and the
    # two legs bank the same dollar premium.
    dv = solve(Params()).desk_view(10_000_000)
    good = (abs(dv["premium_A"] - dv["premium_B"]) < 1e-6
            and abs(dv["premium_A"] - 0.032946 * 10_000_000) < 50
            and abs(dv["shares"] - 100_000) < 1e-9
            and abs(dv["contracts_A"] - 1000) < 1e-9)
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] desk view $10mm: "
              f"premium ${dv['premium_A']:,.0f} both legs, "
              f"{dv['contracts_A']:.0f} contracts A / {dv['contracts_B']:.1f} B")

    # Term grid: the (c_A, 1M) cell must reproduce the base solve.
    g = strike_tenor_grid(Params(), caps=(0.0, 0.05), taus_m=(1,))
    cell = g[(g.cap == 0.05) & (g.tenor_m == 1)].iloc[0]
    good = (bool(cell.feasible) and abs(cell.f_B - s.f_B) < 1e-12
            and abs(cell.y - s.y_A) < 1e-12
            and abs(cell.prob_called - s.prob_A) < 1e-12)
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] term grid (5%,1M) cell "
              f"matches solve(): f_B={cell.f_B:.4f}")

    # Sweet-spot cap (§5.1): D_peak(c) = c*y_A(c)/y_B is a "price x quantity"
    # curve with an interior max where the point elasticity of y_A wrt c is
    # -1. At short tenor that max sits inside the dashboard's cap range
    # ([0, 25%]); at long tenor it moves past 25% OTM, so within the range
    # the curve is monotone (still concave, just no interior turning point).
    def dpeak_argmax(tau_years, c_max=0.25, n=500):
        caps = [c_max * i / n for i in range(1, n + 1)]
        dp = [solve(Params().with_(c_A=c, tau=tau_years)).D_peak for c in caps]
        i = max(range(n), key=lambda k: dp[k])
        return caps[i], i < n - 2   # interior iff not pinned to the boundary

    c_1m, interior_1m = dpeak_argmax(1 / 12)
    c_12m, interior_12m = dpeak_argmax(1.0)
    good = interior_1m and abs(c_1m - 0.090) < 0.01 and not interior_12m
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] sweet-spot cap: 1M interior "
              f"max at c={c_1m:.3f} ({interior_1m}), 12M pinned to boundary "
              f"({not interior_12m})")

    # elasticity = -1 at that interior max (monopoly-pricing analogy, §5.1)
    def y_a(tau_years, c):
        return solve(Params().with_(c_A=c, tau=tau_years)).y_A
    h = 1e-6
    elasticity = c_1m * (y_a(1 / 12, c_1m + h) - y_a(1 / 12, c_1m - h)) \
        / (2 * h * y_a(1 / 12, c_1m))
    good = abs(elasticity - (-1.0)) < 0.02
    ok &= good
    if verbose:
        print(f"  [{'ok' if good else 'FAIL'}] elasticity at sweet-spot cap "
              f"= {elasticity:.4f} (want -1)")

    if verbose:
        print(f"\n  {'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'}")
    return ok


if __name__ == "__main__":
    print(__doc__.split("Reference anchors")[0].strip()[:0] or "", end="")
    print("ab_core self-check\n" + "-" * 60)
    ok = self_check()
    s = solve(Params())
    print("\n" + s.verdict())
    if not ok:
        raise SystemExit(1)
