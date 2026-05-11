## Plan: Artemis Econometrics Track

Turn the current paper reading into a competition-ready research pipeline centered on a **latent-factor-adjusted cross-sectional crypto model**. The novelty is not to copy any one paper, but to combine four ideas already reviewed:

- on-chain and exchange-flow characteristics from `Bitcoin price direction prediction using on-chain data and feature selection`
- cross-asset structure from `A Time-Varying Network for Cryptocurrencies`
- sparse characteristic-driven factor loadings from `Dynamic Latent-Factor Model with High-Dimensional Asset Characteristics`
- omitted-risk controls from `Crypto Pricing with Hidden Factors`

The output should be a new top-level pipeline at `06_artemis_econometrics` that scores the cross-section weekly, forms long-short portfolios, and produces paper-style diagnostics plus competition-facing results.

### Proposed Competition Thesis
Build a **cross-sectional expected return model for crypto assets** that combines:
- asset-level characteristics
- network/community structure
- latent-factor controls

This gives a cleaner econometric story than a pure prediction model:
- characteristics explain expected-return differences
- community structure captures cross-asset spillovers
- latent factors absorb common omitted risks

### Immediate Build Plan
1. Create `06_artemis_econometrics` with `README.md`, `REPORT.md`, `_common.py`, numbered scripts, and artifacts folders mirroring `05_btc_direction`.
2. Define the weekly competition panel in `06_artemis_econometrics/01_build_panel.py` using cleaned datasets from `01_Data_Collection/data/clean` and universe logic adapted from `03_analysis/02_universe_profile.py` and `04_factors/_common.py`.
3. Implement baseline characteristics in `06_artemis_econometrics/02_characteristics.py`:
   - size / log market cap
   - 1w / 4w / 12w momentum
   - volatility
   - turnover or dollar volume
   - Artemis factor exposures from `04_factors/01_F_fundamental_yield.py`, `02_S_supply_absorption.py`, `03_G_activity_growth.py`, and `04_RAAM_v2_composite.py`
   - exchange-flow and on-chain activity features where available
4. Add cross-asset structure in `06_artemis_econometrics/03_network_features.py`:
   - rolling return-correlation clusters as the minimum viable network layer
   - optional predictive-link network inspired by the time-varying network paper
   - cluster labels, within-cluster momentum, and cross-cluster relative-strength features
5. Add latent controls in `06_artemis_econometrics/04_latent_controls.py`:
   - estimate weekly or monthly PCA factors from the return panel
   - compute each asset’s loading on those latent factors
   - store residualized returns and factor exposures for downstream regressions
6. Build benchmark econometric models in `06_artemis_econometrics/05_models.py`:
   - Fama-MacBeth style cross-sectional regression
   - pooled panel regression with fixed standardization rules
   - Lasso / elastic-net sparse cross-sectional model
   - characteristic model with latent-factor controls
   - characteristic + network + latent-factor model as the competition candidate
7. Evaluate ranking quality in `06_artemis_econometrics/06_backtest.py`:
   - top-minus-bottom quintile spread
   - information coefficient
   - long-short Sharpe
   - turnover
   - alpha relative to simple crypto market / SMB / momentum benchmarks
8. Summarize findings in `06_artemis_econometrics/07_report.py`, with emphasis on whether network features and latent controls improve Artemis factor signals rather than replacing them.

### Competition Novelty
The novelty should be framed as:
- Artemis-style fundamental and on-chain characteristics are **not** used as standalone scores
- they are embedded in a **cross-sectional econometric model**
- that model is adjusted for **hidden common crypto risks**
- and enriched with **cross-asset network/community information**

This is stronger than:
- plain momentum
- plain on-chain ranking
- plain latent-factor pricing
- plain network clustering

because it combines all four in one implementable framework.

### Minimum Viable Version
If scope becomes a problem, the minimum viable competition submission is:
1. Weekly panel.
2. Artemis characteristics plus basic market features.
3. PCA latent factors as controls.
4. Fama-MacBeth or Lasso ranking model.
5. Long-short quintile evaluation.

Only after that should network/community features be added.

### First Questions To Resolve Before Coding
1. What exactly is the Artemis competition target:
   - cross-sectional weekly ranking
   - long-short portfolio construction
   - single-asset forecasting
2. Which on-chain fields are already clean enough to support exchange-flow or holder-behavior features?
3. Should network structure be based on:
   - simple rolling correlations
   - predictive regressions
   - factor-residual correlations
4. Do we want a pure econometrics baseline first, or immediate comparison against tree/boosting models?

### Recommended Build Order
1. Get the weekly panel and benchmark regressions working first.
2. Verify Artemis factors have signal in simple cross-sectional tests.
3. Add latent controls and check whether the factor signal survives.
4. Add network/community features and measure incremental lift.
5. Only then consider nonlinear or more complex ML extensions.

### Success Criteria
- A reproducible weekly research pipeline.
- A clear benchmark table comparing simple factors vs latent-adjusted models.
- Evidence on whether network features add incremental value.
- A competition-ready claim that is both novel and econometrically defendable.
