"""Per-ticker configuration for the covered-call pipeline.

Every step script (01–06) reads its ticker from the TICKER env var (default NVDA),
so the same code runs any ticker whose attribution CSVs live under data/<subdir>/:

    .venv/bin/python 01_build_panel.py                 # NVDA (default)
    TICKER=AAPL .venv/bin/python 01_build_panel.py      # Apple

Outputs land in results/<TICKER>/. Add a ticker by appending a TickerConfig below.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"          # TB3MS.csv and other shared macro data live here
OUT = ROOT / "results"


def income_pct(index_name: str) -> float:
    """Monthly premium target, in percent, from an Income index name.

    Mirrors the filename parsing in 01_build_panel.py: 1-2 digit codes are whole
    percents per month (`3_Income` -> 3.0), 4-digit zero-padded codes are
    thousandths of a percent (`0083_Income` -> 0.083).
    """
    raw = index_name.split("_")[-2]
    return int(raw) / 1000.0 if len(raw) == 4 else float(int(raw))


def target_label(index_name: str) -> str:
    """Display label for an Income tier, e.g. `0083_Income` -> '0.083%'."""
    pct = income_pct(index_name)
    return f"{pct:g}%" if pct >= 1 else f"{pct:.3f}%"


@dataclass(frozen=True)
class TickerConfig:
    ticker: str        # NVDA / AAPL / GOOGL / MSFT
    prefix: str        # attribution-file prefix, e.g. "NV_CoveredCall"
    cc: str            # index-name short prefix, e.g. "NV_CC"
    subdir: str        # data/ subfolder holding this ticker's attribution CSVs
    expected: set      # index_names the study expects (drives the completeness warning)

    @property
    def data_dir(self) -> Path:
        return DATA / self.subdir

    @property
    def out_dir(self) -> Path:
        return OUT / self.ticker

    @property
    def bench_name(self) -> str:
        return f"{self.ticker}_buyhold"

    @property
    def switch_targets(self) -> list[str]:
        """Income levels the A<->B analyses sweep (steps 05, 06 add-ons, wing audit).

        Every Income tier this ticker has, ascending by monthly premium target, so
        the sub-1%/mo grid (0083/0167/0250/0417) is covered alongside the original
        1%/3% headline pair. High tiers self-skip inside each script when B is
        feasible in too few months.
        """
        return sorted(
            (n for n in self.expected if n.endswith("_Income")), key=income_pct
        )


def _expected(
    cc: str,
    *,
    income: tuple[int | str, ...],
    exposure: tuple[int, ...],
    delta: tuple[int, ...] = (),
    bd: tuple[tuple[int, int], ...] = (),
) -> set[str]:
    return (
        {f"{cc}_{n}_Income" for n in income}
        | {f"{cc}_{n}_Exposure" for n in exposure}
        | {f"{cc}_Delta_{n}" for n in delta}
        | {f"{cc}_{coverage}Exp_Delta_{d}" for coverage, d in bd}
    )


_CONFIGS = {
    "NVDA": TickerConfig(
        ticker="NVDA", prefix="NV_CoveredCall", cc="NV_CC", subdir="NVDA",
        expected=_expected(
            "NV_CC",
            # 4-digit entries are the sub-1%/mo grid (0083 -> 0.0083/mo ~ 10%/yr)
            income=(1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 15,
                    "0083", "0167", "0250", "0417"),
            exposure=(10, 20, 30, 40, 50, 60, 70, 80, 90, 100),
            delta=(30, 50, 70),
            bd=((50, 30), (50, 70)),
        ),
    ),
    "AAPL": TickerConfig(
        ticker="AAPL", prefix="AAPL_CoveredCall", cc="AAPL_CC", subdir="Apple",
        expected=_expected("AAPL_CC", income=(1, 2, 3, 4, 5, 8, 12, "0083", "0167", "0250"),
                           exposure=(20, 50, 80, 100)),
    ),
    "GOOGL": TickerConfig(
        ticker="GOOGL", prefix="GOOGL_CoveredCall", cc="GOOGL_CC", subdir="GOOGL",
        expected=_expected("GOOGL_CC", income=(1, 2, 3, 4, 5, 8, 12, "0083", "0167", "0250"),
                           exposure=(50, 80, 100)),
    ),
    "MSFT": TickerConfig(
        ticker="MSFT", prefix="MSFT_CoveredCall", cc="MSFT_CC", subdir="MSFT",
        expected=_expected("MSFT_CC", income=(1, 2, 3, 4, 5, 8, 12, "0083", "0167", "0250"),
                           exposure=(20, 50, 80, 100)),
    ),
    "AMZN": TickerConfig(
        ticker="AMZN", prefix="AMZN_CoveredCall", cc="AMZN_CC", subdir="AMZN",
        expected=_expected("AMZN_CC", income=(1, 2, 3, 4, "0083", "0167", "0250"),
                           exposure=(100,)),
    ),
    "META": TickerConfig(
        ticker="META", prefix="META_CoveredCall", cc="META_CC", subdir="META",
        expected=_expected("META_CC", income=(1, 2, 3, 4, "0083", "0167", "0250"),
                           exposure=(100,)),
    ),
    "TSLA": TickerConfig(
        ticker="TSLA", prefix="TSLA_CoveredCall", cc="TSLA_CC", subdir="TSLA",
        expected=_expected("TSLA_CC", income=(1, 2, 3, 4, "0083", "0167", "0250"),
                           exposure=(100,)),
    ),
}


def get_config() -> TickerConfig:
    t = os.environ.get("TICKER", "NVDA").upper()
    if t not in _CONFIGS:
        raise SystemExit(f"unknown TICKER={t!r}; known: {sorted(_CONFIGS)}")
    return _CONFIGS[t]
