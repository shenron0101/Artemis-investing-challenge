#!/usr/bin/env python3
"""
Stage 14 - XGBoost regime-aware weekly crypto factor strategy.

This script uses the factors summarized in 12_factor_viz/RESULTS.md, detects
market regimes with a chronological train/test XGBoost classifier, optimizes
three weekly long/short strategy variants in-sample, and writes an embedded-plot
RESULTS.md.
"""
from __future__ import annotations

import json
import logging
import math
import warnings
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import accuracy_score, f1_score, log_loss
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
DATA09 = ROOT / "09_nalfp_add" / "artifacts" / "data"
DATA08 = ROOT / "08_nalfp" / "artifacts" / "data"

OUT = STAGE / "artifacts"
DATA_OUT = OUT / "data"
FIG_OUT = OUT / "figures"
MANIFEST_OUT = OUT / "manifests"
for d in (DATA_OUT, FIG_OUT, MANIFEST_OUT):
    d.mkdir(parents=True, exist_ok=True)

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
NN_PARAMS = {
    "hidden_layer_sizes": (24, 8),
    "activation": "relu",
    "solver": "adam",
    "alpha": 0.002,
    "learning_rate_init": 0.002,
    "max_iter": 500,
    "early_stopping": True,
    "validation_fraction": 0.20,
    "n_iter_no_change": 20,
    "random_state": 42,
}

# The active factor set intentionally covers the factors called out in
# 12_factor_viz/RESULTS.md. Unsupported factors are included with small base
# sleeves so the optimizer can use their realized IC only when they help.
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
NN_FEATURES = [f"z_{fac}" for fac in FACTOR_ORDER] + [f"p_{state}" for state in REGIME_STATES]

CORE = ["VolC", "MAXRET"]
PRICED = ["CRASH8", "BETA26", "TVLC", "SKEW52", "NEWC"]
MISPRICING = ["RMOM1w", "RMOM2w", "SMBC", "NetRel"]
LEGACY = ["MomC", "NetMom", "FunC"]

# Economic regime gating. Values are not fitted; the grid search chooses how
# much capital to allocate to factor sleeves, while this matrix encodes the
# mechanisms described in RESULTS.md.
ACTIVATION = {
    "VolC": {"RiskOn": 0.75, "Neutral": 1.00, "RiskOff": 1.40},
    "MAXRET": {"RiskOn": 1.35, "Neutral": 1.00, "RiskOff": 0.95},
    "CRASH8": {"RiskOn": 1.00, "Neutral": 1.35, "RiskOff": 1.10},
    "BETA26": {"RiskOn": 1.65, "Neutral": 0.80, "RiskOff": 0.15},
    "TVLC": {"RiskOn": 0.60, "Neutral": 1.00, "RiskOff": 1.45},
    "SKEW52": {"RiskOn": 1.45, "Neutral": 0.90, "RiskOff": 0.30},
    "NEWC": {"RiskOn": 1.35, "Neutral": 0.80, "RiskOff": 0.20},
    "RMOM1w": {"RiskOn": 1.20, "Neutral": 1.00, "RiskOff": 0.80},
    "RMOM2w": {"RiskOn": 1.15, "Neutral": 1.00, "RiskOff": 0.85},
    "SMBC": {"RiskOn": 1.40, "Neutral": 0.80, "RiskOff": 0.20},
    "NetRel": {"RiskOn": 1.25, "Neutral": 1.05, "RiskOff": 0.45},
    "MomC": {"RiskOn": 0.60, "Neutral": 0.25, "RiskOff": 0.10},
    "NetMom": {"RiskOn": 0.50, "Neutral": 0.25, "RiskOff": 0.10},
    "FunC": {"RiskOn": 0.60, "Neutral": 0.60, "RiskOff": 0.60},
}


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
    return pd.read_parquet(DATA09 / name)


def cs_zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=1)
    if not np.isfinite(sd) or sd <= 0:
        return s * 0.0
    return (s - s.mean()) / sd


def rolling_z(s: pd.Series, window: int = 52, minp: int = 12) -> pd.Series:
    mu = s.rolling(window, min_periods=minp).mean()
    sd = s.rolling(window, min_periods=minp).std().replace(0, np.nan)
    return (s - mu) / sd


def perf_metrics(r: pd.Series) -> dict:
    x = r.dropna()
    if len(x) < 5:
        return {
            "ann_return": np.nan,
            "ann_vol": np.nan,
            "sharpe": np.nan,
            "max_dd": np.nan,
            "calmar": np.nan,
            "hit_rate": np.nan,
            "weeks": int(len(x)),
        }
    ann_ret = float(x.mean() * WEEKS_PER_YEAR)
    ann_vol = float(x.std(ddof=1) * math.sqrt(WEEKS_PER_YEAR))
    sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan
    curve = (1 + x).cumprod()
    dd = curve / curve.cummax() - 1
    max_dd = float(dd.min())
    calmar = ann_ret / abs(max_dd) if max_dd < 0 else np.nan
    return {
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": float(sharpe),
        "max_dd": max_dd,
        "calmar": float(calmar),
        "hit_rate": float((x > 0).mean()),
        "weeks": int(len(x)),
    }


