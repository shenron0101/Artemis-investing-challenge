## Plan: Hidden Factor Pricing Stage

Turn the paper “Crypto Pricing with Hidden Factors” into a new top-level research pipeline at `06_hidden_factor_pricing`. The plan mirrors the staged structure in `05_btc_direction/README.md`, reuses shared factor utilities from `04_factors/_common.py`, and focuses on comparing observed crypto factors against latent-factor-adjusted pricing results.

### Steps
1. Create `06_hidden_factor_pricing` with `README.md`, `REPORT.md`, `_common.py`, numbered scripts, and artifacts folders mirroring `05_btc_direction`.
2. Define the weekly asset-pricing panel in `06_hidden_factor_pricing/01_build_panel.py` using clean datasets from `01_Data_Collection/data/clean` and exclusion logic patterned after `04_factors/_common.py`.
3. Implement observed factor builders in `06_hidden_factor_pricing/02_observed_factors.py` for market, size, momentum, and TVL-based long-short factors using conventions from `04_factors` and diagnostics inspired by `03_analysis/06_cross_sectional.py`.
4. Add external regime and benchmark loaders in `06_hidden_factor_pricing/03_external_inputs.py` so paper-parity equity and sentiment variables remain separable from repo-native approximations.
5. Estimate baseline and latent models in `06_hidden_factor_pricing/04_price_models.py`, comparing Fama-MacBeth-style premia with hidden-factor-adjusted results and writing tables to artifacts.
6. Summarize whether Artemis factors survive latent controls in `06_hidden_factor_pricing/05_report.py`, linking findings back to `04_factors/04_RAAM_v2_composite.py` and `05_btc_direction/04_train_eval.py`.

### Further Considerations
0. Clone and use any data and repos they might also be using.
1. Choose scope early: strict paper reproduction with external equity/state series, or repo-native extension using currently available crypto data only.
2. Confirm the paper’s exact TVL sort and portfolio construction rules before coding, since that factor is likely the most implementation-sensitive.
3. Decide whether `06_hidden_factor_pricing` is inference-only or should also feed downstream ranking and BTC-direction workflows.
