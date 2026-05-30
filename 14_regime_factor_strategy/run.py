#!/usr/bin/env python3
"""
Stage 14 - Regime-aware weekly crypto factor strategy.

This script uses the factors summarized in 12_factor_viz/RESULTS.md, detects
market regimes with a causal Gaussian HMM, optimizes three weekly long/short
strategy variants in-sample, and writes an embedded-plot RESULTS.md.
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
from hmmlearn.hmm import GaussianHMM

warnings.filterwarnings("ignore")
logging.getLogger("hmmlearn").setLevel(logging.ERROR)

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
TURNOVER_CAP = 0.45
HMM_STATES = ["RiskOff", "Neutral", "RiskOn"]

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


def build_regime_panel(panel: pd.DataFrame) -> pd.DataFrame:
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

    obs_cols = ["csd", "dbtc_dom", "network_entropy", "mktmom4"]
    for col in obs_cols:
        weekly[f"{col}_z"] = rolling_z(weekly[col]).shift(1)

    # Network entropy exists only where the stage-08 network panel has enough
    # coverage. Treat missing entropy as "no extra structural information"
    # instead of dropping the older regime history.
    weekly["network_entropy_z"] = weekly["network_entropy_z"].fillna(0.0)

    obs = weekly[[f"{c}_z" for c in obs_cols]].dropna(subset=["csd_z", "dbtc_dom_z", "mktmom4_z"])
    obs.columns = ["csd_z", "dbtc_z", "netent_z", "mktmom_z"]

    rows = []
    model = None
    last_fit = -999
    # Keep the HMM lightweight enough for an iterative research run. Multi-start
    # is still useful, but two seeds and quarterly refits are sufficient here.
    seeds = [0, 42]
    values = obs.to_numpy()
    weeks = list(obs.index)

    for i, wk in enumerate(weeks):
        if i < 52:
            rows.append({"week": wk, "p_RiskOff": 0.0, "p_Neutral": 1.0, "p_RiskOn": 0.0})
            continue
        if model is None or i - last_fit >= 13:
            best_model = None
            best_score = -np.inf
            x_train = values[: i + 1]
            for seed in seeds:
                try:
                    candidate = GaussianHMM(
                        n_components=3,
                        covariance_type="full",
                        n_iter=80,
                        tol=1e-3,
                        min_covar=1e-3,
                        random_state=seed,
                    )
                    candidate.fit(x_train)
                    score = candidate.score(x_train)
                    path = candidate.predict(x_train)
                    occupancy = np.bincount(path, minlength=3).max() / len(path)
                    if occupancy <= 0.88 and score > best_score:
                        best_model = candidate
                        best_score = score
                except Exception:
                    continue
            if best_model is not None:
                model = best_model
                last_fit = i

        if model is None:
            rows.append({"week": wk, "p_RiskOff": 0.0, "p_Neutral": 1.0, "p_RiskOn": 0.0})
            continue

        means = model.means_
        risk_score = means[:, 3] + means[:, 0] - means[:, 1]
        order = np.argsort(risk_score)
        mapping = {int(order[0]): "RiskOff", int(order[1]): "Neutral", int(order[2]): "RiskOn"}
        try:
            proba = model.predict_proba(values[: i + 1])[-1]
        except Exception:
            proba = np.array([0.0, 1.0, 0.0])
        p = {"RiskOff": 0.0, "Neutral": 0.0, "RiskOn": 0.0}
        for state_idx, state_prob in enumerate(proba):
            p[mapping[state_idx]] += float(state_prob)
        rows.append({"week": wk, "p_RiskOff": p["RiskOff"], "p_Neutral": p["Neutral"], "p_RiskOn": p["RiskOn"]})

    regime = pd.DataFrame(rows)
    all_weeks = pd.DataFrame({"week": sorted(panel["week"].unique())})
    regime = all_weeks.merge(regime, on="week", how="left")
    for c in ["p_RiskOff", "p_Neutral", "p_RiskOn"]:
        regime[c] = regime[c].fillna(0.0)
    empty = regime[["p_RiskOff", "p_Neutral", "p_RiskOn"]].sum(axis=1) == 0
    regime.loc[empty, "p_Neutral"] = 1.0
    regime["label"] = regime[["p_RiskOff", "p_Neutral", "p_RiskOn"]].idxmax(axis=1).str.replace("p_", "", regex=False)
    regime = regime.merge(weekly.reset_index(), on="week", how="left")
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
            activation = sum(float(r[f"p_{state}"]) * ACTIVATION[fac][state] for state in HMM_STATES)
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


def gross_for_week(candidate: Candidate, r: pd.Series) -> float:
    return (
        float(r["p_RiskOn"]) * candidate.gross_risk_on
        + float(r["p_Neutral"]) * candidate.gross_neutral
        + float(r["p_RiskOff"]) * candidate.gross_risk_off
    )


def construct_weights(signal_panel: pd.DataFrame, regime: pd.DataFrame, candidate: Candidate) -> pd.DataFrame:
    gross_map = regime.set_index("week").apply(lambda r: gross_for_week(candidate, r), axis=1)
    previous = None
    rows = []
    for wk, g in signal_panel.groupby("week", sort=True):
        g = g.dropna(subset=["signal"]).copy()
        if len(g) < MIN_NAMES:
            continue
        hi = g["signal"].quantile(1 - candidate.top_frac)
        lo = g["signal"].quantile(candidate.top_frac)
        g["side"] = 0
        g.loc[g["signal"] >= hi, "side"] = 1
        g.loc[g["signal"] <= lo, "side"] = -1
        if (g["side"] != 0).sum() == 0:
            continue

        g["w"] = 0.0
        vol = g["vol4"].fillna(g["vol4"].median()).clip(lower=VOL_FLOOR)
        for side, target in [(1, 0.5), (-1, -0.5)]:
            mask = g["side"] == side
            if mask.sum() == 0:
                continue
            inv_vol = 1.0 / vol[mask]
            g.loc[mask, "w"] = target * (inv_vol / inv_vol.sum()).to_numpy()

        # single-name cap, then renormalize each side.
        g["w"] = g["w"].clip(lower=-MAX_ASSET_WEIGHT, upper=MAX_ASSET_WEIGHT)
        for side, target in [(1, 0.5), (-1, -0.5)]:
            mask = g["side"] == side
            side_sum = g.loc[mask, "w"].sum()
            if abs(side_sum) > 1e-12:
                g.loc[mask, "w"] *= target / side_sum

        gross = float(gross_map.get(wk, candidate.gross_neutral))
        g["w"] = g["w"] * gross
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
        ("defensive_a", (0.55, 0.20, 0.20, 0.05), 0.75, 0.20, (0.85, 0.65, 0.40), 0.90),
        ("defensive_b", (0.50, 0.20, 0.25, 0.05), 0.75, 0.30, (1.00, 0.75, 0.45), 0.90),
        ("core_alpha_a", (0.45, 0.25, 0.25, 0.05), 0.75, 0.20, (1.00, 0.80, 0.50), 1.00),
        ("core_alpha_b", (0.45, 0.20, 0.30, 0.05), 0.00, 0.30, (1.10, 0.85, 0.55), 1.00),
        ("balanced_a", (0.35, 0.35, 0.25, 0.05), 0.75, 0.20, (1.15, 0.90, 0.55), 1.00),
        ("balanced_b", (0.30, 0.35, 0.30, 0.05), 0.00, 0.30, (1.20, 0.90, 0.60), 1.00),
        ("mispricing_a", (0.30, 0.25, 0.40, 0.05), 0.75, 0.20, (1.10, 0.85, 0.50), 1.00),
        ("mispricing_b", (0.25, 0.25, 0.45, 0.05), 0.00, 0.30, (1.20, 0.90, 0.55), 1.00),
        ("priced_a", (0.25, 0.50, 0.20, 0.05), 0.25, 0.20, (1.30, 1.00, 0.60), 1.15),
        ("priced_b", (0.20, 0.55, 0.20, 0.05), 0.00, 0.30, (1.40, 1.05, 0.65), 1.20),
        ("return_a", (0.20, 0.60, 0.15, 0.05), 0.00, 0.20, (1.55, 1.15, 0.70), 1.25),
        ("return_b", (0.15, 0.65, 0.15, 0.05), 0.25, 0.30, (1.65, 1.20, 0.75), 1.30),
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
    plt.title("Causal HMM Regime Probabilities")
    plt.ylabel("Probability")
    plt.xlabel("Week")
    plt.ylim(0, 1)
    plt.legend(loc="upper left", ncol=3)
    plt.tight_layout()
    plt.savefig(FIG_OUT / "hmm_regimes.png", dpi=160)
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

    counts = regime["label"].value_counts().reindex(HMM_STATES).fillna(0).astype(int)
    top_grid = all_results.sort_values("is_sharpe", ascending=False).head(8)[
        ["candidate", "is_sharpe", "is_ann_return", "is_max_dd", "oos_sharpe", "oos_ann_return", "oos_max_dd"]
    ]

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

    md = f"""# Stage 14 - Regime-Aware Weekly Factor Strategy

