# 09 — Dynamic Mid-Cap Crypto Universe: PCA + CCA

## Overview

Build a **weekly point-in-time ranked mid-cap crypto universe** (ranks #21–#70 by market cap), extract latent factors via **PCA on returns**, provide economic intuition using asset metadata, then conduct **CCA** with BTC, SPY, and VIX to identify cross-asset comovements. Timeframe: **Jan 2021 → present** (post-COVID institutional regime).

## Pipeline

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 0 | Scaffold | — | `config/*.yaml`, `requirements.txt` |
| 1a | `src/00_scrape_cmc_snapshots.py` | CMC historical pages | `data/clean/cmc_rankings_weekly.parquet` |
| 1b | `src/01_fetch_coingecko.py` | CMC symbols → CoinGecko API | `data/clean/coingecko_daily.parquet` |
| 1b | `src/02_fetch_macro.py` | yfinance (SPY, VIX) | `data/clean/macro_daily.parquet` |
| 2 | `src/03_build_universe.py` | CMC + CoinGecko + exclusions | `data/clean/universe_weekly.parquet` |
| 3 | `src/04_build_returns.py` | Universe + CoinGecko daily | `data/features/returns_weekly_*.parquet` |
| 4 | `src/05_pca_factors.py` | Z-scored returns | `data/features/pca_*.parquet` |
| 5 | `src/06_factor_interpretation.py` | PCA loadings + metadata | `data/features/pc_*.parquet` |
| 6 | `src/07_cca_analysis.py` | PCA scores + macro | `data/features/cca_*.parquet` |
| 7 | `src/08_report.py` | All outputs | `artifacts/figures/*.png` |

## Key Design Decisions

- **Universe**: Top 200 via CoinGecko + CMC historical snapshots; filter to #21–#70 with ±5 hysteresis buffer
- **Stablecoin/wrapped exclusion**: Static list in `config/exclusion_list.yaml`
- **Supply dilution**: Adjusted market cap penalises tokens with >10% 4-week supply growth
- **PCA**: 12-week rolling window, EWMA weighting (halflife=4w), Marchenko–Pastur denoising, parallel analysis for component selection, sign alignment across weeks
- **CCA**: Crypto PC scores vs. [BTC return, SPY return, VIX change]
- **Calendar**: NYSE calendar, Friday 4:00 PM ET close
- **Portfolio**: 80/20 long/short split

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Configuration

All parameters in `config/settings.yaml`. See `IMPLEMENTATION_PLAN.md` for full details.