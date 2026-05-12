"""03 — IC-Weighted Factor Signal Combination (v3 trading layer).

Replaces the two-stream regime detector (E_net vs E_gx blend) from v2.

Instead of blending two aggregate signals, v3 treats each factor as an
independent signal stream and combines them via rolling out-of-sample IC
weights — the RAAM v2 IC-proportional convention already validated in
stage 04 of this project.

Mechanics
---------
Step 1. Per-factor weekly IC time series loaded from factor_ic_timeseries.parquet
        (written by 02_factor_pricing.py).
Step 2. Rolling 8-week mean IC, lagged 1 week — strictly OOS.
Step 3. Positive-clipped IC-proportional weights::

          w_{k,t} = clip+(IC_roll_{k,t}) / sum_j clip+(IC_roll_{j,t})

        If every factor has non-positive IC in the lookback, fall back to
        equal weight across IC_TRADEABLE_FACTORS.
Step 4. E_final_{i,t} = sum_k w_{k,t} * sign_k * z_cs(c_{k,i,t}).
Step 5. Output blended_signals.parquet (same schema as v2 so 04/05 are
        unchanged) plus signal_weights.parquet for diagnostics.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    DATA_DIR,
    FACTOR_RECIPES,
    IC_LOOKBACK_WEEKS,
    IC_TRADEABLE_FACTORS,
    MANIFEST_DIR,
    TRAIN_WEEKS,
    cs_zscore,
    load_characteristics,
    save_plotly,
    write_frame,
    write_json,
)


def _load_panel() -> pd.DataFrame:
    """Merge stage-06 characteristics with Pillar-1 network signals."""
    char = load_characteristics()
    net = pd.read_parquet(DATA_DIR / "network_panel.parquet")
    net["week"] = pd.to_datetime(net["week"])
    keep_net = ["week", "symbol", "cluster_id", "within_cluster_mom",
                "cross_cluster_rel", "network_entropy", "fwd_ret_1w"]
    df = char.merge(net[keep_net], on=["week", "symbol"], how="inner",
                    suffixes=("", "_net"))
    # prefer network fwd_ret (same source, avoids duplicate columns)
    if "fwd_ret_1w_net" in df.columns:
        df["fwd_ret_1w"] = df["fwd_ret_1w"].combine_first(df.pop("fwd_ret_1w_net"))
    return df.sort_values(["week", "symbol"]).reset_index(drop=True)


def _rolling_ic_weights(ic_ts: pd.DataFrame) -> pd.DataFrame:
    """Compute per-factor rolling IC weights (strictly OOS).

    Returns a wide DataFrame indexed by week with one column per tradeable
    factor, plus a 'fallback_eq' boolean column indicating weeks where all
    ICs were non-positive and equal weights were used."""
    # pivot to wide: week x factor
    wide = (ic_ts[ic_ts["factor"].isin(IC_TRADEABLE_FACTORS)]
            .pivot_table(index="week", columns="factor", values="ic", aggfunc="last")
            .sort_index())
    # lag 1 then rolling mean — strictly past ICs
    roll = wide.shift(1).rolling(IC_LOOKBACK_WEEKS, min_periods=3).mean()
    pos = roll.clip(lower=0.0)
    denom = pos.sum(axis=1)
    # equal-weight fallback
    n_factors = pos.shape[1]
    eq_weight = 1.0 / n_factors
    fallback = denom <= 0
    weights = pos.div(denom, axis=0).where(~fallback, eq_weight)
    weights["fallback_eq"] = fallback
    return weights


def _build_e_final(panel: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    """Compute IC-weighted expected return E_final per asset per week.

    For each factor k in IC_TRADEABLE_FACTORS:
        z_k_{i,t}    = z_cs(c_{k,i,t}) within week t
        E_final_{i,t} = sum_k w_{k,t} * sign_k * z_k_{i,t}
    """
    factor_col_map = {
        name: (recipe["sort_col"], recipe["direction"])
        for name, recipe in FACTOR_RECIPES.items()
        if name in IC_TRADEABLE_FACTORS
    }

    weeks = sorted(panel["week"].unique())
    result_rows: list[pd.DataFrame] = []

    w_long = (weights
              .drop(columns=["fallback_eq"], errors="ignore")
              .reset_index()
              .melt(id_vars="week", var_name="factor", value_name="w"))
    w_long["week"] = pd.to_datetime(w_long["week"])

    for wk in weeks:
        week_data = panel[panel["week"] == wk].copy()
        if week_data.empty:
            continue
        w_row = w_long[w_long["week"] == wk].set_index("factor")["w"]
        score = pd.Series(0.0, index=week_data.index)
        total_w = 0.0
        for fname, (col, direction) in factor_col_map.items():
            if fname not in w_row.index:
                continue
            w_k = float(w_row[fname]) if not np.isnan(w_row[fname]) else 0.0
            if w_k == 0.0:
                continue
            if col not in week_data.columns:
                continue
            char_z = cs_zscore(week_data[col])
            score += w_k * direction * char_z
            total_w += w_k
        # if no factor has weight (very early weeks before lookback filled)
        if total_w > 0:
            score = score / total_w * len(factor_col_map)
        sub = week_data[["week", "symbol", "cluster_id", "network_entropy",
                         "fwd_ret_1w"]].copy()
        sub["E_final"] = score.values
        result_rows.append(sub)

    return pd.concat(result_rows, ignore_index=True)


def _signal_weights_long(weights: pd.DataFrame) -> pd.DataFrame:
    """Long (week, factor, w_k) frame for diagnostics and reporting."""
    factor_cols = [c for c in weights.columns if c != "fallback_eq"]
    long = (weights[factor_cols]
            .reset_index()
            .melt(id_vars="week", var_name="factor", value_name="w_k"))
    long["week"] = pd.to_datetime(long["week"])
    return long.dropna(subset=["w_k"]).reset_index(drop=True)


def _figures(ic_ts: pd.DataFrame, weights_long: pd.DataFrame) -> None:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    # Rolling IC per factor
    wide_ic = (ic_ts[ic_ts["factor"].isin(IC_TRADEABLE_FACTORS)]
               .pivot_table(index="week", columns="factor", values="ic", aggfunc="last")
               .sort_index())
    roll_ic = wide_ic.shift(1).rolling(IC_LOOKBACK_WEEKS, min_periods=3).mean()

    fig = go.Figure()
    for col in roll_ic.columns:
        fig.add_trace(go.Scatter(x=roll_ic.index, y=roll_ic[col],
                                 mode="lines", name=col))
    fig.add_hline(y=0, line=dict(color="#888", dash="dash", width=1))
    fig.update_layout(title="Per-factor rolling 8-week IC (lagged, OOS)", height=520)
    save_plotly(fig, "ic_per_factor", "03_signal_combination")

    # Factor weights over time (stacked area not available cleanly in plotly, use lines)
    fig2 = go.Figure()
    for fname in sorted(IC_TRADEABLE_FACTORS):
        sub = weights_long[weights_long["factor"] == fname]
        fig2.add_trace(go.Scatter(x=sub["week"], y=sub["w_k"],
                                  mode="lines", name=fname, stackgroup="one"))
    fig2.update_layout(title="IC-proportional factor weights w_{k,t}", height=480,
                       yaxis_title="weight")
    save_plotly(fig2, "factor_weights", "03_signal_combination")

    # Average weight bar chart over OOS window
    oos_weights = weights_long.copy()
    # identify OOS weeks (after TRAIN_WEEKS from start)
    all_weeks = sorted(oos_weights["week"].unique())
    if len(all_weeks) > TRAIN_WEEKS:
        oos_start = all_weeks[TRAIN_WEEKS]
        oos_weights = oos_weights[oos_weights["week"] >= oos_start]
    avg_w = oos_weights.groupby("factor")["w_k"].mean().reset_index()
    fig3 = px.bar(avg_w, x="factor", y="w_k",
                  title="Mean IC-proportional weight per factor (OOS window)",
                  labels={"w_k": "mean weight", "factor": "factor"})
    save_plotly(fig3, "weight_bar", "03_signal_combination")


def main() -> None:
    print("loading panel ...")
    panel = _load_panel()
    print(f"  rows: {len(panel):,} | weeks: {panel['week'].nunique()} | "
          f"symbols: {panel['symbol'].nunique()}")

    print("loading factor IC timeseries ...")
    ic_ts = pd.read_parquet(DATA_DIR / "factor_ic_timeseries.parquet")
    ic_ts["week"] = pd.to_datetime(ic_ts["week"])
    print(f"  {len(ic_ts):,} rows | factors: {ic_ts['factor'].nunique()} | "
          f"weeks: {ic_ts['week'].nunique()}")

    print("computing rolling IC weights ...")
    weights = _rolling_ic_weights(ic_ts)

    print("computing E_final ...")
    blended = _build_e_final(panel, weights)
    print(f"  blended rows: {len(blended):,} | weeks: {blended['week'].nunique()}")

    weights_long = _signal_weights_long(weights)

    write_frame(blended[["week", "symbol", "E_final", "cluster_id",
                          "network_entropy", "fwd_ret_1w"]],
                DATA_DIR / "blended_signals")
    write_frame(weights_long, DATA_DIR / "signal_weights")

    # --- manifest ---
    all_weeks = sorted(ic_ts["week"].unique())
    oos_weeks = all_weeks[TRAIN_WEEKS:] if len(all_weeks) > TRAIN_WEEKS else []
    ic_mean = (ic_ts[ic_ts["factor"].isin(IC_TRADEABLE_FACTORS)]
               .groupby("factor")["ic"].mean().to_dict())
    ic_oos_mean: dict[str, float] = {}
    if oos_weeks:
        oos_ts = ic_ts[ic_ts["week"].isin(oos_weeks)]
        ic_oos_mean = (oos_ts[oos_ts["factor"].isin(IC_TRADEABLE_FACTORS)]
                       .groupby("factor")["ic"].mean().to_dict())
    wt_mean = weights_long.groupby("factor")["w_k"].mean().to_dict()
    fallback_frac = float(weights["fallback_eq"].mean()) if "fallback_eq" in weights.columns else 0.0

    manifest = {
        "ic_lookback_weeks": IC_LOOKBACK_WEEKS,
        "ic_tradeable_factors": sorted(IC_TRADEABLE_FACTORS),
        "per_factor_ic_mean": {k: float(v) for k, v in ic_mean.items()},
        "per_factor_ic_oos_mean": {k: float(v) for k, v in ic_oos_mean.items()},
        "per_factor_weight_mean": {k: float(v) for k, v in wt_mean.items()},
        "fallback_eq_weight_frac": fallback_frac,
    }
    write_json(manifest, MANIFEST_DIR / "03_signal_combination_manifest.json")

    print("\nrendering figures ...")
    _figures(ic_ts, weights_long)
    print("done.")


if __name__ == "__main__":
    main()