def load_base_panel() -> pd.DataFrame:
    returns = read_parquet("returns_weekly.parquet")
    mcap = read_parquet("price_mcap_panel_weekly.parquet")[["week", "symbol", "mcap"]]
    fundamentals = read_parquet("fundamentals_weekly.parquet")
    network = pd.read_parquet(DATA08 / "network_panel.parquet")[
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

    # Profitable score direction per RESULTS.md.
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


def factor_ic(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for wk, g in panel.dropna(subset=["fwd_ret"]).groupby("week"):
        for fac in FACTOR_ORDER:
            sub = g.dropna(subset=[f"z_{fac}", "fwd_ret"])
            ic = np.nan
            if len(sub) >= 12:
                ic = sub[f"z_{fac}"].rank().corr(sub["fwd_ret"].rank())
            rows.append({"week": wk, "factor": fac, "ic": ic})
    out = pd.DataFrame(rows)
    out.to_csv(DATA_OUT / "factor_ic_timeseries.csv", index=False)
    out.to_parquet(DATA_OUT / "factor_ic_timeseries.parquet", index=False)
    return out


def regime_classification_metrics(regime: pd.DataFrame) -> dict[str, dict[str, float]]:
    out = {}
    labeled = regime.dropna(subset=["target_regime", "predicted_regime"])
    for split, g in labeled.groupby("split"):
        if g["target_regime"].nunique() < 2:
            continue
        labels = REGIME_STATES
        y_true = g["target_regime"].map({name: i for i, name in enumerate(labels)}).astype(int)
        y_pred = g["predicted_regime"].map({name: i for i, name in enumerate(labels)}).astype(int)
        probs = g[[f"p_{name}" for name in labels]].clip(1e-9, 1.0)
        out[str(split)] = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
            "log_loss": float(log_loss(y_true, probs, labels=list(range(len(labels))))),
            "weeks": int(len(g)),
        }
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

    # Network entropy exists only where the stage-08 network panel has enough
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


def base_factor_weights(candidate: Candidate) -> dict[str, float]:
    weights = {}

    def assign(group: list[str], sleeve: float) -> None:
        if not group or sleeve <= 0:
            return
        for fac in group:
            weights[fac] = sleeve / len(group)

    assign(CORE, candidate.sleeve_core)
    assign(PRICED, candidate.sleeve_priced * candidate.slow_factor_boost)
    assign(MISPRICING, candidate.sleeve_mispricing)
    assign(LEGACY, candidate.sleeve_legacy)
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items() if total > 0}


def rolling_ic_weight(ic_ts: pd.DataFrame) -> pd.DataFrame:
    wide = ic_ts.pivot(index="week", columns="factor", values="ic").sort_index()
    # Positive part rewards recent realized ranking power; a small floor prevents
    # the priced-risk sleeve from being eliminated by a noisy short IC window.
    pos = wide.rolling(8, min_periods=2).mean().shift(1).clip(lower=0.0)
    pos = pos.fillna(0.0)
    return pos


def weekly_factor_weights(
    candidate: Candidate,
    regime: pd.DataFrame,
    ic_wide: pd.DataFrame,
) -> pd.DataFrame:
    base = base_factor_weights(candidate)
    rows = []
    for _, r in regime.iterrows():
        raw = {}
        for fac in FACTOR_ORDER:
            b = base.get(fac, 0.0)
            if b <= 0:
                raw[fac] = 0.0
                continue
            activation = sum(float(r[f"p_{state}"]) * ACTIVATION[fac][state] for state in REGIME_STATES)
            ic = 0.0
            if r["week"] in ic_wide.index and fac in ic_wide:
                ic = float(ic_wide.loc[r["week"], fac])
            ic_multiplier = (1 - candidate.ic_blend) + candidate.ic_blend * (0.25 + max(ic, 0.0))
            raw[fac] = b * activation * ic_multiplier
        total = sum(raw.values())
        if total <= 0:
            raw = base.copy()
            total = sum(raw.values())
        row = {"week": r["week"]}
        row.update({fac: raw.get(fac, 0.0) / total for fac in FACTOR_ORDER})
        rows.append(row)
    return pd.DataFrame(rows)


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


