"""02 — Pillar 2: Instrumented PCA (IPCA) expected-return estimation.

Reference: Kelly, Pruitt & Su (2019), "Characteristics are covariances: a unified
model of risk and return", JFE. The restricted (no alpha) model is:

    r_{i,t+1} = z_{i,t}' Gamma * f_{t+1} + e_{i,t+1}
    beta_{i,t} = Gamma' z_{i,t}              (L characteristics x K factors)

with the identifying restrictions Gamma' Gamma = I_K and the latent factors
F_t = (Sum_t Z_t' Z_t)^{-1} Sum_t Z_t' R_t  given Gamma fixed.

We estimate Gamma + F by alternating least squares on the *training* window
(first TRAIN_WEEKS), then carry Gamma forward to produce out-of-sample
expected returns

    E[r_{i,t+1} | F_history] = z_{i,t}' Gamma * lambda

where lambda is the time-series mean of the estimated F_t inside the
walk-forward training history. This matches the IPCA risk-premium estimator
used in Kelly-Pruitt-Su §3.4 ("characteristic-managed portfolios"), and is
identical in spirit to the Fama-MacBeth λ already estimated in
07_hidden_factor_pricing — only with characteristic-driven loadings.

Novelty over stage 07. Stage 07 uses static PCA loadings on returns. We use
loadings that vary continuously with 11 observable characteristics — including
the three network signals from Pillar 1 — so a single latent factor can have
*different* exposure to the same asset week-to-week. The latent factors here
are statistical and are *not* assigned economic labels (consistent with the
Crypto Pricing with Hidden Factors paper).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    DATA_DIR,
    INSTRUMENT_COLS,
    MANIFEST_DIR,
    TRAIN_WEEKS,
    UPSTREAM_06,
    load_characteristics,
    save_plotly,
    standardize_panel,
    winsorize_cs,
    write_frame,
    write_json,
)

N_FACTORS = 3
MAX_ITER = 200
TOL = 1e-6


def build_ipca_panel() -> pd.DataFrame:
    """Stage-06 characteristics + Pillar 1 network signals + (broadcast) entropy.

    All instruments enter as cross-sectionally standardised z-scores so the
    IPCA optimisation is scale-free."""
    char = load_characteristics()
    net = pd.read_parquet(DATA_DIR / "network_panel.parquet")
    net["week"] = pd.to_datetime(net["week"])
    keep = ["week", "symbol", "cluster_id", "within_cluster_mom",
            "cross_cluster_rel", "network_entropy"]
    df = char.merge(net[keep], on=["week", "symbol"], how="left")

    # Drop weeks with no clustering (early lookback before W is satisfied).
    df = df.dropna(subset=["cluster_id"]).copy()

    # Winsorise extreme values, then cross-section z-score each instrument.
    df = winsorize_cs(df, INSTRUMENT_COLS, p=0.02)
    df = standardize_panel(df, INSTRUMENT_COLS)

    # Drop rows where forward return is missing — they cannot be fit.
    df = df.dropna(subset=["fwd_ret_1w"]).reset_index(drop=True)
    return df


def _als_step_factor(Z_t: np.ndarray, r_t: np.ndarray, gamma: np.ndarray) -> np.ndarray:
    """Given Gamma (L x K), find F_t (K,) that solves R_t = Z_t Gamma F_t + e.

    OLS:  F_t = (Gamma' Z_t' Z_t Gamma)^-1 Gamma' Z_t' R_t."""
    A = Z_t @ gamma                       # N x K
    G = A.T @ A
    rhs = A.T @ r_t
    return np.linalg.solve(G + 1e-8 * np.eye(G.shape[0]), rhs)


def _als_step_gamma(Z_list: list[np.ndarray], R_list: list[np.ndarray],
                    F_mat: np.ndarray, K: int) -> np.ndarray:
    """Update Gamma given factors F (T x K).
    Stacks the per-week kron(F_t, Z_t) onto returns and runs OLS for the
    vectorised Gamma in R^{LK}, then reshapes to L x K and re-orthonormalises."""
    L = Z_list[0].shape[1]
    XtX = np.zeros((L * K, L * K))
    Xty = np.zeros(L * K)
    for Z_t, r_t, f_t in zip(Z_list, R_list, F_mat):
        # Vectorise: r_t = Z_t Gamma f_t = (f_t' kron I_L) vec(Gamma' ) ...
        # equivalently model = (Z_t f_t')_{i,l,k} → flatten so design is N x (LK)
        # design[i, l*K + k] = Z_t[i, l] * f_t[k]
        design = np.einsum("nl,k->nlk", Z_t, f_t).reshape(Z_t.shape[0], L * K)
        XtX += design.T @ design
        Xty += design.T @ r_t
    vec_gamma = np.linalg.solve(XtX + 1e-8 * np.eye(L * K), Xty)
    Gamma = vec_gamma.reshape(L, K)
    # Orthonormalise: QR-decompose so Gamma' Gamma = I (Kelly et al. identification).
    Q, _ = np.linalg.qr(Gamma)
    return Q


def fit_ipca(df: pd.DataFrame, K: int = N_FACTORS, max_iter: int = MAX_ITER, tol: float = TOL):
    """Alternating-least-squares fit of the restricted IPCA model.

    Returns (Gamma, factors_df, instruments_list)."""
    instruments = INSTRUMENT_COLS
    weeks = sorted(df["week"].unique())
    Z_list: list[np.ndarray] = []
    R_list: list[np.ndarray] = []
    week_idx: list[pd.Timestamp] = []
    for wk in weeks:
        block = df[df["week"] == wk]
        if len(block) < 8:
            continue
        Z = block[instruments].values
        r = block["fwd_ret_1w"].values
        Z_list.append(Z)
        R_list.append(r)
        week_idx.append(pd.Timestamp(wk))

    L = len(instruments)
    rng = np.random.default_rng(0)
    Gamma = rng.standard_normal((L, K))
    Gamma, _ = np.linalg.qr(Gamma)

    prev_loss = np.inf
    for it in range(max_iter):
        # Step 1: update factors given gamma
        F_mat = np.array([_als_step_factor(Z, r, Gamma) for Z, r in zip(Z_list, R_list)])
        # Step 2: update gamma given factors
        Gamma = _als_step_gamma(Z_list, R_list, F_mat, K)
        # Compute training loss
        loss = 0.0
        for Z, r, f in zip(Z_list, R_list, F_mat):
            res = r - Z @ Gamma @ f
            loss += float(res @ res)
        rel = abs(prev_loss - loss) / max(prev_loss, 1e-12)
        if it % 25 == 0:
            print(f"  iter {it:3d}  loss={loss:.6f}  rel={rel:.2e}")
        if rel < tol and it > 5:
            break
        prev_loss = loss

    factors = pd.DataFrame(F_mat, index=pd.Index(week_idx, name="week"),
                           columns=[f"f{k+1}" for k in range(K)]).reset_index()
    return Gamma, factors, instruments


def expected_returns_walkforward(df: pd.DataFrame, K: int = N_FACTORS) -> pd.DataFrame:
    """Walk-forward expected returns.

    Schedule: for the first TRAIN_WEEKS weeks, fit IPCA on the training panel
    only (in-sample fitted values are written for diagnostic use); then for
    every t >= TRAIN_WEEKS, refit Gamma on the *expanding* training window
    once every 4 weeks (compute-cheap, common practice) and use the latest
    lambda = mean(F_history) as the latent risk-premium estimate.

    Returns long frame with columns [week, symbol, E_ipca, in_sample]."""
    df = df.sort_values(["week", "symbol"]).reset_index(drop=True)
    weeks = sorted(df["week"].unique())
    out_rows: list[pd.DataFrame] = []

    # Initial training fit (first TRAIN_WEEKS).
    train_weeks = weeks[:TRAIN_WEEKS]
    train_df = df[df["week"].isin(train_weeks)]
    print(f"initial IPCA fit on {len(train_weeks)} training weeks ...")
    Gamma, factors, instruments = fit_ipca(train_df, K=K)
    lam = factors[[f"f{k+1}" for k in range(K)]].mean().values

    # Emit in-sample E for diagnostic; flagged in_sample=True.
    for wk in train_weeks:
        block = df[df["week"] == wk]
        if block.empty:
            continue
        Z = block[instruments].values
        e = Z @ Gamma @ lam
        out_rows.append(pd.DataFrame({
            "week": pd.Timestamp(wk), "symbol": block["symbol"].values,
            "E_ipca": e, "in_sample": True,
        }))

    # Walk-forward — refit Gamma every REFIT_FREQ weeks on expanding history.
    REFIT_FREQ = 4
    history = list(train_weeks)
    for i, wk in enumerate(weeks[TRAIN_WEEKS:]):
        # decide whether to refit
        if (i % REFIT_FREQ == 0) and i > 0:
            train_df = df[df["week"].isin(history)]
            print(f"  refit at week {pd.Timestamp(wk).date()} | history={len(history)} weeks")
            Gamma, factors, instruments = fit_ipca(train_df, K=K, max_iter=80)
            lam = factors[[f"f{k+1}" for k in range(K)]].mean().values
        block = df[df["week"] == wk]
        if block.empty:
            continue
        Z = block[instruments].values
        e = Z @ Gamma @ lam
        out_rows.append(pd.DataFrame({
            "week": pd.Timestamp(wk), "symbol": block["symbol"].values,
            "E_ipca": e, "in_sample": False,
        }))
        history.append(wk)
    return pd.concat(out_rows, ignore_index=True), Gamma, factors


def factor_premia(factors: pd.DataFrame, K: int) -> pd.DataFrame:
    """Time-series mean / t-stat of each latent factor (Newey-West not needed
    here because we report under iid assumption per Kelly-Pruitt-Su §3.4)."""
    rows = []
    for k in range(K):
        col = f"f{k+1}"
        f = factors[col].dropna().values
        mu = f.mean()
        se = f.std(ddof=1) / np.sqrt(len(f))
        rows.append({"factor": col, "mean": mu, "se": se, "tstat": mu / se if se > 0 else np.nan,
                     "n": len(f)})
    return pd.DataFrame(rows)


def _figures(Gamma: np.ndarray, factors: pd.DataFrame, instruments: list[str]) -> None:
    import plotly.express as px
    import plotly.graph_objects as go

    df = pd.DataFrame(Gamma, index=instruments,
                      columns=[f"f{k+1}" for k in range(Gamma.shape[1])])
    fig = px.imshow(df.values, x=df.columns, y=df.index,
                    color_continuous_scale="RdBu_r",
                    color_continuous_midpoint=0,
                    aspect="auto", text_auto=".2f")
    fig.update_layout(title="IPCA loading matrix Γ (characteristics × latent factors)", height=520)
    save_plotly(fig, "gamma_loadings", "02_ipca_pricing")

    fig = go.Figure()
    for col in factors.columns:
        if col == "week":
            continue
        fig.add_trace(go.Scatter(x=factors["week"], y=factors[col].cumsum(),
                                 mode="lines", name=col))
    fig.update_layout(title="Cumulative latent factor returns (training window)",
                      yaxis_title="cumulative return", height=520)
    save_plotly(fig, "factor_cumulative", "02_ipca_pricing")


def main() -> None:
    ipca_panel = build_ipca_panel()
    print(f"IPCA panel: {len(ipca_panel):,} rows, "
          f"{ipca_panel['week'].nunique()} weeks, {ipca_panel['symbol'].nunique()} symbols")
    e_df, Gamma, factors = expected_returns_walkforward(ipca_panel)
    premia = factor_premia(factors, K=N_FACTORS)

    write_frame(e_df, DATA_DIR / "ipca_expected_returns")
    write_frame(factors, DATA_DIR / "ipca_latent_factors")
    write_frame(premia, DATA_DIR / "ipca_factor_premia")
    write_frame(pd.DataFrame(Gamma, index=INSTRUMENT_COLS,
                             columns=[f"f{k+1}" for k in range(N_FACTORS)]).reset_index().rename(columns={"index": "instrument"}),
                DATA_DIR / "ipca_gamma")

    survived = premia.loc[premia["tstat"].abs() >= 1.65, "factor"].tolist()
    manifest = {
        "n_factors": N_FACTORS,
        "instruments": INSTRUMENT_COLS,
        "train_weeks": TRAIN_WEEKS,
        "premia": premia.to_dict(orient="records"),
        "survived_factors_t_ge_1p65": survived,
    }
    write_json(manifest, MANIFEST_DIR / "02_ipca_manifest.json")

    _figures(Gamma, factors, INSTRUMENT_COLS)
    print("done.")


if __name__ == "__main__":
    main()
