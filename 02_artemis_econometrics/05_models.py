"""05 — Benchmark econometric models.

Five models compared on the same out-of-sample window:

    base_fm    — Fama-MacBeth on characteristics only
    base_pool  — Pooled OLS on characteristics only
    base_lasso — ElasticNetCV on characteristics only
    plus_lat   — characteristics + PCA latent factor loadings
    plus_net   — characteristics + latent + network features (the competition
                 candidate)

Cross-sectional standardization is applied per week before fitting so the
coefficients are interpretable as z-score → return units. We use a single
chronological train/test split (70/30) for compute simplicity; Fama-MacBeth
diagnostics also use the *training* weeks to produce mean β / t-stats.

The output is a long frame `(week, symbol, model, prediction)` over the test
weeks, plus a `betas` table of per-model coefficients.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNetCV

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    DATA_DIR,
    MANIFEST_DIR,
    TABLE_DIR,
    standardize_features,
    winsorize_cs,
    write_frame,
    write_json,
)

INPUT_CHARACTERISTICS = DATA_DIR / "characteristics.parquet"
INPUT_NETWORK = DATA_DIR / "network_features.parquet"
INPUT_LATENT = DATA_DIR / "latent_controls.parquet"

TRAIN_FRAC = 0.70
MIN_OBS_PER_WEEK = 8

BASE_FEATURES = [
    "log_mcap",
    "log_dollar_vol",
    "turnover",
    "tvl_to_mcap",
    "mom_1w",
    "mom_4w",
    "mom_12w",
    "vol_4w",
    "F_yield",
    "G_growth",
    "S_supply",
    "stable_inflow_z",
]
LATENT_FEATURES = ["pc1_load", "pc2_load", "pc3_load"]
NETWORK_FEATURES = ["within_cluster_mom", "cross_cluster_rel"]


def assemble_dataset() -> pd.DataFrame:
    panel = pd.read_parquet(INPUT_CHARACTERISTICS)
    net = pd.read_parquet(INPUT_NETWORK) if INPUT_NETWORK.exists() else None
    lat = pd.read_parquet(INPUT_LATENT) if INPUT_LATENT.exists() else None

    out = panel.copy()
    if net is not None:
        out = out.merge(net, on=["week", "symbol"], how="left")
    if lat is not None:
        out = out.merge(lat, on=["week", "symbol"], how="left")
    return out


def winsorize_and_standardize(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    feature_cols = [c for c in feature_cols if c in out.columns]
    for c in feature_cols:
        wide = out.pivot_table(index="week", columns="symbol", values=c, aggfunc="last")
        wide_w = winsorize_cs(wide, p=0.01)
        long = wide_w.stack(future_stack=True).rename(c).reset_index()
        out = out.drop(columns=[c]).merge(long, on=["week", "symbol"], how="left")
    out = standardize_features(out, feature_cols, by="week")
    return out


def train_test_split_by_week(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    weeks = sorted(df["week"].unique())
    cutoff = weeks[int(len(weeks) * TRAIN_FRAC)]
    train = df.loc[df["week"].lt(cutoff)].copy()
    test = df.loc[df["week"].ge(cutoff)].copy()
    return train, test, cutoff


def fit_fama_macbeth(train: pd.DataFrame, features: list[str]) -> tuple[pd.Series, pd.DataFrame]:
    """Cross-sectional OLS per week; mean and t-stat of slope coefficients.

    Each weekly regression: fwd_ret = α + Σ β_k * x_k. Returns:
      mean_beta — Series indexed by feature
      weekly_betas — DataFrame (week × feature) of per-week slopes

    Missing features are imputed with 0 (post-standardization mean) so that
    rows with sparse coverage still contribute to the within-week regression.
    """
    rows = []
    for week, grp in train.groupby("week"):
        x_raw = grp[features].to_numpy(dtype=float)
        y = grp["fwd_ret_1w"].to_numpy(dtype=float)
        mask = ~np.isnan(y)
        if mask.sum() < MIN_OBS_PER_WEEK:
            continue
        x_clean = np.where(np.isnan(x_raw[mask]), 0.0, x_raw[mask])
        y_clean = y[mask]
        x1 = np.hstack([np.ones((x_clean.shape[0], 1)), x_clean])
        beta, *_ = np.linalg.lstsq(x1, y_clean, rcond=None)
        rows.append([week] + beta.tolist())
    if not rows:
        return pd.Series(0.0, index=["intercept"] + features), pd.DataFrame()
    cols = ["week", "intercept"] + features
    weekly = pd.DataFrame(rows, columns=cols).set_index("week")
    mean_beta = weekly.mean()
    return mean_beta, weekly


def fit_pooled_ols(train: pd.DataFrame, features: list[str]) -> pd.Series:
    df = train.dropna(subset=["fwd_ret_1w"]).copy()
    if df.empty:
        return pd.Series(0.0, index=["intercept"] + features)
    x = df[features].to_numpy(dtype=float)
    x = np.where(np.isnan(x), 0.0, x)
    y = df["fwd_ret_1w"].to_numpy(dtype=float)
    x1 = np.hstack([np.ones((x.shape[0], 1)), x])
    beta, *_ = np.linalg.lstsq(x1, y, rcond=None)
    return pd.Series(beta, index=["intercept"] + features)


def fit_elasticnet(train: pd.DataFrame, features: list[str]) -> pd.Series:
    df = train.dropna(subset=["fwd_ret_1w"]).copy()
    if len(df) < 30:
        return pd.Series(0.0, index=["intercept"] + features)
    x = df[features].to_numpy(dtype=float)
    x = np.where(np.isnan(x), 0.0, x)
    y = df["fwd_ret_1w"].to_numpy(dtype=float)
    model = ElasticNetCV(
        l1_ratio=[0.1, 0.5, 0.9, 1.0],
        n_alphas=20,
        cv=5,
        random_state=0,
        max_iter=5000,
    )
    model.fit(x, y)
    coefs = pd.Series(model.coef_, index=features)
    coefs["intercept"] = float(model.intercept_)
    return coefs.reindex(["intercept"] + features)


def predict_linear(df: pd.DataFrame, betas: pd.Series, features: list[str]) -> pd.Series:
    x = df[features].to_numpy(dtype=float)
    nan_mask = np.isnan(x)
    x_filled = np.where(nan_mask, 0.0, x)
    intercept = float(betas.get("intercept", 0.0))
    pred = intercept + x_filled @ betas.reindex(features).fillna(0.0).to_numpy()
    # treat a row as missing only when every characteristic is NaN
    pred = np.where(nan_mask.all(axis=1), np.nan, pred)
    return pd.Series(pred, index=df.index, name="prediction")


def run_models(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    base_cols = [c for c in BASE_FEATURES if c in df.columns]
    lat_cols = base_cols + [c for c in LATENT_FEATURES if c in df.columns]
    net_cols = lat_cols + [c for c in NETWORK_FEATURES if c in df.columns]

    train, test, cutoff = train_test_split_by_week(df)

    # Fama-MacBeth: betas computed on TRAIN weeks; applied to TEST features.
    fm_mean, fm_weekly = fit_fama_macbeth(train, base_cols)

    pooled = fit_pooled_ols(train, base_cols)
    lat_pooled = fit_pooled_ols(train, lat_cols)
    net_pooled = fit_pooled_ols(train, net_cols)

    fm_pred = predict_linear(test, fm_mean, base_cols)
    pool_pred = predict_linear(test, pooled, base_cols)
    lat_pred = predict_linear(test, lat_pooled, lat_cols)
    net_pred = predict_linear(test, net_pooled, net_cols)

    pred_long = (
        test[["week", "symbol", "fwd_ret_1w"]]
        .assign(
            base_fm=fm_pred.values,
            base_pool=pool_pred.values,
            plus_lat=lat_pred.values,
            plus_net=net_pred.values,
        )
        .melt(
            id_vars=["week", "symbol", "fwd_ret_1w"],
            var_name="model",
            value_name="prediction",
        )
    )

    betas = (
        pd.concat(
            [
                fm_mean.rename("base_fm"),
                pooled.rename("base_pool"),
                lat_pooled.rename("plus_lat"),
                net_pooled.rename("plus_net"),
            ],
            axis=1,
        )
        .rename_axis("feature")
        .reset_index()
    )

    diagnostics = {
        "cutoff_week": str(cutoff.date()) if hasattr(cutoff, "date") else str(cutoff),
        "n_train_weeks": int(train["week"].nunique()),
        "n_test_weeks": int(test["week"].nunique()),
        "base_features": base_cols,
        "lat_features": lat_cols,
        "net_features": net_cols,
        "fm_t_stats": {
            feat: float(fm_weekly[feat].mean() / (fm_weekly[feat].std() / np.sqrt(len(fm_weekly))))
            if feat in fm_weekly.columns and fm_weekly[feat].std() > 0
            else None
            for feat in fm_weekly.columns
        }
        if not fm_weekly.empty
        else {},
    }
    return pred_long, betas, diagnostics


def main() -> None:
    df = assemble_dataset()
    all_features = list(dict.fromkeys(BASE_FEATURES + LATENT_FEATURES + NETWORK_FEATURES))
    df = winsorize_and_standardize(df, all_features)

    pred_long, betas, diag = run_models(df)
    write_frame(pred_long, DATA_DIR / "model_predictions")
    write_frame(betas, TABLE_DIR / "model_betas")
    write_json(diag, MANIFEST_DIR / "05_models_manifest.json")
    print("done.")


if __name__ == "__main__":
    main()