Generated by `14_regime_factor_strategy/run.py`.

Evaluation uses the same weekly panel as the factor research. The optimizer uses
the period before `{first_oos:%Y-%m-%d}` as in-sample, and the final {OOS_WEEKS}
weeks as out-of-sample. The strategy is weekly rebalanced, dollar-neutral,
inverse-vol weighted inside long/short legs, turnover capped, and charged
{COST_BPS:.0f} bps per unit one-way turnover.

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

## Regime Detection

Regimes are detected with a causal 3-state Gaussian HMM. The observation vector is
lagged one week and contains rolling z-scores of cross-sectional dispersion,
4-week BTC dominance change, network entropy, and 4-week equal-weight market
momentum. The HMM is refit on an expanding window every 13 weeks and produces soft
RiskOff, Neutral, and RiskOn probabilities.

HMM hard-label counts:

| Regime | Weeks |
|---|---:|
| RiskOff | {counts.get('RiskOff', 0)} |
| Neutral | {counts.get('Neutral', 0)} |
| RiskOn | {counts.get('RiskOn', 0)} |

![HMM regimes](artifacts/figures/hmm_regimes.png)

## Optimized Variants

Three variants come from the same compact in-sample grid. I enforce distinct
candidate selections so the report gives three different books rather than one
winner repeated three times:

