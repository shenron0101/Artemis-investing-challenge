#!/usr/bin/env python3
"""Build weekly return matrix for PCA input.

Aligns to NYSE Friday 4:00 PM ET close, computes weekly log returns,
builds wide matrix (rows=weeks, cols=all-ever-in-universe assets),
and cross-sectional z-scores per week.

Outputs:
  data/features/returns_weekly_raw.parquet
  data/features/returns_weekly_zscore.parquet
  data/features/asset_metadata_weekly.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.data_io import (
    clean_dir,
    features_dir,
    get_logger,
    load_settings,
    write_parquet,
)

PROJ_ROOT = Path(__file__).resolve().parent.parent


def get_nyse_fridays(start: str = "2021-01-01", end: str | None = None) -> pd.DatetimeIndex:
    nyse = mcal.get_calendar("NYSE")
    if end is None:
        end = pd.Timestamp.now().strftime("%Y-%m-%d")
    schedule = nyse.valid_days(start_date=start, end_date=end)
    fridays = schedule[schedule.dayofweek == 4]
    return fridays


def main() -> None:
    logger = get_logger("build_returns")
    settings = load_settings()

    universe_path = clean_dir() / "universe_weekly.parquet"
    artemis_path = clean_dir() / "artemis_daily.parquet"
    coingecko_path = clean_dir() / "coingecko_daily.parquet"

    if not universe_path.exists():
        logger.error("Universe not found: %s. Run 03_build_universe.py first.", universe_path)
        sys.exit(1)

    universe_df = pd.read_parquet(universe_path)

    # Use Artemis data as primary, fall back to CoinGecko
    if artemis_path.exists():
        logger.info("Using Artemis daily data for price series")
        price_source = pd.read_parquet(artemis_path)
        price_source["date"] = pd.to_datetime(price_source["date"])
        id_col = "symbol"
        price_col = "price_usd" if "price_usd" in price_source.columns else "PRICE"
        price_pivot = price_source.pivot_table(
            index="date", columns=id_col, values=price_col,
        )
    elif coingecko_path.exists():
        logger.info("Using CoinGecko daily data for price series")
        price_source = pd.read_parquet(coingecko_path)
        price_source["date"] = pd.to_datetime(price_source["date"])
        price_pivot = price_source.pivot_table(
            index="date", columns="coingecko_id", values="price_usd",
        )
    else:
        logger.error("No daily price data found. Run 01_fetch_artemis.py or 01_fetch_coingecko.py first.")
        sys.exit(1)

    universe_dates = sorted(universe_df["rebalance_date"].unique())

    first_date = pd.Timestamp(universe_dates[0]) - pd.Timedelta(days=14)
    last_date = pd.Timestamp(universe_dates[-1])

    nyse_fridays = get_nyse_fridays(start=first_date.strftime("%Y-%m-%d"), end=last_date.strftime("%Y-%m-%d"))
    nyse_fridays = nyse_fridays.tz_localize(None) if nyse_fridays.tzinfo else nyse_fridays
    logger.info("Found %d NYSE Fridays", len(nyse_fridays))

    price_pivot = price_pivot.sort_index()
    price_pivot.columns = price_pivot.columns.str.upper()
    price_df = price_pivot.reindex(price_pivot.index)

    nearest_fridays = []
    for friday in nyse_fridays:
        friday_ts = pd.Timestamp(friday)
        available = price_df.index[price_df.index <= friday_ts + pd.Timedelta(days=1)]
        if len(available) == 0:
            continue
        nearest = available[-1]
        nearest_fridays.append(nearest)

    friday_prices = price_df.loc[price_df.index.isin(nearest_fridays)].copy()
    friday_prices = friday_prices.sort_index()

    log_returns = np.log(friday_prices / friday_prices.shift(1))
    log_returns = log_returns.iloc[1:]

    # Determine ID column for pivoted data
    id_col = price_pivot.columns.name if price_pivot.columns.name else "symbol"

    all_symbols = universe_df["symbol_upper"].dropna().unique()

    rebalance_dates = sorted(universe_df["rebalance_date"].unique())
    rebalance_dates_ts = [pd.Timestamp(d) for d in rebalance_dates]

    raw_rows = []
    zscore_rows = []
    metadata_rows = []

    for rd in rebalance_dates_ts:
        rd_str = rd.strftime("%Y-%m-%d")
        week_members = universe_df[universe_df["rebalance_date"] == rd_str]

        available_dates = log_returns.index[log_returns.index <= rd]
        if len(available_dates) == 0:
            continue
        closest_date = available_dates[-1]

        ret_row = log_returns.loc[closest_date]
        week_syms = week_members["symbol_upper"].dropna().unique()

        raw_data = {"date": rd_str}
        z_data = {"date": rd_str}

        week_returns = ret_row.reindex(week_syms).dropna()
        if len(week_returns) > 1:
            mean_r = week_returns.mean()
            std_r = week_returns.std()
            if std_r > 0:
                week_z = (week_returns - mean_r) / std_r
            else:
                week_z = pd.Series(0.0, index=week_returns.index)
        else:
            week_z = pd.Series(0.0, index=week_returns.index)

        for sym in week_syms:
            raw_val = ret_row.get(sym, np.nan)
            z_val = week_z.get(sym, np.nan) if not pd.isna(raw_val) else np.nan

            col_name = f"{sym}"
            raw_data[col_name] = raw_val
            z_data[col_name] = z_val

        raw_rows.append(raw_data)
        zscore_rows.append(z_data)

        for _, member in week_members.iterrows():
            metadata_rows.append(
                {
                    "date": rd_str,
                    "coingecko_id": member.get("coingecko_id", ""),
                    "symbol_upper": member.get("symbol_upper", ""),
                    "market_cap_usd": member.get("market_cap_usd"),
                    "adj_mcap": member.get("adj_mcap"),
                    "adj_rank": member.get("adj_rank"),
                    "supply_growth_4w": member.get("supply_growth_4w", 0.0),
                    "is_entry": member.get("is_entry", False),
                    "is_exit": member.get("is_exit", False),
                }
            )

    raw_df = pd.DataFrame(raw_rows)
    zscore_df = pd.DataFrame(zscore_rows)
    meta_df = pd.DataFrame(metadata_rows)

    raw_path = features_dir() / "returns_weekly_raw.parquet"
    z_path = features_dir() / "returns_weekly_zscore.parquet"
    meta_path = features_dir() / "asset_metadata_weekly.parquet"

    write_parquet(raw_df, raw_path)
    write_parquet(zscore_df, z_path)
    write_parquet(meta_df, meta_path)

    logger.info("Wrote raw returns: %d weeks, %d columns", len(raw_df), len(raw_df.columns) - 1)
    logger.info("Wrote z-score returns: %d weeks, %d columns", len(zscore_df), len(zscore_df.columns) - 1)
    logger.info("Wrote metadata: %d rows", len(meta_df))


if __name__ == "__main__":
    main()