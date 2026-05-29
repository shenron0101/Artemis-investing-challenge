#!/usr/bin/env python3
"""Fetch daily price + market cap from CoinGecko for all unique symbols in CMC rankings.

Uses the existing CoinGeckoClient pattern from 01_Data_Collection, with yearly chunking
and caching. Derives implied_circulating_supply = market_cap / price for supply dilution.

Output: data/clean/coingecko_daily.parquet
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.data_io import (
    clean_dir,
    ensure_dir,
    get_logger,
    load_settings,
    raw_dir,
    write_json,
    write_parquet,
)

PROJ_ROOT = Path(__file__).resolve().parent.parent


class CoinGeckoClient:
    def __init__(self, base_url: str = "https://api.coingecko.com/api/v3", api_key: str | None = None, sleep_seconds: float = 1.0):
        import requests
        from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.is_demo_key = bool(api_key and api_key.startswith("CG-"))
        self.sleep_seconds = sleep_seconds
        self.session = requests.Session()

        resolved_url = base_url
        if self.is_demo_key and "pro-api.coingecko.com" in base_url:
            resolved_url = "https://api.coingecko.com/api/v3"

        self._resolved_base_url = resolved_url.rstrip("/")

        @retry(
            retry=retry_if_exception_type((Exception,)),
            wait=wait_exponential(multiplier=1, min=1, max=20),
            stop=stop_after_attempt(4),
            reraise=True,
        )
        def _request(method: str, path: str, params: dict | None = None, headers: dict | None = None) -> Any:
            import time
            url = f"{self._resolved_base_url}{path}"
            resp = self.session.request(method=method, url=url, params=params, headers=headers, timeout=30)
            if resp.status_code >= 400:
                raise requests.HTTPError(f"{url} failed ({resp.status_code}): {resp.text[:300]}")
            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)
            content_type = (resp.headers.get("content-type") or "").lower()
            if "application/json" in content_type or resp.text.startswith("{") or resp.text.startswith("["):
                return resp.json()
            return resp.text

        self._request = _request

    @property
    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            if self.is_demo_key:
                headers["x-cg-demo-api-key"] = self.api_key
            else:
                headers["x-cg-pro-api-key"] = self.api_key
        return headers

    def get_coins_list(self) -> list[dict[str, Any]]:
        return self._request("GET", "/coins/list", headers=self._headers)

    def get_markets_page(self, *, vs_currency: str = "usd", per_page: int = 250, page: int = 1) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/coins/markets",
            params={
                "vs_currency": vs_currency,
                "per_page": per_page,
                "page": page,
                "sparkline": "false",
                "price_change_percentage": "7d",
            },
            headers=self._headers,
        )

    def get_market_chart_range(
        self,
        coin_id: str,
        vs_currency: str = "usd",
        from_unix: int = 0,
        to_unix: int = 0,
        interval: str = "daily",
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/coins/{coin_id}/market_chart/range",
            params={
                "vs_currency": vs_currency,
                "from": from_unix,
                "to": to_unix,
                "interval": interval,
            },
            headers=self._headers,
        )


def map_symbols_to_coingecko(
    symbols: set[str],
    client: CoinGeckoClient,
    overrides: dict[str, str],
    logger: Any,
) -> dict[str, str]:
    logger.info("Fetching CoinGecko coins list...")
    coins_list = client.get_coins_list()
    coins_df = pd.DataFrame(coins_list)
    coins_df["symbol_norm"] = coins_df["symbol"].str.upper().str.strip()
    coins_df["name_norm"] = coins_df["name"].str.lower().str.strip()

    mapping: dict[str, str] = {}
    for sym in symbols:
        sym_upper = sym.upper()
        if sym_upper in overrides:
            mapping[sym] = overrides[sym_upper]
            continue

        cands = coins_df.loc[coins_df["symbol_norm"] == sym_upper]
        if len(cands) == 1:
            mapping[sym] = cands.iloc[0]["id"]
        elif len(cands) > 1:
            best = cands.iloc[0]["id"]
            mapping[sym] = best
            logger.debug("Ambiguous symbol %s, chose %s", sym, best)
        else:
            logger.warning("No CoinGecko match for symbol %s", sym)

    logger.info("Mapped %d/%d symbols to CoinGecko IDs", len(mapping), len(symbols))
    return mapping


def fetch_daily_ticks(
    symbol_to_id: dict[str, str],
    client: CoinGeckoClient,
    start_date: str,
    cache_dir: Path,
    chunk_days: int = 365,
    logger: Any | None = None,
) -> pd.DataFrame:
    if logger is None:
        logger = get_logger("coingecko_daily")

    end_dt = datetime.now(timezone.utc)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if start_dt < end_dt - timedelta(days=5 * 365):
        start_dt = end_dt - timedelta(days=5 * 365)

    chunk_boundaries: list[tuple[int, int, str]] = []
    chunk_start = start_dt
    while chunk_start < end_dt:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end_dt)
        label = chunk_start.strftime("%Y%m%d")
        chunk_boundaries.append((int(chunk_start.timestamp()), int(chunk_end.timestamp()), label))
        chunk_start = chunk_end

    all_rows: list[dict[str, Any]] = []
    for sym, coin_id in symbol_to_id.items():
        by_ts: dict[int, dict[str, Any]] = {}

        for from_unix, to_unix, label in chunk_boundaries:
            is_last_chunk = label == chunk_boundaries[-1][2]
            chunk_path = cache_dir / "daily_ticks" / f"{coin_id}_{label}.json"
            legacy_path = cache_dir / "daily_ticks" / f"{coin_id}.json"

            payload: dict[str, Any] | None = None
            if not is_last_chunk and chunk_path.exists():
                try:
                    payload = json.loads(chunk_path.read_text(encoding="utf-8"))
                except Exception:
                    payload = None

            if payload is None:
                try:
                    payload = client.get_market_chart_range(
                        coin_id=coin_id,
                        vs_currency="usd",
                        from_unix=from_unix,
                        to_unix=to_unix,
                        interval="daily",
                    )
                    if not is_last_chunk:
                        ensure_dir(chunk_path.parent)
                        chunk_path.write_text(
                            json.dumps(payload, default=str), encoding="utf-8"
                        )
                except Exception as exc:
                    logger.warning("CoinGecko failed for %s (%s) chunk %s: %s", sym, coin_id, label, exc)
                    if legacy_path.exists() and is_last_chunk:
                        try:
                            payload = json.loads(legacy_path.read_text(encoding="utf-8"))
                        except Exception:
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
            price = vals.get("price_usd")
            mcap = vals.get("market_cap_usd")
            implied_supply = None
            if price and mcap and price > 0:
                implied_supply = mcap / price
            all_rows.append(
                {
                    "date": dt.date().isoformat(),
                    "coingecko_id": coin_id,
                    "symbol": sym,
                    "price_usd": price,
                    "market_cap_usd": mcap,
                    "total_volume_usd": vals.get("total_volume_usd"),
                    "implied_circulating_supply": implied_supply,
                }
            )

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    df = df.sort_values(["coingecko_id", "date"]).drop_duplicates(
        subset=["coingecko_id", "date"], keep="last"
    ).reset_index(drop=True)
    return df


def fetch_weekly_rankings(
    client: CoinGeckoClient,
    top_n: int = 200,
    logger: Any | None = None,
) -> pd.DataFrame:
    """Pull current top-N coins by market cap from CoinGecko /coins/markets.

    This is used as the ranking source when CMC data is unavailable.
    For a true point-in-time ranking, we would need historical snapshots.
    This provides the current snapshot as a baseline.
    """
    if logger is None:
        logger = get_logger("coingecko_rankings")

    all_rows = []
    pages = (top_n + 249) // 250

    for page in range(1, pages + 1):
        per_page = min(250, top_n - (page - 1) * 250)
        try:
            data = client.get_markets_page(vs_currency="usd", per_page=per_page, page=page)
            if not data:
                logger.warning("No data for markets page %d", page)
                continue
            for coin in data:
                all_rows.append(
                    {
                        "coingecko_id": coin.get("id", ""),
                        "symbol": (coin.get("symbol") or "").upper(),
                        "name": coin.get("name", ""),
                        "market_cap_usd": coin.get("market_cap"),
                        "price_usd": coin.get("current_price"),
                        "volume_24h_usd": coin.get("total_volume"),
                        "circulating_supply": coin.get("circulating_supply"),
                        "change_7d_pct": (
                            coin.get("price_change_percentage_7d")
                            if coin.get("price_change_percentage_7d") is not None
                            else None
                        ),
                        "market_cap_rank": coin.get("market_cap_rank"),
                    }
                )
        except Exception as exc:
            logger.warning("Markets page %d failed: %s", page, exc)
            continue

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    df = df.sort_values("market_cap_rank").reset_index(drop=True)
    df["snapshot_date"] = datetime.now(timezone.utc).strftime("%Y%m%d")

    cache_path = raw_dir() / "coingecko" / f"markets_{df['snapshot_date'].iloc[0]}.json"
    ensure_dir(cache_path.parent)
    cache_path.write_text(json.dumps(all_rows, default=str), encoding="utf-8")

    return df


def main() -> None:
    logger = get_logger("coingecko_fetch")
    settings = load_settings()
    cg_cfg = settings.get("coingecko", {})
    universe_cfg = settings.get("universe", {})
    ranking_source = universe_cfg.get("ranking_source", "cmc")

    client = CoinGeckoClient(
        base_url=cg_cfg.get("base_url", "https://api.coingecko.com/api/v3"),
        api_key=cg_cfg.get("api_key"),
        sleep_seconds=float(cg_cfg.get("sleep_seconds", 1.0)),
    )

    rankings_path = clean_dir() / "cmc_rankings_weekly.parquet"
    if not rankings_path.exists():
        logger.error("Rankings not found at %s. Run 01_fetch_artemis.py or 00_scrape_cmc_snapshots.py first.", rankings_path)
        sys.exit(1)

    rankings_df = pd.read_parquet(rankings_path)
    unique_symbols = set(rankings_df["symbol"].dropna().unique())

    if ranking_source == "artemis":
        artemis_path = clean_dir() / "artemis_daily.parquet"
        if artemis_path.exists():
            artemis_df = pd.read_parquet(artemis_path)
            artemis_syms = set(artemis_df["symbol"].dropna().unique())
            logger.info("Loaded Artemis daily data with %d symbols", len(artemis_syms))
            unique_symbols.update(artemis_syms)

    logger.info("Found %d unique symbols for CoinGecko fetch", len(unique_symbols))

    overrides_path = PROJ_ROOT / "config" / "coingecko_id_overrides.yaml"
    overrides_cfg: dict[str, str] = {}
    if overrides_path.exists():
        overrides_yaml = yaml.safe_load(overrides_path.read_text(encoding="utf-8")) or {}
        overrides_cfg = {str(k).upper(): str(v) for k, v in (overrides_yaml.get("overrides") or {}).items()}

    symbol_to_id = map_symbols_to_coingecko(unique_symbols, client, overrides_cfg, logger)

    cache_dir = raw_dir() / "coingecko"
    ensure_dir(cache_dir / "daily_ticks")

    start_date = "2020-12-01"
    chunk_days = int(cg_cfg.get("chunk_days", 365))

    df = fetch_daily_ticks(
        symbol_to_id=symbol_to_id,
        client=client,
        start_date=start_date,
        cache_dir=cache_dir,
        chunk_days=chunk_days,
        logger=logger,
    )

    if df.empty:
        logger.error("No CoinGecko data fetched. Exiting.")
        sys.exit(1)

    out_path = clean_dir() / "coingecko_daily.parquet"
    write_parquet(df, out_path)
    logger.info("Wrote %d rows to %s", len(df), out_path)

    n_ids = df["coingecko_id"].nunique()
    date_range = f"{df['date'].min()} → {df['date'].max()}"
    logger.info("IDs: %d, Date range: %s", n_ids, date_range)


if __name__ == "__main__":
    main()