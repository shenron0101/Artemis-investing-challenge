# Artemis Investing Challenge — Repository Structure

```text
Artemis-investing-challenge
├── 01_Data_Collection
│   ├── config
│   │   ├── defillama_overrides.yaml
│   │   └── settings.yaml
│   ├── README.md
│   ├── REMAINING.md
│   ├── requirements.txt
│   └── src
│       ├── clients.py
│       ├── __init__.py
│       ├── io_utils.py
│       ├── logging_utils.py
│       ├── main.py
│       ├── pipeline.py
│       └── universe.py
├── 02_Research
│   ├── 2025- Equities vs Crypto Tokens - Who Wins?.md
│   ├── 2602.11708v1.html
│   ├── Artemis Crypto Factor Model Analysis: March 2026 Update.md
│   ├── artemis_factor_model_explainer.py
│   ├── artemis_track1_research_consolidation.md
│   ├── Crypto Factor Model Analysis.md
│   ├── Crypto Revenue.md
│   ├── Figure Open Deep Dive: Rebuilding Capital Markets On-Chain.md
│   ├── Figure Technology Solutions: Compelling After Its Worst Day Ever.md
│   ├── images
│   │   └── paper_explainers
│   │       ├── 01_bitcoin_onchain_explainer.png
│   │       ├── 02_time_varying_network_explainer.png
│   │       ├── 03_dynamic_latent_factor_explainer.png
│   │       ├── 04_crypto_pricing_hidden_factors_explainer.png
│   │       └── 05_adaptive_trend_explainer.png
│   ├── rank_images
│   │   ├── 01.png
│   │   ├── 02.png
│   │   ├── 03.png
│   │   ├── 04.png
│   │   ├── 05.png
│   │   ├── 06.png
│   │   ├── 07.png
│   │   ├── 08.png
│   │   ├── 09.png
│   │   ├── 10.png
│   │   ├── 11.png
│   │   ├── 12.png
│   │   ├── 13.png
│   │   ├── 14.png
│   │   ├── 15.png
│   │   ├── 16.png
│   │   ├── 17.png
│   │   ├── 18.png
│   │   ├── 19.png
│   │   ├── 20.png
│   │   ├── 21.png
│   │   ├── 22.png
│   │   ├── 23.png
│   │   └── 24.png
│   ├── rank.md
│   ├── research_paper_review.md
│   ├── Shares vs. Tokens: Why We Need "Outstanding Supply" and a Smarter Circulating Supply.md
│   └── The Great Unwind of Crypto and Growth.md
├── 03_analysis
│   ├── 00_DATA_INVENTORY.md
│   ├── 01_data_quality.py
│   ├── 02_universe_profile.py
│   ├── 03_price_returns.py
│   ├── 04_onchain_activity.py
│   ├── 05_factor_signals.py
│   ├── 06_cross_sectional.py
│   └── _common.py
├── 04_factors
│   ├── 01_F_fundamental_yield.py
│   ├── 02_S_supply_absorption.py
│   ├── 03_G_activity_growth.py
│   ├── 04_RAAM_v2_composite.py
│   ├── _common.py
│   └── README.md
├── 05_btc_direction
│   ├── 01_build_dataset.py
│   ├── 02_feature_engineering.py
│   ├── 03_feature_selection.py
│   ├── 04_train_eval.py
│   ├── 05_trading_simulation.py
│   ├── 06_report.py
│   ├── _common.py
│   ├── README.md
│   ├── REPORT.md
│   └── requirements.txt
├── 06_artemis_econometrics
│   ├── 01_build_panel.py
│   ├── 02_characteristics.py
│   ├── 03_network_features.py
│   ├── 04_latent_controls.py
│   ├── 05_models.py
│   ├── 06_backtest.py
│   ├── 07_report.py
│   ├── _common.py
│   ├── README.md
│   └── REPORT.md
├── 07_hidden_factor_pricing
│   ├── 01_build_panel.py
│   ├── 02_observed_factors.py
│   ├── 03_external_inputs.py
│   ├── 04_price_models.py
│   ├── 05_report.py
│   ├── _common.py
│   ├── inputs
│   │   └── .gitkeep
│   ├── README.md
│   └── REPORT.md
├── 08_nalfp
│   ├── 01_network_dynamics.py
│   ├── 02_factor_pricing.py
│   ├── 03_regime_detector.py
│   ├── 04_portfolio_construction.py
│   ├── 05_backtest.py
│   ├── 06_report.py
│   ├── artifacts
│   │   ├── data
│   │   │   ├── blended_signals.parquet
│   │   │   ├── factor_correlations.parquet
│   │   │   ├── factor_zoo_returns.parquet
│   │   │   ├── factor_zoo_stats.parquet
│   │   │   ├── gx_bai_ng.parquet
│   │   │   ├── gx_betas.parquet
│   │   │   ├── gx_expected_returns.parquet
│   │   │   ├── gx_hidden_factors.parquet
│   │   │   ├── gx_lambda_obs_only.parquet
│   │   │   ├── gx_lambda_obs_vs_full.parquet
│   │   │   ├── gx_lambda.parquet
│   │   │   ├── network_market.parquet
│   │   │   ├── network_panel.parquet
│   │   │   ├── regime_weights.parquet
│   │   │   ├── weekly_attribution.parquet
│   │   │   ├── weekly_diag.parquet
│   │   │   ├── weekly_pnl.parquet
│   │   │   ├── weekly_weights_no_cluster_cap.parquet
│   │   │   └── weekly_weights.parquet
│   │   └── manifests
│   │       ├── 01_network_manifest.json
│   │       ├── 02_factor_pricing_manifest.json
│   │       ├── 03_regime_manifest.json
│   │       ├── 04_portfolio_manifest.json
│   │       └── 05_metrics.json
│   ├── _common.py
│   ├── figures
│   │   ├── 01_network_dynamics
│   │   │   ├── mst_2025-11-10.png
│   │   │   ├── mst_2026-05-04.png
│   │   │   └── network_overview.png
│   │   ├── 02_factor_pricing
│   │   │   ├── bai_ng_diagnostic.png
│   │   │   ├── factor_correlation_heatmap.png
│   │   │   ├── factor_zoo_cumulative.png
│   │   │   ├── hidden_factor_loadings.png
│   │   │   ├── lambda_full.png
│   │   │   └── lambda_obs_only.png
│   │   ├── 03_regime_detector
│   │   │   └── regime_blend.png
│   │   ├── 04_portfolio_construction
│   │   │   ├── cluster_composition.png
│   │   │   └── portfolio_diagnostics.png
│   │   └── 05_backtest
│   │       └── cumulative_pnl.png
│   ├── .gitignore
│   ├── paper
│   │   ├── nalfp.pdf
│   │   └── nalfp.tex
│   ├── REPORT.md
│   └── RESEARCH_PLAN.md
├── Artemis Quant Competition.pdf
├── Coins.md
├── Data Groupings.md
├── Data Sources Reference.md
├── .env.example
├── .git
├── .github
│   ├── bug-fix-plan.md
│   ├── plan-artemisEconometrics.prompt.md
│   ├── plan-hiddenFactorPricing.prompt.md
│   └── prompts
│       └── plan-btcDirectionPaperReproduction.prompt.md
└── .gitignore
```

**Summary:** 43 directories, 189 files
