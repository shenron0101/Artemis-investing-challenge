"""01 — Weekly cross-sectional panel for the Artemis econometrics track.

Builds a symbol×week panel keyed on Monday-start weeks. Columns include the
weekly close price, market cap, dollar volume, TVL (when mappable), and the
weekly-mean Artemis activity metrics. Stablecoins / wrapped / bridged tokens
are excluded up front so downstream feature steps inherit a clean universe.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    DATA_DIR,
    MANIFEST_DIR,
    coerce_date,
    coerce_week,
    exclude_symbols,
    load_clean,
    write_frame,
    write_json,
)

MIN_WEEKS_PER_SYMBOL = 12


def _numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def load_weekly_market() -> pd.DataFrame:
    """Weekly last-observation close, market cap, volume per symbol."""
    ticks = load_clean("coingecko_daily_ticks.parquet").copy()
    ticks["date"] = coerce_date(ticks["date"])
    ticks["week"] = coerce_week(ticks["date"])
    ticks["symbol"] = ticks["symbol"].astype(str).str.upper()
    ticks = _numeric(ticks, ["price_usd", "market_cap_usd", "total_volume_usd"])
    ticks = ticks.dropna(subset=["date", "week", "symbol", "price_usd"])
    ticks = ticks.loc[ticks["price_usd"].gt(0)]
    ticks = ticks.loc[~ticks["symbol"].isin(exclude_symbols())]

    weekly = (
        ticks.sort_values(["symbol", "date"])
        .groupby(["symbol", "week"], as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )

    master = load_clean("asset_master.parquet")[
        ["symbol", "coin_name", "cohort", "coingecko_id"]
    ].drop_duplicates("symbol").copy()
    master["symbol"] = master["symbol"].astype(str).str.upper()
    weekly = weekly.merge(master, on="symbol", how="left", suffixes=("", "_m"))
    weekly["coin_name"] = weekly["coin_name_m"].combine_first(weekly["coin_name"])
    weekly["coingecko_id"] = weekly["coingecko_id_m"].combine_first(weekly["coingecko_id"])
    weekly = weekly.drop(columns=[c for c in weekly.columns if c.endswith("_m")])
    return weekly


def load_weekly_tvl() -> pd.DataFrame:
    tvl = load_clean("defillama_protocol_tvl_daily.parquet").copy()
    tvl["date"] = coerce_date(tvl["date"])
    tvl["week"] = coerce_week(tvl["date"])
    tvl = _numeric(tvl, ["tvl_usd"])
    dl_map = load_clean("defillama_protocol_map.parquet")[
        ["symbol", "defillama_slug"]
    ].dropna().drop_duplicates()
    dl_map["symbol"] = dl_map["symbol"].astype(str).str.upper()
    joined = tvl.merge(dl_map, on="defillama_slug", how="inner")
    last_obs = (
        joined.dropna(subset=["week", "symbol"])
        .sort_values(["symbol", "defillama_slug", "date"])
        .groupby(["symbol", "defillama_slug", "week"], as_index=False)
        .tail(1)
    )
    return last_obs.groupby(["symbol", "week"], as_index=False)["tvl_usd"].sum(min_count=1)


def load_weekly_activity() -> pd.DataFrame:
    activity = load_clean("artemis_activity_metrics.parquet").copy()
    activity["date"] = coerce_date(activity["date"])
    activity["week"] = coerce_week(activity["date"])
    activity["symbol"] = activity["symbol"].astype(str).str.upper()
    candidate = [
        "dau",
        "fees",
        "revenue",
        "active_revenue",
        "passive_revenue",
        "transactions",
        "txns",
        "volume",
        "active_addresses",
    ]
    keep = [c for c in candidate if c in activity.columns]
    activity = _numeric(activity, keep)
    weekly = activity.groupby(["symbol", "week"], as_index=False)[keep].mean(numeric_only=True)
    return weekly.rename(columns={c: f"act_{c}" for c in keep})


def load_weekly_stablecoin_supply() -> pd.DataFrame:
    """System-wide stablecoin supply / inflow — broadcast across symbols later."""
    df = load_clean("defillama_stablecoin_inflows_daily.parquet").copy()
    df["date"] = coerce_date(df["date"])
    df["week"] = coerce_week(df["date"])
    df = _numeric(df, ["supply_usd", "inflow_usd"])
    all_chain = df.loc[df["chain"].astype(str).str.upper().eq("ALL")]
    if all_chain.empty:
        all_chain = df.groupby(["week", "date"], as_index=False)[
            ["supply_usd", "inflow_usd"]
        ].sum(min_count=1)
    weekly = (
        all_chain.sort_values("date")
        .groupby("week", as_index=False)
        .tail(1)
        .reset_index(drop=True)[["week", "supply_usd", "inflow_usd"]]
    )
    return weekly.rename(
        columns={
            "supply_usd": "stable_supply_usd",
            "inflow_usd": "stable_inflow_usd",
        }
    )


def add_returns(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.sort_values(["symbol", "week"]).copy()
    by_sym = out.groupby("symbol", group_keys=False)
    out["ret_1w"] = by_sym["price_usd"].pct_change()
    out["log_ret_1w"] = by_sym["price_usd"].transform(lambda s: np.log(s / s.shift(1)))
    # forward return used downstream by 02..06 — kept here so the panel is the
    # single source of truth for response variables.
    out["fwd_ret_1w"] = by_sym["log_ret_1w"].shift(-1)
    return out.replace([np.inf, -np.inf], np.nan)


def build_panel() -> pd.DataFrame:
    market = load_weekly_market()
    tvl = load_weekly_tvl()
    activity = load_weekly_activity()
    stable = load_weekly_stablecoin_supply()

    panel = market.merge(tvl, on=["symbol", "week"], how="left")
    panel = panel.merge(activity, on=["symbol", "week"], how="left")
    panel = panel.merge(stable, on=["week"], how="left")
    panel = add_returns(panel)

    panel = panel.loc[
        panel["ret_1w"].notna()
        & panel["price_usd"].gt(0)
    ].copy()

    counts = panel.groupby("symbol")["ret_1w"].count()
    keep = counts[counts.ge(MIN_WEEKS_PER_SYMBOL)].index
    panel = panel.loc[panel["symbol"].isin(keep)].copy()

    return panel.sort_values(["week", "symbol"]).reset_index(drop=True)


def main() -> None:
    panel = build_panel()
    write_frame(panel, DATA_DIR / "panel")
    write_json(
        {
            "rows": int(len(panel)),
            "symbols": int(panel["symbol"].nunique()),
            "weeks": int(panel["week"].nunique()),
            "start_week": panel["week"].min(),
            "end_week": panel["week"].max(),
            "min_weeks_per_symbol": MIN_WEEKS_PER_SYMBOL,
            "excluded_symbol_count": len(exclude_symbols()),
            "source_tables": [
                "coingecko_daily_ticks.parquet",
                "asset_master.parquet",
                "coingecko_coin_details.parquet",
                "defillama_protocol_tvl_daily.parquet",
                "defillama_protocol_map.parquet",
                "artemis_activity_metrics.parquet",
                "defillama_stablecoin_inflows_daily.parquet",
            ],
        },
        MANIFEST_DIR / "01_panel_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
