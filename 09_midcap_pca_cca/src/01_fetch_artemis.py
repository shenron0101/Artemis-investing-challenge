#!/usr/bin/env python3
"""Fetch daily market data from Artemis API for all tracked assets.

Uses the Artemis Python SDK to pull PRICE, MC (market cap),
CIRCULATING_SUPPLY_NATIVE, and 24H_VOLUME daily time series
from Jan 2021 to present. This provides survivorship-bias-free
point-in-time data for universe construction.

Output: data/clean/artemis_daily.parquet
       data/clean/cmc_rankings_weekly.parquet (updated weekly rankings from Artemis MC)
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

PROJ_ROOT = Path(__file__).resolve().parent.parent
PARENT_VENV = Path(__file__).resolve().parent.parent.parent / ".venv" / "lib" / "python3.14" / "site-packages"
sys.path.insert(0, str(PARENT_VENV))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.data_io import clean_dir, get_logger, load_settings, raw_dir, write_parquet


def fetch_artemis_assets(api_key: str, logger: Any) -> list[dict[str, Any]]:
    """Fetch the full list of Artemis assets with symbol and coingecko_id mappings."""
    from artemis import Artemis

    client = Artemis(api_key=api_key)
    response = client.asset.list_asset_symbols()
    assets = []
    for a in response.assets:
        assets.append({
            "artemis_id": a.artemis_id,
            "symbol": a.symbol,
            "name": a.title,
            "coingecko_id": a.coingecko_id,
        })
    logger.info("Fetched %d Artemis assets", len(assets))
    return assets


def fetch_artemis_metrics(
    api_key: str,
    symbols: list[str],
    metrics: list[str],
    start_date: date,
    end_date: date,
    logger: Any,
) -> pd.DataFrame:
    """Fetch daily time series for multiple symbols and metrics from Artemis."""
    from artemis import Artemis

    client = Artemis(api_key=api_key)
    metric_str = ",".join(metrics)
    all_rows = []

    batch_size = 20
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        sym_str = ",".join(batch)
        logger.info("Fetching Artemis batch %d/%d: %s", i // batch_size + 1, (len(symbols) + batch_size - 1) // batch_size, sym_str[:80])

        try:
            response = client.fetch_metrics(
                metric_names=metric_str,
                api_key=api_key,
                symbols=sym_str,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            logger.warning("Artemis batch failed: %s", exc)
            continue

        data = response.data
        if not hasattr(data, "symbols"):
            logger.warning("No symbols in response for batch starting at %d", i)
            continue

        for sym, sym_metrics in data.symbols.items():
            if not isinstance(sym_metrics, dict):
                continue
            for metric_name, values in sym_metrics.items():
                if values is None:
                    continue
                for item in values:
                    if hasattr(item, "date") and hasattr(item, "val"):
                        all_rows.append({
                            "date": str(item.date),
                            "symbol": sym,
                            "metric": metric_name,
                            "value": item.val,
                        })
                    elif isinstance(item, dict):
                        all_rows.append({
                            "date": str(item.get("date", "")),
                            "symbol": sym,
                            "metric": metric_name,
                            "value": item.get("val"),
                        })

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])

    pivoted = df.pivot_table(index=["date", "symbol"], columns="metric", values="value", aggfunc="first").reset_index()
    pivoted.columns.name = None

    return pivoted


def build_weekly_rankings(artemis_daily: pd.DataFrame, assets_df: pd.DataFrame, logger: Any) -> pd.DataFrame:
    """Build weekly point-in-time top-200 rankings from Artemis daily market cap data.

    For each Sunday (aligned with CMC snapshot convention), rank all assets by
    market cap and produce the same schema as cmc_rankings_weekly.parquet.
    """
    mc_col = "market_cap_usd" if "market_cap_usd" in artemis_daily.columns else "MC"
    mc_df = artemis_daily[["date", "symbol", mc_col]].dropna(subset=[mc_col]).copy()
    mc_df = mc_df.rename(columns={mc_col: "MC"})
    mc_df["date"] = pd.to_datetime(mc_df["date"])

    mc_df["dow"] = mc_df["date"].dt.dayofweek
    sundays = mc_df[mc_df["dow"] == 6].copy()

    rows = []
    for date_val, group in sundays.groupby("date"):
        date_str = date_val.strftime("%Y%m%d") if hasattr(date_val, "strftime") else str(date_val)[:8]
        ranked = group.sort_values("MC", ascending=False).reset_index(drop=True)
        ranked["rank"] = range(1, len(ranked) + 1)

        sym_to_name = dict(zip(assets_df["symbol"].str.upper(), assets_df["name"]))
        sym_to_cg = dict(zip(assets_df["symbol"].str.upper(), assets_df["coingecko_id"]))

        for _, row in ranked.iterrows():
            sym_upper = str(row["symbol"]).upper()
            rows.append({
                "snapshot_date": date_str,
                "rank": int(row["rank"]),
                "name": sym_to_name.get(sym_upper, row["symbol"]),
                "symbol": row["symbol"],
                "market_cap_usd": row["MC"],
                "price_usd": None,
                "volume_24h_usd": None,
                "circulating_supply": None,
                "change_7d_pct": None,
            })

    return pd.DataFrame(rows)


def fill_artemis_daily(artemis_pivoted: pd.DataFrame, logger: Any) -> pd.DataFrame:
    """Merge Artemis daily metrics into a single wide DataFrame and add derived columns."""
    df = artemis_pivoted.copy()

    col_map = {}
    for col in df.columns:
        cl = col.upper()
        if cl == "MC":
            col_map[col] = "market_cap_usd"
        elif cl == "PRICE":
            col_map[col] = "price_usd"
        elif "CIRCULATING" in cl or cl == "CIRCULATING_SUPPLY_NATIVE":
            col_map[col] = "circulating_supply"
        elif "24H_VOLUME" in cl or cl == "24H_VOLUME":
            col_map[col] = "volume_24h_usd"
        elif cl == "FDMC":
            col_map[col] = "fdmc_usd"

    df = df.rename(columns=col_map)

    if "price_usd" in df.columns and "market_cap_usd" in df.columns:
        valid = (df["price_usd"] > 0) & df["market_cap_usd"].notna()
        df.loc[valid, "implied_circulating_supply"] = df.loc[valid, "market_cap_usd"] / df.loc[valid, "price_usd"]

    if "circulating_supply" not in df.columns:
        df["circulating_supply"] = np.nan

    return df


def main() -> None:
    logger = get_logger("artemis_fetch")
    settings = load_settings()
    artemis_cfg = settings.get("artemis", {})
    api_key = artemis_cfg.get("api_key", "")

    if not api_key:
        logger.error("ARTEMIS_API_KEY not set in config/settings.yaml")
        sys.exit(1)

    assets = fetch_artemis_assets(api_key, logger)
    assets_df = pd.DataFrame(assets)

    valid_symbols = [a["artemis_id"] for a in assets if a["symbol"]]
    logger.info("Fetching data for %d assets", len(valid_symbols))

    metrics = artemis_cfg.get("metrics", ["PRICE", "MC", "CIRCULATING_SUPPLY_NATIVE", "24H_VOLUME"])
    start_date = date(2021, 1, 1)
    end_date = date.today()

    full_df = fetch_artemis_metrics(
        api_key=api_key,
        symbols=valid_symbols,
        metrics=metrics,
        start_date=start_date,
        end_date=end_date,
        logger=logger,
    )

    if full_df.empty:
        logger.error("No Artemis data fetched. Falling back to CoinGecko-only pipeline.")
        sys.exit(1)

    logger.info("Artemis data: %d rows, %d columns", len(full_df), len(full_df.columns))

    daily_df = fill_artemis_daily(full_df, logger)
    out_daily = clean_dir() / "artemis_daily.parquet"
    write_parquet(daily_df, out_daily)
    logger.info("Wrote %d rows to %s", len(daily_df), out_daily)

    rankings = build_weekly_rankings(daily_df, assets_df, logger)
    if not rankings.empty:
        out_rankings = clean_dir() / "cmc_rankings_weekly.parquet"
        write_parquet(rankings, out_rankings)
        logger.info("Wrote %d weekly ranking rows to %s", len(rankings), out_rankings)

        n_dates = rankings["snapshot_date"].nunique()
        n_syms = rankings["symbol"].nunique()
        logger.info("Weekly snapshots: %d, Unique symbols: %d", n_dates, n_syms)


if __name__ == "__main__":
    main()