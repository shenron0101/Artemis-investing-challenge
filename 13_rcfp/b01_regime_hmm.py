#!/usr/bin/env python3
"""
Plan B — Gaussian HMM regime detection
======================================

A 3-state Gaussian HMM is fit on a 4-signal observation vector and produces
SOFT regime probabilities each week. The HMM learns regime boundaries and
persistence from data instead of using hand-set thresholds.

Observation vector (all lagged 1 week, 52w rolling z-scored):
  1. csd_z      cross-sectional dispersion of weekly returns (factor viability)
  2. dbtc_z     4-week BTC-dominance change       (flight-to-quality direction)
  3. netent_z   Louvain network entropy           (correlation-structure regime)
  4. mktmom_z   4-week equal-weight market return  (risk-on/off level)

  Note: the original design listed `stable_inflow_z` as the 4th signal, but the
  5-year panel does not carry stablecoin flows (Stage-06 characteristics were
  never materialised on disk). `mktmom_z` is the crypto-native substitute — a
  direct risk-on/off level proxy with independent data lineage.

Causality: the HMM is refit on an expanding window every REFIT_EVERY weeks and
the FILTERED posterior at the last observation is taken (smoothed == filtered at
the terminal point of the supplied sequence, so no future leaks in). States are
re-labelled at every refit by their economic risk-score means, which fixes the
HMM label-switching problem.

Output: artifacts/data/b_regime_panel.parquet
        [week, p_RiskOn, p_Neutral, p_RiskOff, label, gross]
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

import _rcfp_common as C

OBS_COLS = ["csd_z", "dbtc_z", "netent_z", "mktmom_z"]
N_STATES = 3
MIN_TRAIN = 52
REFIT_EVERY = 4
N_ITER = 200
SEEDS = [0, 7, 21, 42, 99]      # multi-start to dodge degenerate local optima
MAX_OCCUPANCY = 0.85            # reject fits where one state swallows > 85% of weeks

warnings.filterwarnings("ignore")


def build_obs() -> pd.DataFrame:
    """Assemble the lagged, z-scored 4-signal observation panel."""
    rets = C.load_returns()
    mcap = C.load_mcap()
    net = C.load_network()

    csd = rets.groupby("week")["ret"].std().rename("csd")
    mkt = rets.groupby("week")["ret"].mean().rename("mkt_ret")

    tot = mcap.groupby("week")["mcap"].sum().rename("tot_mcap")
    btc = mcap[mcap["symbol"] == "BTC"].set_index("week")["mcap"].rename("btc_mcap")
    dom = pd.concat([tot, btc], axis=1)
    dom["btc_dom"] = dom["btc_mcap"] / dom["tot_mcap"]
    dbtc = (dom["btc_dom"] - dom["btc_dom"].shift(4)).rename("dbtc_dom")

    netent = net.groupby("week")["network_entropy"].first().rename("netent")

    obs = pd.concat([csd, mkt, dbtc, netent], axis=1).sort_index()
    obs["mktmom"] = obs["mkt_ret"].rolling(4, min_periods=2).sum()

    obs["csd_z"] = C.rolling_z(obs["csd"])
    obs["dbtc_z"] = C.rolling_z(obs["dbtc_dom"])
    obs["netent_z"] = C.rolling_z(obs["netent"])
    obs["mktmom_z"] = C.rolling_z(obs["mktmom"])

    # lag one week so the regime at t uses information through t-1
    for c in OBS_COLS:
        obs[c] = obs[c].shift(1)

    return obs.reset_index().rename(columns={"index": "week"})


def _fit_hmm(X: np.ndarray) -> GaussianHMM | None:
    """Multi-start Gaussian HMM fit. Among converged fits, keep the one with the
    highest log-likelihood whose Viterbi path is NOT degenerate (no single state
    above MAX_OCCUPANCY). Falls back to the best-scoring fit if all degenerate."""
    best, best_score = None, -np.inf
    best_any, best_any_score = None, -np.inf
    for seed in SEEDS:
        try:
            m = GaussianHMM(n_components=N_STATES, covariance_type="full",
                            n_iter=N_ITER, random_state=seed, tol=1e-3,
                            min_covar=1e-3)
            m.fit(X)
            score = m.score(X)
        except Exception:
            continue
        if score > best_any_score:
            best_any, best_any_score = m, score
        path = m.predict(X)
        occ = np.bincount(path, minlength=N_STATES).max() / len(path)
        if occ <= MAX_OCCUPANCY and score > best_score:
            best, best_score = m, score
    return best if best is not None else best_any


def _label_states(model: GaussianHMM) -> dict[int, str]:
    """Map HMM state index -> regime label using economic risk-score of means.
    risk = mktmom_z + csd_z - dbtc_z  (high => risk-on)."""
    means = model.means_  # (n_states, n_features) in OBS_COLS order
    risk = means[:, 3] + means[:, 0] - means[:, 1]
    order = np.argsort(risk)  # ascending: lowest risk first
    mapping = {int(order[0]): "RiskOff",
               int(order[1]): "Neutral",
               int(order[2]): "RiskOn"}
    return mapping


def main() -> None:
    obs = build_obs()
    valid = obs.dropna(subset=OBS_COLS).reset_index(drop=True)
    X_all = valid[OBS_COLS].to_numpy()
    weeks = valid["week"].tolist()

    model = None
    last_fit = -10_000
    rows = []
    transition_snapshot = None

    for i in range(len(valid)):
        if i + 1 < MIN_TRAIN:
            rows.append({"week": weeks[i], "p_RiskOn": 0.0,
                         "p_Neutral": 1.0, "p_RiskOff": 0.0})
            continue

        need_fit = (model is None) or (i - last_fit >= REFIT_EVERY)
        if need_fit:
            m = _fit_hmm(X_all[: i + 1])
            if m is not None:
                model = m
                last_fit = i
                if i >= len(valid) - REFIT_EVERY:
                    transition_snapshot = model.transmat_.tolist()

        if model is None:
            rows.append({"week": weeks[i], "p_RiskOn": 0.0,
                         "p_Neutral": 1.0, "p_RiskOff": 0.0})
            continue

        mapping = _label_states(model)
        try:
            proba = model.predict_proba(X_all[: i + 1])[-1]  # filtered @ last pt
        except Exception:
            proba = np.array([1.0 / N_STATES] * N_STATES)

        p = {"RiskOn": 0.0, "Neutral": 0.0, "RiskOff": 0.0}
        for st in range(N_STATES):
            p[mapping[st]] += float(proba[st])
        rows.append({"week": weeks[i], "p_RiskOn": p["RiskOn"],
                     "p_Neutral": p["Neutral"], "p_RiskOff": p["RiskOff"]})

    out = pd.DataFrame(rows)
    out["week"] = pd.to_datetime(out["week"])  # match obs dtype for the merge
    pcols = ["p_RiskOn", "p_Neutral", "p_RiskOff"]

    # re-attach all weeks (pre-MIN_TRAIN / pre-burn-in default Neutral)
    obs["week"] = pd.to_datetime(obs["week"])
    full = obs[["week"]].merge(out, on="week", how="left")
    for c in pcols:
        full[c] = full[c].fillna(0.0)
    full.loc[full[pcols].sum(axis=1) == 0, "p_Neutral"] = 1.0
    # derive label + gross on the full frame (robust to the merge)
    full["label"] = full[pcols].idxmax(axis=1).str.replace("p_", "", regex=False)
    full["gross"] = (full["p_RiskOn"] * C.GROSS["RiskOn"]
                     + full["p_Neutral"] * C.GROSS["Neutral"]
                     + full["p_RiskOff"] * C.GROSS["RiskOff"])

    C.write_frame(full, "b_regime_panel")

    counts = full["label"].value_counts().to_dict()
    C.write_json({"regime_counts": counts,
                  "obs_cols": OBS_COLS,
                  "n_states": N_STATES, "min_train": MIN_TRAIN,
                  "refit_every": REFIT_EVERY,
                  "final_transition_matrix": transition_snapshot,
                  "weeks": int(len(full))},
                 "b_hmm_manifest.json")

    print("Plan B HMM regime panel written.")
    print("Hard-label counts:", counts)
    if transition_snapshot is not None:
        print("Final transition matrix (RiskOff/Neutral/RiskOn ordering varies):")
        print(np.round(np.array(transition_snapshot), 3))
    print(full.tail(8).to_string(index=False))


if __name__ == "__main__":
    main()
