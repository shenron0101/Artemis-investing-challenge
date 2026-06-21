# Artemis — Systematic Crypto Factor Strategy

A systematic, weekly-rebalanced long/short crypto factor portfolio over ~113
large-cap assets. The pipeline collects public market/on-chain data, discovers
and validates return factors, and combines them into a regime-aware ensemble
strategy. Full methodology and results are in `Artemis_Track1_Report.tex` (or
its compiled PDF).

**Out-of-sample headline (79 weeks, Nov 2024 – May 2026):**

| Strategy | Sharpe | Annual return | Max drawdown |
|---|---:|---:|---:|
| Sharpe Ensemble | +0.84 | +29.9% | -24.7% |
| Bitcoin | -0.33 | -12.3% | -46.7% |
| Equal-weight market | -0.51 | -34.4% | -68.3% |

---

## Quick start — reproduce all results

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add API keys (needed only for stage 01; stages 02–06 use committed artifacts)
cp .env.example .env
# edit .env and set ARTEMIS_API_KEY, COINGECKO_API_KEY, FRED_API_KEY

# 3. Run the full pipeline and assemble report figures
python3 reproduce.py

# 4. Compile the report (requires a LaTeX distribution: TeX Live / MiKTeX)
pdflatex Artemis_Track1_Report.tex && pdflatex Artemis_Track1_Report.tex
```

To resume from a specific stage (if step 1 already ran):

```bash
python3 reproduce.py --from 03   # run stages 03 → 06
python3 reproduce.py --stage 06  # run one stage only
python3 reproduce.py --figures   # re-assemble figures/ without re-running
```

---

## Repository layout

```
Artemis_Track1_Report.tex      report source (compile with pdflatex, twice)
reproduce.py                   master reproduction script
requirements.txt               unified Python dependencies
.env.example                   API key template (copy to .env and fill in)
figures/                       figures directory for LaTeX (auto-populated by reproduce.py)

01_Data_Collection/            stage 01 — data ingestion
02_artemis_econometrics/       stage 02 — cross-sectional characteristics
03_nalfp_add/                  stage 03 — factor discovery and validation
04_behavioral_gx/              stage 04 — behavioral factor search
05_factor_viz/                 stage 05 — per-factor dashboards
06_factor_ensemble_strategy/   stage 06 — ensemble strategy and backtest
```

---

## Pipeline stages

Each numbered stage consumes the artifacts of the stage(s) before it and writes
its outputs under its own `artifacts/` subdirectory.

### Stage 01 — `01_Data_Collection/`

Fetches and cleans the raw data. Pulls prices and market-cap from CoinGecko,
on-chain metrics (fees, TVL) from the Artemis Terminal API, and macro series
from FRED via Binance. Writes cleaned weekly parquet/CSV panels to
`01_Data_Collection/data/clean/`.

**API keys required.** See `.env.example`.

```bash
python3 01_Data_Collection/src/main.py
```

Key outputs: `data/clean/prices_weekly.parquet`, `data/clean/mcap_weekly.parquet`,
`data/clean/artemis_weekly.parquet`, `data/clean/defillama_tvl_weekly.parquet`.

### Stage 02 — `02_artemis_econometrics/`

Builds the weekly cross-sectional panel from stage 01 data. Computes lagged
characteristics (size, momentum, volatility, TVL ratios, on-chain fundamentals),
then runs econometric diagnostics: Fama–MacBeth, Lasso, and Giglio–Xiu (GX)
pricing. Produces a reference backtest and `REPORT.md`.

```bash
python3 02_artemis_econometrics/01_build_panel.py        # → panel.parquet
python3 02_artemis_econometrics/02_characteristics.py    # → characteristics.parquet
python3 02_artemis_econometrics/03_network_features.py
python3 02_artemis_econometrics/04_latent_controls.py
python3 02_artemis_econometrics/05_models.py
python3 02_artemis_econometrics/06_backtest.py
python3 02_artemis_econometrics/07_report.py             # → REPORT.md
```

Key output: `artifacts/data/characteristics.parquet` (lagged weekly characteristics,
read by stage 03's network producer).

### Stage 03 — `03_nalfp_add/`

The factor-discovery stage. Runs the **network producer first**:

`00_network_dynamics.py` reads the stage-02 characteristics and builds a
time-varying MST + Louvain community graph from rolling 12-week Spearman
correlations. Outputs `network_panel.parquet` containing four network-derived
signals — `cluster_id`, `within_cluster_mom` (NetMom), `cross_cluster_rel`
(NetRel), `network_entropy` — consumed by the factor viz (stage 05) and the
strategy engine (stage 06).

The remaining scripts build the production universe (~113 assets), reconstruct
the weekly market-cap panel, compute returns and DeFi fundamentals (fees, TVL
via Artemis Terminal), and run the three-lens factor validation: IC
(Newey–West), ASD (almost stochastic dominance vs Bitcoin), and full Giglio–Xiu
latent-factor pricing.

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
python3 03_nalfp_add/08_factor_validation.py       # IC / ASD per factor
python3 03_nalfp_add/09c_gx_pricing_full.py        # canonical GX pricing
```

