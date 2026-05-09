from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class APIClientError(Exception):
    pass


class BaseClient:
    def __init__(self, base_url: str, timeout: int = 30, sleep_seconds: float = 0.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds
        self.session = requests.Session()

    @retry(
        retry=retry_if_exception_type((requests.RequestException, APIClientError)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        resp = self.session.request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            message = f"{url} failed ({resp.status_code}): {resp.text[:300]}"
            if resp.status_code in (429, 500, 502, 503, 504):
                raise APIClientError(message)
            raise requests.HTTPError(message)

        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)

        content_type = (resp.headers.get("content-type") or "").lower()
        if "application/json" in content_type or resp.text.startswith("{") or resp.text.startswith("["):
            return resp.json()
        return resp.text


class CoinGeckoClient(BaseClient):
    def __init__(self, api_key: str | None, base_url: str, sleep_seconds: float = 1.0):
        self.api_key = api_key
        self.is_demo_key = bool(api_key and api_key.startswith("CG-"))
        resolved_base_url = base_url
        if self.is_demo_key and "pro-api.coingecko.com" in base_url:
            resolved_base_url = "https://api.coingecko.com/api/v3"

        super().__init__(base_url=resolved_base_url, sleep_seconds=sleep_seconds)
        self.api_key = api_key

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

    def get_markets_page(self, *, vs_currency: str, per_page: int, page: int) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/coins/markets",
            params={
                "vs_currency": vs_currency,
                "per_page": per_page,
                "page": page,
                "sparkline": "false",
                "price_change_percentage": "24h,7d,30d",
            },
            headers=self._headers,
        )

    def get_markets_by_ids(self, ids: list[str], vs_currency: str = "usd") -> list[dict[str, Any]]:
        if not ids:
            return []
        return self._request(
            "GET",
            "/coins/markets",
            params={
                "vs_currency": vs_currency,
                "ids": ",".join(ids),
                "sparkline": "false",
                "price_change_percentage": "24h,7d,30d",
            },
            headers=self._headers,
        )

    def get_coin_detail(self, coin_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/coins/{coin_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
            headers=self._headers,
        )

    def get_market_chart_range(
        self,
        *,
        coin_id: str,
        vs_currency: str,
        from_unix: int,
        to_unix: int,
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


class BinanceClient(BaseClient):
    def __init__(self, base_url: str, sleep_seconds: float = 0.2):
        super().__init__(base_url=base_url, sleep_seconds=sleep_seconds)

    def get_exchange_info(self) -> dict[str, Any]:
        return self._request("GET", "/api/v3/exchangeInfo")

    def get_klines(
        self,
        *,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
        limit: int,
    ) -> list[list[Any]]:
        return self._request(
            "GET",
            "/api/v3/klines",
            params={
                "symbol": symbol,
                "interval": interval,
                "startTime": start_time_ms,
                "endTime": end_time_ms,
                "limit": limit,
            },
        )

    @staticmethod
    def utc_ms(dt: datetime) -> int:
        return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

    @staticmethod
    def date_window(days: int) -> tuple[int, int]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


class ArtemisClient(BaseClient):
    def __init__(self, api_key: str, base_url: str, sleep_seconds: float = 0.75):
        super().__init__(base_url=base_url, sleep_seconds=sleep_seconds)
        self.api_key = api_key

    def _with_key(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        p = dict(params or {})
        p["APIKey"] = self.api_key
        return p

    def get_asset_symbols(self) -> Any:
        return self._request("GET", "/asset/symbols/", params=self._with_key())

    def get_supported_metrics(self, symbol: str) -> Any:
        return self._request(
            "GET",
            "/supported-metrics/",
            params=self._with_key({"symbol": symbol}),
        )

    def get_data(
        self,
        *,
        metric_names: list[str],
        symbols: list[str],
        start_date: str,
        end_date: str,
        dimension_type: str | None = None,
    ) -> Any:
        if not metric_names or not symbols:
            return []

        path = f"/data/{','.join(metric_names)}/"
        params: dict[str, Any] = {
            "symbols": ",".join(symbols),
            "startDate": start_date,
            "endDate": end_date,
        }
        if dimension_type:
            params["dimensionType"] = dimension_type

        return self._request("GET", path, params=self._with_key(params))


class DefiLlamaClient(BaseClient):
    """Public DeFiLlama API. No key required."""

    def __init__(self, base_url: str = "https://api.llama.fi", sleep_seconds: float = 0.4):
        super().__init__(base_url=base_url, sleep_seconds=sleep_seconds)

    def get_protocols(self) -> list[dict[str, Any]]:
        return self._request("GET", "/protocols")

    def get_protocol(self, slug: str) -> dict[str, Any]:
        return self._request("GET", f"/protocol/{slug}")

    def get_fees_summary(self, slug: str, *, data_type: str = "dailyFees") -> dict[str, Any]:
        # data_type: dailyFees | dailyRevenue | dailyHoldersRevenue
        return self._request(
            "GET",
            f"/summary/fees/{slug}",
            params={"dataType": data_type},
        )
