#!/usr/bin/env python3
"""Give economic meaning to abstract PCs by correlating loadings with observable characteristics.

For each PC and each week:
1. Compute Spearman rank correlation between PC loading vector and:
   - log(market_cap) — size
   - 4-week price momentum — trend
   - 4-week realised volatility — risk
   - volume / market_cap — turnover
   - supply_growth_4w — dilution
2. Time-average correlations to find stable associations
3. K-means clustering on loading profiles (k=3-5) per week
4. Track cluster composition over time

Outputs:
  data/features/pc_char_correlations.parquet
  data/features/pc_clusters.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.data_io import (
    clean_dir,
    features_dir,
    get_logger,
    load_settings,
    write_parquet,
)

PROJ_ROOT = Path(__file__).resolve().parent.parent


def compute_momentum(price_df: pd.DataFrame, lookback: int = 4) -> pd.DataFrame:
    id_col = "symbol" if "symbol" in price_df.columns else "coingecko_id"
    prices = price_df[["date", id_col, "price_usd"]].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices.sort_values([id_col, "date"])

    prices["price_lag4"] = prices.groupby(id_col)["price_usd"].shift(lookback)
    prices["momentum_4w"] = np.log(prices["price_usd"] / prices["price_lag4"])

    return prices[["date", id_col, "momentum_4w"]].dropna()


def compute_volatility(price_df: pd.DataFrame, lookback: int = 4) -> pd.DataFrame:
    id_col = "symbol" if "symbol" in price_df.columns else "coingecko_id"
    prices = price_df[["date", id_col, "price_usd"]].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices.sort_values([id_col, "date"])

    prices["log_ret"] = np.log(prices["price_usd"] / prices.groupby(id_col)["price_usd"].shift(1))

    def rolling_std(group):
        return group["log_ret"].rolling(lookback, min_periods=3).std()

    prices["vol_4w"] = prices.groupby(id_col, group_keys=False).apply(rolling_std)
    return prices[["date", id_col, "vol_4w"]].dropna()


def main() -> None:
    logger = get_logger("factor_interpretation")
    settings = load_settings()

    loadings_path = features_dir() / "pca_loadings.parquet"
    meta_path = features_dir() / "asset_metadata_weekly.parquet"
    artemis_path = clean_dir() / "artemis_daily.parquet"
    cg_path = clean_dir() / "coingecko_daily.parquet"

    for p, name in [(loadings_path, "PCA loadings"), (meta_path, "metadata")]:
        if not p.exists():
            logger.error("%s not found: %s", name, p)
            sys.exit(1)

    loadings_df = pd.read_parquet(loadings_path)
    meta_df = pd.read_parquet(meta_path)

    if artemis_path.exists():
        logger.info("Using Artemis daily data for characteristics")
        price_df = pd.read_parquet(artemis_path)
        price_df["date"] = pd.to_datetime(price_df["date"])
        id_col = "symbol"
        vol_col = "volume_24h_usd" if "volume_24h_usd" in price_df.columns else "total_volume_usd"
        price_df[id_col] = price_df[id_col].str.upper()
    elif cg_path.exists():
        logger.info("Using CoinGecko daily data for characteristics")
        price_df = pd.read_parquet(cg_path)
        price_df["date"] = pd.to_datetime(price_df["date"])
        id_col = "coingecko_id"
        vol_col = "total_volume_usd"
    else:
        logger.error("No daily price data found. Run 01_fetch_artemis.py or 01_fetch_coingecko.py first.")
        sys.exit(1)

    momentum_df = compute_momentum(price_df)
    volatility_df = compute_volatility(price_df)

    turnover_df = price_df[["date", id_col, vol_col, "market_cap_usd"]].copy()
    turnover_df["turnover_ratio"] = turnover_df[vol_col] / turnover_df["market_cap_usd"].replace(0, np.nan)
    turnover_df = turnover_df[["date", id_col, "turnover_ratio"]].dropna()

    meta_df["log_mcap"] = np.log1p(meta_df["market_cap_usd"].fillna(0).clip(lower=0))

    pc_cols = [c for c in loadings_df.columns if c.endswith("_loading")]

    join_col = "symbol_upper" if "symbol_upper" in loadings_df.columns else ("symbol" if "symbol" in loadings_df.columns else "coingecko_id")
    meta_join_col = "symbol_upper" if "symbol_upper" in meta_df.columns else ("symbol" if "symbol" in meta_df.columns else "coingecko_id")
    corr_rows = []
    cluster_rows = []

    dates = sorted(loadings_df["date"].unique())

    for date in dates:
        week_loadings = loadings_df[loadings_df["date"] == date].copy()
        week_meta = meta_df[meta_df["date"] == date].copy()

        merged = week_loadings.merge(
            week_meta[[meta_join_col, "log_mcap", "market_cap_usd", "supply_growth_4w"]],
            left_on=join_col,
            right_on=meta_join_col,
            how="left",
            suffixes=("", "_meta"),
        )

        date_ts = pd.Timestamp(date)

        week_mom = momentum_df[
            (momentum_df["date"] <= date_ts) & (momentum_df["date"] >= date_ts - pd.Timedelta(days=14))
        ].groupby(id_col)["momentum_4w"].last().reset_index()

        week_vol = volatility_df[
            (volatility_df["date"] <= date_ts) & (volatility_df["date"] >= date_ts - pd.Timedelta(days=14))
        ].groupby(id_col)["vol_4w"].last().reset_index()

        week_turn = turnover_df[
            (turnover_df["date"] <= date_ts) & (turnover_df["date"] >= date_ts - pd.Timedelta(days=14))
        ].groupby(id_col)["turnover_ratio"].last().reset_index()

        merged = merged.merge(week_mom, left_on=join_col, right_on=id_col, how="left")
        merged = merged.merge(week_vol, left_on=join_col, right_on=id_col, how="left")
        merged = merged.merge(week_turn, left_on=join_col, right_on=id_col, how="left")

        characteristics = {
            "log_mcap": "log_mcap",
            "momentum_4w": "momentum_4w",
            "vol_4w": "vol_4w",
            "turnover_ratio": "turnover_ratio",
            "supply_growth_4w": "supply_growth_4w",
        }

        for pc_col in pc_cols:
            pc_name = pc_col.replace("_loading", "")
            for char_name, char_col in characteristics.items():
                valid = merged[[pc_col, char_col]].dropna()
                if len(valid) < 5:
                    continue
                corr, pval = spearmanr(valid[pc_col], valid[char_col])
                corr_rows.append(
                    {
                        "date": date,
                        "pc": pc_name,
                        "characteristic": char_name,
                        "spearman_rho": corr,
                        "p_value": pval,
                        "n_assets": len(valid),
                    }
                )

        loading_matrix = merged[pc_cols].dropna()
        if len(loading_matrix) < 5:
            continue

        n_clusters = min(5, max(3, len(loading_matrix) // 10))
        try:
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(loading_matrix.values)

            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)

            valid_indices = loading_matrix.index
            for j, idx in enumerate(valid_indices):
                cluster_rows.append(
                    {
                        "date": date,
                        "symbol": merged.loc[idx, join_col] if join_col in merged.columns else "",
                        "cluster": int(labels[j]),
                    }
                )
        except Exception as exc:
            logger.warning("Clustering failed for %s: %s", date, exc)
            continue

    corr_df = pd.DataFrame(corr_rows)
    cluster_df = pd.DataFrame(cluster_rows)

    write_parquet(corr_df, features_dir() / "pc_char_correlations.parquet")
    write_parquet(cluster_df, features_dir() / "pc_clusters.parquet")

    logger.info("Wrote %d characteristic correlations", len(corr_df))
    logger.info("Wrote %d cluster assignments", len(cluster_df))

    if not corr_df.empty:
        avg_corr = corr_df.groupby(["pc", "characteristic"])["spearman_rho"].mean().reset_index()
        for _, row in avg_corr.iterrows():
            logger.info("  %s x %s: avg rho=%.3f", row["pc"], row["characteristic"], row["spearman_rho"])


if __name__ == "__main__":
    main()