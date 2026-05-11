## Plan: BTC Direction Paper Reproduction (Stage 05)

Create a new top-level Stage 05 focused on reproducing the attached paper workflow from data assembly through feature selection, prediction, and strategy backtest. The plan mirrors this repo’s numbered-stage style and reuses shared plotting/output conventions so results are reproducible, comparable, and easy to extend.

### Steps
1. Define Stage 05 scope from [02_Research/Bitcoin price direction prediction using on-chain data and feature selection.pdf](02_Research/Bitcoin%20price%20direction%20prediction%20using%20on-chain%20data%20and%20feature%20selection.pdf) and [02_Research/research_paper_review.md](02_Research/research_paper_review.md).
2. Create folder skeleton and docs: [05_btc_direction/README.md](05_btc_direction/README.md), [05_btc_direction/_common.py](05_btc_direction/_common.py), figures/artifacts subfolders.
3. Implement dataset build and feature engineering scripts, reusing `run_pipeline()` patterns from [01_Data_Collection/src/pipeline.py](01_Data_Collection/src/pipeline.py) and shared helpers in [03_analysis/_common.py](03_analysis/_common.py).
4. Add feature-selection stage (`L1`, `Boruta`, `PCA`) in [05_btc_direction/03_feature_selection.py](05_btc_direction/03_feature_selection.py), saving selected-feature manifests.
5. Build chronological training/evaluation and trading simulation in [05_btc_direction/04_train_eval.py](05_btc_direction/04_train_eval.py) and [05_btc_direction/05_trading_simulation.py](05_btc_direction/05_trading_simulation.py), then publish outputs via [05_btc_direction/06_report.py](05_btc_direction/06_report.py).

### Further Considerations
1. Data source choice for paper parity: Option A current Artemis/CoinGecko/Binance only, Option B add Glassnode adapter, Option C hybrid fallback mapping.
2. Model scope for first pass: Option A classical models only, Option B classical + `CNN-LSTM`, Option C classical + `TCN`.
3. Draft review checkpoint: approve this structure as-is, or request renaming (e.g., [05_btc_direction](05_btc_direction) vs [05_prediction](05_prediction)).
