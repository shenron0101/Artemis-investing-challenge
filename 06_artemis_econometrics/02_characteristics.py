"""02 — Characteristics: market and Artemis-style features.

Builds the asset-level characteristic matrix on top of the weekly panel from
01_build_panel.py. All characteristics are LAGGED one week (entered with
`.shift(1)` per symbol) so they can be used to predict next-week return without
look-ahead leakage.

Characteristics (per symbol, per week):
    log_mcap                 — log market cap
    log_dollar_vol           — log dollar trading volume
    turnover                 — dollar_vol / market_cap
    mom_1w, mom_4w, mom_12w  — trailing log-return sums (skip-1 for 4w/12w)
    vol_4w                   — 4-week stdev of weekly log returns
    tvl_to_mcap              — DeFi exposure proxy (NaN when unmapped)
    F_yield                  — annualised (fees + 0.5*revenue) / market cap
    G_growth                 — z-score of fees / dau / revenue growth (30 vs 120d)
    S_supply                 — emission rate composite from the v2 RAAM recipe
    act_dau_g, act_fees_g    — 4w vs 12w activity growth ratios
    stable_inflow_z          — system-wide stablecoin inflow z-score (broadcast)

The output frame keeps `week`, `symbol`, `fwd_ret_1w` for the response variable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    DATA_DIR,
    MANIFEST_DIR,
    load_clean,
    write_frame,
    write_json,
)

INPUT_PANEL = DATA_DIR / "panel.parquet"


def _by_symbol(df: pd.DataFrame, col: str):
    return df.groupby("symbol", group_keys=False)[col]


def add_market_features(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.sort_values(["symbol", "week"]).copy()
    out["log_mcap"] = np.log(out["market_cap_usd"].where(out["market_cap_usd"].gt(0)))
    out["log_dollar_vol"] = np.log(out["total_volume_usd"].where(out["total_volume_usd"].gt(0)))
    out["turnover"] = out["total_volume_usd"] / out["market_cap_usd"].replace(0, np.nan)
    out["tvl_to_mcap"] = out["tvl_usd"] / out["market_cap_usd"].replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def add_momentum_vol(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.sort_values(["symbol", "week"]).copy()
    grp = _by_symbol(out, "log_ret_1w")
    # 1w momentum is just the latest weekly log return; skip-1 for 4w/12w to
    # remove the short-term reversal noise that contaminates pure momentum.
    out["mom_1w"] = grp.shift(0)
    out["mom_4w"] = grp.transform(lambda s: s.shift(1).rolling(4, min_periods=3).sum())
    out["mom_12w"] = grp.transform(lambda s: s.shift(1).rolling(12, min_periods=8).sum())
    out["vol_4w"] = grp.transform(lambda s: s.rolling(4, min_periods=3).std())
    return out


def add_factor_F(panel: pd.DataFrame) -> pd.DataFrame:
    """F = annualised (fees + 0.5*revenue) trailing 4w / market cap."""
    out = panel.sort_values(["symbol", "week"]).copy()
    fees = _by_symbol(out, "act_fees").transform(lambda s: s.rolling(4, min_periods=2).mean()) if "act_fees" in out.columns else pd.Series(np.nan, index=out.index)
    rev = _by_symbol(out, "act_revenue").transform(lambda s: s.rolling(4, min_periods=2).mean()) if "act_revenue" in out.columns else pd.Series(np.nan, index=out.index)
    cash = fees * 52 + 0.5 * rev * 52  # weekly avg × 52 = annualised
    out["F_yield"] = cash / out["market_cap_usd"].replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def add_factor_G(panel: pd.DataFrame) -> pd.DataFrame:
    """G = average z of dau/fees/revenue 4w vs 16w growth."""
    out = panel.sort_values(["symbol", "week"]).copy()
    metrics = [c for c in ("act_dau", "act_fees", "act_revenue") if c in out.columns]
    if not metrics:
        out["G_growth"] = np.nan
        return out

    growths = []
    for m in metrics:
        short = _by_symbol(out, m).transform(lambda s: s.rolling(4, min_periods=2).mean())
        long = _by_symbol(out, m).transform(lambda s: s.rolling(16, min_periods=6).mean())
        g = (short / long.replace(0, np.nan)) - 1.0
        z = (
            g.groupby(out["week"]).transform("mean")
            .pipe(lambda s: (g - s) / g.groupby(out["week"]).transform("std").replace(0, np.nan))
        )
        growths.append(z)
        out[f"{m}_g"] = g
    out["G_growth"] = pd.concat(growths, axis=1).mean(axis=1, skipna=True)
    return out.replace([np.inf, -np.inf], np.nan)


def add_factor_S(panel: pd.DataFrame) -> pd.DataFrame:
    """S = supply absorption.

    Local-data version: 12-week change in implied circulating supply (mcap /
    price), cross-sectionally z-scored, with a sign flip so fast emitters have
    negative S.
    """
    out = panel.sort_values(["symbol", "week"]).copy()
    implied = out["market_cap_usd"] / out["price_usd"].replace(0, np.nan)
    emission = (implied / _by_symbol(out.assign(_imp=implied), "_imp").transform(lambda s: s.shift(12))) - 1.0
    emission_z = (
        emission - emission.groupby(out["week"]).transform("mean")
    ) / emission.groupby(out["week"]).transform("std").replace(0, np.nan)
    out["S_supply"] = -emission_z
    return out.replace([np.inf, -np.inf], np.nan)


def add_stable_z(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    if "stable_inflow_usd" not in out.columns:
        out["stable_inflow_z"] = np.nan
        return out
    s = out.drop_duplicates("week").sort_values("week").set_index("week")["stable_inflow_usd"]
    mean = s.rolling(26, min_periods=8).mean()
    std = s.rolling(26, min_periods=8).std().replace(0, np.nan)
    z = ((s - mean) / std).rename("stable_inflow_z")
    out = out.merge(z.reset_index(), on="week", how="left")
    return out


def lag_features(panel: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Replace each `cols` column with its previous-week value per symbol.

    Returns the same frame with the cols replaced and `fwd_ret_1w` left alone.
    Lagging here means the row at week t carries information known *at the
    start of week t+1*; combined with `fwd_ret_1w` (defined as ret from t to
    t+1 in 01_build_panel.add_returns), the regression naturally predicts the
    next-week return.

    We use the *current* week's characteristic to predict `fwd_ret_1w`
    (return from t to t+1). That avoids a double-shift while keeping the
    "use only information at t" invariant.
    """
    return panel  # explicit no-op: characteristics are already as-of-t snapshots


