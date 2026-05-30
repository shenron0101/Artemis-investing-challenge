#!/usr/bin/env python3
"""
Stage 13 — Regime-Conditioned Factor Portfolio (RCFP): shared core
==================================================================

This module holds everything shared between Plan A (economic two-signal
classifier) and Plan B (Gaussian HMM regime detection):

  * data loading from the 5-year Stage-09 panel
  * per-asset cross-sectional factor SCORES for the 7 GX-confirmed factors
    (VOLC, MAXRET, CRASH8, BETA26, NEWC, SKEW52, TVLC), using the exact
    factor definitions + sign conventions validated in 12_factor_viz/
  * per-factor weekly Information Coefficient time series + rolling IC weights
  * regime-activated composite signal (hard label OR soft probabilities)
  * portfolio construction (quintile L/S, inverse-vol, single-asset & Louvain
    cluster caps, turnover budget, regime gross-exposure scaling)
  * walk-forward backtest + performance metrics + benchmarks

The per-plan scripts (a*/b*) are thin orchestrators that build a regime frame
and call run_strategy().

Factor scores are defined in the PROFITABLE direction (higher score => long):
    VOLC   = -vol        (low-vol premium)
    MAXRET = -maxret     (lottery reversal)
    CRASH8 = -crash8     (capitulation: long the most-crashed)
    SKEW52 = -skew52     (long low-skew)
    NEWC   = -age         (newness premium: long young)
    TVLC   = -tvl_to_mcap (TVL irrelevance: long LOW TVL/mcap — GX premium is
                            negative, so the tradeable leg is the inverse of the
                            12_factor_viz display convention)
    BETA26 = +beta        (high-beta leverage-substitute premium)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA09 = ROOT / "09_nalfp_add" / "artifacts" / "data"
RETURNS = DATA09 / "returns_weekly.parquet"
PRICE_MCAP = DATA09 / "price_mcap_panel_weekly.parquet"
FUNDAMENTALS = DATA09 / "fundamentals_weekly.parquet"
REFERENCE = DATA09 / "reference_weekly.parquet"
NETWORK_PANEL = ROOT / "08_nalfp" / "artifacts" / "data" / "network_panel.parquet"
NALFP_PNL = ROOT / "08_nalfp" / "artifacts" / "data" / "weekly_pnl.parquet"

STAGE = Path(__file__).resolve().parent
ART = STAGE / "artifacts"
DATA_OUT = ART / "data"
MANIFEST_OUT = ART / "manifests"
TABLE_OUT = ART / "tables"
FIG_OUT = ART / "figures"
for _d in (DATA_OUT, MANIFEST_OUT, TABLE_OUT, FIG_OUT):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WEEKS_PER_YEAR = 52
FACTORS = ["VOLC", "MAXRET", "CRASH8", "BETA26", "NEWC", "SKEW52", "TVLC"]

# Two sleeves. FAST factors are genuine weekly cross-sectional rankers
# (positive weekly IC); they are traded weekly and IC-weighted. SLOW factors
# are long-run GX priced-risk exposures (negative/zero weekly IC); they are run
# as a low-turnover strategic tilt rebalanced every SLOW_REBAL weeks, NOT
# IC-weighted (IC is the wrong lens for a priced-risk premium).
FAST_FACTORS = ["VOLC", "MAXRET", "SKEW52"]
SLOW_FACTORS = ["BETA26", "CRASH8", "NEWC", "TVLC"]
FAST_GROSS = 0.7   # share of book in the weekly alpha sleeve
SLOW_GROSS = 0.3   # share of book in the slow priced-risk tilt
SLOW_REBAL = 4     # rebalance the slow sleeve every N weeks (turnover control)

# Factor windows — match the validated 12_factor_viz definitions exactly:
#   VOLC   vol_4w        = ret.rolling(4).std()
#   MAXRET maxret_4w     = ret.rolling(4).max()
#   CRASH8 minret_8w     = ret.rolling(8).min()
#   BETA26 beta_26w      = rolling 26w cov(ret, mkt)/var(mkt)
#   SKEW52 skew_52w      = ret.rolling(52, min_periods=26).skew()
#   NEWC   coin_age_weeks= weeks since first observation
#   TVLC   tvl_to_mcap   = precomputed in fundamentals_weekly.parquet
VOL_WINDOW = 4
MAXRET_WINDOW = 4
CRASH_WINDOW = 8
BETA_WINDOW = 26
SKEW_WINDOW = 52
VOL_MINP = 4
SKEW_MINP = 26
BETA_MINP = 13
CRASH_MINP = 6

Z_WINDOW = 52          # rolling window for regime-signal z-scores
IC_LOOKBACK = 8        # rolling window for IC-weighting
QUINTILE = 0.25        # top/bottom fraction for L/S legs
MIN_VOL_FLOOR = 0.05   # weekly vol floor for inverse-vol weighting
MAX_ASSET_WEIGHT = 0.05
MAX_CLUSTER_FRACTION = 0.40
TURNOVER_CAP = 0.30    # one-sided weekly turnover budget
COST_BPS = 10.0        # round-trip cost per unit turnover (basis points)
OOS_WEEKS = 79         # final OOS window length (matches NALFP v3 convention)

REGIMES = ["RiskOn", "Neutral", "RiskOff"]

# Regime x factor activation multipliers (economic mechanism gating).
ACTIVATION = {
    "VOLC":   {"RiskOn": 0.5, "Neutral": 1.0, "RiskOff": 1.5},
    "MAXRET": {"RiskOn": 1.5, "Neutral": 1.0, "RiskOff": 1.0},
    "CRASH8": {"RiskOn": 1.0, "Neutral": 1.5, "RiskOff": 1.0},
    "BETA26": {"RiskOn": 1.5, "Neutral": 1.0, "RiskOff": 0.0},
    "SKEW52": {"RiskOn": 1.5, "Neutral": 0.5, "RiskOff": 0.0},
    "NEWC":   {"RiskOn": 1.0, "Neutral": 0.5, "RiskOff": 0.0},
    "TVLC":   {"RiskOn": 0.5, "Neutral": 1.0, "RiskOff": 1.5},
}

GROSS = {"RiskOn": 1.0, "Neutral": 0.8, "RiskOff": 0.6}


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------
def write_frame(df: pd.DataFrame, stem: str) -> None:
    """Write a frame to artifacts/data as both parquet and csv."""
    path = DATA_OUT / stem
    df.to_parquet(path.with_suffix(".parquet"), index=False)
    df.to_csv(path.with_suffix(".csv"), index=False)


def write_json(obj: dict, name: str) -> None:
    (MANIFEST_OUT / name).write_text(json.dumps(obj, indent=2, default=str))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_returns() -> pd.DataFrame:
    df = pd.read_parquet(RETURNS)
    df["week"] = pd.to_datetime(df["week"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df.sort_values(["symbol", "week"]).reset_index(drop=True)


def load_mcap() -> pd.DataFrame:
    df = pd.read_parquet(PRICE_MCAP)[["symbol", "week", "mcap"]]
    df["week"] = pd.to_datetime(df["week"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df


def load_fundamentals() -> pd.DataFrame:
    df = pd.read_parquet(FUNDAMENTALS)
    df["week"] = pd.to_datetime(df["week"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df


def load_network() -> pd.DataFrame:
    df = pd.read_parquet(NETWORK_PANEL)[
        ["week", "symbol", "cluster_id", "network_entropy"]
    ]
    df["week"] = pd.to_datetime(df["week"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df


# ---------------------------------------------------------------------------
# Cross-sectional helpers
# ---------------------------------------------------------------------------
def cs_zscore(s: pd.Series) -> pd.Series:
    """Cross-sectional z-score within a single week (NaN-safe)."""
    mu = s.mean()
    sd = s.std()
    if not np.isfinite(sd) or sd == 0:
        return s * 0.0
    return (s - mu) / sd


def rolling_z(s: pd.Series, window: int = Z_WINDOW, minp: int = 12) -> pd.Series:
    """Trailing rolling z-score of a time series."""
    mu = s.rolling(window, min_periods=minp).mean()
    sd = s.rolling(window, min_periods=minp).std().replace(0, np.nan)
    return (s - mu) / sd


# ---------------------------------------------------------------------------
# Factor SCORE construction (per asset, per week, profitable direction)
# ---------------------------------------------------------------------------
def build_factor_scores() -> pd.DataFrame:
    """Return a long panel [week, symbol, ret, fwd_ret, vol, cluster_id,
    z_<FACTOR>...] with cross-sectionally z-scored profitable factor scores."""
    rets = load_returns()
    mcap = load_mcap()
    fund = load_fundamentals()

    df = rets.merge(mcap, on=["symbol", "week"], how="left")
    df = df.merge(fund, on=["symbol", "week"], how="left")
    df = df.sort_values(["symbol", "week"]).reset_index(drop=True)

    # forward return (return realised from t -> t+1), per symbol
    df["fwd_ret"] = df.groupby("symbol")["ret"].shift(-1)

    # equal-weight market return for beta
    mkt = df.groupby("week")["ret"].mean().rename("mkt_ret")
    df = df.merge(mkt, on="week", how="left")

    g = df.groupby("symbol", sort=False)

    # --- raw factor values (exact 12_factor_viz definitions) ---
    df["vol"] = g["ret"].transform(
        lambda s: s.rolling(VOL_WINDOW, min_periods=VOL_MINP).std())
    df["maxret"] = g["ret"].transform(
        lambda s: s.rolling(MAXRET_WINDOW, min_periods=VOL_MINP).max())
    df["crash8"] = g["ret"].transform(
        lambda s: s.rolling(CRASH_WINDOW, min_periods=CRASH_MINP).min())
    df["skew52"] = g["ret"].transform(
        lambda s: s.rolling(SKEW_WINDOW, min_periods=SKEW_MINP).skew())
    df["age"] = g.cumcount().astype(float)
    # tvl_to_mcap is precomputed in fundamentals_weekly.parquet (matches viz)
    if "tvl_to_mcap" not in df.columns:
        df["tvl_to_mcap"] = df["tvl_usd"] / df["mcap"]

    # rolling beta vs equal-weight market
    betas = []
    for sym, gg in df.groupby("symbol", sort=False):
        gg = gg.sort_values("week")
        cov = gg["ret"].rolling(BETA_WINDOW, min_periods=BETA_MINP).cov(gg["mkt_ret"])
        var = gg["mkt_ret"].rolling(BETA_WINDOW, min_periods=BETA_MINP).var()
        betas.append(pd.DataFrame({"symbol": sym, "week": gg["week"],
                                   "beta": cov / var}))
    df = df.merge(pd.concat(betas, ignore_index=True), on=["symbol", "week"], how="left")

    # --- profitable signed score (higher => long) ---
    df["s_VOLC"] = -df["vol"]
    df["s_MAXRET"] = -df["maxret"]
    df["s_CRASH8"] = -df["crash8"]
    df["s_SKEW52"] = -df["skew52"]
    df["s_NEWC"] = -df["age"]
    df["s_TVLC"] = -df["tvl_to_mcap"]
    df["s_BETA26"] = df["beta"]

    # --- cross-sectional z-score per week ---
    for fac in FACTORS:
        df[f"z_{fac}"] = df.groupby("week")[f"s_{fac}"].transform(cs_zscore)

    keep = (["week", "symbol", "ret", "fwd_ret", "vol", "mkt_ret"]
            + [f"z_{f}" for f in FACTORS])
    return df[keep].copy()


# ---------------------------------------------------------------------------
# Per-factor Information Coefficient + rolling IC weights
# ---------------------------------------------------------------------------
def factor_ic_timeseries(panel: pd.DataFrame) -> pd.DataFrame:
    """Weekly Spearman IC of each factor's z-score vs forward return."""
    rows = []
    for wk, g in panel.groupby("week"):
        gg = g.dropna(subset=["fwd_ret"])
        if len(gg) < 10:
            continue
        for fac in FACTORS:
            sub = gg.dropna(subset=[f"z_{fac}"])
            if len(sub) < 10:
                ic = np.nan
            else:
                ic = sub[f"z_{fac}"].rank().corr(sub["fwd_ret"].rank())
            rows.append({"week": wk, "factor": fac, "ic": ic})
    return pd.DataFrame(rows)


