# Mid-Cap Crypto PCA+CCA Factor Analysis — Results Summary

## Project Overview

Dynamic mid-cap crypto universe (ranks #21–#70 by market cap) with PCA+CCA factor analysis, using point-in-time data from the Artemis API. The pipeline covers Jan 2021 – May 2026 (282 weekly rebalances).

## Pipeline Steps Completed

| Step | Script | Output | Status |
|------|--------|--------|--------|
| 1a | `01_fetch_artemis.py` | `data/clean/artemis_daily.parquet` (1.28M rows, 849 symbols) | Done |
| 1b | `02_fetch_macro.py` | `data/clean/macro_daily.parquet` (4,691 rows: BTC, SPY, ^VIX) | Done |
| 2 | `03_build_universe.py` | `data/clean/universe_weekly.parquet` (20,571 rows) | Done |
| 3 | `04_build_returns.py` | `data/features/returns_weekly_{raw,zscore}.parquet` (280 weeks) | Done |
| 4 | `05_pca_factors.py` | PCA scores, loadings, diagnostics | Done |
| 5 | `06_factor_interpretation.py` | Characteristic correlations, clusters | Done |
| 6 | `07_cca_analysis.py` | CCA results, variates, rolling CCA | Done |
| 7 | `08_report.py` | 10 figures + 2 manifests | Done |

## Data Sources

- **Artemis Pro API** — Daily PRICE, MARKET_CAP_USD, CIRCULATING_SUPPLY, 24H_VOLUME for ~849 crypto assets (Jan 2021 – May 2026). Used as primary ranking and price source.
- **yfinance** — SPY and ^VIX daily close prices for macro benchmarks.
- **Exclusion list** — 51 symbols excluded (stablecoins, wrapped tokens, aggregates like TOTAL/ALTCOIN, equity trackers like NASDAQ100).

## Universe Construction

| Metric | Value |
|--------|-------|
| Weekly rebalances | 282 |
| Unique symbols (lifetime) | 177 |
| Mean assets per week | 73 |
| Range | 70–75 |
| Median market cap | $2.6B |
| Mean weekly turnover | 1.7% |
| Avg supply growth | ~0% |

## PCA Results

**Configuration:** 12-week rolling window, EWMA halflife=4w, RMT denoising, sign alignment, parallel analysis (100 permutations, α=0.05).

**Key finding:** Parallel analysis retains only **1 principal component** per week, explaining **14–28% of variance** (mean ~21%). This is consistent with crypto markets being dominated by a single "market" factor.

| PC | Avg Spearman ρ with characteristics |
|----|--------------------------------------|
| | log_mcap | momentum_4w | vol_4w | turnover_ratio |
| PC1 | –0.037 | –0.030 | +0.068 | +0.078 |

PC1 is weakly correlated with turnover and volatility — a shallow "market/liquidity" factor. Size and momentum correlations are near-zero.

## CCA Results

**Canonical Correlation Analysis** between PC1 scores and macro variables (BTC return, SPY return, VIX change).

| Metric | Value |
|--------|-------|
| Canonical components | 1 |
| Full-sample CV1 correlation | 0.087 |
| Permutation p-value | 0.193 |
| Rolling CV1 (52w) mean | 0.116 |
| Rolling CV1 range | 0.0004 – 0.458 |

The full-sample canonical correlation of 0.087 is **not statistically significant** (p = 0.19). Rolling CCA shows the crypto–macro link is time-varying (range 0.00–0.46), spiking during macro regime shifts but averaging near zero.

**Interpretation:** Mid-cap crypto factors are largely independent of traditional macro assets (SPY, VIX) and even BTC on a weekly basis. The single dominant factor within crypto is an internal "market" factor rather than an externally-driven one.

## Output File Locations

### Data
| File | Path | Description |
|------|------|-------------|
| Artemis daily | `data/clean/artemis_daily.parquet` | Raw price/mcap/volume/supply for 849 symbols |
| CMC/Artemis rankings | `data/clean/cmc_rankings_weekly.parquet` | Weekly rankings (69,457 rows) |
| Universe | `data/clean/universe_weekly.parquet` | Weekly universe membership (20,571 rows) |
| Universe summary | `data/clean/universe_summary.parquet` | Per-week stats (282 rows) |
| Macro | `data/clean/macro_daily.parquet` | BTC, SPY, ^VIX daily (4,691 rows) |
| Returns (raw) | `data/features/returns_weekly_raw.parquet` | Weekly log returns (280 weeks × 177 assets) |
| Returns (z-score) | `data/features/returns_weekly_zscore.parquet` | Cross-sectionally z-scored returns |
| PCA scores | `data/features/pca_scores.parquet` | PC1 scores (268 weeks) |
| PCA loadings | `data/features/pca_loadings.parquet` | Asset loadings (21,775 rows) |
| PCA diagnostics | `data/features/pca_diagnostics.parquet` | Eigenvalues, explained variance |
| Char. correlations | `data/features/pc_char_correlations.parquet` | PC–characteristic Spearman ρ (1,340 rows) |
| Clusters | `data/features/pc_clusters.parquet` | K-means clusters (21,775 rows) |
| CCA results | `data/features/cca_results.parquet` | Canonical correlations & weights |
| CCA variates | `data/features/cca_variates.parquet` | Canonical variate time series |
| CCA rolling | `data/features/cca_rolling.parquet` | 52-week rolling CCA (211 windows) |
| Asset metadata | `data/features/asset_metadata_weekly.parquet` | Per-asset weekly metadata (20,430 rows) |

### Figures
All figures in `artifacts/figures/`:

| # | File | Description |
|---|------|-------------|
| 1 | `01_universe_size.png` | Universe composition over time |
| 2 | `02_universe_turnover.png` | Weekly entry/exit rates |
| 3 | `03_supply_growth_distribution.png` | Supply growth histogram |
| 4 | `04_scree_mp_threshold.png` | Eigenvalue scree vs Marchenko-Pastur threshold |
| 5 | `06_pc_scores_timeseries.png` | PC1 score time series |
| 6 | `07_char_correlations.png` | PC–characteristic correlation heatmap |
| 7 | `08_cluster_evolution.png` | Cluster composition over time |
| 8 | `09_cca_biplot.png` | CCA variate scatter |
| 9 | `10_cca_rolling_correlations.png` | Rolling canonical correlation |
| 10 | `11_canonical_variate_timeseries.png` | Canonical variate time series |

### Manifests
- `artifacts/manifests/pca_manifest.json` — PCA configuration & output files
- `artifacts/manifests/cca_manifest.json` — CCA configuration & results

## Deviations from Original Plan

Documented in `DEVIATIONS.md`. Key changes:

1. **Artemis API replaces CMC scraping** — CMC virtual scrolling limited to ~38 rows; Artemis provides 849 assets survivorship-bias-free.
2. **CoinGecko not used** — Artemis covers all needed metrics; CoinGecko rate limits make it impractical.
3. **NASDAQ100 excluded** — Equity tracker found in top ranks, added to exclusion list.
4. **Column name normalization** — Artemis uses lowercase symbols; converted to uppercase for consistency with universe.

## How to Re-Run

```bash
cd 09_midcap_pca_cca
# Activate venv
source .venv/bin/activate
# Or add PYTHONPATH for artemis:
export PYTHONPATH="/path/to/parent/venv/lib/python3.14/site-packages:$PYTHONPATH"

# Run full pipeline
python src/01_fetch_artemis.py   # ~10 min, 849 symbols
python src/02_fetch_macro.py     # ~30 sec (yfinance + Artemis BTC)
python src/03_build_universe.py
python src/04_build_returns.py
python src/05_pca_factors.py    # ~30 sec
python src/06_factor_interpretation.py
python src/07_cca_analysis.py
python src/08_report.py
```