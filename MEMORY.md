# Artemis Quant Competition — Project Memory

## What this project is

**Artemis Quant Competition — Track #1: Crypto Factor Rebalancing Strategy.**
Goal: build a defensible weekly-rebalanced long-short crypto factor portfolio across ~113 large-cap assets (CoinGecko snapshot 2026-05-08, excluding stablecoins/wrapped/bridged). The competition rewards cross-sectional ranking power, regime robustness, turnover control, and economic interpretability.

**Current submission: Stage 15 Factor Ensemble Strategy** — the production pipeline runs Stages 09 → 10 → 12 → 15. Stages 01–08 and 13–14 are research history / appendix material.

---

## Folder map

| Folder | Role | Status |
|---|---|---|
| `01_Data_Collection/` | Data pull scripts, raw snapshots (Artemis, CoinGecko, Binance, DeFiLlama) | Archive |
| `02_Research/` | 10-paper literature review + research synthesis | Archive |
| `03_analysis/` | Exploratory analysis, universe profiling, early factor signals | Archive |
| `04_factors/` | RAAM v2 composite prototype (M/V/C/T + F/S/G signals) | Archive |
| `05_btc_direction/` | BTC directional model (Dubey & Enke 2025 reproduction) | Archive |
| `06_artemis_econometrics/` | Weekly Fama-MacBeth panel + latent controls + network features | Archive |
| `07_hidden_factor_pricing/` | Giglio-Xiu latent factor pricing (paper reproduction) | Archive |
| `08_nalfp/` | NALFP v3 — initial IC-weighted factor portfolio build | Archive |
| `09_nalfp_add/` | **Production** — universe + returns + Sparse-PCA + GX pricing + factor validation | Production |
| `10_behavioral_gx/` | **Production** — 182-candidate behavioral factor search → 4 priced-risk factors | Production |
| `12_factor_viz/` | **Production** — per-factor visualizations and RESULTS.md | Production |
| `13_rcfp/` | Regime-conditioned factor portfolios (Appendix A) | Appendix |
| `14_regime_factor_strategy/` | XGBoost regime-aware strategy (Appendix B) | Appendix |
| `15_factor_ensemble_strategy/` | **Production** — three-book ensemble, causal allocator, backtest, ablations | Production |
| `16_reports/` | Final research report (.md + .docx) and audit report | Reports |
| `17_presentation_slides/` | HTML presentation deck (in progress) | In Progress |

---

## Data sources

| Source | Provides | Auth |
|---|---|---|
| Binance | OHLCV returns, realized vol, turnover, trade count | Public (no key for market data) |
| CoinGecko | Price, mcap, supply, FDV, exclusion flags, categories | `COINGECKO_API_KEY` |
| Artemis | Adjusted txns/volume, real vs gamed, DAU, fees, network data | `ARTEMIS_API_KEY` |
| DeFiLlama | Protocol/chain TVL, fees/revenue, stablecoin inflows | Free, no auth |

Credentials: `~/.hermes/.env`. Never commit to repo.

Clean parquet files in `01_Data_Collection/data/clean/`:
- `coingecko_daily_ticks.parquet` — daily price/mcap/vol
- `coingecko_coin_details.parquet` — metadata + exclusion flags
- `artemis_activity_long.parquet` — on-chain activity
- `asset_master.parquet` — symbol/ID master table

Stage 09 artifacts (in `09_nalfp_add/artifacts/`):
- `price_mcap_panel_weekly.parquet`, `returns_weekly.parquet`
- `factor_validation_stats.parquet`, `gx5y_full_factor_zoo`, `universe_manifest.json`

---

## Research progression and key findings

### Stage 04 — RAAM v2 composite
IC results: VolC=+0.090, SMBC=+0.012, MomC=+0.026. T-factor silenced by ATR bug (A1). RAAM v2 validated VolC as the dominant signal.

### Stage 05 — BTC direction model
Best classifier: `l1__random_forest`, balanced accuracy 53.94%. Best trading: `all__gradient_boosting`, Sharpe 1.82. Directional models don't add enough to justify complexity.

### Stage 06 — Artemis econometrics
`plus_lat` model (Artemis + latent controls): IC IR=+0.54, LS Sharpe=+3.74 (16 OOS weeks only). `plus_net` was weak (IC IR=+0.20). Latent controls matter.

### Stage 07 — Hidden factor pricing
Only `crypto_smb` survives GX latent controls (FMB t=2.19, latent-adj t=1.97). Most factors don't survive hidden-factor adjustment — validated the need for proper GX pricing in the main pipeline.

### Stage 08 — NALFP v3
IC-weighted three-pillar design (network dynamics, GX factor zoo, IC-weighted combination). OOS Sharpe +1.24 over 24-week OOS. Low-vol and low-drawdown but lagged benchmarks on raw return. VolC dominated at ~44% weight.

### Stage 09 — NALFP Additional (production data pipeline)

Comprehensive factor validation framework. Deprecated `09_gx_pricing.py` (single-cross-section FMB shortcut with wrong SEs); all GX t-stats come from `09c_gx_pricing_full.py`.

Key design: market cap before ~2025 reconstructed as price × emissions-anchored supply, drift clamped to −3%/yr to +50%/yr per-day (supply clip bug fixed per audit Finding 3).

**Factor validation results:**

