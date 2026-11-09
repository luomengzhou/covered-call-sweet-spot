# Step 0 — Covered Call Theory Notes (A vs B Prior)

> **English version.** Chinese original is preserved in `00_theory_notes_zh.md` (中文原文).
>
> Date context: 2026-07-14. These are prior hypotheses and framing assumptions for the NVDA sweet-spot study; all claims require empirical validation.

## 1) Analytical win/loss regions for A vs B

Notation:

- `r`: monthly NVDA return
- `y`: target premium (as a fraction of full notional)
- `c`: cap return for A, where `c = strike/spot - 1 > 0`
- A: full-notional OTM covered call
- B: partial-coverage ATM covered call with coverage `f` such that `f * y_ATM = y` (premium matched)

Monthly returns (ignoring carry on cash):

- `r_A = min(r, c) + y`
- `r_B = (1-f)*r + f*min(r, 0) + y`

Define edge:

- `D = r_A - r_B = min(r, c) - (1-f)r - f*min(r, 0)`

Piecewise result:

- If `r <= 0`: `D = 0` (exact tie)
- If `0 < r <= c`: `D = f*r` (A wins)
- If `r > c`: `D = c - (1-f)r`; crossover at `r* = c/(1-f)`; for `r > r*`, B wins and upside edge is unbounded

Interpretation:

- A has capped upside edge (wins small/often),
- B has uncapped upside edge (wins big/rarely),
- expected edge depends on realized distribution vs implied distribution.

## 2) AQR framework (Israelov & Nielsen, 2015)

Covered-call returns can be decomposed into:

1. Passive equity beta (dominant risk/return source)
2. Short volatility / variance risk premium leg (structural compensated source)
3. Equity timing/reversal leg from dynamic short-call delta (material risk, weak compensation)

Implication for this project:

- Differences between A and B can be framed as differences in nonlinear timing exposure.
- Partial ATM (B) is generally more linear than full-notional OTM near cap (A), where delta collapses more abruptly.

## 3) Industry analogs

- **BXM** (1M ATM buy-write on S&P 500) and **BXY** (2% OTM) provide useful intuition for standardized overwrite structures.
- Current index construction here uses **American-style** options, but for near-zero-dividend NVDA, European approximation is often acceptable for high-level interpretation.

## 4) Commercial warning case: YieldMax NVDY

Key practical lesson:

- distribution yield is not total return,
- high payout can coincide with NAV erosion.

Relevance:

- high target-yield buckets may look attractive in cash distribution terms while economically returning capital through foregone upside and/or NAV decay.

## 5) Pre-registered hypotheses to validate

1. **VRP regime effect**: implied vol proxy from call yield should often exceed future realized vol; when not, overwrite strategies struggle.
2. **Target-yield endogeneity trap**: low-vol periods force strikes closer to ATM for fixed target yield (tighter caps), making this design structurally vulnerable in slow-grind bull markets.
3. **Sharpe overstates quality** for negatively skewed overwrite structures; Calmar/Sortino and month-level win/loss decomposition should be emphasized.

## 6) Experiment design from stakeholder discussion (2026-07-08)

Explicit requirement:

- Compare A and B at **matched premium**, not matched risk.

Backtest blocks requested:

1. Strategy A: full-notional OTM covered calls, target-yield sweep from 1% to 15%.
2. Strategy B: same target yield and expiry, implemented via partial ATM coverage.

Requested outputs:

- cap-hit frequencies
- realized monthly returns
- monthly winner between A and B
- regime-level interpretation

Planned downstream path:

- complete NVDA first,
- then test z-score switch logic,
- then expand to the rest of Mag7.

## 7) Why backtesting is still required even with `r*`

`r* = c/(1-f)` only gives a deterministic winner conditional on `r` for a given month. It does **not** tell:

- how often realized `r` crosses `r*`,
- or the magnitude-weighted long-run payoff asymmetry.

Therefore:

- analytical decomposition (mechanics) and empirical backtest (distribution + magnitude) are both necessary.

## 8) Panel specification and data inventory

Target monthly panel fields include:

- underlier, month, `r`, target yield `y`, cap `c`, ATM premium `y_ATM`, coverage `f`, `r_A`, `r_B`, `D`,
- winner/cap-hit flags,
- implied/realized volatility features,
- rates.

Current data understanding:

- Exposure-family files correspond to fixed-coverage partial ATM structures (not premium-matched monthly `f` by default).
- Income-family files represent full-notional yield-target structures.
- TB3MS is available for macro-rate conditioning.

## 9) Rebalance report unit conventions

Critical implementation notes:

- Exposure fraction is encoded in option shares vs equity shares ratio, not in a separate notional field.
- Option premium cash line matches `|opt_shares| * option_price`.
- `Cap` and `Call Yield` are option-level attributes; across fixed-coverage exposure variants they can be identical because the option contract is the same while notional coverage differs.

## 10) Index construction logic validated from attribution + rebalance

Empirically validated monthly structure:

- Full equity held, overwrite sleeve applied on selected fraction.
- `Cap = strike/spot`, `Call Yield = option_price/spot`.
- Return identity:
  - `Index Return = r - f*max(r-(Cap-1), 0) + f*CallYield`
  - with option terms aligned to the prior rebalance (live option in current month).

After excluding split-artifact months, reconstruction error is near zero.

## 11) z-score switching theory (Phase 5 framing)

Goal:

- decide A vs B at month start by forecasting probability of right-tail upside month.

Candidate month-start observable signals:

- momentum
- implied-vol proxy / IV rank
- VRP proxy
- valuation/overextension proxy
- rates

Important caveat:

- if the signal cannot predict right-tail months, switching adds uncompensated timing noise rather than persistent alpha.

## Sources

- [Israelov & Nielsen, Covered Calls Uncovered (AQR PDF)](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Covered-Calls-Uncovered.pdf)
- [SSRN link](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2444999)
- [Cboe BuyWrite Indices Methodology](https://cdn.cboe.com/api/global/us_indices/governance/Cboe_BuyWrite_Indices_Methodology.pdf)
- [BXM overview (Wikipedia)](https://en.wikipedia.org/wiki/CBOE_S&P_500_BuyWrite_Index)
- [NVDY overview (StockAnalysis)](https://stockanalysis.com/etf/nvdy/)
- [NVDY NAV erosion discussion (AInvest)](https://www.ainvest.com/news/nvdy-yield-illusion-synthetic-exposure-capital-erosion-risks-2512/)
