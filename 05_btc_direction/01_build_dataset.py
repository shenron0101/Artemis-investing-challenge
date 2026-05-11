"""01 — Build BTC daily base table.

This reproduces the paper's data-assembly shape with the data available in
this repository: BTC market data from Binance/CoinGecko, BTC network activity
from Artemis, and broad liquidity context from DeFiLlama stablecoin/TVL tables.
"""
# %% Imports
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, MANIFEST_DIR, coerce_date, load_clean, write_frame, write_json

STEM = Path(__file__).stem


def _numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def load_btc_market() -> pd.DataFrame:
    """Daily BTC OHLCV, preferring Binance BTCUSDT and adding CoinGecko fields."""
    ohlcv = load_clean("binance_ohlcv_daily.parquet")
    ohlcv = ohlcv.loc[ohlcv["symbol"].astype(str).str.upper().eq("BTC")].copy()
    if ohlcv.empty:
        cg = load_clean("coingecko_daily_ticks.parquet")
        cg = cg.loc[cg["symbol"].astype(str).str.upper().eq("BTC")].copy()
        cg["date"] = coerce_date(cg["date"])
        cg = _numeric(cg, ["price_usd", "market_cap_usd", "total_volume_usd"])
        return (
            cg.rename(
                columns={
                    "price_usd": "close",
                    "market_cap_usd": "cg_market_cap_usd",
                    "total_volume_usd": "cg_total_volume_usd",
                }
            )
            .assign(open=lambda x: x["close"], high=lambda x: x["close"], low=lambda x: x["close"])
            [["date", "open", "high", "low", "close", "cg_market_cap_usd", "cg_total_volume_usd"]]
            .sort_values("date")
        )

    ohlcv["date"] = coerce_date(ohlcv["open_time"])
    ohlcv = _numeric(ohlcv, ["open", "high", "low", "close", "base_volume", "quote_volume", "trade_count"])
    ohlcv = ohlcv[
        ["date", "open", "high", "low", "close", "base_volume", "quote_volume", "trade_count"]
    ].dropna(subset=["date", "close"])
    ohlcv = ohlcv.sort_values("date").drop_duplicates("date", keep="last")

    cg = load_clean("coingecko_daily_ticks.parquet")
    cg = cg.loc[cg["symbol"].astype(str).str.upper().eq("BTC")].copy()
    if not cg.empty:
        cg["date"] = coerce_date(cg["date"])
        cg = _numeric(cg, ["price_usd", "market_cap_usd", "total_volume_usd"])
        cg = cg.rename(
            columns={
                "price_usd": "cg_price_usd",
                "market_cap_usd": "cg_market_cap_usd",
                "total_volume_usd": "cg_total_volume_usd",
            }
        )[["date", "cg_price_usd", "cg_market_cap_usd", "cg_total_volume_usd"]]
        cg = cg.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
        ohlcv = ohlcv.merge(cg, on="date", how="left")

    return ohlcv


def load_btc_activity() -> pd.DataFrame:
    activity = load_clean("artemis_activity_metrics.parquet")
    activity = activity.loc[activity["symbol"].astype(str).str.upper().eq("BTC")].copy()
    activity["date"] = coerce_date(activity["date"])
    metric_cols = [
        col
        for col in activity.columns
        if col not in {"date", "symbol", "run_id"} and pd.api.types.is_numeric_dtype(activity[col])
    ]
    activity = _numeric(activity, metric_cols)
    keep = ["date"] + [col for col in metric_cols if activity[col].notna().sum() > 0]
    activity = activity[keep].dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    return activity.rename(columns={col: f"artemis_{col}" for col in keep if col != "date"})


def load_stablecoin_liquidity() -> pd.DataFrame:
    supply = load_clean("defillama_stablecoin_inflows_daily.parquet")
    supply = supply.copy()
    supply["date"] = coerce_date(supply["date"])
    supply = _numeric(supply, ["supply_usd", "inflow_usd"])
    all_chain = supply.loc[supply["chain"].astype(str).str.upper().eq("ALL")].copy()
    if all_chain.empty:
        all_chain = supply.groupby("date", as_index=False)[["supply_usd", "inflow_usd"]].sum(min_count=1)
    else:
        all_chain = all_chain[["date", "supply_usd", "inflow_usd"]]
    all_chain = all_chain.sort_values("date").drop_duplicates("date", keep="last")
    return all_chain.rename(
        columns={"supply_usd": "defillama_stablecoin_supply_usd", "inflow_usd": "defillama_stablecoin_inflow_usd"}
    )


def load_defi_tvl() -> pd.DataFrame:
    tvl = load_clean("defillama_protocol_tvl_daily.parquet")
    tvl = tvl.copy()
    tvl["date"] = coerce_date(tvl["date"])
    tvl = _numeric(tvl, ["tvl_usd"])
    out = tvl.groupby("date", as_index=False)["tvl_usd"].sum(min_count=1)
    return out.rename(columns={"tvl_usd": "defillama_tracked_protocol_tvl_usd"})


def build_dataset() -> pd.DataFrame:
    base = load_btc_market()
    for loader in (load_btc_activity, load_stablecoin_liquidity, load_defi_tvl):
        side = loader()
        base = base.merge(side, on="date", how="left")

    base = base.sort_values("date").drop_duplicates("date", keep="last")
    # Forward-fill exogenous daily series only after sorting, preserving the
    # no-lookahead property for feature engineering.
    fill_cols = [col for col in base.columns if col not in {"date", "open", "high", "low", "close"}]
    base[fill_cols] = base[fill_cols].ffill()
    return base.reset_index(drop=True)


def main() -> None:
    df = build_dataset()
    write_frame(df, DATA_DIR / "btc_direction_base")
    write_json(
        {
            "rows": int(len(df)),
            "start_date": df["date"].min(),
            "end_date": df["date"].max(),
            "columns": df.columns.tolist(),
            "source_tables": [
                "binance_ohlcv_daily.parquet",
                "coingecko_daily_ticks.parquet",
                "artemis_activity_metrics.parquet",
                "defillama_stablecoin_inflows_daily.parquet",
                "defillama_protocol_tvl_daily.parquet",
            ],
            "paper_parity_note": "Uses current repo data as a hybrid fallback; Glassnode-style realized/unrealized value fields are not present.",
        },
        MANIFEST_DIR / "01_dataset_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
