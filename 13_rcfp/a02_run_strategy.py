#!/usr/bin/env python3
"""
Plan A — run the regime-conditioned strategy with HARD activation.

Loads the Plan A regime labels, builds factor scores, IC weights, the
regime-activated composite, the portfolio, and the backtest. Writes all
artifacts with the `a` prefix and prints a metrics summary + per-regime
factor-IC attribution (the key validation that conditioning does real work).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import _rcfp_common as C


def regime_ic_attribution(panel: pd.DataFrame, regime_df: pd.DataFrame,
                          tag: str) -> pd.DataFrame:
    """Mean weekly factor IC within each regime label — proves BETA26/SKEW52
    are alive in RiskOn and dead in RiskOff."""
    ic_ts = pd.read_parquet(C.DATA_OUT / f"{tag}_factor_ic_timeseries.parquet")
    ic_ts = ic_ts.merge(regime_df[["week", "label"]], on="week", how="left")
    tab = (ic_ts.dropna(subset=["ic", "label"])
           .groupby(["factor", "label"])["ic"].mean().unstack("label"))
    cols = [c for c in C.REGIMES if c in tab.columns]
    tab = tab[cols].reindex(C.FACTORS)
    return tab


def main() -> None:
    regime = pd.read_parquet(C.DATA_OUT / "a_regime_panel.parquet")
    regime["week"] = pd.to_datetime(regime["week"])

    panel = C.build_factor_scores()
    metrics = C.run_strategy(regime, mode="hard", tag="a", panel=panel)

    print("\n=== PLAN A (economic classifier) — performance ===")
    for k in ("full", "is", "oos"):
        m = metrics[k]
        print(f"  {k.upper():4s}  Sharpe={m['sharpe']:+.2f}  "
              f"AnnRet={m['ann_return']:+.1%}  AnnVol={m['ann_vol']:.1%}  "
              f"MaxDD={m['max_dd']:+.1%}  weeks={m['weeks']}")
    print(f"  mean weekly turnover: {metrics['mean_turnover']:.1%}")

    print("\n=== Per-regime factor IC attribution (mean weekly IC) ===")
    tab = regime_ic_attribution(panel, regime, "a")
    print(tab.round(4).to_string())
    tab.to_csv(C.TABLE_OUT / "a_regime_ic_attribution.csv")


if __name__ == "__main__":
    main()