def build_neural_network_signal(
    panel: pd.DataFrame,
    regime: pd.DataFrame,
    first_oos: pd.Timestamp,
    *,
    persist: bool = True,
) -> pd.DataFrame:
    """Predict next-week returns with an in-sample MLP using XGBoost regimes."""
    regime_probs = regime[["week", "p_RiskOff", "p_Neutral", "p_RiskOn"]].copy()
    df = panel.merge(regime_probs, on="week", how="left")
    for col in ["p_RiskOff", "p_Neutral", "p_RiskOn"]:
        df[col] = df[col].fillna(0.0)
    empty = df[["p_RiskOff", "p_Neutral", "p_RiskOn"]].sum(axis=1) == 0
    df.loc[empty, "p_Neutral"] = 1.0

    x = df[NN_FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y = df["fwd_ret"].replace([np.inf, -np.inf], np.nan)
    train_mask = (df["week"] < pd.to_datetime(first_oos)) & y.notna()
    if train_mask.sum() < 200:
        signal = np.zeros(len(df), dtype=float)
    else:
        x_train = x.loc[train_mask].copy()
        y_train = y.loc[train_mask].clip(y.loc[train_mask].quantile(0.01), y.loc[train_mask].quantile(0.99))
        mu = x_train.mean()
        sd = x_train.std(ddof=0).replace(0, 1.0)
        x_train_scaled = (x_train - mu) / sd
        x_train_scaled.index = pd.to_datetime(df.loc[train_mask, "week"])
        x_scaled = (x - mu) / sd
        model = MLPRegressor(**NN_PARAMS)
        model.fit(x_train_scaled, y_train)
        signal = model.predict(x_scaled)

    out = df[["week", "symbol", "fwd_ret", "vol4", "cluster_id"]].copy()
    out["signal"] = signal
    if persist:
        out.to_csv(DATA_OUT / "neural_network_signals.csv", index=False)
        out.to_parquet(DATA_OUT / "neural_network_signals.parquet", index=False)
    return out


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


def run_candidate(
    candidate: Candidate,
    panel: pd.DataFrame,
    regime: pd.DataFrame,
    ic_wide: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fw = weekly_factor_weights(candidate, regime, ic_wide)
    signal = build_signal(panel, fw)
    weights = construct_weights(signal, regime, candidate)
    pnl = backtest(weights, panel)
    return pnl, weights, fw


def candidate_grid() -> list[Candidate]:
    specs = [
        # name, sleeves core/priced/mispricing/legacy, ic, top, gross on/neutral/off, slow boost
        ("defensive_a", (0.55, 0.20, 0.20, 0.05), 0.75, 0.20, (0.80, 0.68, 0.48), 0.90),
        ("defensive_b", (0.50, 0.20, 0.25, 0.05), 0.75, 0.30, (0.85, 0.72, 0.52), 0.90),
        ("core_alpha_a", (0.45, 0.25, 0.25, 0.05), 0.75, 0.20, (0.92, 0.78, 0.55), 1.00),
        ("core_alpha_b", (0.45, 0.20, 0.30, 0.05), 0.00, 0.30, (0.96, 0.82, 0.58), 1.00),
        ("balanced_a", (0.35, 0.35, 0.25, 0.05), 0.75, 0.20, (1.00, 0.85, 0.60), 1.00),
        ("balanced_b", (0.30, 0.35, 0.30, 0.05), 0.00, 0.30, (1.02, 0.88, 0.62), 1.00),
        ("mispricing_a", (0.30, 0.25, 0.40, 0.05), 0.75, 0.20, (0.96, 0.82, 0.56), 1.00),
        ("mispricing_b", (0.25, 0.25, 0.45, 0.05), 0.00, 0.30, (1.00, 0.86, 0.60), 1.00),
        ("priced_a", (0.25, 0.50, 0.20, 0.05), 0.25, 0.20, (1.04, 0.90, 0.62), 1.15),
        ("priced_b", (0.20, 0.55, 0.20, 0.05), 0.00, 0.30, (1.08, 0.94, 0.65), 1.20),
        ("return_a", (0.20, 0.60, 0.15, 0.05), 0.00, 0.20, (1.10, 0.96, 0.66), 1.25),
        ("return_b", (0.15, 0.65, 0.15, 0.05), 0.25, 0.30, (1.12, 0.98, 0.68), 1.30),
    ]
    rows = []
    for name, sleeves, ic_blend, top_frac, gross, slow_boost in specs:
        rows.append(
            Candidate(
                name=name,
                sleeve_core=sleeves[0],
                sleeve_priced=sleeves[1],
                sleeve_mispricing=sleeves[2],
                sleeve_legacy=sleeves[3],
                ic_blend=ic_blend,
                top_frac=top_frac,
                gross_risk_on=gross[0],
                gross_neutral=gross[1],
                gross_risk_off=gross[2],
                slow_factor_boost=slow_boost,
            )
        )
    return rows


def choose_variants(results: pd.DataFrame) -> dict[str, str]:
    valid = results.replace([np.inf, -np.inf], np.nan).dropna(subset=["is_sharpe", "is_ann_return"])
    # Remove catastrophic IS drawdowns from the optimizer. Crypto is volatile,
    # but a strategy requiring a near wipeout is not a usable weekly rebalance.
    valid = valid[valid["is_max_dd"] > -0.85].copy()
    if valid.empty:
        valid = results.copy()

    used = set()
    sharpe_name = valid.sort_values(["is_sharpe", "is_ann_return"], ascending=False).iloc[0]["candidate"]
    used.add(sharpe_name)

    return_pool = valid[~valid["candidate"].isin(used)]
    if return_pool.empty:
        return_pool = valid
    return_name = return_pool.sort_values(["is_ann_return", "is_sharpe"], ascending=False).iloc[0]["candidate"]
    used.add(return_name)

    v = valid.copy()
    v["sharpe_rank"] = v["is_sharpe"].rank(pct=True)
    v["return_rank"] = v["is_ann_return"].rank(pct=True)
    v["dd_rank"] = v["is_max_dd"].rank(pct=True)  # less negative is higher
    v["balanced_score"] = 0.45 * v["sharpe_rank"] + 0.45 * v["return_rank"] + 0.10 * v["dd_rank"]
    middle_pool = v[~v["candidate"].isin(used)]
    if middle_pool.empty:
        middle_pool = v
    middle_name = middle_pool.sort_values(["balanced_score", "is_sharpe"], ascending=False).iloc[0]["candidate"]

    return {
        "Sharpe Optimized": sharpe_name,
        "Return Optimized": return_name,
        "Balanced": middle_name,
    }


def benchmark_returns(panel: pd.DataFrame) -> pd.DataFrame:
    ew = panel.dropna(subset=["fwd_ret"]).groupby("week")["fwd_ret"].mean().rename("EW Market")
    btc = panel[(panel["symbol"] == "BTC")].set_index("week")["fwd_ret"].rename("BTC")
    out = pd.concat([ew, btc], axis=1).reset_index()
    return out


def format_pct(x: float) -> str:
    if not np.isfinite(x):
        return "n/a"
    return f"{x:+.1%}"


def format_num(x: float) -> str:
    if not np.isfinite(x):
        return "n/a"
    return f"{x:+.2f}"


def metrics_table(metrics: dict[str, dict]) -> str:
    header = "| Strategy | Sharpe | AnnRet | AnnVol | MaxDD | Hit | Weeks |\n|---|---:|---:|---:|---:|---:|---:|\n"
    body = ""
    for name, m in metrics.items():
        body += (
            f"| {name} | {format_num(m['sharpe'])} | {format_pct(m['ann_return'])} | "
            f"{format_pct(m['ann_vol']).replace('+', '')} | {format_pct(m['max_dd'])} | "
            f"{m['hit_rate']:.0%} | {m['weeks']} |\n"
        )
    return header + body


def plot_cumulative(selected_pnl: dict[str, pd.DataFrame], bm: pd.DataFrame, first_oos: pd.Timestamp) -> None:
    plt.figure(figsize=(12, 7))
    for name, df in selected_pnl.items():
        curve = (1 + df.sort_values("week").set_index("week")["pnl_net"]).cumprod()
        plt.plot(curve.index, curve.values, linewidth=2, label=name)
    for col, style in [("EW Market", "--"), ("BTC", ":")]:
        s = bm.dropna(subset=[col]).sort_values("week").set_index("week")[col]
        plt.plot(s.index, (1 + s).cumprod(), linestyle=style, linewidth=1.6, label=col)
    plt.axvline(first_oos, color="black", linestyle="--", linewidth=1, alpha=0.6)
    plt.yscale("log")
    plt.title("Cumulative Net Return, Weekly Rebalanced")
    plt.ylabel("Growth of $1, log scale")
    plt.xlabel("Week")
    plt.legend(ncol=2)
    plt.tight_layout()
    plt.savefig(FIG_OUT / "cumulative_returns.png", dpi=160)
    plt.close()


def plot_drawdown(selected_pnl: dict[str, pd.DataFrame]) -> None:
    plt.figure(figsize=(12, 6))
    for name, df in selected_pnl.items():
        curve = (1 + df.sort_values("week").set_index("week")["pnl_net"]).cumprod()
        dd = curve / curve.cummax() - 1
        plt.plot(dd.index, dd.values, linewidth=2, label=name)
    plt.title("Strategy Drawdowns")
    plt.ylabel("Drawdown")
    plt.xlabel("Week")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_OUT / "drawdowns.png", dpi=160)
    plt.close()


def plot_regime(regime: pd.DataFrame) -> None:
    r = regime.sort_values("week")
    plt.figure(figsize=(12, 6))
    plt.stackplot(
        r["week"],
        r["p_RiskOff"],
        r["p_Neutral"],
        r["p_RiskOn"],
        labels=["RiskOff", "Neutral", "RiskOn"],
        colors=["#c83e4d", "#d9a441", "#357a38"],
        alpha=0.85,
    )
    plt.title("XGBoost Regime Probabilities")
    plt.ylabel("Probability")
    plt.xlabel("Week")
    plt.ylim(0, 1)
    plt.legend(loc="upper left", ncol=3)
    plt.tight_layout()
    plt.savefig(FIG_OUT / "xgboost_regimes.png", dpi=160)
    plt.close()


def plot_factor_heatmap(fw: pd.DataFrame, variant_name: str) -> None:
    data = fw.set_index("week")[FACTOR_ORDER].rolling(4, min_periods=1).mean().T
    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(data.values, aspect="auto", cmap="viridis")
    ax.set_yticks(range(len(data.index)))
    ax.set_yticklabels(data.index)
    ticks = np.linspace(0, len(data.columns) - 1, 6).astype(int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.to_datetime(data.columns[i]).strftime("%Y-%m") for i in ticks], rotation=30, ha="right")
    ax.set_title(f"{variant_name} Factor Weights, 4w Smoothed")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    plt.tight_layout()
    safe = variant_name.lower().replace(" ", "_")
    plt.savefig(FIG_OUT / f"factor_weights_{safe}.png", dpi=160)
    plt.close()


