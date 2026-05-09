# 01_Data_Collection

Python pipeline to collect Coins/Tokens data for:
- all large-cap coins
- top-100 below large-cap (from `Coins.md`)

## What this pulls
- CoinGecko: market snapshot, coin metadata, supply/FDV, ATH/ATL fields, daily ticks (`price_usd`, `market_cap_usd`, `total_volume_usd`)
- Binance: pair mapping, OHLCV (daily), quote volume, trade count
- Artemis: asset symbol map and usage/activity metrics (best effort, endpoint-configurable), normalized daily long/wide tables

## Security first
Your current `.env` contains live-looking secrets. Rotate keys before running production pulls.

Use env vars (example):
- `COINGECKO_API_KEY`
- `COINGECKO_BASE_URL` (optional, default `https://pro-api.coingecko.com/api/v3`)
- `ARTEMIS_API_KEY`
- `ARTEMIS_BASE_URL` (optional, default `https://data-svc.artemisxyz.com`)
- `BINANCE_BASE_URL` (optional, default `https://api.binance.com`)

## Setup
1. Create and activate venv in this folder
2. Install requirements
3. Run pipeline

## Run
From repo root:

`/home/omegashenr01n/Desktop/Projects/artemis/01_Data_Collection/.venv/bin/python /home/omegashenr01n/Desktop/Projects/artemis/01_Data_Collection/src/main.py --coins-file /home/omegashenr01n/Desktop/Projects/artemis/Coins.md`

Outputs:
- Raw JSON: `01_Data_Collection/data/raw/<provider>/...`
- Clean CSV/Parquet: `01_Data_Collection/data/clean/...`
- Logs: `01_Data_Collection/data/logs/pipeline.log`

Notable clean outputs include:
- `coingecko_daily_ticks` (daily market data for mapped assets)
- `binance_ohlcv_daily` (daily candles for Binance-listed assets)
- `artemis_activity_long` and `artemis_activity_metrics`
- `coverage_summary`
