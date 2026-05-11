from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from clients import (
    ArtemisClient,
    BinanceClient,
    CoinGeckoClient,
    DefiLlamaClient,
    DefiLlamaStablecoinsClient,
)
from io_utils import stable_hash, utc_now_iso, write_json, write_table
from universe import load_universe_from_markdown


_STABLE_TOKENS = ("stablecoin", "stable coin")
_WRAPPED_TOKENS = ("wrapped", "wrapped-tokens")
_BRIDGED_TOKENS = ("bridged", "bridge token")


def _coerce_scalar(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, default=str, ensure_ascii=False)
    return value


def _flag_from_categories(categories: Any, needles: tuple[str, ...]) -> bool:
    if not isinstance(categories, (list, tuple)):
        return False
    for cat in categories:
        if not isinstance(cat, str):
            continue
        low = cat.lower()
        if any(n in low for n in needles):
            return True
    return False


@dataclass
class PipelinePaths:
    root: Path
    raw_dir: Path
    clean_dir: Path


@dataclass
class PipelineSettings:
    cfg: dict[str, Any]

    @staticmethod
    def from_yaml(path: Path) -> "PipelineSettings":
        with path.open("r", encoding="utf-8") as f:
            return PipelineSettings(cfg=yaml.safe_load(f))


class DataCollectionPipeline:
    def __init__(
        self,
        *,
        root: Path,
        settings: PipelineSettings,
        logger: logging.Logger,
        coingecko_client: CoinGeckoClient,
        binance_client: BinanceClient,
        artemis_client: ArtemisClient | None,
        defillama_client: DefiLlamaClient | None = None,
        defillama_stable_client: DefiLlamaStablecoinsClient | None = None,
    ) -> None:
        self.root = root
        self.settings = settings
        self.logger = logger
        self.cg = coingecko_client
        self.binance = binance_client
        self.artemis = artemis_client
        self.defillama = defillama_client
        self.defillama_stable = defillama_stable_client

        self.paths = PipelinePaths(
            root=root,
            raw_dir=root / "data" / "raw",
            clean_dir=root / "data" / "clean",
        )

    def run(self, coins_md_path: Path) -> None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.logger.info("Starting run_id=%s", run_id)

        coverage_summary: dict[str, Any] = {
            "run_id": run_id,
            "pulled_at_utc": utc_now_iso(),
        }

        universe_df = load_universe_from_markdown(coins_md_path)
        self.logger.info("Parsed universe rows=%s", len(universe_df))

        mapped_df = self._map_coingecko_ids(universe_df)
        mapped_df["run_id"] = run_id
        mapped_count = int((mapped_df["mapping_status"] == "mapped").sum())
        unmapped_count = int((mapped_df["mapping_status"] == "unmapped").sum())
        coverage_summary.update(
            {
                "universe_assets": int(len(mapped_df)),
                "coingecko_mapped_assets": mapped_count,
                "coingecko_unmapped_assets": unmapped_count,
            }
        )
        write_table(
            mapped_df,
            self.paths.clean_dir / "asset_master",
            write_csv=True,
            write_parquet=self.settings.cfg["storage"]["write_parquet"],
        )

        try:
            market_df, detail_df = self._pull_coingecko(mapped_df, run_id)
            daily_ticks_df = self._pull_coingecko_daily_ticks(mapped_df, run_id)
            write_table(
                market_df,
                self.paths.clean_dir / "coingecko_market_snapshot",
                write_csv=self.settings.cfg["storage"]["write_csv"],
                write_parquet=self.settings.cfg["storage"]["write_parquet"],
            )
            write_table(
                detail_df,
                self.paths.clean_dir / "coingecko_coin_details",
                write_csv=self.settings.cfg["storage"]["write_csv"],
                write_parquet=self.settings.cfg["storage"]["write_parquet"],
            )
            write_table(
                daily_ticks_df,
                self.paths.clean_dir / "coingecko_daily_ticks",
                write_csv=self.settings.cfg["storage"]["write_csv"],
                write_parquet=self.settings.cfg["storage"]["write_parquet"],
            )
            market_unique = int(market_df["coingecko_id"].dropna().nunique()) if not market_df.empty else 0
            detail_unique = int(detail_df["coingecko_id"].dropna().nunique()) if not detail_df.empty else 0
            daily_unique = int(daily_ticks_df["coingecko_id"].dropna().nunique()) if not daily_ticks_df.empty else 0
            coverage_summary.update(
                {
                    "coingecko_market_unique_ids": market_unique,
                    "coingecko_detail_unique_ids": detail_unique,
                    "coingecko_daily_ticks_rows": int(len(daily_ticks_df)),
                    "coingecko_daily_ticks_unique_ids": daily_unique,
                    "coingecko_market_missing_vs_mapped": max(mapped_count - market_unique, 0),
                    "coingecko_detail_missing_vs_mapped": max(mapped_count - detail_unique, 0),
                    "coingecko_daily_missing_vs_mapped": max(mapped_count - daily_unique, 0),
                }
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("CoinGecko stage failed run_id=%s error=%s", run_id, exc)
            coverage_summary["coingecko_stage_error"] = str(exc)

        try:
            binance_map_df, klines_df = self._pull_binance(mapped_df, run_id)
            write_table(
                binance_map_df,
                self.paths.clean_dir / "binance_symbol_map",
                write_csv=self.settings.cfg["storage"]["write_csv"],
                write_parquet=self.settings.cfg["storage"]["write_parquet"],
            )
            write_table(
                klines_df,
                self.paths.clean_dir / "binance_ohlcv_daily",
                write_csv=self.settings.cfg["storage"]["write_csv"],
                write_parquet=self.settings.cfg["storage"]["write_parquet"],
            )
            binance_mapped = int((binance_map_df["mapping_status"] == "mapped").sum()) if not binance_map_df.empty else 0
            coverage_summary.update(
                {
                    "binance_mapped_assets": binance_mapped,
                    "binance_unmapped_assets": max(int(len(binance_map_df)) - binance_mapped, 0),
                    "binance_ohlcv_rows": int(len(klines_df)),
                }
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Binance stage failed run_id=%s error=%s", run_id, exc)
            coverage_summary["binance_stage_error"] = str(exc)

        defillama_slugs: list[str] = []
        if self.defillama is not None:
            try:
                llama_map_df, llama_tvl_df, llama_fees_df = self._pull_defillama(mapped_df, run_id)
                write_table(
                    llama_map_df,
                    self.paths.clean_dir / "defillama_protocol_map",
                    write_csv=self.settings.cfg["storage"]["write_csv"],
                    write_parquet=self.settings.cfg["storage"]["write_parquet"],
                )
                write_table(
                    llama_tvl_df,
                    self.paths.clean_dir / "defillama_protocol_tvl_daily",
                    write_csv=self.settings.cfg["storage"]["write_csv"],
                    write_parquet=self.settings.cfg["storage"]["write_parquet"],
                )
                write_table(
                    llama_fees_df,
                    self.paths.clean_dir / "defillama_fees_revenue_summary",
                    write_csv=self.settings.cfg["storage"]["write_csv"],
                    write_parquet=self.settings.cfg["storage"]["write_parquet"],
                )
                coverage_summary.update(
                    {
                        "defillama_mapped_protocols": int((llama_map_df["mapping_status"] == "mapped").sum()) if not llama_map_df.empty else 0,
                        "defillama_tvl_rows": int(len(llama_tvl_df)),
                        "defillama_fees_rows": int(len(llama_fees_df)),
                    }
                )
                if not llama_map_df.empty:
                    defillama_slugs = (
                        llama_map_df.loc[llama_map_df["mapping_status"] == "mapped", "defillama_slug"]
                        .dropna()
                        .unique()
                        .tolist()
                    )
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("DeFiLlama stage failed run_id=%s error=%s", run_id, exc)
                coverage_summary["defillama_stage_error"] = str(exc)

        defillama_cfg = self.settings.cfg.get("defillama", {}) or {}

        if self.defillama is not None and defillama_cfg.get("pull_raises", False):
            try:
                raises_df = self._pull_defillama_raises(defillama_slugs, mapped_df, run_id)
                write_table(
                    raises_df,
                    self.paths.clean_dir / "defillama_raises",
                    write_csv=self.settings.cfg["storage"]["write_csv"],
                    write_parquet=self.settings.cfg["storage"]["write_parquet"],
                )
                coverage_summary["defillama_raises_rows"] = int(len(raises_df))
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("DeFiLlama raises stage failed run_id=%s error=%s", run_id, exc)
                coverage_summary["defillama_raises_stage_error"] = str(exc)

        if self.defillama is not None and defillama_cfg.get("pull_unlocks", False):
            try:
                unlocks_df = self._pull_defillama_unlocks(defillama_slugs, run_id)
                write_table(
                    unlocks_df,
                    self.paths.clean_dir / "defillama_unlocks_schedule",
                    write_csv=self.settings.cfg["storage"]["write_csv"],
                    write_parquet=self.settings.cfg["storage"]["write_parquet"],
                )
                coverage_summary["defillama_unlocks_rows"] = int(len(unlocks_df))
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("DeFiLlama unlocks stage failed run_id=%s error=%s", run_id, exc)
                coverage_summary["defillama_unlocks_stage_error"] = str(exc)

        if self.defillama_stable is not None and defillama_cfg.get("pull_stablecoins", False):
            try:
                stable_supply_df, stable_inflows_df = self._pull_stablecoins(run_id)
                write_table(
                    stable_supply_df,
                    self.paths.clean_dir / "defillama_stablecoin_supply_daily",
                    write_csv=self.settings.cfg["storage"]["write_csv"],
                    write_parquet=self.settings.cfg["storage"]["write_parquet"],
                )
                write_table(
                    stable_inflows_df,
                    self.paths.clean_dir / "defillama_stablecoin_inflows_daily",
                    write_csv=self.settings.cfg["storage"]["write_csv"],
                    write_parquet=self.settings.cfg["storage"]["write_parquet"],
                )
                coverage_summary["defillama_stablecoin_supply_rows"] = int(len(stable_supply_df))
                coverage_summary["defillama_stablecoin_inflow_rows"] = int(len(stable_inflows_df))
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("DeFiLlama stablecoins stage failed run_id=%s error=%s", run_id, exc)
                coverage_summary["defillama_stablecoin_stage_error"] = str(exc)

        if self.artemis is not None and self.settings.cfg.get("artemis", {}).get("debug_dimensions", False):
            try:
                self._debug_artemis_dimensions(run_id)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Artemis dimension diagnostic failed error=%s", exc)

        if self.artemis is not None:
            try:
                artemis_assets_df, artemis_activity_df, artemis_activity_long_df = self._pull_artemis(mapped_df, run_id)
                write_table(
                    artemis_assets_df,
                    self.paths.clean_dir / "artemis_asset_symbols",
                    write_csv=self.settings.cfg["storage"]["write_csv"],
                    write_parquet=self.settings.cfg["storage"]["write_parquet"],
                )
                write_table(
                    artemis_activity_df,
                    self.paths.clean_dir / "artemis_activity_metrics",
                    write_csv=self.settings.cfg["storage"]["write_csv"],
                    write_parquet=self.settings.cfg["storage"]["write_parquet"],
                )
                write_table(
                    artemis_activity_long_df,
                    self.paths.clean_dir / "artemis_activity_long",
                    write_csv=self.settings.cfg["storage"]["write_csv"],
                    write_parquet=self.settings.cfg["storage"]["write_parquet"],
                )
                coverage_summary.update(
                    {
                        "artemis_assets_rows": int(len(artemis_assets_df)),
                        "artemis_activity_rows": int(len(artemis_activity_df)),
                        "artemis_activity_long_rows": int(len(artemis_activity_long_df)),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("Artemis stage failed run_id=%s error=%s", run_id, exc)
                coverage_summary["artemis_stage_error"] = str(exc)

        write_table(
            pd.DataFrame([coverage_summary]),
            self.paths.clean_dir / "coverage_summary",
            write_csv=self.settings.cfg["storage"]["write_csv"],
            write_parquet=self.settings.cfg["storage"]["write_parquet"],
        )

        self.logger.info("Run completed run_id=%s", run_id)

    def _map_coingecko_ids(self, universe_df: pd.DataFrame) -> pd.DataFrame:
        coins_list = self.cg.get_coins_list()
        coins_df = pd.DataFrame(coins_list)
        coins_df["symbol_norm"] = coins_df["symbol"].str.upper()
        coins_df["name_norm"] = coins_df["name"].str.lower().str.strip()

        out_rows: list[dict[str, Any]] = []
        for row in universe_df.to_dict("records"):
            symbol = row["symbol"]
            coin_name = str(row["coin_name"]).lower().strip()
            cands = coins_df.loc[coins_df["symbol_norm"] == symbol]

            chosen_id = None
            chosen_name = None
            if not cands.empty:
                exact = cands.loc[cands["name_norm"] == coin_name]
                if not exact.empty:
                    chosen = exact.iloc[0]
                    chosen_id = chosen["id"]
                    chosen_name = chosen["name"]
                elif len(cands) == 1:
                    chosen = cands.iloc[0]
                    chosen_id = chosen["id"]
                    chosen_name = chosen["name"]

            out_rows.append(
                {
                    **row,
                    "coingecko_id": chosen_id,
                    "coingecko_name_match": chosen_name,
                }
            )

        mapped_df = pd.DataFrame(out_rows)
        mapped_df["mapping_status"] = mapped_df["coingecko_id"].apply(
            lambda x: "mapped" if isinstance(x, str) and len(x) > 0 else "unmapped"
        )

        raw_path = self.paths.raw_dir / "coingecko" / "coins_list.json"
        write_json(raw_path, coins_list)

        self.logger.info(
            "Mapped coingecko ids: mapped=%s unmapped=%s",
            int((mapped_df["mapping_status"] == "mapped").sum()),
            int((mapped_df["mapping_status"] == "unmapped").sum()),
        )
        return mapped_df

    def _pull_coingecko(self, mapped_df: pd.DataFrame, run_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        ids = mapped_df.loc[mapped_df["mapping_status"] == "mapped", "coingecko_id"].dropna().unique().tolist()

        batch_size = min(int(self.settings.cfg["coingecko"]["ids_batch_size"]), 100)
        market_rows: list[dict[str, Any]] = []
        detail_rows: list[dict[str, Any]] = []

        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i : i + batch_size]
            try:
                market_payload = self.cg.get_markets_by_ids(batch_ids)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "CoinGecko markets batch failed batch_idx=%s size=%s error=%s",
                    i // batch_size + 1,
                    len(batch_ids),
                    exc,
                )
                continue
            write_json(
                self.paths.raw_dir / "coingecko" / f"markets_batch_{i // batch_size + 1}.json",
                market_payload,
            )
            market_rows.extend(market_payload)

        for coin_id in ids:
            detail_path = self.paths.raw_dir / "coingecko" / "details" / f"{coin_id}.json"
            try:
                if detail_path.exists():
                    with detail_path.open("r", encoding="utf-8") as f:
                        detail_payload = json.load(f)
                else:
                    detail_payload = self.cg.get_coin_detail(coin_id)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Coin detail failed coin_id=%s error=%s", coin_id, exc)
                continue

            if not detail_path.exists():
                write_json(detail_path, detail_payload)
            md = detail_payload.get("market_data", {})
            cats = detail_payload.get("categories")
            detail_rows.append(
                {
                    "coingecko_id": coin_id,
                    "symbol": detail_payload.get("symbol"),
                    "name": detail_payload.get("name"),
                    "categories": cats,
                    "is_stablecoin": _flag_from_categories(cats, _STABLE_TOKENS),
                    "is_wrapped": _flag_from_categories(cats, _WRAPPED_TOKENS),
                    "is_bridged": _flag_from_categories(cats, _BRIDGED_TOKENS),
                    "asset_platform_id": detail_payload.get("asset_platform_id"),
                    "ath_usd": (md.get("ath") or {}).get("usd"),
                    "ath_date_usd": (md.get("ath_date") or {}).get("usd"),
                    "atl_usd": (md.get("atl") or {}).get("usd"),
                    "atl_date_usd": (md.get("atl_date") or {}).get("usd"),
                    "circulating_supply": md.get("circulating_supply"),
                    "total_supply": md.get("total_supply"),
                    "max_supply": md.get("max_supply"),
                    "fdv_usd": (md.get("fully_diluted_valuation") or {}).get("usd"),
                    "run_id": run_id,
                    "pulled_at_utc": utc_now_iso(),
                }
            )

        market_df = pd.DataFrame(market_rows)
        if market_df.empty:
            market_df = pd.DataFrame(columns=["id", "symbol", "name"])
        market_df = market_df.rename(columns={"id": "coingecko_id"})
        market_df["run_id"] = run_id
        market_df["pulled_at_utc"] = utc_now_iso()

        detail_df = pd.DataFrame(detail_rows)
        return market_df, detail_df

    def _pull_coingecko_daily_ticks(self, mapped_df: pd.DataFrame, run_id: str) -> pd.DataFrame:
        ids_df = mapped_df.loc[mapped_df["mapping_status"] == "mapped", ["coingecko_id", "symbol", "coin_name"]].dropna()
        if ids_df.empty:
            return pd.DataFrame()

        lookback_days = int(self.settings.cfg["coingecko"].get("daily_lookback_days", 365))
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=lookback_days)

        # Split into 365-day chunks so we never exceed per-request limits on any
        # key tier. Each chunk is cached separately; on re-runs only the last
        # (incomplete) chunk is re-fetched — older chunks already cover full years.
        chunk_days = 365
        chunk_boundaries: list[tuple[int, int, str]] = []
        chunk_start = start_dt
        while chunk_start < end_dt:
            chunk_end = min(chunk_start + timedelta(days=chunk_days), end_dt)
            label = chunk_start.strftime("%Y%m%d")
            chunk_boundaries.append((int(chunk_start.timestamp()), int(chunk_end.timestamp()), label))
            chunk_start = chunk_end

        rows: list[dict[str, Any]] = []
        for rec in ids_df.to_dict("records"):
            coin_id = rec["coingecko_id"]
            by_ts: dict[int, dict[str, Any]] = {}

            for from_unix, to_unix, label in chunk_boundaries:
                # Last chunk: always re-fetch (partial; new days arrive daily).
                # Earlier chunks: use cache — those years won't change.
                is_last_chunk = (label == chunk_boundaries[-1][2])
                chunk_path = (
                    self.paths.raw_dir / "coingecko" / "daily_ticks"
                    / f"{coin_id}_{label}.json"
                )
                # Also handle the old-style single-file cache from the 1-year run
                legacy_path = self.paths.raw_dir / "coingecko" / "daily_ticks" / f"{coin_id}.json"

                payload: dict[str, Any] | None = None
                if not is_last_chunk and chunk_path.exists():
                    try:
                        with chunk_path.open("r", encoding="utf-8") as f:
                            payload = json.load(f)
                    except Exception:  # noqa: BLE001
                        payload = None

                if payload is None:
                    try:
                        payload = self.cg.get_market_chart_range(
                            coin_id=coin_id,
                            vs_currency="usd",
                            from_unix=from_unix,
                            to_unix=to_unix,
                            interval="daily",
                        )
                        if not is_last_chunk:
                            write_json(chunk_path, payload)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.warning(
                            "CoinGecko daily ticks failed coin_id=%s chunk=%s error=%s",
                            coin_id, label, exc,
                        )
                        # Fall back to legacy single-file cache for any chunk that fails
                        if legacy_path.exists() and label == chunk_boundaries[-1][2]:
                            try:
                                with legacy_path.open("r", encoding="utf-8") as f:
                                    payload = json.load(f)
                            except Exception:  # noqa: BLE001
                                pass
                        if payload is None:
                            continue

                for ts, val in (payload or {}).get("prices", []):
                    by_ts.setdefault(int(ts), {})["price_usd"] = val
                for ts, val in (payload or {}).get("market_caps", []):
                    by_ts.setdefault(int(ts), {})["market_cap_usd"] = val
                for ts, val in (payload or {}).get("total_volumes", []):
                    by_ts.setdefault(int(ts), {})["total_volume_usd"] = val

            for ts, vals in by_ts.items():
                dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                rows.append(
                    {
                        "date": dt.date().isoformat(),
                        "timestamp_utc": dt.isoformat(),
                        "coingecko_id": coin_id,
                        "symbol": rec.get("symbol"),
                        "coin_name": rec.get("coin_name"),
                        "price_usd": vals.get("price_usd"),
                        "market_cap_usd": vals.get("market_cap_usd"),
                        "total_volume_usd": vals.get("total_volume_usd"),
                        "run_id": run_id,
                    }
                )

        out_df = pd.DataFrame(rows)
        if out_df.empty:
            return out_df
        out_df = out_df.sort_values(["coingecko_id", "date", "timestamp_utc"]).drop_duplicates(
            subset=["coingecko_id", "date"],
            keep="last",
        )
        return out_df.reset_index(drop=True)

    def _pull_binance(self, mapped_df: pd.DataFrame, run_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        exchange_info = self.binance.get_exchange_info()
        write_json(self.paths.raw_dir / "binance" / "exchange_info.json", exchange_info)

        quote_priority = self.settings.cfg["binance"]["quote_priority"]
        symbols_info = exchange_info.get("symbols", [])

        map_rows: list[dict[str, Any]] = []
        for asset in mapped_df.to_dict("records"):
            sym = asset["symbol"]
            tradable = [
                s
                for s in symbols_info
                if s.get("status") == "TRADING"
                and s.get("baseAsset", "").upper() == sym
                and s.get("quoteAsset") in quote_priority
            ]

            chosen = None
            for quote in quote_priority:
                match = next((x for x in tradable if x.get("quoteAsset") == quote), None)
                if match:
                    chosen = match
                    break

            map_rows.append(
                {
                    "symbol": sym,
                    "coin_name": asset["coin_name"],
                    "coingecko_id": asset.get("coingecko_id"),
                    "binance_symbol": chosen.get("symbol") if chosen else None,
                    "base_asset": chosen.get("baseAsset") if chosen else None,
                    "quote_asset": chosen.get("quoteAsset") if chosen else None,
                    "mapping_status": "mapped" if chosen else "unmapped",
                    "run_id": run_id,
                }
            )

        map_df = pd.DataFrame(map_rows)

        interval = self.settings.cfg["binance"]["interval"]
        lookback_days = int(self.settings.cfg["binance"]["lookback_days"])
        limit = int(self.settings.cfg["binance"]["kline_limit"])

        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=lookback_days)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)

        kline_rows: list[dict[str, Any]] = []
        for row in map_df.loc[map_df["mapping_status"] == "mapped"].to_dict("records"):
            b_symbol = row["binance_symbol"]
            if not b_symbol:
                continue

            # Paginate: Binance returns at most `limit` bars per call.
            # For 5 years of daily bars we need ~2 pages (1825 / 1000).
            all_klines: list[Any] = []
            page_start = start_ms
            while page_start < end_ms:
                try:
                    page = self.binance.get_klines(
                        symbol=b_symbol,
                        interval=interval,
                        start_time_ms=page_start,
                        end_time_ms=end_ms,
                        limit=limit,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning("Binance klines failed symbol=%s error=%s", b_symbol, exc)
                    break
                if not page:
                    break
                all_klines.extend(page)
                # Advance start to the close_time of the last bar + 1 ms
                last_close_ms = int(page[-1][6])
                if last_close_ms <= page_start:
                    break  # guard against infinite loop
                page_start = last_close_ms + 1

            klines = all_klines
            write_json(self.paths.raw_dir / "binance" / "klines" / f"{b_symbol}.json", klines)
            for k in klines:
                if len(k) < 9:
                    continue
                kline_rows.append(
                    {
                        "binance_symbol": b_symbol,
                        "symbol": row["symbol"],
                        "coingecko_id": row["coingecko_id"],
                        "open_time": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).isoformat(),
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "base_volume": float(k[5]),
                        "close_time": datetime.fromtimestamp(k[6] / 1000, tz=timezone.utc).isoformat(),
                        "quote_volume": float(k[7]),
                        "trade_count": int(k[8]),
                        "run_id": run_id,
                    }
                )

        kline_df = pd.DataFrame(kline_rows)
        return map_df, kline_df

    def _pull_defillama(self, mapped_df: pd.DataFrame, run_id: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if self.defillama is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        protocols = self.defillama.get_protocols()
        write_json(self.paths.raw_dir / "defillama" / "protocols.json", protocols)

        proto_by_slug: dict[str, dict[str, Any]] = {}
        proto_by_gecko: dict[str, list[dict[str, Any]]] = {}
        for p in protocols:
            slug = p.get("slug")
            if isinstance(slug, str):
                proto_by_slug[slug] = p
            gid = p.get("gecko_id")
            if isinstance(gid, str) and gid:
                proto_by_gecko.setdefault(gid, []).append(p)

        overrides_path = self.root / "config" / "defillama_overrides.yaml"
        overrides_cfg: dict[str, Any] = {}
        if overrides_path.exists():
            with overrides_path.open("r", encoding="utf-8") as f:
                overrides_cfg = yaml.safe_load(f) or {}
        symbol_overrides: dict[str, Any] = {
            str(k).upper(): v for k, v in (overrides_cfg.get("overrides") or {}).items()
        }
        skip_symbols: set[str] = {str(s).upper() for s in (overrides_cfg.get("skip") or [])}

        allowed_fallback_cats = {
            c.lower()
            for c in (
                self.settings.cfg.get("defillama", {}).get(
                    "allowed_fallback_categories",
                    [
                        "Dexs",
                        "Lending",
                        "Yield",
                        "Derivatives",
                        "Liquid Staking",
                        "Liquid Restaking",
                        "Restaking",
                        "RWA",
                        "RWA Lending",
                        "CDP",
                        "Synthetics",
                        "Basis Trading",
                        "DEX Aggregator",
                        "Algo-Stables",
                        "Cross Chain Bridge",
                        "Launchpad",
                        "Options",
                        "Prediction Market",
                        "Insurance",
                    ],
                )
            )
        }

        def slugs_for(symbol: str, gecko_id: Any) -> tuple[list[str], str]:
            sym = (symbol or "").upper()
            if sym in skip_symbols:
                return [], "skipped"
            if sym in symbol_overrides:
                v = symbol_overrides[sym]
                if v is None:
                    return [], "override_skip"
                if isinstance(v, str):
                    return [v], "override"
                if isinstance(v, list):
                    return [str(x) for x in v if isinstance(x, str)], "override"
                return [], "override_invalid"
            cands = proto_by_gecko.get(gecko_id) if isinstance(gecko_id, str) else None
            if not cands:
                return [], "unmapped"
            filtered = [
                c for c in cands
                if str(c.get("category") or "").lower() in allowed_fallback_cats
            ]
            if not filtered:
                return [], "fallback_filtered_out"
            filtered.sort(key=lambda c: (c.get("tvl") or 0), reverse=True)
            chosen = filtered[0]
            slug = chosen.get("slug")
            return ([slug], "gecko_id_fallback") if slug else ([], "unmapped")

        map_rows: list[dict[str, Any]] = []
        for asset in mapped_df.to_dict("records"):
            sym = str(asset.get("symbol") or "").upper()
            gid = asset.get("coingecko_id")
            slugs_chosen, source = slugs_for(sym, gid)
            for slug in slugs_chosen or [None]:
                meta = proto_by_slug.get(slug) if slug else None
                map_rows.append(
                    {
                        "symbol": sym,
                        "coin_name": asset.get("coin_name"),
                        "coingecko_id": gid,
                        "defillama_slug": slug,
                        "defillama_name": meta.get("name") if meta else None,
                        "defillama_category": meta.get("category") if meta else None,
                        "current_tvl_usd": meta.get("tvl") if meta else None,
                        "mapping_status": "mapped" if slug else "unmapped",
                        "mapping_source": source,
                        "run_id": run_id,
                    }
                )
        map_df = pd.DataFrame(map_rows)

        tvl_rows: list[dict[str, Any]] = []
        fees_rows: list[dict[str, Any]] = []
        slugs = map_df.loc[map_df["mapping_status"] == "mapped", "defillama_slug"].dropna().unique().tolist()
        for slug in slugs:
            try:
                proto_payload = self.defillama.get_protocol(slug)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("DeFiLlama protocol failed slug=%s error=%s", slug, exc)
                continue
            write_json(self.paths.raw_dir / "defillama" / "protocols" / f"{slug}.json", proto_payload)

            tvl_series = proto_payload.get("tvl") if isinstance(proto_payload, dict) else None
            if isinstance(tvl_series, list):
                for point in tvl_series:
                    if not isinstance(point, dict):
                        continue
                    ts = point.get("date")
                    if ts is None:
                        continue
                    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                    tvl_rows.append(
                        {
                            "date": dt.date().isoformat(),
                            "defillama_slug": slug,
                            "tvl_usd": point.get("totalLiquidityUSD") or point.get("tvl"),
                            "run_id": run_id,
                        }
                    )

            for data_type in ("dailyFees", "dailyRevenue", "dailyHoldersRevenue"):
                try:
                    summary = self.defillama.get_fees_summary(slug, data_type=data_type)
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning(
                        "DeFiLlama fees summary failed slug=%s data_type=%s error=%s",
                        slug,
                        data_type,
                        exc,
                    )
                    continue
                write_json(
                    self.paths.raw_dir / "defillama" / "fees" / f"{slug}_{data_type}.json",
                    summary,
                )
                if not isinstance(summary, dict):
                    continue
                fees_rows.append(
                    {
                        "defillama_slug": slug,
                        "data_type": data_type,
                        "total24h": summary.get("total24h"),
                        "total7d": summary.get("total7d"),
                        "total30d": summary.get("total30d"),
                        "totalAllTime": summary.get("totalAllTime"),
                        "change_1d": summary.get("change_1d"),
                        "change_7d": summary.get("change_7d"),
                        "change_1m": summary.get("change_1m"),
                        "run_id": run_id,
                    }
                )

        tvl_df = pd.DataFrame(tvl_rows)
        if not tvl_df.empty:
            tvl_df = tvl_df.sort_values(["defillama_slug", "date"]).drop_duplicates(
                subset=["defillama_slug", "date"], keep="last"
            ).reset_index(drop=True)
        fees_df = pd.DataFrame(fees_rows)
        return map_df, tvl_df, fees_df

    def _pull_defillama_raises(
        self,
        defillama_slugs: list[str],
        mapped_df: pd.DataFrame,
        run_id: str,
    ) -> pd.DataFrame:
        """Pull /raises (full DeFiLlama dump) once and filter to our universe."""
        if self.defillama is None:
            return pd.DataFrame()

        try:
            payload = self.defillama.get_raises()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("DeFiLlama raises pull failed error=%s", exc)
            return pd.DataFrame()

        write_json(self.paths.raw_dir / "defillama" / "raises.json", payload)

        # Endpoint shape: {"raises": [...]} OR a bare list, depending on version.
        if isinstance(payload, dict) and isinstance(payload.get("raises"), list):
            raw_raises = payload["raises"]
        elif isinstance(payload, list):
            raw_raises = payload
        else:
            self.logger.warning("DeFiLlama raises payload unexpected shape type=%s", type(payload).__name__)
            return pd.DataFrame()

        slug_set = {s.lower() for s in defillama_slugs if isinstance(s, str)}
        # Build name lookup so we can match raises by protocol display name too —
        # /raises does not always carry a slug field.
        name_to_slug: dict[str, str] = {}
        if self.defillama is not None:
            try:
                proto_path = self.paths.raw_dir / "defillama" / "protocols.json"
                if proto_path.exists():
                    with proto_path.open("r", encoding="utf-8") as f:
                        protos = json.load(f)
                    for p in protos:
                        slug = p.get("slug")
                        name = p.get("name")
                        if isinstance(slug, str) and isinstance(name, str) and slug.lower() in slug_set:
                            name_to_slug[name.lower().strip()] = slug
            except Exception:  # noqa: BLE001
                pass

        rows: list[dict[str, Any]] = []
        for r in raw_raises:
            if not isinstance(r, dict):
                continue
            slug = r.get("slug") or r.get("defillamaId")
            name = r.get("name") or r.get("protocol")
            matched_slug: str | None = None
            if isinstance(slug, str) and slug.lower() in slug_set:
                matched_slug = slug
            elif isinstance(name, str) and name.lower().strip() in name_to_slug:
                matched_slug = name_to_slug[name.lower().strip()]
            if matched_slug is None:
                continue

            ts = r.get("date")
            date_iso: str | None = None
            if isinstance(ts, (int, float)):
                date_iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
            elif isinstance(ts, str):
                date_iso = ts[:10]

            leads = r.get("leadInvestors")
            if isinstance(leads, list):
                leads_str = ", ".join(str(x) for x in leads if x)
            else:
                leads_str = leads if isinstance(leads, str) else None

            rows.append(
                {
                    "defillama_slug": matched_slug,
                    "name": name,
                    "date": date_iso,
                    "amount_raised_usd": r.get("amount") or r.get("amountRaised"),
                    "round_type": r.get("round"),
                    "valuation_usd": r.get("valuation"),
                    "category": r.get("category"),
                    "lead_investors": leads_str,
                    "source_url": r.get("source"),
                    "run_id": run_id,
                }
            )

        df = pd.DataFrame(rows)
        if df.empty:
            return df
        return df.sort_values(["defillama_slug", "date"], na_position="last").reset_index(drop=True)

    def _pull_defillama_unlocks(
        self,
        defillama_slugs: list[str],
        run_id: str,
    ) -> pd.DataFrame:
        """Per-slug emission/unlock schedule. Many protocols return 404 — that's expected."""
        if self.defillama is None or not defillama_slugs:
            return pd.DataFrame()

        rows: list[dict[str, Any]] = []
        for slug in defillama_slugs:
            try:
                payload = self.defillama.get_unlocks(slug)
            except Exception as exc:  # noqa: BLE001
                # 404 is the dominant failure mode here — protocol simply doesn't have unlock data
                self.logger.info("DeFiLlama unlocks unavailable slug=%s error=%s", slug, str(exc)[:200])
                continue

            write_json(self.paths.raw_dir / "defillama" / "unlocks" / f"{slug}.json", payload)

            if not isinstance(payload, dict):
                continue

            # The /emission/{slug} payload typically carries:
            #   metadata: token, gecko_id, sources, max_supply
            #   documented or sources: an array of unlock events
            #   chartData: cumulative unlock series
            doc_source = (
                payload.get("documented")
                or payload.get("sources")
                or payload.get("events")
            )
            events: list[Any] = []
            if isinstance(doc_source, list):
                events = doc_source
            elif isinstance(doc_source, dict) and isinstance(doc_source.get("events"), list):
                events = doc_source.get("events")

            token_symbol = payload.get("token") or payload.get("tokenSymbol")
            max_supply = payload.get("maxSupply") or payload.get("max_supply")

            for ev in events:
                if not isinstance(ev, dict):
                    continue
                ts = ev.get("timestamp") or ev.get("date") or ev.get("time")
                date_iso: str | None = None
                if isinstance(ts, (int, float)):
                    date_iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
                elif isinstance(ts, str):
                    date_iso = ts[:10]

                amount = ev.get("amount") or ev.get("noOfTokens") or ev.get("tokens")
                category = ev.get("category") or ev.get("description") or ev.get("label")

                pct_supply: float | None = None
                if isinstance(amount, (int, float)) and isinstance(max_supply, (int, float)) and max_supply:
                    try:
                        pct_supply = float(amount) / float(max_supply)
                    except Exception:  # noqa: BLE001
                        pct_supply = None

                rows.append(
                    {
                        "defillama_slug": slug,
                        "token": token_symbol,
                        "date": date_iso,
                        "unlock_amount_tokens": amount,
                        "category": category,
                        "pct_of_max_supply": pct_supply,
                        "run_id": run_id,
                    }
                )

        df = pd.DataFrame(rows)
        if df.empty:
            return df
        return df.sort_values(["defillama_slug", "date"], na_position="last").reset_index(drop=True)

    def _pull_stablecoins(self, run_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Global + per-chain stablecoin supply series, plus derived daily inflows."""
        if self.defillama_stable is None:
            return pd.DataFrame(), pd.DataFrame()

        chains = list(self.settings.cfg.get("defillama", {}).get("stablecoin_chains") or [])

        supply_rows: list[dict[str, Any]] = []

        # Global aggregate first
        try:
            all_payload = self.defillama_stable.get_stablecoin_charts_all()
            write_json(self.paths.raw_dir / "defillama" / "stablecoins" / "all.json", all_payload)
            for point in all_payload if isinstance(all_payload, list) else []:
                if not isinstance(point, dict):
                    continue
                supply_rows.append(self._parse_stable_point(point, chain="ALL", run_id=run_id))
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("DeFiLlama stablecoin all-chains pull failed error=%s", exc)

        # Per-chain
        for chain in chains:
            try:
                chain_payload = self.defillama_stable.get_stablecoin_charts_chain(chain)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("DeFiLlama stablecoin chain pull failed chain=%s error=%s", chain, exc)
                continue
            write_json(
                self.paths.raw_dir / "defillama" / "stablecoins" / f"{chain}.json",
                chain_payload,
            )
            for point in chain_payload if isinstance(chain_payload, list) else []:
                if not isinstance(point, dict):
                    continue
                supply_rows.append(self._parse_stable_point(point, chain=chain, run_id=run_id))

        supply_df = pd.DataFrame([r for r in supply_rows if r])
        if supply_df.empty:
            return supply_df, pd.DataFrame()

        supply_df = (
            supply_df.dropna(subset=["date"])
            .sort_values(["chain", "date"])
            .drop_duplicates(subset=["chain", "date"], keep="last")
            .reset_index(drop=True)
        )

        # Derived: daily inflow = supply_t − supply_{t-1} per chain
        supply_df["supply_usd_prev"] = supply_df.groupby("chain")["supply_usd"].shift(1)
        supply_df["inflow_usd"] = supply_df["supply_usd"] - supply_df["supply_usd_prev"]

        inflows_df = supply_df[["date", "chain", "supply_usd", "inflow_usd", "run_id"]].copy()

        # Drop helper col before returning supply
        supply_out = supply_df.drop(columns=["supply_usd_prev", "inflow_usd"]).reset_index(drop=True)
        return supply_out, inflows_df.reset_index(drop=True)

    @staticmethod
    def _parse_stable_point(point: dict[str, Any], *, chain: str, run_id: str) -> dict[str, Any] | None:
        """Normalise one entry from /stablecoincharts/{*} → flat row."""
        ts = point.get("date")
        date_iso: str | None = None
        if isinstance(ts, (int, float)):
            date_iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
        elif isinstance(ts, str):
            try:
                # DeFiLlama returns date as a string Unix timestamp, e.g. "1511913600"
                date_iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
            except (ValueError, OverflowError, OSError):
                date_iso = ts[:10]

        peg_obj = point.get("totalCirculatingUSD") or point.get("totalCirculating")
        # totalCirculatingUSD may be a dict keyed by peg type ({"peggedUSD": <num>, ...}).
        # Sum all peg types so we get a single supply number per (chain, date).
        supply_usd: float | None = None
        if isinstance(peg_obj, dict):
            try:
                supply_usd = float(sum(v for v in peg_obj.values() if isinstance(v, (int, float))))
            except Exception:  # noqa: BLE001
                supply_usd = None
        elif isinstance(peg_obj, (int, float)):
            supply_usd = float(peg_obj)

        if date_iso is None or supply_usd is None:
            return None

        return {
            "date": date_iso,
            "chain": chain,
            "supply_usd": supply_usd,
            "run_id": run_id,
        }

    def _debug_artemis_dimensions(self, run_id: str) -> None:
        """One-shot diagnostic — log the response shape of 4 candidate by-chain
        endpoint variants. Only runs when artemis.debug_dimensions is true.
        Does not write any clean tables; raw payloads land in raw/artemis/_debug/."""
        if self.artemis is None:
            return

        probe_metric = "fees"
        probe_symbol = "ETH"
        end_date = datetime.now(timezone.utc).date().isoformat()
        start_date = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
        debug_dir = self.paths.raw_dir / "artemis" / "_debug"

        attempts: list[tuple[str, dict[str, Any], str]] = [
            (
                "dimensionType_CHAIN",
                {
                    "metric_names": [probe_metric],
                    "symbols": [probe_symbol],
                    "start_date": start_date,
                    "end_date": end_date,
                    "dimension_type": "CHAIN",
                },
                f"/data/{probe_metric}/?dimensionType=CHAIN",
            ),
            (
                "dimensionType_chain_lower",
                {
                    "metric_names": [probe_metric],
                    "symbols": [probe_symbol],
                    "start_date": start_date,
                    "end_date": end_date,
                    "dimension_type": "chain",
                },
                f"/data/{probe_metric}/?dimensionType=chain",
            ),
        ]

        # Simulate two extra param-name variants by calling the underlying _request directly
        for label, params_extra, _doc in [
            (
                "groupBy_CHAIN",
                {"metric_names": [probe_metric], "symbols": [probe_symbol],
                 "start_date": start_date, "end_date": end_date},
                "groupBy=CHAIN",
            ),
        ]:
            try:
                path = f"/data/{probe_metric}/"
                resp = self.artemis._request(  # noqa: SLF001  — diagnostic only
                    "GET",
                    path,
                    params=self.artemis._with_key(  # noqa: SLF001
                        {
                            "symbols": probe_symbol,
                            "startDate": start_date,
                            "endDate": end_date,
                            "groupBy": "CHAIN",
                        }
                    ),
                )
                write_json(debug_dir / f"{label}_{run_id}.json", resp)
                self.logger.info(
                    "artemis_dim_probe label=%s bytes=%d top_keys=%s",
                    label,
                    len(json.dumps(resp, default=str)),
                    list(resp.keys()) if isinstance(resp, dict) else "[list]",
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("artemis_dim_probe label=%s error=%s", label, exc)

        for label, kwargs, _doc in attempts:
            try:
                resp = self.artemis.get_data(**kwargs)
                write_json(debug_dir / f"{label}_{run_id}.json", resp)
                self.logger.info(
                    "artemis_dim_probe label=%s bytes=%d top_keys=%s",
                    label,
                    len(json.dumps(resp, default=str)),
                    list(resp.keys()) if isinstance(resp, dict) else "[list]",
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("artemis_dim_probe label=%s error=%s", label, exc)

    def _pull_artemis(self, mapped_df: pd.DataFrame, run_id: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if self.artemis is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        assets_payload = self.artemis.get_asset_symbols()
        write_json(self.paths.raw_dir / "artemis" / "asset_symbols.json", assets_payload)

        if isinstance(assets_payload, dict) and isinstance(assets_payload.get("assets"), list):
            artemis_assets_df = pd.DataFrame(assets_payload.get("assets", []))
        elif isinstance(assets_payload, list):
            artemis_assets_df = pd.DataFrame(assets_payload)
        else:
            artemis_assets_df = pd.json_normalize(assets_payload)

        start_date = (datetime.now(timezone.utc) - timedelta(days=int(self.settings.cfg["artemis"]["date_lookback_days"]))).date().isoformat()
        end_date = datetime.now(timezone.utc).date().isoformat()

        metric_keywords = [m.lower() for m in self.settings.cfg["artemis"]["metric_keywords"]]
        mapped_symbols = mapped_df["symbol"].dropna().astype(str).str.lower().unique().tolist()

        selected_metrics: set[str] = set()
        support_cache: dict[str, Any] = {}
        for symbol in mapped_symbols:
            try:
                supported = self.artemis.get_supported_metrics(symbol)
                support_cache[symbol] = supported
                text = str(supported).lower()
                for kw in metric_keywords:
                    if kw in text:
                        selected_metrics.add(kw)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Artemis supported-metrics failed symbol=%s error=%s", symbol, exc)

        write_json(self.paths.raw_dir / "artemis" / "supported_metrics_cache.json", support_cache)

        # Metric names are API-specific; we keep a conservative default set that often appears.
        candidate_metric_names = [
            "transactions",
            "real_transactions",
            "volume",
            "real_volume",
            "cumulative_buyers",
            "cumulative_sellers",
            "gamed_transactions_pct",
            "gamed_volume_pct",
            "avg_transaction_size",
            "dau",
            "active_addresses",
            "fees",
            "revenue",
            "active_revenue",
            "passive_revenue",
        ]

        used_metric_names = [m for m in candidate_metric_names if any(k in m.replace("_", " ") for k in selected_metrics)]
        if not used_metric_names:
            used_metric_names = candidate_metric_names[:4]

        self.logger.info(
            "Artemis metric selection: keywords_matched=%s requesting=%s",
            sorted(selected_metrics),
            used_metric_names,
        )

        batch_size = int(self.settings.cfg["artemis"]["symbols_batch_size"])
        rows_long: list[dict[str, Any]] = []

        symbols_upper = mapped_df["symbol"].dropna().astype(str).str.upper().unique().tolist()
        for i in range(0, len(symbols_upper), batch_size):
            symbol_batch = symbols_upper[i : i + batch_size]
            try:
                payload = self.artemis.get_data(
                    metric_names=used_metric_names,
                    symbols=symbol_batch,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Artemis data pull failed batch=%s error=%s", symbol_batch[:3], exc)
                continue

            file_name = f"activity_batch_{i // batch_size + 1}_{stable_hash(symbol_batch)[:10]}.json"
            write_json(self.paths.raw_dir / "artemis" / "activity" / file_name, payload)

            batch_rows = self._extract_artemis_rows(payload=payload, run_id=run_id)
            rows_long.extend(batch_rows)

        dimension_types = list(self.settings.cfg["artemis"].get("dimension_types") or [])
        dimension_rows: list[dict[str, Any]] = []
        for dim in dimension_types:
            for i in range(0, len(symbols_upper), batch_size):
                symbol_batch = symbols_upper[i : i + batch_size]
                try:
                    payload = self.artemis.get_data(
                        metric_names=used_metric_names,
                        symbols=symbol_batch,
                        start_date=start_date,
                        end_date=end_date,
                        dimension_type=dim,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning(
                        "Artemis dim pull failed dim=%s batch=%s error=%s",
                        dim,
                        symbol_batch[:3],
                        exc,
                    )
                    continue

                file_name = f"activity_{dim.lower()}_batch_{i // batch_size + 1}_{stable_hash(symbol_batch)[:10]}.json"
                write_json(self.paths.raw_dir / "artemis" / "activity" / file_name, payload)

                batch_rows = self._extract_artemis_rows(payload=payload, run_id=run_id, dimension=dim)
                dimension_rows.extend(batch_rows)

        if dimension_rows:
            dim_long_df = pd.DataFrame(dimension_rows).sort_values(
                ["dimension", "date", "symbol", "metric"], na_position="last"
            ).reset_index(drop=True)
            dim_long_df["value"] = pd.to_numeric(dim_long_df["value"], errors="coerce")
            write_table(
                dim_long_df,
                self.paths.clean_dir / "artemis_activity_dimensions_long",
                write_csv=self.settings.cfg["storage"]["write_csv"],
                write_parquet=self.settings.cfg["storage"]["write_parquet"],
            )

        activity_long_df = pd.DataFrame(rows_long)
        if activity_long_df.empty:
            return artemis_assets_df, pd.DataFrame(), pd.DataFrame()

        activity_long_df["value"] = pd.to_numeric(activity_long_df["value"], errors="coerce")
        activity_long_df = activity_long_df.sort_values(["date", "symbol", "metric"]).reset_index(drop=True)

        activity_df = (
            activity_long_df.pivot_table(
                index=["date", "symbol", "run_id"],
                columns="metric",
                values="value",
                aggfunc="first",
                dropna=False,
            )
            .reset_index()
            .rename_axis(columns=None)
        )
        return artemis_assets_df, activity_df, activity_long_df

    def _extract_artemis_rows(
        self,
        *,
        payload: Any,
        run_id: str,
        dimension: str | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        if isinstance(payload, list):
            for item in payload:
                rows.extend(self._extract_artemis_rows(payload=item, run_id=run_id, dimension=dimension))
            return rows

        if not isinstance(payload, dict):
            return rows

        root_data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        dates = root_data.get("dates") or root_data.get("timestamps") or payload.get("dates") or []
        symbols_obj = root_data.get("symbols") or payload.get("symbols") or {}

        if not isinstance(symbols_obj, dict):
            return rows

        for symbol, metrics_obj in symbols_obj.items():
            if not isinstance(metrics_obj, dict):
                continue

            for metric_name, series in metrics_obj.items():
                metric = str(metric_name)
                if isinstance(series, list):
                    for idx, val in enumerate(series):
                        date_val = dates[idx] if isinstance(dates, list) and idx < len(dates) else None
                        value_val: Any = val
                        dim_key: Any = None

                        if isinstance(val, dict):
                            if date_val is None:
                                date_val = val.get("date") or val.get("timestamp") or val.get("time")
                            dim_key = (
                                val.get("dimension")
                                or val.get("chain")
                                or val.get("category")
                                or val.get("protocol")
                                or val.get("version")
                            )
                            if "val" in val:
                                value_val = val.get("val")
                            elif "value" in val:
                                value_val = val.get("value")

                        row = {
                            "date": str(date_val)[:10] if date_val is not None else None,
                            "symbol": str(symbol).upper(),
                            "metric": metric,
                            "value": _coerce_scalar(value_val),
                            "run_id": run_id,
                        }
                        if dimension is not None:
                            row["dimension"] = dimension
                            row["dimension_key"] = _coerce_scalar(dim_key)
                        rows.append(row)
                elif isinstance(series, dict):
                    for dim_key, sub_series in series.items():
                        if isinstance(sub_series, list):
                            for idx, val in enumerate(sub_series):
                                date_val = dates[idx] if isinstance(dates, list) and idx < len(dates) else None
                                value_val = val
                                if isinstance(val, dict):
                                    if date_val is None:
                                        date_val = val.get("date") or val.get("timestamp") or val.get("time")
                                    if "val" in val:
                                        value_val = val.get("val")
                                    elif "value" in val:
                                        value_val = val.get("value")
                                row = {
                                    "date": str(date_val)[:10] if date_val is not None else None,
                                    "symbol": str(symbol).upper(),
                                    "metric": metric,
                                    "value": _coerce_scalar(value_val),
                                    "run_id": run_id,
                                }
                                if dimension is not None:
                                    row["dimension"] = dimension
                                    row["dimension_key"] = str(dim_key)
                                rows.append(row)
                        else:
                            row = {
                                "date": None,
                                "symbol": str(symbol).upper(),
                                "metric": metric,
                                "value": _coerce_scalar(sub_series),
                                "run_id": run_id,
                            }
                            if dimension is not None:
                                row["dimension"] = dimension
                                row["dimension_key"] = str(dim_key)
                            rows.append(row)
                else:
                    row = {
                        "date": None,
                        "symbol": str(symbol).upper(),
                        "metric": metric,
                        "value": _coerce_scalar(series),
                        "run_id": run_id,
                    }
                    if dimension is not None:
                        row["dimension"] = dimension
                        row["dimension_key"] = None
                    rows.append(row)

        return rows
