"""01 - Build weekly crypto asset-pricing panel.

The panel follows the local-data version of "Crypto Pricing with Hidden
Factors": weekly asset returns, lagged market capitalization, lagged TVL /
market cap, and lagged characteristics used by long-short crypto factors.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, MANIFEST_DIR, coerce_date, coerce_week, exclude_symbols, load_clean, write_frame, write_json


def _numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _weekly_last(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return (
        df.sort_values(keys + ["date"])
        .dropna(subset=["week"])
        .groupby(keys + ["week"], as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )


def load_weekly_market_panel() -> pd.DataFrame:
    ticks = load_clean("coingecko_daily_ticks.parquet").copy()
    ticks["date"] = coerce_date(ticks["date"])
    ticks["week"] = coerce_week(ticks["date"])
    ticks["symbol"] = ticks["symbol"].astype(str).str.upper()
    ticks = _numeric(ticks, ["price_usd", "market_cap_usd", "total_volume_usd"])
    ticks = ticks.dropna(subset=["date", "week", "symbol", "price_usd"])
    ticks = ticks.loc[ticks["price_usd"].gt(0)]
    ticks = ticks.loc[~ticks["symbol"].isin(exclude_symbols())]

    master = load_clean("asset_master.parquet")[
        ["symbol", "coin_name", "cohort", "coingecko_id", "mapping_status"]
    ].copy()
    master["symbol"] = master["symbol"].astype(str).str.upper()
    weekly = _weekly_last(ticks, ["symbol"])
    weekly = weekly.merge(
        master.drop_duplicates("symbol"),
        on="symbol",
        how="left",
        suffixes=("", "_master"),
    )
    weekly["coin_name"] = weekly["coin_name_master"].combine_first(weekly["coin_name"])
    weekly["coingecko_id"] = weekly["coingecko_id_master"].combine_first(weekly["coingecko_id"])
    weekly = weekly.drop(columns=["coin_name_master", "coingecko_id_master"], errors="ignore")
    return weekly


def load_weekly_tvl_by_symbol() -> pd.DataFrame:
    tvl = load_clean("defillama_protocol_tvl_daily.parquet").copy()
    tvl["date"] = coerce_date(tvl["date"])
    tvl["week"] = coerce_week(tvl["date"])
    tvl = _numeric(tvl, ["tvl_usd"])
    dl_map = load_clean("defillama_protocol_map.parquet")[["symbol", "defillama_slug"]].dropna().drop_duplicates()
    dl_map["symbol"] = dl_map["symbol"].astype(str).str.upper()
    joined = tvl.merge(dl_map, on="defillama_slug", how="inner")
    weekly = (
        joined.dropna(subset=["week", "symbol"])
        .sort_values(["symbol", "defillama_slug", "date"])
        .groupby(["symbol", "defillama_slug", "week"], as_index=False)
        .tail(1)
    )
    return weekly.groupby(["symbol", "week"], as_index=False)["tvl_usd"].sum(min_count=1)


def load_weekly_activity() -> pd.DataFrame:
    activity = load_clean("artemis_activity_metrics.parquet").copy()
    activity["date"] = coerce_date(activity["date"])
    activity["week"] = coerce_week(activity["date"])
    activity["symbol"] = activity["symbol"].astype(str).str.upper()
    metric_cols = [
        col
        for col in ["dau", "fees", "revenue", "transactions", "volume", "active_addresses"]
        if col in activity.columns
    ]
    activity = _numeric(activity, metric_cols)
    weekly = activity.groupby(["symbol", "week"], as_index=False)[metric_cols].mean()
    return weekly.rename(columns={col: f"artemis_{col}_weekly_avg" for col in metric_cols})


def add_lagged_characteristics(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.sort_values(["symbol", "week"]).copy()
    by_symbol = out.groupby("symbol", group_keys=False)
    out["ret_1w"] = by_symbol["price_usd"].pct_change()
    out["log_ret_1w"] = by_symbol["price_usd"].transform(lambda s: np.log(s / s.shift(1)))
    out["lag_price_usd"] = by_symbol["price_usd"].shift(1)
    out["lag_market_cap_usd"] = by_symbol["market_cap_usd"].shift(1)
    out["lag_total_volume_usd"] = by_symbol["total_volume_usd"].shift(1)
    out["lag_tvl_usd"] = by_symbol["tvl_usd"].shift(1)
    out["lag_tvl_to_mcap"] = out["lag_tvl_usd"] / out["lag_market_cap_usd"]
    out["log_lag_market_cap"] = np.log(out["lag_market_cap_usd"].where(out["lag_market_cap_usd"].gt(0)))
    out["mom_5w"] = by_symbol["log_ret_1w"].transform(
        lambda s: np.exp(s.shift(1).rolling(5, min_periods=4).sum()) - 1.0
    )
    return out.replace([np.inf, -np.inf], np.nan)


def build_panel() -> pd.DataFrame:
    market = load_weekly_market_panel()
    tvl = load_weekly_tvl_by_symbol()
    activity = load_weekly_activity()
    panel = market.merge(tvl, on=["symbol", "week"], how="left")
    panel = panel.merge(activity, on=["symbol", "week"], how="left")
    panel = add_lagged_characteristics(panel)
    panel = panel.loc[
        panel["ret_1w"].notna()
        & panel["lag_market_cap_usd"].gt(0)
        & panel["price_usd"].gt(0)
    ].copy()
    counts = panel.groupby("symbol")["ret_1w"].count()
    keep_symbols = counts[counts.ge(12)].index
    panel = panel.loc[panel["symbol"].isin(keep_symbols)].copy()
    keep_cols = [
        "week",
        "date",
        "symbol",
        "coin_name",
        "cohort",
        "coingecko_id",
        "mapping_status",
        "price_usd",
        "market_cap_usd",
        "total_volume_usd",
        "tvl_usd",
        "ret_1w",
        "log_ret_1w",
        "lag_price_usd",
        "lag_market_cap_usd",
        "lag_total_volume_usd",
        "lag_tvl_usd",
        "lag_tvl_to_mcap",
        "log_lag_market_cap",
        "mom_5w",
    ] + [col for col in panel.columns if col.startswith("artemis_")]
    return panel[keep_cols].sort_values(["week", "symbol"]).reset_index(drop=True)


def main() -> None:
    panel = build_panel()
    write_frame(panel, DATA_DIR / "weekly_asset_panel")
    write_json(
        {
            "rows": int(len(panel)),
            "symbols": int(panel["symbol"].nunique()),
            "weeks": int(panel["week"].nunique()),
            "start_week": panel["week"].min(),
            "end_week": panel["week"].max(),
            "excluded_symbol_count": len(exclude_symbols()),
            "source_tables": [
                "coingecko_daily_ticks.parquet",
                "asset_master.parquet",
                "coingecko_coin_details.parquet",
                "defillama_protocol_map.parquet",
                "defillama_protocol_tvl_daily.parquet",
                "artemis_activity_metrics.parquet",
            ],
            "scope_note": "Repo-native weekly panel; returns are raw crypto returns because a risk-free series is not present in clean data.",
        },
        MANIFEST_DIR / "01_panel_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