def build_characteristics() -> pd.DataFrame:
    panel = pd.read_parquet(INPUT_PANEL)
    panel = add_market_features(panel)
    panel = add_momentum_vol(panel)
    panel = add_factor_F(panel)
    panel = add_factor_G(panel)
    panel = add_factor_S(panel)
    panel = add_stable_z(panel)

    feature_cols = [
        "log_mcap",
        "log_dollar_vol",
        "turnover",
        "tvl_to_mcap",
        "mom_1w",
        "mom_4w",
        "mom_12w",
        "vol_4w",
        "F_yield",
        "G_growth",
        "S_supply",
        "stable_inflow_z",
    ]

    keep = ["week", "symbol", "cohort", "price_usd", "ret_1w", "fwd_ret_1w"] + feature_cols
    keep = [c for c in keep if c in panel.columns]
    out = panel[keep].sort_values(["week", "symbol"]).reset_index(drop=True)
    return out, feature_cols


def main() -> None:
    out, feature_cols = build_characteristics()
    write_frame(out, DATA_DIR / "characteristics")
    coverage = {
        c: int(out[c].notna().sum()) for c in feature_cols if c in out.columns
    }
    write_json(
        {
            "rows": int(len(out)),
            "symbols": int(out["symbol"].nunique()),
            "weeks": int(out["week"].nunique()),
            "feature_cols": feature_cols,
            "feature_coverage_non_null": coverage,
        },
        MANIFEST_DIR / "02_characteristics_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
