# Artemis — Systematic Crypto Factor Strategy

A systematic, weekly-rebalanced long/short crypto factor portfolio over ~113
large-cap assets. The pipeline collects public market/on-chain data, builds a
weekly cross-sectional panel, discovers and validates return factors, and
combines the survivors into a regime-aware ensemble strategy.

This repository is organised as a linear pipeline: each numbered stage consumes
the artifacts of the stage(s) before it. Run them in order and each stage writes
its outputs under its own `artifacts/` directory.

```
01_Data_Collection      → cleaned market / on-chain panels
02_artemis_econometrics → weekly cross-sectional characteristics + diagnostics
03_nalfp_add            → universe, returns, network panel, factor zoo + validation
04_behavioral_gx        → behavioral-factor search (multiple-testing corrected)
05_factor_viz           → per-factor dashboards for the validated factors
06_factor_ensemble_strategy → final regime-aware sub-book ensemble + backtest
```

## Pipeline stages

### 01 — `01_Data_Collection/`
Public-API loaders (Binance, CoinGecko, Artemis, DeFiLlama, FRED). The
orchestrator `src/main.py` runs the staged pipeline (`src/pipeline.py`) and
writes cleaned parquet/CSV panels to `01_Data_Collection/data/clean/`. Those
clean panels are gitignored — they regenerate from this stage.

```bash
python3 01_Data_Collection/src/main.py
```

### 02 — `02_artemis_econometrics/`
Builds the weekly cross-sectional panel and characteristics from the clean
data, then runs the econometric diagnostics (Fama–MacBeth, Lasso, Giglio–Xiu
pricing) and a reference backtest. Run the steps in order:

```bash
python3 02_artemis_econometrics/01_build_panel.py        # weekly panel
python3 02_artemis_econometrics/02_characteristics.py    # → characteristics.parquet
python3 02_artemis_econometrics/03_network_features.py
python3 02_artemis_econometrics/04_latent_controls.py
python3 02_artemis_econometrics/05_models.py
python3 02_artemis_econometrics/06_backtest.py
python3 02_artemis_econometrics/07_report.py             # → REPORT.md
```

The key output is `artifacts/data/characteristics.parquet` (already lagged),
which the network producer in stage 03 reads.

### 03 — `03_nalfp_add/`
The factor-discovery stage. It begins with the **network producer**
(`00_network_dynamics.py`), which builds a time-varying MST + Louvain community
graph from the stage-02 characteristics and writes `network_panel.parquet` — the
source of the network factors (NetMom, NetRel, `cluster_id`, `network_entropy`)
used downstream by stages 05 and 06. The remaining scripts build the production
universe, reconstructed market cap, weekly returns, fundamentals, the Sparse-PCA
factor set, and the factor validation (IC / ASD / Giglio–Xiu pricing).

```bash
python3 03_nalfp_add/00_network_dynamics.py        # → network_panel.parquet
python3 03_nalfp_add/01_universe_coverage.py
python3 03_nalfp_add/02_coinmetrics_coverage.py
python3 03_nalfp_add/03_reconstruct_mcap_panel.py  # → price_mcap_panel_weekly.parquet
python3 03_nalfp_add/04_freeze_universe.py
python3 03_nalfp_add/05_returns_and_reference.py   # → returns_weekly.parquet
python3 03_nalfp_add/06_sparse_pca.py
python3 03_nalfp_add/07_cca_macro.py
python3 03_nalfp_add/09b_fundamentals.py           # → fundamentals_weekly.parquet
python3 03_nalfp_add/08_factor_validation.py       # IC / ASD validation
python3 03_nalfp_add/09c_gx_pricing_full.py        # canonical GX pricing (Newey-West)
```

`09c_gx_pricing_full.py` is the canonical Giglio–Xiu implementation (proper
Fama–MacBeth with Newey–West standard errors); every GX t-statistic in the
factor documentation comes from it.

### 04 — `04_behavioral_gx/`
Searches 182 behavioral-factor candidates with Bonferroni and Benjamini–Hochberg
multiple-testing corrections, then prices the shortlist (CRASH8, BETA26, SKEW52,
NEWC) through the stage-03 GX engine. Reads the stage-03 data artifacts.

```bash
python3 04_behavioral_gx/01_behavioral_gx_search.py
```

### 05 — `05_factor_viz/`
One self-contained dashboard script per validated factor (15 in total), each
writing its figures and a short per-factor report. The network-factor dashboards
(NetMom, NetRel) read `network_panel.parquet` from stage 03; the rest read the
stage-03 / stage-04 factor data. Scripts are independent and can be run in any
order, e.g.:

```bash
python3 05_factor_viz/volc_visualisation/12_volc_visualisation.py
python3 05_factor_viz/netmom_visualisation/18_netmom_visualisation.py
# ... one per factor
```

### 06 — `06_factor_ensemble_strategy/`
The final strategy. `engine.py` builds the weekly factor panel and the XGBoost
regime panel from the stage-03 data, and provides the portfolio primitives.
`run.py` builds three sub-books (mispricing, core-rank, priced-tilt) and
allocates between them with a causal rolling-performance rule plus regime
sizing, then runs the backtest, ablations, and sensitivity grid.

```bash
python3 06_factor_ensemble_strategy/run.py
```

`run.py` is self-contained: on first run `engine.load_panels()` builds
`factor_panel.parquet` and `regime_panel.parquet` from the stage-03 artifacts
(no separate step required). Results are written to `RESULTS.md` and
`artifacts/manifests/metrics.json`. Unit tests for the allocator live in
`test_strategy.py` (synthetic data, no live fetch):

```bash
cd 06_factor_ensemble_strategy
python3 -c "import test_strategy as t; t.test_rolling_book_allocations_use_only_prior_returns(); t.test_combine_book_weights_scales_each_subbook_by_weekly_allocation()"
```

## Credentials

Step 01 needs API keys. Copy `.env.example` to a `.env` file in the repository
root and fill in `ARTEMIS_API_KEY`, `COINGECKO_API_KEY`, and `FRED_API_KEY`.
The loaders read this repo-root `.env` directly.

## Data and artifacts

The cleaned panels in `01_Data_Collection/data/clean/` and the intermediate
parquets are gitignored — they regenerate by running the pipeline. Committed
per-stage `artifacts/manifests/*.json` and `RESULTS.md` files hold the numbers
and figures each stage produced.

## Key result

Out-of-sample (final 79 weeks, a bull→bear transition):

| Strategy | Sharpe | Annual return | Max drawdown |
|---|---:|---:|---:|
| Sharpe Ensemble | +0.84 | +29.9% | -24.7% |
| Bitcoin | -0.33 | -12.3% | -46.7% |
| Equal-weight market | -0.51 | -34.4% | -68.3% |

Full in-sample, full-window, ablation, and sensitivity results are in
`06_factor_ensemble_strategy/RESULTS.md` and its `artifacts/manifests/metrics.json`.
