# Stage 06 — Artemis Econometrics Track

A cross-sectional, weekly crypto research pipeline that turns the four reviewed
papers into one econometric story:

- on-chain / activity characteristics
  (`Bitcoin price direction prediction using on-chain data and feature selection`)
- cross-asset structure
  (`A Time-Varying Network for Cryptocurrencies`)
- sparse characteristic-driven factor loadings
  (`Dynamic Latent-Factor Model with High-Dimensional Asset Characteristics`)
- omitted-risk controls
  (`Crypto Pricing with Hidden Factors`)

The artefact is a long–short ranking of the crypto cross-section each Monday,
plus diagnostics on what each layer (Artemis factors, PCA controls, network
features) contributes to the signal.

## Run Order

```bash
./.venv/bin/python 06_artemis_econometrics/01_build_panel.py
./.venv/bin/python 06_artemis_econometrics/02_characteristics.py
./.venv/bin/python 06_artemis_econometrics/03_network_features.py
./.venv/bin/python 06_artemis_econometrics/04_latent_controls.py
./.venv/bin/python 06_artemis_econometrics/05_models.py
./.venv/bin/python 06_artemis_econometrics/06_backtest.py
./.venv/bin/python 06_artemis_econometrics/07_report.py
```

## Outputs

- `artifacts/data/panel.parquet`: weekly symbol×week panel with returns.
- `artifacts/data/characteristics.parquet`: panel + Artemis / market features.
- `artifacts/data/network_features.parquet`: cluster labels and network features.
- `artifacts/data/latent_controls.parquet`: PCA loadings and residual returns.
- `artifacts/data/model_predictions.parquet`: per-model fitted/predicted ranks.
- `artifacts/tables/`: model diagnostics, IC, Sharpe, alpha tables.
- `figures/`: Plotly charts (HTML by default; set `ARTEMIS_SAVE_PNG=1` for PNG).
- `REPORT.md`: generated summary of the latest run.

## Method Notes

- Weekly cadence; Monday-start weeks aligned to `coerce_week`.
- Universe drops stablecoins / wrapped / bridged tokens via
  `coingecko_coin_details` flags, and keeps symbols with ≥12 weekly returns.
- All features are lagged one week before entering predictive models.
- PCA latent factors are fit on a rolling 52-week return panel; loadings join
  the asset record at the same week as a control.
- Cross-asset structure starts as a rolling correlation network (KMeans on
  rolling-correlation eigenvectors) and is meant to be swapped for a richer
  predictive-link network later.
- Models:
  1. Fama–MacBeth cross-sectional OLS (mean-of-weekly betas).
  2. Pooled panel OLS with cross-sectional standardization.
  3. Lasso / ElasticNetCV.
  4. Characteristic + latent controls.
  5. Characteristic + latent + network — the competition candidate.

## Scope Notes

This stage runs entirely on the clean data already in
`01_Data_Collection/data/clean/`. The risk-free series, perp basis, and
exchange-flow specific feeds are not in the repo today, so the panel relies on
Artemis activity, Binance OHLCV, CoinGecko snapshots, and DeFiLlama TVL /
stablecoin tables.