| Factor | IC (IS / OOS) | GX t-stat | ASD vs BTC | Grade |
|---|---|---:|---|---|
| VolC | −3.32 / −4.31 | −5.05 | No | Confirmed |
| MAXRET | −3.49 / −4.05 | +5.52 | No | Confirmed |
| RMOM1w | Weak | +1.86 | Yes (all 3 windows) | Priced risk |
| RMOM2w | IS yes / OOS weak | +1.05 | Yes | Suggestive |
| SMBC | Weak | +0.36 | Yes | Suggestive |
| NetRel | Weak | −0.01 | Yes | Suggestive |
| MispricingM | Composite | n/a | Yes (all 3 windows, ε₂=0.000) | Composite |

**MispricingM** = equal-weight of RMOM1w + RMOM2w + SMBC + NetRel. Dominant alpha source. Confirmed to ASD-dominate BTC in IS, full sample, and OOS windows separately.

### Stage 10 — Behavioral GX search

Searched 182 candidate specifications (91 features × 2 directions). 102 cleared uncorrected |t| ≥ 2.0 (56% hit rate — exploratory mining). Applied Bonferroni (|t| > 3.64) and Benjamini-Hochberg (q < 0.001) corrections. Four factors survived both:

| Factor | GX t-stat | Story |
|---|---:|---|
| CRASH8 | +4.79 | Rebound from deep crash |
| BETA26 | +4.60 | High-beta risk |
| SKEW52 | +3.44 | Lottery/skewness demand |
| NEWC | +3.43 | Newer-coin seasoning |

Re-priced IS/OOS separately — standalone single-window premia are weak. Used only as a small capped Priced Tilt sleeve.

### Stage 13 — Regime-conditioned factor portfolios (Appendix A)

Tested Plan A (economic classifier: dispersion + BTC dominance) and Plan B (HMM). OOS 79 weeks: Plan A +0.19 Sharpe, Plan B +0.36 Sharpe vs BTC −0.33. Regimes help risk control but can't be the whole strategy.

### Stage 14 — XGBoost regime strategy (Appendix B)

XGBoost regime classifier (RiskOff / Neutral / RiskOn). Best variant (Sharpe-optimized): OOS Sharpe +0.61. More complex variants failed: Return-optimized −0.52, Neural-network −0.46. Lesson: complexity hurts OOS robustness.

### Stage 15 — Factor Ensemble Strategy (FINAL SUBMISSION)

Three-book ensemble with causal rolling-performance allocator + XGBoost regime sizing.

| Book | Inputs | Role |
|---|---|---|
| MispricingM | RMOM1w, RMOM2w, SMBC, NetRel | Main alpha |
| Core Rank | VolC, MAXRET | Statistical backbone |
| Priced Tilt | CRASH8, BETA26, TVLC, SKEW52, NEWC | Capped sleeve (net OOS drag) |

**Out-of-sample results (final 79 weeks, bull→bear transition):**

| Strategy | Sharpe | Annual return | Volatility | Max drawdown |
|---|---:|---:|---:|---:|
| Sharpe Ensemble | +0.84 | +29.9% | 35.8% | −24.7% |
| Defensive Ensemble | +0.75 | +21.6% | 29.0% | −19.7% |
| Balanced Ensemble | +0.68 | +18.8% | 27.6% | −18.3% |
| MispricingM only | +0.85 | +37.2% | 44.1% | −29.9% |
| Bitcoin | −0.33 | −12.3% | 37.7% | −46.7% |
| Equal-weight market | −0.51 | −34.4% | 67.2% | −68.3% |

**Ablation findings:**
- Removing Priced Tilt → OOS Sharpe +0.90 (sleeve is a net drag — production version should run it near-zero)
- Removing regime tilt → OOS Sharpe +0.80 (small but real benefit)
- MispricingM alone = OOS Sharpe +0.85 (strategy is effectively single-factor; other books control vol/drawdown)
- OOS Sharpe range across full regime-tilt × priced-cap grid: +0.80 to +0.91 (robust to priors)

IS→OOS Sharpe decay: SE 1.36 → 0.84 (~38%), DE 1.31 → 0.75 (~43%), BE 1.28 → 0.68 (~47%). Compared to neural-network optimizer 2.06 → −0.46 — the ensemble is much more robust.

---

## Reports and audit

`16_reports/Artemis_Track1_Research_Report.md` — final competition report  
`16_reports/AUDIT_AND_FINDINGS_REPORT.md` — 13 findings, all production-pipeline findings resolved

Key resolved findings:
- Finding 1/2: Bonferroni + BH corrections added for behavioral search
- Finding 3: Supply drift clip bug fixed (−3%/yr to +50%/yr band)
- Finding 4: ASD now computed on IS, full, and OOS windows separately
- Finding 5: Regime-tilt sensitivity grid added
- Finding 6: Priced Tilt ablation showing it is OOS drag
- Finding 8: `09_gx_pricing.py` deprecated with runtime warning
- Finding 9: Leakage-free forward-fill in GX engine
- Finding 12: Pipeline provenance documented in README

---

## Research design rules (carry forward from 10-paper review)

1. TVL alone is not alpha. Use only as denominator: fees/TVL, revenue/TVL, fees/mcap.
2. Quality-adjusted Artemis metrics beat raw. Prefer `real_txns`, `real_volume`; penalize `pct_gamed_*`.
3. Factor premia need GX latent-factor survival testing before being credited.
4. No shuffle-based CV. Always chronological splits.
5. Multiple-testing corrections required for any search over >10 factor specifications.
6. Model complexity trades off against OOS robustness in short crypto histories. Prefer simpler.

---

## Current work

- [ ] Stage 17: HTML presentation deck (not started)
- [x] Stage 16: Reports folder created, all reports moved
- [x] Stage 15: Final ensemble with ablations — complete
- [x] Audit: All 13 findings addressed
- [x] CLAUDE.md, AGENTS.md, and MEMORY.md created/updated