def rolling_ic_weights(ic_ts: pd.DataFrame,
                       lookback: int = IC_LOOKBACK) -> pd.DataFrame:
    """Per-week per-factor IC weight: positive part of the lagged rolling-mean
    IC (strictly out-of-sample — uses information through t-1)."""
    wide = ic_ts.pivot(index="week", columns="factor", values="ic").sort_index()
    roll = wide.rolling(lookback, min_periods=2).mean().shift(1)
    pos = roll.clip(lower=0.0)
    out = pos.reset_index().melt(id_vars="week", var_name="factor",
                                 value_name="ic_w")
    return out


# ---------------------------------------------------------------------------
# Regime-activated composite signal
# ---------------------------------------------------------------------------
def _activation_weights(regime_df: pd.DataFrame, mode: str,
                        factors: list[str]) -> pd.DataFrame:
    """Per-week per-factor activation multiplier a_k(regime).

    mode='hard': regime_df has [week, label]
    mode='soft': regime_df has [week, p_RiskOn, p_Neutral, p_RiskOff]
    Returns long frame [week, factor, activation].
    """
    rows = []
    if mode == "hard":
        for _, r in regime_df.iterrows():
            lbl = r["label"]
            for fac in factors:
                rows.append({"week": r["week"], "factor": fac,
                             "activation": ACTIVATION[fac][lbl]})
    elif mode == "soft":
        for _, r in regime_df.iterrows():
            for fac in factors:
                a = sum(r[f"p_{reg}"] * ACTIVATION[fac][reg] for reg in REGIMES)
                rows.append({"week": r["week"], "factor": fac, "activation": a})
    else:
        raise ValueError(mode)
    return pd.DataFrame(rows)


