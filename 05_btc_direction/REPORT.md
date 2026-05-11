# Stage 05 — BTC Direction Paper Reproduction

This stage implements a first-pass reproduction scaffold for `Bitcoin price direction prediction using on-chain data and feature selection`.

## Data Window
- Rows: 1,825
- Dates: 2021-05-12 00:00:00 to 2026-05-10 00:00:00
- Sources: Binance BTCUSDT OHLCV, CoinGecko BTC daily ticks, Artemis BTC activity, DeFiLlama stablecoin supply/inflows, and tracked-protocol TVL.

## Feature Selection
- all: 86 features/components
- l1: 36 features/components
- boruta_shadow: 25 features/components
- pca: 39 features/components

Feature selection is fit only on the first 70% of chronological observations. PCA keeps enough components to explain 95% of training variance.

## Classification Result
- Best test classifier: `l1__random_forest`
- Balanced accuracy: 53.94%
- Accuracy: 54.01%
- F1: 0.488
- ROC AUC: 0.549

Validation-selected champion: `l1__logistic`.

## Trading Result
- Best test strategy: `all__gradient_boosting` / `long_short`
- Total return: 71.99%
- Annualized return: 106.47%
- Sharpe: 1.822
- Max drawdown: -22.20%

## Outputs
- Features: `05_btc_direction/artifacts/tables/03_feature_selection_summary.parquet`
- Model metrics: `05_btc_direction/artifacts/tables/04_model_metrics.parquet`
- Predictions: `05_btc_direction/artifacts/tables/04_predictions.parquet`
- Trading summary: `05_btc_direction/artifacts/tables/05_trading_summary.parquet`
- Equity chart: `05_btc_direction/figures/05_trading_simulation/01_test_equity_curves.html`

## Reproduction Notes
- This is a repo-native hybrid reproduction, not a strict Glassnode reproduction. Realized-value and unrealized-value feature families from the paper are not available in the current clean tables.
- The first implementation covers classical models plus L1, Boruta-style shadow selection, and PCA. CNN-LSTM and TCN are intentionally left for a later deep-learning extension.
- Signals are chronological and evaluated on a held-out test period; no shuffled cross-validation is used.