def plot_oos_return_hist(selected_pnl: dict[str, pd.DataFrame], first_oos: pd.Timestamp) -> None:
    plt.figure(figsize=(12, 6))
    for name, df in selected_pnl.items():
        x = df[df["week"] >= first_oos]["pnl_net"].dropna()
        plt.hist(x, bins=24, alpha=0.45, label=name)
    plt.title("Out-of-Sample Weekly Net Return Distribution")
    plt.xlabel("Weekly return")
    plt.ylabel("Count")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_OUT / "oos_return_hist.png", dpi=160)
    plt.close()


def write_weight_bubble_animation(
    weights: pd.DataFrame,
    regime: pd.DataFrame,
    out_path: Path,
    variant_name: str,
) -> None:
    anim = weights.copy()
    anim = anim[anim["w"].abs() > 1e-12].copy()
    anim["week"] = pd.to_datetime(anim["week"])
    anim["week_frame"] = anim["week"].dt.strftime("%Y-%m-%d")
    anim["weight_pct"] = anim["w"] * 100
    anim["abs_weight"] = anim["w"].abs()
    anim["side_name"] = np.where(anim["w"] >= 0, "Long", "Short")
    anim["rank"] = anim.groupby("week")["w"].rank(method="first", ascending=True)
    regime_cols = regime[["week", "label"]].copy()
    regime_cols["week"] = pd.to_datetime(regime_cols["week"])
    anim = anim.merge(regime_cols, on="week", how="left")

    fig = px.scatter(
        anim.sort_values(["week", "w"]),
        x="weight_pct",
        y="rank",
        size="abs_weight",
        color="side_name",
        animation_frame="week_frame",
        hover_name="symbol",
        hover_data={
            "weight_pct": ":.2f",
            "signal": ":.3f",
            "label": True,
            "rank": False,
            "abs_weight": False,
            "side_name": False,
            "week_frame": False,
        },
        color_discrete_map={"Long": "#2e7d32", "Short": "#b23a48"},
        size_max=42,
        title=f"{variant_name} Weekly Coin Weights",
        labels={"weight_pct": "Portfolio weight (%)", "rank": "Coin weight rank"},
    )
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="#333333")
    fig.update_layout(
        template="plotly_white",
        xaxis_tickformat=".1f",
        yaxis_showticklabels=False,
        legend_title_text="Side",
        margin=dict(l=50, r=30, t=80, b=50),
    )
    fig.write_html(out_path, include_plotlyjs=True, full_html=True)