def build_composite(panel: pd.DataFrame, regime_df: pd.DataFrame, mode: str,
                    factors: list[str],
                    ic_w: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Combine the given factors' z-scores into one per-asset signal E.

    If `ic_w` is given (FAST sleeve), factor weight = activation * clip+(IC),
    which adapts to recent ranking power. If `ic_w` is None (SLOW sleeve), factor
    weight = activation only — the priced-risk premium is long-run, so IC (a
    weekly-ranking statistic) is deliberately not used.
    """
    act = _activation_weights(regime_df, mode, factors)
    if ic_w is not None:
        w = act.merge(ic_w, on=["week", "factor"], how="left")
        w["ic_w"] = w["ic_w"].fillna(0.0)
        tot_ic = w.groupby("week")["ic_w"].transform("sum")
        w.loc[tot_ic <= 0, "ic_w"] = 1.0  # equal-IC fallback
        w["combo"] = w["activation"] * w["ic_w"]
    else:
        w = act.copy()
        w["combo"] = w["activation"]

    norm = w.groupby("week")["combo"].transform("sum").replace(0, np.nan)
    w["fw"] = w["combo"] / norm

    fw_wide = w.pivot(index="week", columns="factor", values="fw")
    fw_map = fw_wide.to_dict(orient="index")

    parts = []
    for wk, g in panel.groupby("week"):
        weights = fw_map.get(wk)
        if weights is None:
            continue
        e = np.zeros(len(g))
        for fac in factors:
            fw = weights.get(fac, np.nan)
            if not np.isfinite(fw):
                continue
            z = g[f"z_{fac}"].to_numpy()
            e = e + np.where(np.isfinite(z), fw * z, 0.0)
        out = g[["week", "symbol", "fwd_ret", "vol"]].copy()
        out["E"] = e
        parts.append(out)
    comp = pd.concat(parts, ignore_index=True)
    return comp, fw_wide.reset_index()


# ---------------------------------------------------------------------------
# Portfolio construction
# ---------------------------------------------------------------------------
def _legs(g: pd.DataFrame) -> pd.DataFrame:
    """Assign +1 long / -1 short / 0 by top/bottom QUINTILE of E."""
    g = g.dropna(subset=["E"]).copy()
    if len(g) < 8:
        g["side"] = 0
        return g
    hi = g["E"].quantile(1 - QUINTILE)
    lo = g["E"].quantile(QUINTILE)
    g["side"] = 0
    g.loc[g["E"] >= hi, "side"] = 1
    g.loc[g["E"] <= lo, "side"] = -1
    return g


def _inverse_vol(g: pd.DataFrame) -> pd.DataFrame:
    """Inverse-vol weights within each leg, normalised to +1 / -1 gross."""
    g = g.copy()
    vol = g["vol"].fillna(g["vol"].median()).clip(lower=MIN_VOL_FLOOR)
    g["raw_w"] = 0.0
    for side, target in ((1, 1.0), (-1, -1.0)):
        m = g["side"] == side
        if m.sum() == 0:
            continue
        iv = 1.0 / vol[m]
        g.loc[m, "raw_w"] = target * (iv / iv.sum()).to_numpy()
    return g


def _cap_single_asset(g: pd.DataFrame) -> pd.DataFrame:
    """Iteratively clip |w| to MAX_ASSET_WEIGHT, redistributing within each leg."""
    g = g.copy()
    g["w"] = g["raw_w"]
    for side, target in ((1, 1.0), (-1, -1.0)):
        m = g["side"] == side
        if m.sum() == 0:
            continue
        for _ in range(20):
            w = g.loc[m, "w"]
            over = w.abs() > MAX_ASSET_WEIGHT + 1e-9
            if not over.any():
                break
            capped = w.copy()
            capped[over] = np.sign(capped[over]) * MAX_ASSET_WEIGHT
            free = ~over
            residual = target - capped[free].sum() - capped[over].sum()
            if free.sum() > 0 and abs(residual) > 1e-12:
                free_w = capped[free]
                scale = (free_w.sum() + residual) / free_w.sum() if free_w.sum() != 0 else 1.0
                capped[free] = free_w * scale
            g.loc[m, "w"] = capped
    return g


def _cap_cluster(g: pd.DataFrame) -> pd.DataFrame:
    """Pro-rata shrink long-leg clusters above MAX_CLUSTER_FRACTION."""
    g = g.copy()
    m = g["side"] == 1
    if m.sum() == 0 or g["cluster_id"].isna().all():
        return g
    long = g.loc[m]
    grp = long.groupby("cluster_id")["w"].sum()
    over = grp[grp > MAX_CLUSTER_FRACTION]
    if over.empty:
        return g
    for cid, tot in over.items():
        scale = MAX_CLUSTER_FRACTION / tot
        idx = long.index[long["cluster_id"] == cid]
        g.loc[idx, "w"] *= scale
    # renormalise long leg back to +1
    long_sum = g.loc[g["side"] == 1, "w"].sum()
    if long_sum > 0:
        g.loc[g["side"] == 1, "w"] /= long_sum
    return g


def _sleeve_raw_weights(comp: pd.DataFrame, network: pd.DataFrame,
                        rebal_every: int = 1) -> pd.DataFrame:
    """Per-week ±1-gross sleeve weights (quintile legs, inverse-vol, single-asset
    and cluster caps). If rebal_every > 1 the sleeve only re-forms every N weeks
    and holds its target weights in between — the low-turnover tilt mechanism."""
    comp = comp.merge(network[["week", "symbol", "cluster_id"]],
                      on=["week", "symbol"], how="left")
    weeks = sorted(comp["week"].unique())
    out = []
    held = None  # last formed target (Series indexed by symbol)
    for i, wk in enumerate(weeks):
        if i % rebal_every == 0 or held is None:
            g = _legs(comp[comp["week"] == wk])
            if (g["side"] != 0).sum() == 0:
                if held is None:
                    continue
            else:
                g = _inverse_vol(g)
                g = _cap_single_asset(g)
                g = _cap_cluster(g)
                held = g.set_index("symbol")["w"]
        cur = held.rename("w").reset_index()
        cur["week"] = wk
        out.append(cur[["week", "symbol", "w"]])
    return pd.concat(out, ignore_index=True)


def construct_two_sleeve(fast_comp: pd.DataFrame, slow_comp: pd.DataFrame,
                         network: pd.DataFrame,
                         gross_by_week: pd.Series) -> pd.DataFrame:
    """Blend the fast weekly sleeve and the slow priced-risk tilt, then apply
    regime gross-exposure scaling and the one-sided turnover budget."""
    wf = _sleeve_raw_weights(fast_comp, network, rebal_every=1)
    ws = _sleeve_raw_weights(slow_comp, network, rebal_every=SLOW_REBAL)
    wf = wf.rename(columns={"w": "w_fast"})
    ws = ws.rename(columns={"w": "w_slow"})

    blend = wf.merge(ws, on=["week", "symbol"], how="outer")
    blend["w_fast"] = blend["w_fast"].fillna(0.0)
    blend["w_slow"] = blend["w_slow"].fillna(0.0)
    blend["w_raw"] = FAST_GROSS * blend["w_fast"] + SLOW_GROSS * blend["w_slow"]

    clusters = network[["week", "symbol", "cluster_id"]]
    blend = blend.merge(clusters, on=["week", "symbol"], how="left")

    prev = None
    out = []
    for wk in sorted(blend["week"].unique()):
        g = blend[blend["week"] == wk].copy()
        g["w"] = g["w_raw"] * float(gross_by_week.get(wk, 1.0))
        if prev is not None:
            g = _apply_turnover(prev, g)
        prev = g.set_index("symbol")["w"]
        out.append(g[["week", "symbol", "cluster_id", "w_fast", "w_slow", "w"]])
    return pd.concat(out, ignore_index=True)


def _apply_turnover(prev_w: pd.Series, g: pd.DataFrame) -> pd.DataFrame:
    """Blend desired weights toward previous to respect one-sided turnover cap."""
    g = g.copy()
    desired = g.set_index("symbol")["w"]
    all_syms = desired.index.union(prev_w.index)
    d = desired.reindex(all_syms).fillna(0.0)
    p = prev_w.reindex(all_syms).fillna(0.0)
    turnover = 0.5 * (d - p).abs().sum()
    if turnover > TURNOVER_CAP and turnover > 0:
        alpha = TURNOVER_CAP / turnover
        blended = p + alpha * (d - p)
        g["w"] = g["symbol"].map(blended).fillna(0.0)
    return g


# ---------------------------------------------------------------------------
# Backtest + metrics
# ---------------------------------------------------------------------------
def backtest(weights: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Weekly gross/net PnL. weights formed at t earn fwd_ret (t -> t+1)."""
    fwd = panel[["week", "symbol", "fwd_ret"]]
    w = weights.merge(fwd, on=["week", "symbol"], how="left")
    rows = []
    prev = None
    for wk in sorted(w["week"].unique()):
        g = w[w["week"] == wk]
        pnl_gross = float((g["w"] * g["fwd_ret"].fillna(0.0)).sum())
        cur = g.set_index("symbol")["w"]
        if prev is None:
            turnover = 0.5 * cur.abs().sum()
        else:
            all_syms = cur.index.union(prev.index)
            turnover = 0.5 * (cur.reindex(all_syms).fillna(0)
                              - prev.reindex(all_syms).fillna(0)).abs().sum()
        prev = cur
        cost = turnover * COST_BPS / 1e4
        gross_exp = float(g["w"].abs().sum())
        rows.append({"week": wk, "pnl_gross": pnl_gross,
                     "turnover": turnover, "cost": cost,
                     "pnl_net": pnl_gross - cost, "gross_exposure": gross_exp})
    return pd.DataFrame(rows)


def perf_metrics(returns: pd.Series) -> dict:
    """Annualised metrics on a weekly return series."""
    r = returns.dropna()
    if len(r) < 5:
        return {k: float("nan") for k in
                ("ann_return", "ann_vol", "sharpe", "max_dd", "hit_rate", "weeks")}
    ann_ret = float(r.mean() * WEEKS_PER_YEAR)
    ann_vol = float(r.std(ddof=1) * np.sqrt(WEEKS_PER_YEAR))
    sharpe = ann_ret / ann_vol if ann_vol > 0 else float("nan")
    curve = (1.0 + r).cumprod()
    dd = (curve / curve.cummax() - 1.0).min()
    return {"ann_return": ann_ret, "ann_vol": ann_vol, "sharpe": float(sharpe),
            "max_dd": float(dd), "hit_rate": float((r > 0).mean()),
            "weeks": int(len(r))}


def split_is_oos(weeks: list[pd.Timestamp]) -> pd.Timestamp:
    """Return the first OOS week (last OOS_WEEKS weeks are out-of-sample)."""
    weeks = sorted(weeks)
    if len(weeks) <= OOS_WEEKS:
        return weeks[len(weeks) // 2]
    return weeks[-OOS_WEEKS]


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------
def benchmark_ew_market(panel: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight long-only market: mean forward return each week."""
    bm = (panel.dropna(subset=["fwd_ret"]).groupby("week")["fwd_ret"]
          .mean().rename("pnl_net").reset_index())
    return bm


def load_nalfp_benchmark() -> pd.DataFrame | None:
    """NALFP v3 net weekly PnL (if available) for comparison."""
    if not NALFP_PNL.exists():
        return None
    df = pd.read_parquet(NALFP_PNL)
    df["week"] = pd.to_datetime(df["week"])
    if "strategy" in df.columns:
        df = df[df["strategy"].astype(str).str.upper().str.contains("NALFP")]
    col = "pnl_net" if "pnl_net" in df.columns else (
        "pnl_gross" if "pnl_gross" in df.columns else None)
    if col is None or df.empty:
        return None
    return df[["week", col]].rename(columns={col: "pnl_net"})


# ---------------------------------------------------------------------------
# Top-level strategy runner (shared by Plan A and Plan B)
# ---------------------------------------------------------------------------
def run_strategy(regime_df: pd.DataFrame, mode: str, tag: str,
                 panel: pd.DataFrame | None = None) -> dict:
    """End-to-end: composite -> portfolio -> backtest -> metrics. Persists
    artifacts prefixed with `tag` and returns a metrics dict.

    regime_df must additionally carry a 'gross' column (per-week gross scale)."""
    if panel is None:
        panel = build_factor_scores()
    network = load_network()

    ic_ts = factor_ic_timeseries(panel)
    ic_w = rolling_ic_weights(ic_ts)

    # Fast sleeve: weekly, IC-weighted, VOLC/MAXRET/SKEW52.
    fast_comp, fast_fw = build_composite(panel, regime_df, mode,
                                         FAST_FACTORS, ic_w=ic_w)
    # Slow sleeve: priced-risk tilt, activation-only, BETA26/CRASH8/NEWC/TVLC.
    slow_comp, slow_fw = build_composite(panel, regime_df, mode,
                                         SLOW_FACTORS, ic_w=None)

    gross_by_week = regime_df.set_index("week")["gross"]
    weights = construct_two_sleeve(fast_comp, slow_comp, network, gross_by_week)
    fw_wide = fast_fw.merge(slow_fw, on="week", how="outer")

    pnl = backtest(weights, panel)

    # IS / OOS split
    weeks = sorted(pnl["week"].unique())
    first_oos = split_is_oos(weeks)
    is_mask = pnl["week"] < first_oos
    oos_mask = pnl["week"] >= first_oos

    metrics = {
        "tag": tag, "mode": mode,
        "full": perf_metrics(pnl["pnl_net"]),
        "is": perf_metrics(pnl.loc[is_mask, "pnl_net"]),
        "oos": perf_metrics(pnl.loc[oos_mask, "pnl_net"]),
        "first_oos_week": str(first_oos),
        "mean_turnover": float(pnl["turnover"].mean()),
    }

    # persist
    write_frame(ic_ts, f"{tag}_factor_ic_timeseries")
    write_frame(fw_wide, f"{tag}_factor_weights")
    write_frame(weights, f"{tag}_weekly_weights")
    write_frame(pnl, f"{tag}_weekly_pnl")
    write_json(metrics, f"{tag}_metrics.json")

    return metrics
