#!/usr/bin/env python3
"""Build weekly mid-cap universe with exclusions, dilution adjustment, and hysteresis.

At each weekly rebalance date:
1. Exclude stablecoins/wrapped/bridged tokens from exclusion_list.yaml
2. Re-rank remaining coins by market_cap_usd
3. Compute 4-week supply growth from CoinGecko implied supply
4. Compute dilution-adjusted market cap: adj_mcap = mcap * max(0, 1 - supply_growth_4w)
5. Re-rank by adj_mcap
6. Apply ±5 hysteresis buffer
7. Output universe membership + metadata

Outputs:
  data/clean/universe_weekly.parquet
  data/clean/universe_summary.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.data_io import (
    clean_dir,
    get_logger,
    load_yaml,
    load_settings,
    raw_dir,
    write_parquet,
)

PROJ_ROOT = Path(__file__).resolve().parent.parent


def load_exclusion_list(path: Path) -> set[str]:
    cfg = load_yaml(path)
    symbols: set[str] = set()
    for key in ("stablecoins", "wrapped_tokens", "bridged_tokens", "aggregate_indices"):
        for s in cfg.get(key, []) or []:
            symbols.add(str(s).upper().strip())
    return symbols


def compute_supply_growth(df: pd.DataFrame) -> pd.DataFrame:
    is_artemis = "circulating_supply" in df.columns and "implied_circulating_supply" not in df.columns

    if is_artemis:
        supply_col = "circulating_supply"
        id_col = "symbol"
        date_col = "date"
        sym_col = "symbol"
    else:
        supply_col = "implied_circulating_supply"
        id_col = "coingecko_id"
        date_col = "date"
        sym_col = "symbol"

    required = [date_col, id_col, sym_col, supply_col]
    available = [c for c in required if c in df.columns]
    if len(available) < len(required):
        available_cols = [c for c in [date_col, sym_col, supply_col] if c in df.columns]
        cg = df[available_cols].copy()
        cg["supply_growth_4w"] = 0.0
        return cg

    cg = df[required].copy()
    cg = cg.dropna(subset=[supply_col])
    cg[date_col] = pd.to_datetime(cg[date_col])
    cg = cg.sort_values([id_col, date_col])

    lag4 = cg.groupby(id_col)[supply_col].shift(4)
    cg["supply_growth_4w"] = (cg[supply_col] / lag4) - 1.0
    cg.loc[cg["supply_growth_4w"].abs() > 10.0, "supply_growth_4w"] = np.nan

    result_cols = [date_col, id_col, sym_col, supply_col, "supply_growth_4w"]
    return cg[result_cols].copy()


def build_universe(
    cmc_df: pd.DataFrame,
    cg_supply_df: pd.DataFrame,
    excluded_symbols: set[str],
    rank_min: int,
    rank_max: int,
    hysteresis_buffer: int,
    supply_growth_penalty: bool,
    supply_growth_threshold: float,
    ranking_source: str,
    symbol_to_id: dict[str, str],
    logger,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cmc = cmc_df.copy()

    if "market_cap_rank" in cmc.columns and "rank" not in cmc.columns:
        cmc["rank"] = cmc["market_cap_rank"]

    if "rank" not in cmc.columns:
        cmc = cmc.sort_values("market_cap_usd", ascending=False, na_position="last")
        cmc["rank"] = range(1, len(cmc) + 1)

    cmc["snapshot_date"] = pd.to_datetime(cmc["snapshot_date"], format="%Y%m%d")
    dates = sorted(cmc["snapshot_date"].unique())

    cg_supply = cg_supply_df.copy()
    cg_supply["date"] = pd.to_datetime(cg_supply["date"])

    universe_rows = []
    prev_members: set[str] = set()

    for i, date in enumerate(dates):
        week_data = cmc[cmc["snapshot_date"] == date].copy()

        week_data["symbol_upper"] = week_data["symbol"].str.upper().str.strip()
        week_data = week_data[~week_data["symbol_upper"].isin(excluded_symbols)]

        week_data = week_data.sort_values("market_cap_usd", ascending=False, na_position="last")
        week_data["raw_rank"] = range(1, len(week_data) + 1)

        if ranking_source == "cmc" and supply_growth_penalty:
            supply_lookup = {}
            for _, sr in cg_supply[cg_supply["date"] == date].iterrows():
                key = (sr.get("coingecko_id", ""), sr.get("symbol", "").upper())
                supply_lookup[key] = sr.get("supply_growth_4w", 0.0)

            def get_supply_growth(row):
                sym = row["symbol_upper"]
                cg_id = symbol_to_id.get(sym, "")
                val = supply_lookup.get((cg_id, sym), 0.0)
                if pd.isna(val):
                    val = 0.0
                return val

            week_data["supply_growth_4w"] = week_data.apply(get_supply_growth, axis=1)
            week_data["supply_growth_4w"] = week_data["supply_growth_4w"].fillna(0.0)
            penalty = (1.0 - week_data["supply_growth_4w"]).clip(lower=0.0)
            week_data["adj_mcap"] = week_data["market_cap_usd"] * penalty
        else:
            week_data["supply_growth_4w"] = 0.0
            week_data["adj_mcap"] = week_data["market_cap_usd"]

        week_data = week_data.sort_values("adj_mcap", ascending=False, na_position="last")
        week_data["adj_rank"] = range(1, len(week_data) + 1)

        upper_bound = rank_max + hysteresis_buffer
        current_members: set[str] = set()

        for _, row in week_data.iterrows():
            sym = row["symbol_upper"]
            adj_rank = row["adj_rank"]

            was_in = sym in prev_members

            if was_in and adj_rank <= upper_bound:
                current_members.add(sym)
            elif not was_in and adj_rank <= rank_max:
                current_members.add(sym)

        for _, row in week_data.iterrows():
            sym = row["symbol_upper"]
            if sym in current_members:
                was_in = sym in prev_members
                universe_rows.append(
                    {
                        "rebalance_date": date.strftime("%Y-%m-%d"),
                        "symbol": row["symbol"],
                        "symbol_upper": sym,
                        "coingecko_id": symbol_to_id.get(sym, ""),
                        "name": row.get("name"),
                        "raw_rank": row["raw_rank"],
                        "adj_rank": row["adj_rank"],
                        "market_cap_usd": row["market_cap_usd"],
                        "adj_mcap": row["adj_mcap"],
                        "supply_growth_4w": row.get("supply_growth_4w", 0.0),
                        "is_entry": not was_in,
                        "is_exit": was_in and sym not in current_members,
                    }
                )

        prev_members = current_members

    universe_df = pd.DataFrame(universe_rows)

    summary_rows = []
    for date in universe_df["rebalance_date"].unique():
        sub = universe_df[universe_df["rebalance_date"] == date]
        summary_rows.append(
            {
                "rebalance_date": date,
                "n_assets": len(sub),
                "n_entries": int(sub["is_entry"].sum()),
                "n_exits": int(sub["is_exit"].sum()),
                "turnover_pct": (int(sub["is_entry"].sum()) + int(sub["is_exit"].sum()))
                / max(len(sub), 1)
                * 100,
                "median_mcap": sub["market_cap_usd"].median(),
                "avg_supply_growth": sub["supply_growth_4w"].mean(),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    return universe_df, summary_df


def main() -> None:
    logger = get_logger("build_universe")
    settings = load_settings()

    universe_cfg = settings.get("universe", {})
    rank_min = int(universe_cfg.get("rank_min", 21))
    rank_max = int(universe_cfg.get("rank_max", 70))
    hysteresis_buffer = int(universe_cfg.get("hysteresis_buffer", 5))
    supply_growth_penalty = bool(universe_cfg.get("supply_growth_penalty", True))
    supply_growth_threshold = float(universe_cfg.get("supply_growth_threshold", 0.10))
    ranking_source = universe_cfg.get("ranking_source", "cmc")

    exclusion_path = PROJ_ROOT / "config" / "exclusion_list.yaml"
    excluded_symbols = load_exclusion_list(exclusion_path)
    logger.info("Loaded %d excluded symbols", len(excluded_symbols))

    cmc_path = clean_dir() / "cmc_rankings_weekly.parquet"
    if not cmc_path.exists():
        logger.error("Rankings data not found: %s. Run 01_fetch_artemis.py or 00_scrape_cmc_snapshots.py first.", cmc_path)
        sys.exit(1)
    cmc_df = pd.read_parquet(cmc_path)

    artemis_path = clean_dir() / "artemis_daily.parquet"
    cg_path = clean_dir() / "coingecko_daily.parquet"

    if ranking_source == "artemis" and artemis_path.exists():
        logger.info("Using Artemis daily data for supply growth")
        artemis_df = pd.read_parquet(artemis_path)
        cg_supply = compute_supply_growth(artemis_df)
    elif cg_path.exists():
        cg_df = pd.read_parquet(cg_path)
        cg_supply = compute_supply_growth(cg_df)
    else:
        logger.error("No price/supply data found. Run 01_fetch_coingecko.py or 01_fetch_artemis.py first.")
        sys.exit(1)

    overrides_path = PROJ_ROOT / "config" / "coingecko_id_overrides.yaml"
    overrides_cfg: dict[str, str] = {}
    if overrides_path.exists():
        overrides_yaml = yaml.safe_load(overrides_path.read_text(encoding="utf-8")) or {}
        overrides_cfg = {
            str(k).upper(): str(v) for k, v in (overrides_yaml.get("overrides") or {}).items()
        }

    # Build symbol_to_id from all available sources
    symbol_to_id: dict[str, str] = {}

    if cg_path.exists():
        cg_df_id = pd.read_parquet(cg_path)
        for _, row in cg_df_id[["symbol", "coingecko_id"]].drop_duplicates().iterrows():
            sym_upper = str(row["symbol"]).upper()
            symbol_to_id[sym_upper] = row["coingecko_id"]

    artemis_path = clean_dir() / "artemis_daily.parquet"
    if artemis_path.exists():
        artemis_df_id = pd.read_parquet(artemis_path)
        if "coingecko_id" in artemis_df_id.columns:
            for _, row in artemis_df_id[["symbol", "coingecko_id"]].dropna(subset=["coingecko_id"]).drop_duplicates().iterrows():
                sym_upper = str(row["symbol"]).upper()
                symbol_to_id[sym_upper] = row["coingecko_id"]

    # Also load from Artemis assets list for ID mapping
    artemis_assets_path = raw_dir() / "artemis" / "asset_symbols.json"
    if artemis_assets_path.exists():
        import json
        assets_list = json.loads(artemis_assets_path.read_text(encoding="utf-8"))
        for asset in assets_list:
            sym_upper = str(asset.get("symbol", "")).upper()
            cg_id = asset.get("coingecko_id")
            if sym_upper and cg_id:
                symbol_to_id[sym_upper] = cg_id

    symbol_to_id.update(overrides_cfg)

    logger.info("Computed supply growth for %d rows", len(cg_supply))

    universe_df, summary_df = build_universe(
        cmc_df=cmc_df,
        cg_supply_df=cg_supply,
        excluded_symbols=excluded_symbols,
        rank_min=rank_min,
        rank_max=rank_max,
        hysteresis_buffer=hysteresis_buffer,
        supply_growth_penalty=supply_growth_penalty,
        supply_growth_threshold=supply_growth_threshold,
        ranking_source=ranking_source,
        symbol_to_id=symbol_to_id,
        logger=logger,
    )

    out_universe = clean_dir() / "universe_weekly.parquet"
    write_parquet(universe_df, out_universe)
    logger.info("Wrote %d universe rows to %s", len(universe_df), out_universe)

    out_summary = clean_dir() / "universe_summary.parquet"
    write_parquet(summary_df, out_summary)
    logger.info("Wrote %d summary rows to %s", len(summary_df), out_summary)

    for col in ["n_assets", "median_mcap", "avg_supply_growth"]:
        if col in summary_df.columns:
            logger.info("  %s: mean=%.2f", col, summary_df[col].mean())


if __name__ == "__main__":
    main()