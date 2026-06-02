# Artemis Quant Competition — Track 1: Code Submission

Companion code for the report `16_reports/Artemis_Track1_Report.tex` (rendered:
`Artemis_Track1_Report.pdf`; long-form Markdown/DOCX versions are also in
`16_reports/`).

The report is a systematic, weekly-rebalanced long-short crypto factor
portfolio over ~113 large-cap assets. This package contains every script
needed to reproduce the report's numbers and figures, organised by report
flow.

## Repository layout

| Folder | Report section it serves | Contents |
|---|---|---|
| `01_Data_Collection/` | Universe, data, design choices | Public-API loaders (Binance, CoinGecko, Artemis, DeFiLlama). Cleaned parquets are gitignored — regenerate locally. |
| `06_artemis_econometrics/` | upstream of Stage 08 | Build scripts that produce `characteristics.parquet` consumed by `08_nalfp/01_network_dynamics.py`. |
| `08_nalfp/` | upstream of Stages 13, 14 | Only the **network-panel producer** (`_common.py`, `01_network_dynamics.py`) is shipped. It writes `network_panel.parquet`, consumed by Stages 12 (NetMom/NetRel viz), 13, 14. |
| `09_nalfp_add/` | §3 Universe / §4 Factor discovery / §5 Master evidence | Production pipeline: universe + reconstructed mcap, weekly returns, Sparse-PCA, factor validation (IC/ASD/GX), MispricingM composite. |
| `10_behavioral_gx/` | §5 Behavioral factors | 182-candidate behavioral factor search with Bonferroni + Benjamini-Hochberg corrections → CRASH8, BETA26, SKEW52, NEWC. |
| `12_factor_viz/` | §5 Selected exhibits | Per-factor dashboards. The PNGs `\includegraphics`'d in §5 of the report live here. |
| `13_rcfp/` | Appendix A — Regime conditioning | Plan A (economic classifier) and Plan B (HMM). |
| `14_regime_factor_strategy/` | Appendix B — ML lessons | XGBoost regime classifier and optimizer variants. Stage 15 imports `run.py` directly. |
| `15_factor_ensemble_strategy/` | §6 Final strategy / §7 Backtest / §7.1 Ablation | Three-book ensemble, causal allocator, regime sizing, ablation grid. |
| `16_reports/` | the report itself | `.tex`, `.pdf`, `.md`, `.docx`. |
| `figures/`, `16_reports/figures/` | §5, §6 figures | `network_clusters.png`, `netmom_netrel_schematic.png`, `factor_routing_graph.png`, plus the `image2/4/5/6.png` set the LaTeX report `\includegraphics`. |
| `submission_assets/` | reproducibility helper | `regenerate_report_figures.py` — see below. |

## Run order

```bash
# 0. Credentials. Required for the live data fetch in step 1.
#    Copy .env.example to ~/.hermes/.env and fill in:
#    ARTEMIS_API_KEY, COINGECKO_API_KEY, FRED_API_KEY.

# 1. Build the cleaned universe parquets in 01_Data_Collection/data/clean/.
python3 01_Data_Collection/src/main.py

# 2. Build the upstream characteristics panel.
python3 06_artemis_econometrics/01_build_panel.py
python3 06_artemis_econometrics/02_characteristics.py

# 3. Build the network panel that Stages 12/13/14 read.
python3 08_nalfp/01_network_dynamics.py

# 4. Production pipeline (Stage 09 → 10 → 12).
python3 09_nalfp_add/03_reconstruct_mcap_panel.py
python3 09_nalfp_add/05_returns_and_reference.py
python3 09_nalfp_add/06_sparse_pca.py
python3 09_nalfp_add/09c_gx_pricing_full.py       # NOT 09_gx_pricing.py — deprecated
python3 09_nalfp_add/08_factor_validation.py
python3 10_behavioral_gx/01_behavioral_gx_search.py

# 5. Optional appendix stages (independent — both feed Appendix A/B).
python3 13_rcfp/a02_run_strategy.py
python3 13_rcfp/b02_run_strategy.py
python3 14_regime_factor_strategy/run.py

# 6. Final ensemble strategy and backtest.
python3 15_factor_ensemble_strategy/run.py
```

`09_nalfp_add/09_gx_pricing.py` is **deprecated** (it uses a single-cross-section
Fama-MacBeth shortcut with the wrong standard errors). The file carries a
runtime deprecation banner and is retained only for historical comparison —
every GX t-statistic in the report comes from `09c_gx_pricing_full.py`.

## What ships vs. what regenerates

The following artifacts are committed and the report uses them directly:

- All Stage 12 per-factor dashboards (`12_factor_viz/**/artifacts/figures/*.png`).
- The Stage 15 metrics manifest (`15_factor_ensemble_strategy/artifacts/manifests/metrics.json`) — contains every Sharpe/return/vol/drawdown number quoted in §7 and the sensitivity grid.
- Stage 09/10/13/14 manifests with the corresponding numbers.
- All LaTeX figures (`figures/*.png`, `16_reports/figures/*.png`).

The four pipeline-output figures the long-form Markdown report references
(`15_factor_ensemble_strategy/artifacts/figures/cumulative_returns.png`,
`sharpe_ensemble_book_allocations.png`,
`balanced_ensemble_book_allocations.png`, and
`14_regime_factor_strategy/artifacts/figures/xgboost_regimes.png`) cannot be
regenerated faithfully without the live data fetch in step 1. They are
reproduced from the committed `metrics.json` by:

```bash
python3 submission_assets/regenerate_report_figures.py
```

The Stage 15 figures rendered this way use the **exact** numbers from §7 of
the report (Tables 5 and 10). The Stage 14 `xgboost_regimes.png` is rendered
as a labelled schematic because weekly regime probabilities are not stored in
the committed manifest — re-run step 5 above to produce the true probability
path.

## Credentials and large data

`.env.example` shows the API key shape expected at `~/.hermes/.env`. The
clean panels live in `01_Data_Collection/data/clean/` and are gitignored;
they regenerate from step 1.

## Key result (for orientation)

Out-of-sample (final 79 weeks, a bull→bear transition):

| Strategy | Sharpe | Annual return | Max drawdown |
|---|---:|---:|---:|
| Sharpe Ensemble | +0.84 | +29.9% | -24.7% |
| Bitcoin | -0.33 | -12.3% | -46.7% |
| Equal-weight market | -0.51 | -34.4% | -68.3% |

Full results, including in-sample, full-window, ablations, and sensitivity
grid, are in §7 of the report and `15_factor_ensemble_strategy/RESULTS.md`.
