#!/usr/bin/env python3
"""Rolling PCA with EWMA weighting, RMT denoising, sign alignment, and parallel analysis.

For each rebalance date after the 12-week burn-in:
1. Extract trailing 12 weeks of z-scored returns for universe assets
2. Apply EWMA weights (halflife=4w) before covariance estimation
3. Compute weighted covariance matrix
4. RMT-denoise the correlation matrix (Marchenko-Pastur)
5. Eigendecompose the denoised matrix
6. Select components via parallel analysis (compare eigenvalues to random matrix 95th pct)
7. Sign-align eigenvectors across time
8. Project current week returns onto retained eigenvectors

Outputs:
  data/features/pca_scores.parquet
  data/features/pca_loadings.parquet
  data/features/pca_diagnostics.parquet
  artifacts/manifests/pca_manifest.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.data_io import (
    features_dir,
    get_logger,
    load_settings,
    manifests_dir,
    write_manifest,
    write_parquet,
)
from utils.missing_data import get_psd_covariance
from utils.rmt import denoise_covariance, marchenko_pastur_bounds

PROJ_ROOT = Path(__file__).resolve().parent.parent


def ewma_weights(window: int, halflife: int) -> np.ndarray:
    """Compute EWMA weights for a rolling window.

    Parameters
    ----------
    window : int
        Window length in weeks.
    halflife : int
        Halflife in weeks.

    Returns
    -------
    np.ndarray
        Normalised weights of shape (window,).
    """
    lags = np.arange(window - 1, -1, -1)
    raw = np.exp(-np.log(2) * lags / halflife)
    return raw / raw.sum()


def parallel_analysis(
    n_assets: int,
    n_obs: int,
    n_permutations: int = 100,
    alpha: float = 0.05,
) -> np.ndarray:
    """Run parallel analysis to determine significant eigenvalues.

    Generate random matrices of shape (n_obs, n_assets) from i.i.d. normal,
    compute eigenvalues, and return the (1-alpha) percentile threshold for each
    component position.

    Parameters
    ----------
    n_assets : int
        Number of variables.
    n_obs : int
        Number of time observations.
    n_permutations : int
        Number of random matrix permutations.
    alpha : float
        Significance level (default 0.05 for 95th percentile).

    Returns
    -------
    np.ndarray
        Threshold eigenvalues of shape (n_assets,).
    """
    eigenvalues_all = np.zeros((n_permutations, min(n_assets, n_obs)))

    for i in range(n_permutations):
        random_data = np.random.randn(n_obs, n_assets)
        random_corr = np.corrcoef(random_data, rowvar=False)
        if random_corr.ndim < 2:
            continue
        eigs = np.sort(np.linalg.eigvalsh(random_corr))[::-1]
        n_eigs = min(n_assets, n_obs)
        eigenvalues_all[i, :n_eigs] = eigs[:n_eigs]

    threshold = np.percentile(eigenvalues_all, (1 - alpha) * 100, axis=0)
    return threshold


def main() -> None:
    logger = get_logger("pca_factors")
    settings = load_settings()
    pca_cfg = settings.get("pca", {})

    window_weeks = int(pca_cfg.get("window_weeks", 12))
    halflife = int(pca_cfg.get("ewma_halflife_weeks", 4))
    min_shared = int(pca_cfg.get("min_shared_weeks", 8))
    sign_alignment = bool(pca_cfg.get("sign_alignment", True))
    rmt_denoising = bool(pca_cfg.get("rmt_denoising", True))
    n_permutations = int(pca_cfg.get("n_parallel_analysis_permutations", 100))
    alpha = float(pca_cfg.get("parallel_analysis_alpha", 0.05))

    zscore_path = features_dir() / "returns_weekly_zscore.parquet"
    meta_path = features_dir() / "asset_metadata_weekly.parquet"

    if not zscore_path.exists():
        logger.error("Z-score returns not found: %s. Run 04_build_returns.py first.", zscore_path)
        sys.exit(1)

    zscore_df = pd.read_parquet(zscore_path)
    logger.info("Loaded z-score returns: %d weeks, %d columns", len(zscore_df), len(zscore_df.columns) - 1)

    dates = sorted(zscore_df["date"].values)
    if len(dates) <= window_weeks:
        logger.error("Not enough weeks (%d) for burn-in window (%d).", len(dates), window_weeks)
        sys.exit(1)

    score_rows = []
    loading_rows = []
    diag_rows = []
    prev_eigenvectors = None

    for i, date in enumerate(dates):
        date_idx = list(zscore_df["date"].values).index(date)
        if date_idx < window_weeks:
            continue

        window_dates = dates[date_idx - window_weeks : date_idx]
        window_df = zscore_df[zscore_df["date"].isin(window_dates)].copy()

        if len(window_df) < window_weeks:
            logger.warning("Window incomplete for %s: %d rows", date, len(window_df))
            continue

        feature_cols = [c for c in window_df.columns if c != "date"]
        window_data = window_df[feature_cols].values.astype(float)

        weights = ewma_weights(window_weeks, halflife)
        sqrt_weights = np.sqrt(weights)
        weighted_data = window_data * sqrt_weights[:, np.newaxis]

        valid_mask = ~np.isnan(weighted_data).all(axis=0)
        valid_cols = np.where(valid_mask)[0]
        if len(valid_cols) < 3:
            logger.warning("Too few valid assets for PCA on %s: %d", date, len(valid_cols))
            continue

        sub_data = weighted_data[:, valid_cols]

        has_nan = np.any(np.isnan(sub_data))
        if has_nan:
            cov_matrix = get_psd_covariance(sub_data, min_shared=min_shared, fallback_to_knn=True)
        else:
            cov_matrix = np.cov(sub_data, rowvar=False, ddof=1)

        n_obs = len(window_df)
        n_assets = sub_data.shape[1]

        if rmt_denoising:
            cov_matrix = denoise_covariance(cov_matrix, n_observations=n_obs)

        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        mp_thresholds = parallel_analysis(
            n_assets=n_assets,
            n_obs=n_obs,
            n_permutations=n_permutations,
            alpha=alpha,
        )

        n_retained = int(np.sum(eigenvalues[:len(mp_thresholds)] > mp_thresholds))
        n_retained = max(n_retained, 1)
        n_retained = min(n_retained, n_assets)

        if sign_alignment and prev_eigenvectors is not None:
            min_dim = min(prev_eigenvectors.shape[0], eigenvectors.shape[0])
            prev_n = min(prev_eigenvectors.shape[1], eigenvectors.shape[1])
            for j in range(prev_n):
                sim = np.dot(eigenvectors[:min_dim, j], prev_eigenvectors[:min_dim, j])
                if sim < 0:
                    eigenvectors[:, j] *= -1

        prev_eigenvectors = eigenvectors.copy()

        current_week_data = zscore_df[zscore_df["date"] == date][feature_cols].values.astype(float).flatten()
        current_week_valid = current_week_data[valid_cols]
        current_week_valid = np.nan_to_num(current_week_valid, nan=0.0)

        scores = np.dot(current_week_valid, eigenvectors[:, :n_retained])

        valid_features = [feature_cols[j] for j in valid_cols]

        score_row = {"date": date}
        for k in range(n_retained):
            score_row[f"PC{k + 1}"] = scores[k]
        score_rows.append(score_row)

        for j, col_name in enumerate(valid_features):
            parts = col_name.rsplit("_", 1)
            sym = parts[0] if len(parts) > 1 else col_name
            cg_id = parts[1] if len(parts) > 1 else ""
            loading_row = {
                "date": date,
                "coingecko_id": cg_id,
                "symbol": sym,
            }
            for k in range(n_retained):
                loading_row[f"PC{k + 1}_loading"] = eigenvectors[j, k]
            loading_rows.append(loading_row)

        total_var = np.sum(eigenvalues)
        cum_var = 0.0
        for k in range(n_assets):
            expl = eigenvalues[k] / total_var if total_var > 0 else 0.0
            cum_var += expl
            diag_rows.append(
                {
                    "date": date,
                    "component": k + 1,
                    "eigenvalue": eigenvalues[k],
                    "expl_var_ratio": eigenvalues[k] / total_var if total_var > 0 else 0.0,
                    "cumul_var": cum_var,
                    "mp_threshold": mp_thresholds[k] if k < len(mp_thresholds) else np.nan,
                    "retained": k < n_retained,
                }
            )

        if i % 20 == 0 or i == len(dates) - 1:
            logger.info(
                "PCA %s: n_retained=%d/%d, expl_var=%.2f%%",
                date,
                n_retained,
                n_assets,
                sum(eigenvalues[:n_retained]) / total_var * 100 if total_var > 0 else 0,
            )

    scores_df = pd.DataFrame(score_rows)
    loadings_df = pd.DataFrame(loading_rows)
    diagnostics_df = pd.DataFrame(diag_rows)

    write_parquet(scores_df, features_dir() / "pca_scores.parquet")
    write_parquet(loadings_df, features_dir() / "pca_loadings.parquet")
    write_parquet(diagnostics_df, features_dir() / "pca_diagnostics.parquet")

    manifest = {
        "window_weeks": window_weeks,
        "halflife_weeks": halflife,
        "rmt_denoising": rmt_denoising,
        "sign_alignment": sign_alignment,
        "n_permutations": n_permutations,
        "alpha": alpha,
        "n_weeks_processed": len(score_rows),
        "output_files": [
            "pca_scores.parquet",
            "pca_loadings.parquet",
            "pca_diagnostics.parquet",
        ],
    }
    write_manifest(manifest, "pca_manifest.json")

    logger.info("PCA complete. Scores: %d weeks, Loadings: %d rows", len(scores_df), len(loadings_df))


if __name__ == "__main__":
    main()