- **Sharpe Optimized** maximizes in-sample Sharpe.
- **Return Optimized** maximizes in-sample annualized return among the remaining
  candidates, with catastrophic drawdowns filtered out.
- **Balanced** maximizes a percentile blend of Sharpe, annualized return, and
  drawdown control among the remaining candidates.

{params_md()}

## Full-Window Performance

{metrics_table(full_metrics)}

## In-Sample Performance

{metrics_table(is_metrics)}

## Out-of-Sample Performance

{metrics_table(oos_metrics)}

## Plots

![Cumulative returns](artifacts/figures/cumulative_returns.png)

![Drawdowns](artifacts/figures/drawdowns.png)

![OOS return histogram](artifacts/figures/oos_return_hist.png)

## Average Factor Weights

The table below is the average weekly composite factor weight after regime
activation and IC blending. It is not portfolio asset weight.

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
{selected_weight_files}
- `artifacts/manifests/metrics.json`

## Caveats

This is a first usable implementation, not a production allocator. The HMM state
labels are economically mapped by state means, transaction costs are simplified,
and the grid search is deliberately small to avoid overfitting. The results should
be read as a strategy research prototype that turns the validated factors into a
regime-aware weekly portfolio.
"""
    (STAGE / "RESULTS.md").write_text(md)

    metrics = {
        "first_oos_week": str(first_oos.date()),
        "selected_candidates": selected_names,
        "full": full_metrics,
        "is": is_metrics,
        "oos": oos_metrics,
    }
    (MANIFEST_OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))


def main() -> None:
    print("Building factor panel...", flush=True)
    panel = build_factor_panel()
    print(f"Panel rows: {len(panel):,}; weeks: {panel['week'].nunique():,}; symbols: {panel['symbol'].nunique():,}", flush=True)

    print("Computing HMM regimes...", flush=True)
    regime = build_regime_panel(panel)

    print("Computing factor ICs and optimizer grid...", flush=True)
    ic_ts = factor_ic(panel)
    ic_wide = rolling_ic_weight(ic_ts)

    weeks = sorted(panel["week"].dropna().unique())
    first_oos = pd.to_datetime(weeks[-OOS_WEEKS])

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
