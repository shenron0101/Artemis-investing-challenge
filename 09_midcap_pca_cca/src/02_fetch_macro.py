#!/usr/bin/env python3
"""Fetch daily close data for SPY and VIX via yfinance.

BTC data is extracted from the CoinGecko daily parquet (already fetched).

Output: data/clean/macro_daily.parquet — columns: [date, asset, close, volume]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.data_io import (
    clean_dir,
    get_logger,
    write_parquet,
)


PROJ_ROOT = Path(__file__).resolve().parent.parent


def fetch_yfinance_data(tickers: list[str], start: str = "2021-01-01") -> pd.DataFrame:
    data = yf.download(tickers, start=start, interval="1d", group_by="ticker", auto_adjust=True)
    rows = []
    for ticker in tickers:
        if len(tickers) > 1:
            ticker_data = data[ticker] if ticker in data.columns.get_level_values(0) else None
        else:
            ticker_data = data

        if ticker_data is None:
            continue

        for idx, row in ticker_data.iterrows():
            rows.append(
                {
                    "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10],
                    "asset": ticker,
                    "close": row.get("Close"),
                    "volume": row.get("Volume"),
                }
            )

    return pd.DataFrame(rows)


def fetch_btc_from_coingecko(coingecko_path: Path, logger) -> pd.DataFrame | None:
    if not coingecko_path.exists():
        logger.warning("CoinGecko daily data not found at %s. BTC will be missing from macro.", coingecko_path)
        return None

    cg_df = pd.read_parquet(coingecko_path)

    overrides_path = PROJ_ROOT / "config" / "coingecko_id_overrides.yaml"
    import yaml
    btc_ids = {"bitcoin"}
    if overrides_path.exists():
        overrides_yaml = yaml.safe_load(overrides_path.read_text(encoding="utf-8")) or {}
        if "BTC" in (overrides_yaml.get("overrides") or {}):
            btc_ids.add(overrides_yaml["overrides"]["BTC"])

    btc_df = cg_df[cg_df["coingecko_id"].isin(btc_ids)].copy()

    if btc_df.empty:
        logger.warning("No BTC data found in CoinGecko daily data. Trying symbol='BTC'.")
        btc_df = cg_df[cg_df["symbol"].str.upper() == "BTC"].copy()

    if btc_df.empty:
        return None

    btc_agg = btc_df.groupby("date").agg({"price_usd": "last", "total_volume_usd": "sum"}).reset_index()

    btc_rows = []
    for _, row in btc_agg.iterrows():
        btc_rows.append(
            {
                "date": row["date"],
                "asset": "BTC",
                "close": row["price_usd"],
                "volume": row["total_volume_usd"],
            }
        )

    return pd.DataFrame(btc_rows)


def fetch_btc_from_artemis(artemis_path: Path, logger) -> pd.DataFrame | None:
    if not artemis_path.exists():
        logger.warning("Artemis daily data not found at %s. BTC will be missing from macro.", artemis_path)
        return None
    artemis_df = pd.read_parquet(artemis_path)
    btc_df = artemis_df[artemis_df["symbol"].str.lower().isin(["bitcoin", "btc"])].copy()
    if btc_df.empty:
        return None
    price_col = "price_usd"
    vol_col = "volume_24h_usd"
    btc_df = btc_df.groupby("date").agg({price_col: "last", vol_col: "sum"}).reset_index()
    btc_rows = []
    for _, row in btc_df.iterrows():
        btc_rows.append(
            {
                "date": row["date"],
                "asset": "BTC",
                "close": row[price_col],
                "volume": row[vol_col],
            }
        )
    return pd.DataFrame(btc_rows)


def main() -> None:
    logger = get_logger("macro_fetch")

    spy_vix = fetch_yfinance_data(["SPY", "^VIX"], start="2021-01-01")
    logger.info("Fetched SPY+VIX: %d rows", len(spy_vix))

    artemis_path = clean_dir() / "artemis_daily.parquet"
    btc_df = fetch_btc_from_artemis(artemis_path, logger)
    if btc_df is not None:
        logger.info("Extracted BTC from Artemis: %d rows", len(btc_df))
    else:
        coingecko_path = clean_dir() / "coingecko_daily.parquet"
        btc_df = fetch_btc_from_coingecko(coingecko_path, logger)
        if btc_df is not None:
            logger.info("Extracted BTC from CoinGecko: %d rows", len(btc_df))
        else:
            btc_df = pd.DataFrame(columns=["date", "asset", "close", "volume"])

    macro_df = pd.concat([spy_vix, btc_df], ignore_index=True)
    macro_df["date"] = pd.to_datetime(macro_df["date"]).dt.strftime("%Y-%m-%d")
    macro_df = macro_df.sort_values(["asset", "date"]).drop_duplicates(
        subset=["asset", "date"], keep="last"
    ).reset_index(drop=True)

    out_path = clean_dir() / "macro_daily.parquet"
    write_parquet(macro_df, out_path)
    logger.info("Wrote %d rows to %s", len(macro_df), out_path)

    for asset in macro_df["asset"].unique():
        sub = macro_df[macro_df["asset"] == asset]
        logger.info(
            "  %s: %d rows, %s → %s",
            asset,
            len(sub),
            sub["date"].min(),
            sub["date"].max(),
        )


if __name__ == "__main__":
    main()