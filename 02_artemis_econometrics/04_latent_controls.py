"""04 — Latent factor controls via rolling PCA on the return panel.

At each week t we fit a PCA on the trailing W=52 weeks of cross-sectional
returns (symbol×week matrix, columns standardized per asset). We retain the
top K=3 principal components, then project the full window onto them. For
each symbol we record:

    pc1_load, pc2_load, pc3_load  — exposure to each latent factor (past-only window)
    pc1_var_share, ...            — explained-variance share of each component
    residual_ret                  — the in-window residual of the most recent
                                    past weekly return (t-1) after regressing
                                    on the top-K factor scores

This is the local-data version of "Crypto Pricing with Hidden Factors". The
residualized return is exposed so downstream models can either control for
latent factors as covariates *or* use the residualized return as a denoised
response variable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, MANIFEST_DIR, write_frame, write_json

INPUT_CHARACTERISTICS = DATA_DIR / "characteristics.parquet"

WINDOW_WEEKS = 26
MIN_OVERLAP = 16
N_FACTORS = 3
MIN_SYMBOLS = N_FACTORS + 2


def returns_wide(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.pivot_table(index="week", columns="symbol", values="ret_1w", aggfunc="last")
        .sort_index()
    )


def pca_one_week(window: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray] | None:
    """Run PCA on the window (rows=weeks, cols=symbols).

    Returns (loadings_df, var_ratio).
    `loadings_df` is symbol×N_FACTORS. We treat each symbol as a series, so we
    transpose the matrix before fitting — that way the components are
    `symbol × factor`. Symbols with too many NaNs in the window are excluded.
    """
    eligible = window.dropna(axis=1, thresh=MIN_OVERLAP)
    if eligible.shape[1] < MIN_SYMBOLS:
        return None
    filled = eligible.fillna(0.0)
    # Center on per-asset mean so PCA captures cross-sectional structure.
    centered = filled - filled.mean(axis=0)
    pca = PCA(n_components=min(N_FACTORS, centered.shape[0], centered.shape[1]))
    # We want loadings PER SYMBOL on each factor — fit on rows=symbols.
    # Equivalent to PCA on symbol covariance.
    loadings = pca.fit_transform(centered.T.values)
    columns = [f"pc{i+1}_load" for i in range(loadings.shape[1])]
    loadings_df = pd.DataFrame(loadings, index=eligible.columns, columns=columns)
    return loadings_df, pca.explained_variance_ratio_


def residual_returns(window: pd.DataFrame, loadings_df: pd.DataFrame) -> pd.Series:
    """Residualize the most recent in-window weekly return against the loadings.

    The calling window is past-only for forecast week t, so the latest row is
    t-1. Fit OLS at that row: r_latest = X β + ε with X = loadings_df. Return
    the residual ε per symbol.
    """
    if loadings_df is None or loadings_df.empty:
        return pd.Series(dtype=float)
    latest = window.iloc[-1].dropna()
    common = latest.index.intersection(loadings_df.index)
    if len(common) < N_FACTORS + 2:
        return pd.Series(dtype=float)
    X = loadings_df.loc[common].values
    y = latest.loc[common].values
    X1 = np.hstack([np.ones((X.shape[0], 1)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ beta
    return pd.Series(resid, index=common, name="residual_ret")


def build_latent_controls(ret: pd.DataFrame) -> tuple[pd.DataFrame, list[float]]:
    weeks = ret.index
    rows: list[pd.DataFrame] = []
    var_means: list[np.ndarray] = []
    for i, week in enumerate(weeks):
        if i < WINDOW_WEEKS:
            continue
        window = ret.iloc[i - WINDOW_WEEKS : i]
        result = pca_one_week(window)
        if result is None:
            continue
        loadings_df, var_ratio = result
        residual = residual_returns(window, loadings_df)
        var_means.append(var_ratio)
        wk_df = loadings_df.copy()
        wk_df["residual_ret"] = residual
        wk_df = wk_df.reset_index().rename(columns={"index": "symbol"})
        wk_df.insert(0, "week", week)
        for j, share in enumerate(var_ratio):
            wk_df[f"pc{j+1}_var_share"] = float(share)
        rows.append(wk_df)

    if not rows:
        empty = pd.DataFrame(columns=["week", "symbol", "pc1_load", "pc2_load", "pc3_load", "residual_ret"])
        return empty, []

    out = pd.concat(rows, ignore_index=True)
    avg_var = list(np.mean(np.vstack(var_means), axis=0)) if var_means else []
    return out, avg_var


def main() -> None:
    panel = pd.read_parquet(INPUT_CHARACTERISTICS)
    ret = returns_wide(panel)
    latent, avg_var = build_latent_controls(ret)
    write_frame(latent, DATA_DIR / "latent_controls")
    write_json(
        {
            "window_weeks": WINDOW_WEEKS,
            "min_overlap": MIN_OVERLAP,
            "n_factors": N_FACTORS,
            "avg_explained_var_per_factor": avg_var,
            "weeks_with_factors": int(latent["week"].nunique()) if len(latent) else 0,
            "rows": int(len(latent)),
        },
        MANIFEST_DIR / "04_latent_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