`09c_gx_pricing_full.py` is the canonical GX implementation (proper Fama–MacBeth
with Newey–West standard errors). Every GX t-statistic in the report comes from it.
`RESULTS.md` documents the full master evidence table (24 factors).

### Stage 04 — `04_behavioral_gx/`

Searches 182 behavioral-factor candidates (crash depth, skewness, beta, and age
variants) with Bonferroni and Benjamini–Hochberg multiple-testing corrections.
Prices the surviving shortlist — CRASH8, BETA26, SKEW52, NEWC — through the
stage-03 GX engine.

```bash
python3 04_behavioral_gx/01_behavioral_gx_search.py
```

### Stage 05 — `05_factor_viz/`

One self-contained dashboard script per validated factor (15 total), each
writing its figures and a per-factor report. Network-factor dashboards
(NetMom, NetRel) read `network_panel.parquet` from stage 03; the rest read
stage-03 / stage-04 data. Scripts are independent and can be run in any order.

The factor figures used in the report (VolC, CRASH8, NetRel) are committed and
live in each factor's `artifacts/figures/` subfolder; `reproduce.py` copies
them into `figures/` for LaTeX.

```bash
python3 05_factor_viz/volc_visualisation/12_volc_visualisation.py
python3 05_factor_viz/crash8_visualisation/24_crash8_visualisation.py
python3 05_factor_viz/netrel_visualisation/17_netrel_visualisation.py
# ... and so on for all 15 factors
```

### Stage 06 — `06_factor_ensemble_strategy/`

The final strategy stage. `engine.py` builds the weekly factor panel and
XGBoost regime panel from the stage-03 data, and exposes the portfolio
primitives used by the sub-book ensemble. `run.py` assembles three sub-books:

| Sub-book | Factors | Rationale |
|---|---|---|
| mispricing | RMOM1w, RMOM2w, SMBC, NetRel | ASSD-dominant mispricing composite (MispricingM) |
| core_rank | VolC, MAXRET | Confirmed IC-robust weekly rankers |
| priced_tilt | CRASH8, BETA26, TVLC, SKEW52, NEWC | Priced behavioral/DeFi systematic exposures; hard-capped at 18% |

Allocation across books uses a 26-week rolling-performance score blended with
fixed priors and XGBoost regime probabilities. Results including full-window,
IS, OOS, ablation, and sensitivity grids are written to `RESULTS.md` and
`artifacts/manifests/metrics.json`.

```bash
python3 06_factor_ensemble_strategy/run.py
```

On first run `engine.load_panels()` builds `factor_panel.parquet` and
`regime_panel.parquet` from the stage-03 artifacts automatically.

Unit tests (synthetic data only, no live fetch):

```bash
cd 06_factor_ensemble_strategy
python3 -c "
import test_strategy as t
t.test_rolling_book_allocations_use_only_prior_returns()
t.test_combine_book_weights_scales_each_subbook_by_weekly_allocation()
print('tests passed')
"
```

---

## Credentials and data

Stage 01 requires API keys. Copy `.env.example` to `.env` in the repository root
and fill in the three keys. The loaders read from this file directly.

Stages 02–06 read only from committed manifests or the intermediate parquets
written by earlier stages. All data panels (`*.parquet`, `*.csv`) are gitignored
— they regenerate by running the pipeline from stage 01.

---

## Report figures

The LaTeX file (`Artemis_Track1_Report.tex`) loads all figures from the
`figures/` directory at the repository root. Running `python3 reproduce.py`
(or `python3 reproduce.py --figures` to skip re-running the pipeline) copies
the pipeline outputs into `figures/`. Three static diagrams —
`network_clusters.png`, `netmom_netrel_schematic.png`, and
`factor_routing_graph.png` — are committed directly and do not need regenerating.

After assembling figures, compile the report with:

```bash
pdflatex Artemis_Track1_Report.tex
pdflatex Artemis_Track1_Report.tex   # second pass for cross-references
```
