#!/usr/bin/env python3
"""CCA between crypto PC scores and macro assets (BTC, SPY, VIX).

1. Load PCA scores and macro daily data
2. Compute weekly returns for BTC and SPY (Friday-to-Friday log returns)
3. Compute weekly VIX change (Friday close - previous Friday close)
4. Align on NYSE calendar dates
5. Full-sample CCA + rolling CCA (52-week expanding window)
6. Wilks' Lambda test + permutation test (1000 shuffles)

Outputs:
  data/features/cca_results.parquet
  data/features/cca_variates.parquet
  data/features/cca_rolling.parquet
  artifacts/manifests/cca_manifest.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cross_decomposition import CCA

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.calendar import get_friday_closes
from utils.data_io import (
    clean_dir,
    features_dir,
    get_logger,
    load_settings,
    manifests_dir,
    write_manifest,
    write_parquet,
)

PROJ_ROOT = Path(__file__).resolve().parent.parent


def wilks_lambda_test(x: np.ndarray, y: np.ndarray, n_components: int) -> dict:
    """Compute Wilks' Lambda and F-approximation for CCA significance.

    Parameters
    ----------
    x : np.ndarray
        X matrix (n_samples, p).
    y : np.ndarray
        Y matrix (n_samples, q).
    n_components : int
        Number of canonical components to test.

    Returns
    -------
    dict
        Wilks' Lambda, F-statistic, p-value.
    """
    from numpy.linalg import inv

    n = x.shape[0]
    p = x.shape[1]
    q = y.shape[1]

    cxx = np.cov(x, rowvar=False)
    cyy = np.cov(y, rowvar=False)
    cxy = np.cov(x, y, rowvar=False)[:p, p:]

    try:
        cxx_inv = inv(cxx)
        cyy_inv = inv(cyy)
    except np.linalg.LinAlgError:
        return {"wilks_lambda": np.nan, "f_stat": np.nan, "p_value": np.nan, "df1": np.nan, "df2": np.nan}

    m = cxx_inv @ cxy @ cyy_inv @ cxy.T
    eigenvalues = np.sort(np.real(np.linalg.eigvalsh(m)))[::-1]
    eigenvalues = eigenvalues[eigenvalues > 0]

    if len(eigenvalues) == 0:
        return {"wilks_lambda": np.nan, "f_stat": np.nan, "p_value": np.nan, "df1": np.nan, "df2": np.nan}

    wilks = np.prod(1.0 - eigenvalues[:n_components])

    t = min(p, q)
    df1 = p * q
    df2 = n - 1 - (p + q + 1) // 2

    if df2 <= 0:
        df2 = 1

    if wilks > 0 and wilks < 1:
        f_stat = ((1 - wilks ** (1 / t)) / (wilks ** (1 / t))) * (df2 / df1)
        p_value = 1.0 - stats.f.cdf(f_stat, df1, df2)
    else:
        f_stat = np.nan
        p_value = np.nan

    return {
        "wilks_lambda": wilks,
        "f_stat": f_stat,
        "p_value": p_value,
        "df1": df1,
        "df2": df2,
    }


def permutation_test(
    x: np.ndarray,
    y: np.ndarray,
    n_components: int,
    n_permutations: int = 1000,
) -> list[float]:
    """Permutation test for CCA canonical correlations.

    Shuffle Y rows independently and recompute CCA to build null distribution.

    Parameters
    ----------
    x : np.ndarray
        X matrix.
    y : np.ndarray
        Y matrix.
    n_components : int
        Number of components.
    n_permutations : int
        Number of permutations.

    Returns
    -------
    list[float]
        List of max canonical correlations under null for each permutation.
    """
    null_corrs = []
    n_samples = x.shape[0]

    for _ in range(n_permutations):
        perm_indices = np.random.permutation(n_samples)
        y_perm = y[perm_indices]

        cca_perm = CCA(n_components=n_components)
        try:
            x_scores, y_scores = cca_perm.fit_transform(x, y_perm)
            corrs = [
                np.corrcoef(x_scores[:, i], y_scores[:, i])[0, 1]
                for i in range(n_components)
            ]
            null_corrs.append(max(corrs))
        except Exception:
            continue

    return null_corrs


def main() -> None:
    logger = get_logger("cca_analysis")
    settings = load_settings()
    cca_cfg = settings.get("cca", {})

    n_permutations = int(cca_cfg.get("n_permutations", 1000))
    rolling_window = int(cca_cfg.get("rolling_window_weeks", 52))

    scores_path = features_dir() / "pca_scores.parquet"
    macro_path = clean_dir() / "macro_daily.parquet"

    if not scores_path.exists():
        logger.error("PCA scores not found: %s. Run 05_pca_factors.py first.", scores_path)
        sys.exit(1)
    if not macro_path.exists():
        logger.error("Macro data not found: %s. Run 02_fetch_macro.py first.", macro_path)
        sys.exit(1)

    scores_df = pd.read_parquet(scores_path)
    macro_df = pd.read_parquet(macro_path)

    scores_df["date"] = pd.to_datetime(scores_df["date"])
    macro_df["date"] = pd.to_datetime(macro_df["date"])

    macro_close = macro_df.pivot_table(index="date", columns="asset", values="close")
    macro_close = macro_close.sort_index()

    pca_dates = sorted(scores_df["date"].dt.strftime("%Y-%m-%d").unique())
    pca_dates_ts = [pd.Timestamp(d) for d in pca_dates]

    nearest_dates = []
    for d in pca_dates_ts:
        available = macro_close.index[macro_close.index <= d + pd.Timedelta(days=3)]
        if len(available) == 0:
            continue
        nearest = available[-1]
        nearest_dates.append(nearest)

    macro_weekly = macro_close.loc[macro_close.index.isin(nearest_dates)].copy()

    returns_dict = {}
    for col in macro_weekly.columns:
        col_ret = f"{col}_return"
        returns_dict[col_ret] = np.log(macro_weekly[col] / macro_weekly[col].shift(1))

    macro_returns = pd.DataFrame(returns_dict, index=macro_weekly.index)

    vix_close = macro_df[macro_df["asset"] == "^VIX"][["date", "close"]].rename(columns={"close": "VIX_close"})
    vix_close = vix_close.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    vix_close["VIX_change"] = vix_close["VIX_close"].diff()

    vix_weekly = vix_close.reindex(nearest_dates)
    macro_features = macro_returns.join(vix_weekly[["VIX_change"]], how="left")
    macro_features = macro_features.dropna(subset=[c for c in macro_features.columns if "return" in c or "change" in c])

    macro_features["pca_date"] = [None] * len(macro_features)
    for i, idx_date in enumerate(macro_features.index):
        diffs = [(abs((idx_date - pd.Timestamp(d)).days), d) for d in pca_dates]
        diffs.sort()
        macro_features.iat[i, macro_features.columns.get_loc("pca_date")] = diffs[0][1]

    macro_features["pca_date"] = pd.to_datetime(macro_features["pca_date"])

    pc_cols = [c for c in scores_df.columns if c.startswith("PC")]
    max_components = min(len(pc_cols), 3)

    scores_df = scores_df.sort_values("date")
    macro_features = macro_features.sort_index()

    merged = scores_df.merge(
        macro_features,
        left_on="date",
        right_on="pca_date",
        how="inner",
    )

    drop_cols = ["pca_date"] if "pca_date" in merged.columns else []
    merged = merged.drop(columns=drop_cols, errors="ignore")

    if merged.empty:
        logger.error("No aligned dates between PCA scores and macro features.")
        sys.exit(1)

    logger.info("Merged dataset: %d weeks, %d PC columns, %d macro columns", len(merged), max_components, macro_features.shape[1])

    pc_cols = [c for c in merged.columns if c.startswith("PC")]
    macro_ret_cols = [c for c in merged.columns if "return" in c or "VIX_change" in c]

    x_cols = pc_cols[:max_components]
    y_cols_target = ["BTC_return", "SPY_return", "VIX_change"]
    available_y = [c for c in y_cols_target if c in merged.columns]
    if len(available_y) < 2:
        available_y = [c for c in macro_ret_cols if c in merged.columns][:3]

    if len(available_y) < 2:
        logger.error("Need at least 2 macro variables for CCA, found: %s", available_y)
        sys.exit(1)

    X = merged[x_cols].values
    y_actual_cols = available_y[:max_components]
    n_components = min(len(x_cols), len(y_actual_cols))
    Y = merged[y_actual_cols].values

    mask = ~(np.isnan(X).any(axis=1) | np.isnan(Y).any(axis=1))
    X_clean = X[mask]
    Y_clean = Y[mask]
    dates_clean = merged.loc[mask, "date"].values

    cca = CCA(n_components=n_components)
    x_scores, y_scores = cca.fit_transform(X_clean, Y_clean)

    canonical_corrs = []
    for i in range(n_components):
        corr = np.corrcoef(x_scores[:, i], y_scores[:, i])[0, 1]
        canonical_corrs.append(corr)

    logger.info("Canonical correlations: %s", [f"{c:.4f}" for c in canonical_corrs])

    wilks = wilks_lambda_test(X_clean, Y_clean, n_components)
    logger.info("Wilks' Lambda: %.4f, p-value: %.4e", wilks["wilks_lambda"], wilks["p_value"])

    x_weights = cca.x_weights_
    y_weights = cca.y_weights_

    results_rows = []
    variate_rows = []

    for i in range(n_components):
        results_rows.append(
            {
                "component": i + 1,
                "canonical_corr": canonical_corrs[i],
                "wilks_lambda": wilks["wilks_lambda"],
                "f_stat": wilks["f_stat"],
                "p_value": wilks["p_value"],
            }
        )

    for i, col in enumerate(x_cols):
        for j in range(n_components):
            results_rows.append(
                {
                    "component": j + 1,
                    "variable": col,
                    "x_weight": float(x_weights[i, j]),
                }
            )

    for i, col in enumerate(y_actual_cols):
        for j in range(n_components):
            results_rows.append(
                {
                    "component": j + 1,
                    "variable": col,
                    "y_weight": float(y_weights[i, j]),
                }
            )

    for idx in range(len(dates_clean)):
        row = {"date": str(dates_clean[idx])[:10]}
        for i in range(n_components):
            row[f"CV{i + 1}_x"] = float(x_scores[idx, i])
            row[f"CV{i + 1}_y"] = float(y_scores[idx, i])
        variate_rows.append(row)

    results_df = pd.DataFrame(results_rows)
    variates_df = pd.DataFrame(variate_rows)

    null_corrs = permutation_test(X_clean, Y_clean, n_components, n_permutations)
    perm_p_values = []
    for i, observed_corr in enumerate(canonical_corrs):
        null = [nc for nc in null_corrs if nc is not None and not np.isnan(nc)]
        if len(null) > 0:
            p_val = float(np.mean(np.array(null) >= observed_corr))
        else:
            p_val = np.nan
        perm_p_values.append(p_val)
        logger.info("  CV%d perm p-value: %.4e", i + 1, p_val)

    rolling_rows = []
    for start_idx in range(0, len(dates_clean) - rolling_window + 1):
        end_idx = start_idx + rolling_window
        if end_idx > len(X_clean):
            break

        x_roll = X_clean[start_idx:end_idx]
        y_roll = Y_clean[start_idx:end_idx]
        d_roll = dates_clean[start_idx:end_idx]

        if np.any(np.isnan(x_roll)) or np.any(np.isnan(y_roll)):
            continue

        try:
            cca_roll = CCA(n_components=n_components)
            x_s, y_s = cca_roll.fit_transform(x_roll, y_roll)
            corrs_roll = [np.corrcoef(x_s[:, i], y_s[:, i])[0, 1] for i in range(n_components)]

            rolling_rows.append(
                {
                    "date": str(d_roll[-1])[:10],
                    "window_start": str(d_roll[0])[:10],
                    "window_end": str(d_roll[-1])[:10],
                    "n_obs": end_idx - start_idx,
                    **{f"CV{i + 1}_corr": corrs_roll[i] for i in range(n_components)},
                }
            )
        except Exception as exc:
            logger.warning("Rolling CCA failed for window ending %s: %s", str(d_roll[-1])[:10], exc)
            continue

    rolling_df = pd.DataFrame(rolling_rows)

    write_parquet(results_df, features_dir() / "cca_results.parquet")
    write_parquet(variates_df, features_dir() / "cca_variates.parquet")
    write_parquet(rolling_df, features_dir() / "cca_rolling.parquet")

    manifest = {
        "n_components": n_components,
        "x_variables": x_cols,
        "y_variables": y_actual_cols,
        "n_observations": len(X_clean),
        "canonical_correlations": canonical_corrs,
        "permutation_p_values": perm_p_values,
        "wilks_lambda": wilks,
        "rolling_window_weeks": rolling_window,
        "n_permutations": n_permutations,
    }
    write_manifest(manifest, "cca_manifest.json")

    logger.info("CCA complete. %d components, %d observations", n_components, len(X_clean))
    for i, corr in enumerate(canonical_corrs):
        logger.info("  CV%d: r=%.4f (perm p=%.4e)", i + 1, corr, perm_p_values[i] if i < len(perm_p_values) else float("nan"))


if __name__ == "__main__":
    main()