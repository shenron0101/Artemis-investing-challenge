#!/usr/bin/env python3
"""Factor-panel, regime, and portfolio engine for the ensemble strategy.

This module builds the weekly factor panel and the XGBoost regime panel from the
stage-03 (`03_nalfp_add`) data artifacts, and exposes the portfolio primitives
(`build_signal`, `construct_weights`, `backtest`) that `run.py` composes into the
sub-book ensemble.

Inputs  (read from `03_nalfp_add/artifacts/data/`):
    returns_weekly.parquet, price_mcap_panel_weekly.parquet,
    fundamentals_weekly.parquet, network_panel.parquet
Outputs (written to `06_factor_ensemble_strategy/artifacts/data/`):
    factor_panel.parquet, regime_panel.parquet
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
DATA03 = ROOT / "03_nalfp_add" / "artifacts" / "data"

OUT = STAGE / "artifacts"
DATA_OUT = OUT / "data"
DATA_OUT.mkdir(parents=True, exist_ok=True)

WEEKS_PER_YEAR = 52
OOS_WEEKS = 79
COST_BPS = 10.0
MIN_NAMES = 14
VOL_FLOOR = 0.05
MAX_ASSET_WEIGHT = 0.08
MAX_LONG_ASSET_WEIGHT = 0.20
MAX_SHORT_ASSET_WEIGHT = 0.065
LONG_WEIGHT_EXPONENT = 1.8
SHORT_WEIGHT_EXPONENT = 1.1
TURNOVER_CAP = 0.45
REGIME_STATES = ["RiskOff", "Neutral", "RiskOn"]
LONG_SHARE_BY_REGIME = {"RiskOn": 0.90, "Neutral": 0.75, "RiskOff": 0.70}
XGB_FEATURES = ["csd_z", "dbtc_z", "netent_z", "mktmom_z", "btcdom_z", "mktvol_z"]
XGB_PARAMS = {
    "objective": "multi:softprob",
    "num_class": 3,
    "n_estimators": 120,
    "max_depth": 2,
    "learning_rate": 0.05,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_lambda": 3.0,
    "eval_metric": "mlogloss",
    "random_state": 42,
    "n_jobs": 1,
}

# The active factor set covers the factors called out in 05_factor_viz/RESULTS.md.
FACTOR_ORDER = [
    "VolC",
    "MAXRET",
    "CRASH8",
    "BETA26",
    "TVLC",
    "SKEW52",
    "NEWC",
    "RMOM1w",
    "RMOM2w",
    "SMBC",
    "NetRel",
    "MomC",
    "NetMom",
    "FunC",
]


@dataclass(frozen=True)
class Candidate:
    name: str
    sleeve_core: float
    sleeve_priced: float
    sleeve_mispricing: float
    sleeve_legacy: float
    ic_blend: float
    top_frac: float
    gross_risk_on: float
    gross_neutral: float
    gross_risk_off: float
    slow_factor_boost: float


def read_parquet(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA03 / name)


def cs_zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=1)
    if not np.isfinite(sd) or sd <= 0:
        return s * 0.0
    return (s - s.mean()) / sd


def rolling_z(s: pd.Series, window: int = 52, minp: int = 12) -> pd.Series:
    mu = s.rolling(window, min_periods=minp).mean()
    sd = s.rolling(window, min_periods=minp).std().replace(0, np.nan)
    return (s - mu) / sd


def load_base_panel() -> pd.DataFrame:
    returns = read_parquet("returns_weekly.parquet")
    mcap = read_parquet("price_mcap_panel_weekly.parquet")[["week", "symbol", "mcap"]]
    fundamentals = read_parquet("fundamentals_weekly.parquet")
    network = pd.read_parquet(DATA03 / "network_panel.parquet")[
        ["week", "symbol", "cluster_id", "within_cluster_mom", "cross_cluster_rel", "network_entropy"]
    ]

    for df in (returns, mcap, fundamentals, network):
        df["week"] = pd.to_datetime(df["week"])
        df["symbol"] = df["symbol"].astype(str).str.upper()

    df = returns.merge(mcap, on=["week", "symbol"], how="left")
    df = df.merge(fundamentals, on=["week", "symbol"], how="left")
    df = df.merge(network, on=["week", "symbol"], how="left")
    df = df.sort_values(["symbol", "week"]).reset_index(drop=True)
    df["fwd_ret"] = df.groupby("symbol")["ret"].shift(-1)
    return df


def build_factor_panel() -> pd.DataFrame:
    df = load_base_panel()
    market = df.groupby("week")["ret"].mean().rename("mkt_ret")
    df = df.merge(market, on="week", how="left")
    g = df.groupby("symbol", sort=False)

    df["vol4"] = g["ret"].transform(lambda s: s.rolling(4, min_periods=4).std())
    df["maxret4"] = g["ret"].transform(lambda s: s.rolling(4, min_periods=4).max())
    df["minret8"] = g["ret"].transform(lambda s: s.rolling(8, min_periods=6).min())
    df["skew52"] = g["ret"].transform(lambda s: s.rolling(52, min_periods=26).skew())
    df["mom4"] = g["ret"].transform(lambda s: (1 + s).rolling(4, min_periods=3).apply(np.prod, raw=True) - 1)
    df["ret2"] = g["ret"].transform(lambda s: (1 + s).rolling(2, min_periods=2).apply(np.prod, raw=True) - 1)
    df["age_weeks"] = g.cumcount().astype(float)
    df["log_mcap"] = np.log(df["mcap"].replace(0, np.nan))
    if "fees_to_mcap" not in df:
        df["fees_to_mcap"] = df["fees_usd"] / df["mcap"]
    if "tvl_to_mcap" not in df:
        df["tvl_to_mcap"] = df["tvl_usd"] / df["mcap"]

    beta_parts = []
    for sym, gg in df.groupby("symbol", sort=False):
        gg = gg.sort_values("week")
        cov = gg["ret"].rolling(26, min_periods=13).cov(gg["mkt_ret"])
        var = gg["mkt_ret"].rolling(26, min_periods=13).var()
        beta_parts.append(pd.DataFrame({"week": gg["week"], "symbol": sym, "beta26": cov / var}))
    df = df.merge(pd.concat(beta_parts, ignore_index=True), on=["week", "symbol"], how="left")

    # Profitable score direction per 05_factor_viz/RESULTS.md.
    df["raw_VolC"] = -df["vol4"]
    df["raw_MAXRET"] = -df["maxret4"]
    df["raw_CRASH8"] = -df["minret8"]
    df["raw_BETA26"] = df["beta26"]
    df["raw_TVLC"] = -df["tvl_to_mcap"]
    df["raw_SKEW52"] = df["skew52"]
    df["raw_NEWC"] = -df["age_weeks"]
    df["raw_RMOM1w"] = df["ret"] / df["vol4"].replace(0, np.nan)
    df["raw_RMOM2w"] = df["ret2"] / df["vol4"].replace(0, np.nan)
    df["raw_SMBC"] = -df["log_mcap"]
    df["raw_NetRel"] = df["cross_cluster_rel"]
    df["raw_MomC"] = df["mom4"]
    df["raw_NetMom"] = df["within_cluster_mom"]
    df["raw_FunC"] = df["fees_to_mcap"]

    for fac in FACTOR_ORDER:
        df[f"z_{fac}"] = df.groupby("week")[f"raw_{fac}"].transform(cs_zscore)

    keep = [
        "week",
        "symbol",
        "ret",
        "fwd_ret",
        "mcap",
        "cluster_id",
        "network_entropy",
        "vol4",
        "mkt_ret",
    ] + [f"z_{f}" for f in FACTOR_ORDER]
    out = df[keep].copy()
    out = out[out.groupby("week")["symbol"].transform("count") >= MIN_NAMES]
    out.to_parquet(DATA_OUT / "factor_panel.parquet", index=False)
    return out


def build_regime_panel(
    panel: pd.DataFrame,
    first_oos: pd.Timestamp | None = None,
    *,
    persist: bool = True,
) -> pd.DataFrame:
    mcap = read_parquet("price_mcap_panel_weekly.parquet")
    mcap["week"] = pd.to_datetime(mcap["week"])
    mcap["symbol"] = mcap["symbol"].astype(str).str.upper()

    weekly = panel.groupby("week").agg(
        csd=("ret", "std"),
        mkt_ret=("ret", "mean"),
        network_entropy=("network_entropy", "mean"),
    )
    total_mcap = mcap.groupby("week")["mcap"].sum()
    btc_mcap = mcap[mcap["symbol"] == "BTC"].set_index("week")["mcap"]
    weekly["btc_dom"] = btc_mcap / total_mcap
    weekly["dbtc_dom"] = weekly["btc_dom"] - weekly["btc_dom"].shift(4)
    weekly["mktmom4"] = weekly["mkt_ret"].rolling(4, min_periods=2).sum()
    weekly["mktvol8"] = weekly["mkt_ret"].rolling(8, min_periods=4).std()

    obs_cols = ["csd", "dbtc_dom", "network_entropy", "mktmom4", "btc_dom", "mktvol8"]
    for col in obs_cols:
        weekly[f"{col}_z"] = rolling_z(weekly[col]).shift(1)

    # Network entropy exists only where the stage-00 network panel has enough
    # coverage. Treat missing entropy as "no extra structural information"
    # instead of dropping the older regime history.
    weekly["network_entropy_z"] = weekly["network_entropy_z"].fillna(0.0)

    target_score = (
        rolling_z(weekly["mktmom4"], minp=12)
        - 0.50 * rolling_z(weekly["csd"], minp=12)
        - 0.25 * rolling_z(weekly["dbtc_dom"], minp=12)
    )
    valid_score = target_score.dropna()
    if len(valid_score) >= 12:
        lo, hi = valid_score.quantile([1 / 3, 2 / 3])
    else:
        lo, hi = -0.35, 0.35
    weekly["target_regime"] = np.select(
        [target_score <= lo, target_score >= hi],
        ["RiskOff", "RiskOn"],
        default="Neutral",
    )

    obs = weekly.rename(
        columns={
            "dbtc_dom_z": "dbtc_z",
            "network_entropy_z": "netent_z",
            "mktmom4_z": "mktmom_z",
            "btc_dom_z": "btcdom_z",
            "mktvol8_z": "mktvol_z",
        }
    )
    obs = obs.dropna(subset=["csd_z", "dbtc_z", "mktmom_z", "btcdom_z", "mktvol_z", "target_regime"])
    if first_oos is None:
        first_oos = pd.to_datetime(obs.index[int(len(obs) * 0.70)])
    else:
        first_oos = pd.to_datetime(first_oos)

    label_to_int = {name: i for i, name in enumerate(REGIME_STATES)}
    train = obs[obs.index < first_oos].copy()
    predictable = obs.copy()
    x_all = predictable[XGB_FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    x_train = train[XGB_FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_train = train["target_regime"].map(label_to_int).astype(int)

    rows = []
    if len(train) >= 30 and y_train.nunique() == 3:
        clf = XGBClassifier(**XGB_PARAMS)
        clf.fit(x_train, y_train)
        proba = clf.predict_proba(x_all)
        if proba.shape[1] != len(REGIME_STATES):
            fixed = np.zeros((len(proba), len(REGIME_STATES)))
            for i, cls in enumerate(getattr(clf, "classes_", [])):
                fixed[:, int(cls)] = proba[:, i]
            proba = fixed
    else:
        # Very short samples cannot support a supervised three-class model; use
        # neutral probabilities while retaining the train/test split metadata.
        proba = np.tile(np.array([[0.0, 1.0, 0.0]]), (len(x_all), 1))

    for wk, probs in zip(x_all.index, proba):
        probs = np.asarray(probs, dtype=float)
        if not np.isfinite(probs).all() or probs.sum() <= 0:
            probs = np.array([0.0, 1.0, 0.0])
        probs = probs / probs.sum()
        pred = REGIME_STATES[int(np.argmax(probs))]
        rows.append(
            {
                "week": wk,
                "p_RiskOff": float(probs[0]),
                "p_Neutral": float(probs[1]),
                "p_RiskOn": float(probs[2]),
                "predicted_regime": pred,
                "target_regime": obs.loc[wk, "target_regime"],
                "split": "test" if wk >= first_oos else "train",
            }
        )

    regime = pd.DataFrame(rows)
    all_weeks = pd.DataFrame({"week": sorted(panel["week"].unique())})
    regime = all_weeks.merge(regime, on="week", how="left")
    for c in ["p_RiskOff", "p_Neutral", "p_RiskOn"]:
        regime[c] = regime[c].fillna(0.0)
    empty = regime[["p_RiskOff", "p_Neutral", "p_RiskOn"]].sum(axis=1) == 0
    regime.loc[empty, "p_Neutral"] = 1.0
    regime["label"] = regime[["p_RiskOff", "p_Neutral", "p_RiskOn"]].idxmax(axis=1).str.replace("p_", "", regex=False)
    weekly_meta = weekly.reset_index().drop(columns=["target_regime"], errors="ignore")
    regime = regime.merge(weekly_meta, on="week", how="left")
    fallback_split = pd.Series(np.where(regime["week"] >= first_oos, "test", "train"), index=regime.index)
    regime["split"] = regime["split"].fillna(fallback_split)
    regime["predicted_regime"] = regime["predicted_regime"].fillna(regime["label"])
    if persist:
        regime.to_csv(DATA_OUT / "regime_panel.csv", index=False)
        regime.to_parquet(DATA_OUT / "regime_panel.parquet", index=False)
    return regime


def build_signal(panel: pd.DataFrame, factor_weights: pd.DataFrame) -> pd.DataFrame:
    fw = factor_weights.set_index("week")
    parts = []
    for wk, g in panel.groupby("week", sort=True):
        if wk not in fw.index:
            continue
        signal = np.zeros(len(g), dtype=float)
        for fac in FACTOR_ORDER:
            z = g[f"z_{fac}"].to_numpy()
            signal += float(fw.loc[wk, fac]) * np.where(np.isfinite(z), z, 0.0)
        out = g[["week", "symbol", "fwd_ret", "vol4", "cluster_id"]].copy()
        out["signal"] = signal
        parts.append(out)
    return pd.concat(parts, ignore_index=True)


def gross_for_week(candidate: Candidate, r: pd.Series) -> float:
    return (
        float(r["p_RiskOn"]) * candidate.gross_risk_on
        + float(r["p_Neutral"]) * candidate.gross_neutral
        + float(r["p_RiskOff"]) * candidate.gross_risk_off
    )


def long_share_for_week(r: pd.Series) -> float:
    return sum(float(r[f"p_{state}"]) * LONG_SHARE_BY_REGIME[state] for state in REGIME_STATES)


def leg_count(n_assets: int, top_frac: float, target: float, cap: float) -> int:
    by_fraction = int(math.ceil(n_assets * top_frac))
    by_capacity = int(math.ceil(target / cap)) if cap > 0 else by_fraction
    return min(n_assets, max(1, by_fraction, by_capacity))


def capped_positive_allocation(raw: pd.Series, target: float, cap: float) -> pd.Series:
    raw = raw.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    out = pd.Series(0.0, index=raw.index, dtype=float)
    if target <= 0 or raw.empty:
        return out

    feasible_target = min(float(target), float(cap) * len(raw))
    remaining = feasible_target
    uncapped = list(raw.index)
    while remaining > 1e-12 and uncapped:
        scores = raw.loc[uncapped]
        if scores.sum() <= 0:
            scores = pd.Series(1.0, index=uncapped)
        proposed = remaining * scores / scores.sum()
        capped = proposed[proposed >= cap - 1e-12]
        if capped.empty:
            out.loc[uncapped] += proposed
            remaining = 0.0
            break
        out.loc[capped.index] = cap
        remaining -= cap * len(capped)
        uncapped = [idx for idx in uncapped if idx not in set(capped.index)]

    if remaining > 1e-9 and uncapped:
        out.loc[uncapped] += remaining / len(uncapped)
    return out


def construct_weights(signal_panel: pd.DataFrame, regime: pd.DataFrame, candidate: Candidate) -> pd.DataFrame:
    regime_idx = regime.set_index("week")
    gross_map = regime_idx.apply(lambda r: gross_for_week(candidate, r), axis=1)
    long_share_map = regime_idx.apply(long_share_for_week, axis=1)
    previous = None
    rows = []
    for wk, g in signal_panel.groupby("week", sort=True):
        g = g.dropna(subset=["signal"]).copy()
        if len(g) < MIN_NAMES:
            continue
        gross = float(gross_map.get(wk, candidate.gross_neutral))
        long_share = float(long_share_map.get(wk, LONG_SHARE_BY_REGIME["Neutral"]))
        long_target = gross * long_share
        short_target = gross * (1 - long_share)
        long_n = leg_count(len(g), candidate.top_frac, long_target, MAX_LONG_ASSET_WEIGHT)
        short_n = leg_count(len(g), candidate.top_frac, short_target, MAX_SHORT_ASSET_WEIGHT)

        ordered = g.sort_values("signal")
        long_symbols = ordered.tail(long_n)["symbol"]
        short_symbols = ordered.head(short_n)["symbol"]
        g["side"] = 0
        g.loc[g["symbol"].isin(long_symbols), "side"] = 1
        g.loc[g["symbol"].isin(short_symbols), "side"] = -1
        if (g["side"] != 0).sum() == 0:
            continue

        g["w"] = 0.0
        vol = g["vol4"].fillna(g["vol4"].median()).clip(lower=VOL_FLOOR)
        long_mask = g["side"] == 1
        if long_mask.any():
            threshold = g.loc[long_mask, "signal"].min()
            raw = ((g.loc[long_mask, "signal"] - threshold + 1e-6) ** LONG_WEIGHT_EXPONENT) / vol[long_mask]
            g.loc[long_mask, "w"] = capped_positive_allocation(raw, long_target, MAX_LONG_ASSET_WEIGHT).to_numpy()

        short_mask = g["side"] == -1
        if short_mask.any():
            threshold = g.loc[short_mask, "signal"].max()
            raw = ((threshold - g.loc[short_mask, "signal"] + 1e-6) ** SHORT_WEIGHT_EXPONENT) / vol[short_mask]
            g.loc[short_mask, "w"] = -capped_positive_allocation(raw, short_target, MAX_SHORT_ASSET_WEIGHT).to_numpy()

        desired = g.set_index("symbol")["w"]
        if previous is not None:
            all_symbols = desired.index.union(previous.index)
            d = desired.reindex(all_symbols).fillna(0.0)
            p = previous.reindex(all_symbols).fillna(0.0)
            turnover = 0.5 * (d - p).abs().sum()
            if turnover > TURNOVER_CAP and turnover > 0:
                alpha = TURNOVER_CAP / turnover
                desired = p + alpha * (d - p)
                g["w"] = g["symbol"].map(desired).fillna(0.0)
        previous = g.set_index("symbol")["w"]
        rows.append(g[["week", "symbol", "cluster_id", "signal", "side", "w"]])
    return pd.concat(rows, ignore_index=True)


def backtest(weights: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    fwd = panel[["week", "symbol", "fwd_ret"]]
    w = weights.merge(fwd, on=["week", "symbol"], how="left")
    previous = None
    rows = []
    for wk, g in w.groupby("week", sort=True):
        current = g.set_index("symbol")["w"]
        if previous is None:
            turnover = 0.5 * current.abs().sum()
        else:
            all_symbols = current.index.union(previous.index)
            turnover = 0.5 * (
                current.reindex(all_symbols).fillna(0.0) - previous.reindex(all_symbols).fillna(0.0)
            ).abs().sum()
        previous = current
        gross = float(current.abs().sum())
        long_gross = float(current.clip(lower=0.0).sum())
        short_gross = float(-current.clip(upper=0.0).sum())
        pnl_gross = float((g["w"] * g["fwd_ret"].fillna(0.0)).sum())
        cost = turnover * COST_BPS / 1e4
        rows.append(
            {
                "week": wk,
                "pnl_gross": pnl_gross,
                "turnover": turnover,
                "cost": cost,
                "pnl_net": pnl_gross - cost,
                "gross_exposure": gross,
                "long_gross": long_gross,
                "short_gross": short_gross,
                "net_exposure": long_gross - short_gross,
                "n_assets": int((g["w"].abs() > 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def load_panels(*, rebuild: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (factor_panel, regime_panel), building them from stage-03 data if
    they are not already present in this stage's artifacts/data directory."""
    factor_path = DATA_OUT / "factor_panel.parquet"
    regime_path = DATA_OUT / "regime_panel.parquet"
    if rebuild or not factor_path.exists() or not regime_path.exists():
        print("Building factor panel from 03_nalfp_add artifacts...", flush=True)
        panel = build_factor_panel()
        weeks = sorted(panel["week"].dropna().unique())
        first_oos = pd.to_datetime(weeks[-OOS_WEEKS])
        print("Building XGBoost regime panel...", flush=True)
        build_regime_panel(panel, first_oos=first_oos)
    panel = pd.read_parquet(factor_path)
    regime = pd.read_parquet(regime_path)
    panel["week"] = pd.to_datetime(panel["week"])
    regime["week"] = pd.to_datetime(regime["week"])
    return panel, regime