def exposure_table(selected_pnl: dict[str, pd.DataFrame], selected_weights: dict[str, pd.DataFrame]) -> str:
    rows = []
    for name, pnl in selected_pnl.items():
        gross = pnl["gross_exposure"].replace(0, np.nan)
        max_short = selected_weights[name].loc[selected_weights[name]["w"] < 0, "w"].abs().max()
        rows.append(
            {
                "Variant": name,
                "Avg Long": pnl["long_gross"].mean(),
                "Avg Short": pnl["short_gross"].mean(),
                "Avg Gross": pnl["gross_exposure"].mean(),
                "Avg Net": pnl["net_exposure"].mean(),
                "Long Share": (pnl["long_gross"] / gross).mean(),
                "Max Short Name": max_short,
            }
        )
    t = pd.DataFrame(rows)
    for c in ["Avg Long", "Avg Short", "Avg Gross", "Avg Net", "Long Share", "Max Short Name"]:
        t[c] = t[c].map(lambda x: f"{x:.1%}" if np.isfinite(x) else "n/a")
    return t.to_markdown(index=False)


def regime_exposure_table(selected_pnl: dict[str, pd.DataFrame], regime: pd.DataFrame) -> str:
    regime_cols = regime[["week", "label"]].copy()
    regime_cols["week"] = pd.to_datetime(regime_cols["week"])
    rows = []
    for name, pnl in selected_pnl.items():
        x = pnl.merge(regime_cols, on="week", how="left")
        x["long_share"] = x["long_gross"] / x["gross_exposure"].replace(0, np.nan)
        grouped = x.groupby("label")
        for label in REGIME_STATES:
            if label not in grouped.groups:
                continue
            g = grouped.get_group(label)
            rows.append(
                {
                    "Variant": name,
                    "Regime": label,
                    "Weeks": len(g),
                    "Avg Gross": g["gross_exposure"].mean(),
                    "Avg Long": g["long_gross"].mean(),
                    "Avg Short": g["short_gross"].mean(),
                    "Long Share": g["long_share"].mean(),
                }
            )
    t = pd.DataFrame(rows)
    for c in ["Avg Gross", "Avg Long", "Avg Short", "Long Share"]:
        t[c] = t[c].map(lambda x: f"{x:.1%}" if np.isfinite(x) else "n/a")
    return t.to_markdown(index=False)


