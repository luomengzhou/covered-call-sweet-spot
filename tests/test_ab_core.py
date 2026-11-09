"""Smoke tests for the theory pack (pure numpy/scipy, no data needed)."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "theory"))

import ab_core  # noqa: E402


def _bs_ref(S, K, sigma, tau, rf, q=0.0):
    d1 = (math.log(S / K) + (rf - q + 0.5 * sigma**2) * tau) / (sigma * math.sqrt(tau))
    d2 = d1 - sigma * math.sqrt(tau)
    return S * math.exp(-q * tau) * norm.cdf(d1) - K * math.exp(-rf * tau) * norm.cdf(d2)


def test_bs_call_matches_textbook_and_put_call_parity():
    S, K, sigma, tau, rf, q = 100.0, 105.0, 0.45, 1 / 12, 0.04, 0.02
    g = ab_core.bs_call(S, K, sigma, tau, rf, q)
    assert float(g["price"]) == pytest.approx(_bs_ref(S, K, sigma, tau, rf, q), rel=1e-10)
    # delta in (0,1), gamma/vega positive, theta negative for a call with q < rf
    assert 0.0 < float(g["delta"]) < 1.0
    assert float(g["gamma"]) > 0 and float(g["vega"]) > 0 and float(g["theta"]) < 0
    # finite-difference delta
    h = 1e-4
    fd = (float(ab_core.bs_call(S + h, K, sigma, tau, rf, q)["price"])
          - float(ab_core.bs_call(S - h, K, sigma, tau, rf, q)["price"])) / (2 * h)
    assert float(g["delta"]) == pytest.approx(fd, rel=1e-6)


def test_reference_anchors_from_docstring():
    sol = ab_core.solve(ab_core.Params())
    assert sol.y_A == pytest.approx(0.032946, abs=2e-6)
    assert sol.y_B == pytest.approx(0.053382, abs=2e-6)
    assert sol.f_B == pytest.approx(0.6172, abs=1e-4)
    assert sol.r_star_star == pytest.approx(0.1306, abs=1e-4)
    assert sol.D_peak == pytest.approx(0.0309, abs=1e-4)


def test_premium_match_and_zero_q_value():
    """Equal premium => f_A*ytil_A == f_B*ytil_B and D has zero risk-neutral value."""
    p = ab_core.Params(sigma_atm=0.30, wing=-0.01, q=0.01, c_A=0.07)
    sol = ab_core.solve(p)
    assert p.f_A * sol.ytil_A == pytest.approx(sol.f_B * sol.ytil_B, abs=1e-12)
    r = np.linspace(-0.5, 0.8, 2001)
    D = sol.D(r)
    assert np.allclose(D, sol.R_A(r) - sol.R_B(r), atol=1e-12)
    assert float(sol.D(np.array([p.c_A]))[0]) == pytest.approx(sol.D_peak, abs=1e-12)
    assert float(np.max(D)) <= sol.D_peak + 1e-12
    assert abs(float(sol.D(np.array([sol.r_star_star]))[0])) < 1e-10


def test_alpha_identity_small_monte_carlo():
    """alpha = f*(E^Q[(R-k)^+] - E^P[(R-k)^+]) reproduced by MC within 4 s.e."""
    rng = np.random.default_rng(0)
    N, sig_iv, sig_rv, tau, rf, mu, k = 400_000, 0.45, 0.40, 1 / 12, 0.04, 0.15, 1.05
    y = float(ab_core.bs_call(1.0, k, sig_iv, tau, rf)["price"])
    d1 = (-math.log(k) + (mu + 0.5 * sig_rv**2) * tau) / (sig_rv * math.sqrt(tau))
    EP = math.exp(mu * tau) * norm.cdf(d1) - k * norm.cdf(d1 - sig_rv * math.sqrt(tau))
    alpha = y * math.exp(rf * tau) - EP
    R = np.exp((mu - 0.5 * sig_rv**2) * tau + sig_rv * math.sqrt(tau) * rng.standard_normal(N))
    payout = np.maximum(R - k, 0)
    mc = y * math.exp(rf * tau) - payout.mean()
    assert abs(mc - alpha) < 4 * payout.std() / math.sqrt(N)
