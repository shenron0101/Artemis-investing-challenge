#!/usr/bin/env python3
"""
Plan B — run the regime-conditioned strategy with SOFT activation.

Uses the HMM soft state probabilities to form a convex blend of the per-regime
activation matrix, giving smooth factor-weight transitions (no discontinuity at
a hard threshold). Writes all artifacts with the `b` prefix.
"""
from __future__ import annotations

import pandas as pd

import _rcfp_common as C


def regime_ic_attribution(regime_df: pd.DataFrame, tag: str) -> pd.DataFrame:
    ic_ts = pd.read_parquet(C.DATA_OUT / f"{tag}_factor_ic_timeseries.parquet")
    ic_ts = ic_ts.merge(regime_df[["week", "label"]], on="week", how="left")
    tab = (ic_ts.dropna(subset=["ic", "label"])
           .groupby(["factor", "label"])["ic"].mean().unstack("label"))
    cols = [c for c in C.REGIMES if c in tab.columns]
    tab = tab[cols].reindex(C.FACTORS)
    return tab


def main() -> None:
    regime = pd.read_parquet(C.DATA_OUT / "b_regime_panel.parquet")
    regime["week"] = pd.to_datetime(regime["week"])

    panel = C.build_factor_scores()
    metrics = C.run_strategy(regime, mode="soft", tag="b", panel=panel)

    print("\n=== PLAN B (HMM) — performance ===")
    for k in ("full", "is", "oos"):
        m = metrics[k]
        print(f"  {k.upper():4s}  Sharpe={m['sharpe']:+.2f}  "
              f"AnnRet={m['ann_return']:+.1%}  AnnVol={m['ann_vol']:.1%}  "
              f"MaxDD={m['max_dd']:+.1%}  weeks={m['weeks']}")
    print(f"  mean weekly turnover: {metrics['mean_turnover']:.1%}")

    print("\n=== Per-regime (argmax label) factor IC attribution ===")
    tab = regime_ic_attribution(regime, "b")
    print(tab.round(4).to_string())
    tab.to_csv(C.TABLE_OUT / "b_regime_ic_attribution.csv")


if __name__ == "__main__":
    main()