def write_results(
    selected_names: dict[str, str],
    selected_candidates: dict[str, Candidate],
    selected_pnl: dict[str, pd.DataFrame],
    selected_weights: dict[str, pd.DataFrame],
    selected_fw: dict[str, pd.DataFrame],
    all_results: pd.DataFrame,
    regime: pd.DataFrame,
    first_oos: pd.Timestamp,
    bm: pd.DataFrame,
) -> None:
    full_metrics = {}
    is_metrics = {}
    oos_metrics = {}
    for name, pnl in selected_pnl.items():
        full_metrics[name] = perf_metrics(pnl["pnl_net"])
        is_metrics[name] = perf_metrics(pnl[pnl["week"] < first_oos]["pnl_net"])
        oos_metrics[name] = perf_metrics(pnl[pnl["week"] >= first_oos]["pnl_net"])

    for col in ["EW Market", "BTC"]:
        b = bm[["week", col]].dropna().rename(columns={col: "pnl_net"})
        full_metrics[col] = perf_metrics(b["pnl_net"])
        is_metrics[col] = perf_metrics(b[b["week"] < first_oos]["pnl_net"])
        oos_metrics[col] = perf_metrics(b[b["week"] >= first_oos]["pnl_net"])

    param_rows = []
    for display_name, candidate in selected_candidates.items():
        param_rows.append(
            {
                "Variant": display_name,
                "Candidate": selected_names[display_name],
                "Core": candidate.sleeve_core,
                "Priced": candidate.sleeve_priced,
                "Mispricing": candidate.sleeve_mispricing,
                "Legacy": candidate.sleeve_legacy,
                "IC blend": candidate.ic_blend,
                "Top fraction": candidate.top_frac,
                "Gross RiskOn/Neutral/RiskOff": f"{candidate.gross_risk_on:.2f}/{candidate.gross_neutral:.2f}/{candidate.gross_risk_off:.2f}",
            }
        )
    params = pd.DataFrame(param_rows)
    params.to_csv(DATA_OUT / "selected_parameters.csv", index=False)

    factor_avg = []
    for name, fw in selected_fw.items():
        avg = fw[FACTOR_ORDER].mean().to_dict()
        avg["Variant"] = name
        factor_avg.append(avg)
    factor_avg = pd.DataFrame(factor_avg).set_index("Variant")[FACTOR_ORDER]
    factor_avg.to_csv(DATA_OUT / "average_factor_weights.csv")

    counts = regime["label"].value_counts().reindex(REGIME_STATES).fillna(0).astype(int)
    detector_metrics = regime_classification_metrics(regime)
    top_grid = all_results.sort_values("is_sharpe", ascending=False).head(8)[
        ["candidate", "is_sharpe", "is_ann_return", "is_max_dd", "oos_sharpe", "oos_ann_return", "oos_max_dd"]
    ]
    animation_variant = next(iter(selected_weights))
    animation_path = FIG_OUT / "weekly_weight_bubbles.html"
    write_weight_bubble_animation(
        selected_weights[animation_variant],
        regime,
        animation_path,
        variant_name=animation_variant,
    )

    def params_md() -> str:
        head = "| Variant | Candidate | Core | Priced | Mispricing | Legacy | IC blend | Top frac | Gross R/N/O |\n|---|---|---:|---:|---:|---:|---:|---:|---|\n"
        body = ""
        for _, r in params.iterrows():
            body += (
                f"| {r['Variant']} | {r['Candidate']} | {r['Core']:.2f} | {r['Priced']:.2f} | "
                f"{r['Mispricing']:.2f} | {r['Legacy']:.2f} | {r['IC blend']:.2f} | "
                f"{r['Top fraction']:.2f} | {r['Gross RiskOn/Neutral/RiskOff']} |\n"
            )
        return head + body

    def factor_md() -> str:
        rounded = factor_avg.copy()
        rounded = rounded.applymap(lambda x: f"{x:.3f}")
        return rounded.reset_index().to_markdown(index=False)

    def grid_md() -> str:
        t = top_grid.copy()
        for c in ["is_ann_return", "is_max_dd", "oos_ann_return", "oos_max_dd"]:
            t[c] = t[c].map(format_pct)
        for c in ["is_sharpe", "oos_sharpe"]:
            t[c] = t[c].map(format_num)
        return t.to_markdown(index=False)

    selected_weight_files = "\n".join(
        f"- `{display.lower().replace(' ', '_')}_weekly_weights.parquet`"
        for display in selected_pnl
    )

    md = f"""# Stage 14 - XGBoost Regime-Aware Weekly Factor Strategy

Generated by `14_regime_factor_strategy/run.py`.

Evaluation uses the same weekly panel as the factor research. The optimizer uses
the period before `{first_oos:%Y-%m-%d}` as in-sample, and the final {OOS_WEEKS}
weeks as out-of-sample. The strategy is weekly rebalanced, long-biased,
nonlinearly score-weighted inside long/short legs, turnover capped, and charged
{COST_BPS:.0f} bps per unit one-way turnover. Regime targets use about 90/10
long/short gross in RiskOn, 75/25 in Neutral, and 70/30 with lower total gross
in RiskOff.

## Factor Inputs

The strategy uses the factors listed in `12_factor_viz/RESULTS.md`:

- Confirmed weekly rankers: VolC and MAXRET.
- Priced-risk sleeve: CRASH8, BETA26, TVLC, SKEW52, NEWC.
- Distributional/mispricing sleeve: RMOM1w, RMOM2w, SMBC, NetRel.
- Low-prior legacy sleeve with small optimizer budget: MomC, NetMom, FunC.

Factor signs are set in the economically profitable direction. For example,
VolC is low volatility, MAXRET fades recent spikes, CRASH8 buys the most-crashed
coins, BETA26 buys high-beta coins, NEWC buys younger coins, and TVLC buys low
TVL/mcap because the reported premium is negative for high TVL/mcap exposure.

## XGBoost Regime Detection

Regimes are detected with a supervised 3-class XGBoost classifier. The target
regime is derived from contemporaneous market state using market momentum,
cross-sectional dispersion, and BTC dominance change, while the feature vector is
lagged one week and contains `{", ".join(XGB_FEATURES)}`. The classifier is fit
only on weeks before `{first_oos:%Y-%m-%d}` and then predicts soft RiskOff,
Neutral, and RiskOn probabilities for both the training and held-out weeks.

XGBoost hard-label counts:

| Regime | Weeks |
|---|---:|
| RiskOff | {counts.get('RiskOff', 0)} |
| Neutral | {counts.get('Neutral', 0)} |
| RiskOn | {counts.get('RiskOn', 0)} |

Train/test classifier diagnostics:

```json
{json.dumps(detector_metrics, indent=2)}
```

![XGBoost regimes](artifacts/figures/xgboost_regimes.png)

## Optimized Variants

Three variants come from the same compact in-sample grid. I enforce distinct
candidate selections so the report gives three different books rather than one
winner repeated three times:

- **Sharpe Optimized** maximizes in-sample Sharpe.
- **Return Optimized** maximizes in-sample annualized return among the remaining
  candidates, with catastrophic drawdowns filtered out.
- **Balanced** maximizes a percentile blend of Sharpe, annualized return, and
  drawdown control among the remaining candidates.

I also test a separate **Neural Network Optimizer**. It uses the same XGBoost
regime probabilities, trains an in-sample `MLPRegressor` on factor z-scores plus
regime probabilities to predict next-week returns, and then routes those
predictions through the same portfolio construction constraints as the balanced
book.

{params_md()}

## Full-Window Performance

{metrics_table(full_metrics)}

## In-Sample Performance

{metrics_table(is_metrics)}

## Out-of-Sample Performance

{metrics_table(oos_metrics)}

## Portfolio Exposure

The strategy now expresses most conviction through longs. Shorts are smaller,
capped at {MAX_SHORT_ASSET_WEIGHT:.1%} per name before turnover smoothing, and
mainly act as a hedge sleeve that grows in RiskOff while total gross falls.

{exposure_table(selected_pnl, selected_weights)}

Average exposure by hard XGBoost regime:

{regime_exposure_table(selected_pnl, regime)}

## Plots

![Cumulative returns](artifacts/figures/cumulative_returns.png)

![Drawdowns](artifacts/figures/drawdowns.png)

![OOS return histogram](artifacts/figures/oos_return_hist.png)

Interactive weekly coin-weight bubble animation:
[`artifacts/figures/weekly_weight_bubbles.html`](artifacts/figures/weekly_weight_bubbles.html)

## Average Factor Weights

The table below is the average weekly composite factor weight after regime
activation and IC blending for the three grid-selected modes. It is not
portfolio asset weight, and the neural-network optimizer is omitted because it
learns asset-level return predictions rather than explicit factor sleeve weights.

{factor_md()}

### Sharpe Optimized Factor Weights

![Sharpe factor weights](artifacts/figures/factor_weights_sharpe_optimized.png)

### Return Optimized Factor Weights

![Return factor weights](artifacts/figures/factor_weights_return_optimized.png)

### Balanced Factor Weights

![Balanced factor weights](artifacts/figures/factor_weights_balanced.png)

## Top In-Sample Grid Candidates

{grid_md()}

## Artifacts

- `artifacts/data/factor_panel.parquet`
- `artifacts/data/regime_panel.parquet`
- `artifacts/data/factor_ic_timeseries.parquet`
- `artifacts/data/selected_parameters.csv`
- `artifacts/data/average_factor_weights.csv`
- `artifacts/data/neural_network_signals.parquet`
{selected_weight_files}
- `artifacts/figures/weekly_weight_bubbles.html`
- `artifacts/manifests/metrics.json`

## Caveats

This is a first usable implementation, not a production allocator. The supervised
regime labels are heuristic market-state labels, transaction costs are simplified,
and the grid search is deliberately small to avoid overfitting. The results should
be read as a strategy research prototype that turns the validated factors into a
machine-learning regime-aware weekly portfolio.
"""
    (STAGE / "RESULTS.md").write_text(md)

    metrics = {
        "first_oos_week": str(first_oos.date()),
        "regime_detector": "xgboost",
        "xgboost_features": XGB_FEATURES,
        "xgboost_params": XGB_PARAMS,
        "regime_classification_metrics": detector_metrics,
        "selected_candidates": selected_names,
        "full": full_metrics,
        "is": is_metrics,
        "oos": oos_metrics,
        "long_share_by_regime": LONG_SHARE_BY_REGIME,
        "max_long_asset_weight": MAX_LONG_ASSET_WEIGHT,
        "max_short_asset_weight": MAX_SHORT_ASSET_WEIGHT,
        "weight_bubble_animation": str(animation_path.relative_to(STAGE)),
    }
    (MANIFEST_OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))


