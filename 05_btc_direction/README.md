# Stage 05 — BTC Direction Paper Reproduction

This stage is a repo-native reproduction scaffold for:

`Bitcoin price direction prediction using on-chain data and feature selection`

The target is next-day BTC close direction. The implementation follows the paper workflow: assemble daily data, engineer on-chain/market features, run L1/Boruta/PCA feature selection, train chronological classifiers, and evaluate the resulting signals in a trading simulation.

## Run Order

```bash
./.venv/bin/python 05_btc_direction/01_build_dataset.py
./.venv/bin/python 05_btc_direction/02_feature_engineering.py
./.venv/bin/python 05_btc_direction/03_feature_selection.py
./.venv/bin/python 05_btc_direction/04_train_eval.py
./.venv/bin/python 05_btc_direction/05_trading_simulation.py
./.venv/bin/python 05_btc_direction/06_report.py
```

## Outputs

- `artifacts/data/btc_direction_base.parquet`: merged daily BTC base table.
- `artifacts/data/btc_direction_features.parquet`: feature matrix and next-day targets.
- `artifacts/manifests/`: run metadata and selected feature manifests.
- `artifacts/tables/`: rankings, model metrics, predictions, and strategy summaries.
- `figures/`: Plotly HTML charts, with PNG exports when local image export is available.
- `REPORT.md`: generated summary of the latest run.

## Scope Notes

This first pass uses the clean data already present in this repo: Binance, CoinGecko, Artemis, and DeFiLlama. It does not yet add a Glassnode adapter, so the paper's realized-value and unrealized-value feature families are documented as missing rather than approximated. The model scope is classical ML for reproducibility in the current environment; CNN-LSTM and TCN can be layered on after the data contract is stable.