def main() -> None:
    print("Building factor panel...", flush=True)
    panel = build_factor_panel()
    print(f"Panel rows: {len(panel):,}; weeks: {panel['week'].nunique():,}; symbols: {panel['symbol'].nunique():,}", flush=True)

    weeks = sorted(panel["week"].dropna().unique())
    first_oos = pd.to_datetime(weeks[-OOS_WEEKS])

    print("Computing XGBoost regimes...", flush=True)
    regime = build_regime_panel(panel, first_oos=first_oos)

    print("Computing factor ICs and optimizer grid...", flush=True)
    ic_ts = factor_ic(panel)
    ic_wide = rolling_ic_weight(ic_ts)

    all_rows = []
    stored = {}
    candidates = candidate_grid()
    for i, candidate in enumerate(candidates, start=1):
        pnl, weights, fw = run_candidate(candidate, panel, regime, ic_wide)
        is_pnl = pnl[pnl["week"] < first_oos]["pnl_net"]
        oos_pnl = pnl[pnl["week"] >= first_oos]["pnl_net"]
        is_m = perf_metrics(is_pnl)
        oos_m = perf_metrics(oos_pnl)
        row = {
            "candidate": candidate.name,
            "is_sharpe": is_m["sharpe"],
            "is_ann_return": is_m["ann_return"],
            "is_max_dd": is_m["max_dd"],
            "oos_sharpe": oos_m["sharpe"],
            "oos_ann_return": oos_m["ann_return"],
            "oos_max_dd": oos_m["max_dd"],
        }
        all_rows.append(row)
        stored[candidate.name] = (candidate, pnl, weights, fw)
        if i % 5 == 0:
            print(f"  evaluated {i}/{len(candidates)} candidates", flush=True)

    all_results = pd.DataFrame(all_rows)
    all_results.to_csv(DATA_OUT / "grid_results.csv", index=False)
    all_results.to_parquet(DATA_OUT / "grid_results.parquet", index=False)

    selected_names = choose_variants(all_results)
    selected_candidates = {}
    selected_pnl = {}
    selected_weights = {}
    selected_fw = {}

    for display_name, candidate_name in selected_names.items():
        candidate, pnl, weights, fw = stored[candidate_name]
        safe = display_name.lower().replace(" ", "_")
        selected_candidates[display_name] = candidate
        selected_pnl[display_name] = pnl
        selected_weights[display_name] = weights
        selected_fw[display_name] = fw
        pnl.to_csv(DATA_OUT / f"{safe}_weekly_pnl.csv", index=False)
        pnl.to_parquet(DATA_OUT / f"{safe}_weekly_pnl.parquet", index=False)
        weights.to_csv(DATA_OUT / f"{safe}_weekly_weights.csv", index=False)
        weights.to_parquet(DATA_OUT / f"{safe}_weekly_weights.parquet", index=False)
        fw.to_csv(DATA_OUT / f"{safe}_factor_weights.csv", index=False)
        fw.to_parquet(DATA_OUT / f"{safe}_factor_weights.parquet", index=False)

    print("Testing neural-network portfolio optimizer...", flush=True)
    nn_signal = build_neural_network_signal(panel, regime, first_oos)
    nn_candidate = selected_candidates["Balanced"]
    nn_weights = construct_weights(nn_signal, regime, nn_candidate)
    nn_pnl = backtest(nn_weights, panel)
    selected_names["Neural Network Optimizer"] = "mlp_return_forecaster"
    selected_candidates["Neural Network Optimizer"] = nn_candidate
    selected_pnl["Neural Network Optimizer"] = nn_pnl
    selected_weights["Neural Network Optimizer"] = nn_weights
    nn_pnl.to_csv(DATA_OUT / "neural_network_optimizer_weekly_pnl.csv", index=False)
    nn_pnl.to_parquet(DATA_OUT / "neural_network_optimizer_weekly_pnl.parquet", index=False)
    nn_weights.to_csv(DATA_OUT / "neural_network_optimizer_weekly_weights.csv", index=False)
    nn_weights.to_parquet(DATA_OUT / "neural_network_optimizer_weekly_weights.parquet", index=False)

    bm = benchmark_returns(panel)
    bm.to_csv(DATA_OUT / "benchmarks.csv", index=False)
    bm.to_parquet(DATA_OUT / "benchmarks.parquet", index=False)

    print("Writing figures...", flush=True)
    plot_cumulative(selected_pnl, bm, first_oos)
    plot_drawdown(selected_pnl)
    plot_regime(regime)
    plot_oos_return_hist(selected_pnl, first_oos)
    for display_name, fw in selected_fw.items():
        plot_factor_heatmap(fw, display_name)

    print("Writing RESULTS.md...", flush=True)
    write_results(
        selected_names=selected_names,
        selected_candidates=selected_candidates,
        selected_pnl=selected_pnl,
        selected_weights=selected_weights,
        selected_fw=selected_fw,
        all_results=all_results,
        regime=regime,
        first_oos=first_oos,
        bm=bm,
    )

    print("\nSelected candidates:")
    for display, name in selected_names.items():
        pnl = selected_pnl[display]
        oos = perf_metrics(pnl[pnl["week"] >= first_oos]["pnl_net"])
        print(f"  {display:18s} {name} OOS Sharpe={oos['sharpe']:+.2f} AnnRet={oos['ann_return']:+.1%}")


if __name__ == "__main__":
    main()
