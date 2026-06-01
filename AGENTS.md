# Artemis Track 1 — Agent Context Reference

## Competition context

This project is a submission for **Track 1 of the Artemis Quant Competition**. The competition asks for a systematic crypto factor rebalancing strategy with a clear economic story, statistical defensibility, and honest evaluation of limitations. The final deliverable is a research report plus supporting code.

Track 1 focus: cross-sectional factor portfolio, weekly rebalancing, long–short positions across ~113 large-cap crypto assets. The portfolio is evaluated on Sharpe ratio, annualized return, max drawdown, turnover, and out-of-sample robustness.

---

## Universe

~113 large-cap and upper-mid-cap crypto coins. Constructed from CoinGecko market-cap rankings (snapshot date 2026-05-08). Stablecoins (USDT, USDC, USDS, etc.), wrapped duplicates (WBTC, etc.), and bridged assets are excluded. The universe excludes very illiquid assets where slippage would make paper returns untradeable.

Research period: 2017–2026 (broad factor validation). Main IS/OOS split: in-sample 2021-05-10 to 2024-11-11, out-of-sample 2024-11-18 to 2026-05-25 (79 weeks OOS).

---

## Data sources

### Binance
- OHLCV klines via REST API (`/api/v3/klines`) and bulk download portal
- Primary source for weekly return series — lower noise than CoinGecko for exchange-listed assets
- Also: realized volatility, turnover, quote volume, trade count

### CoinGecko
- Market cap, supply, FDV, 24h volume, price
- Universe definition and exclusion flags (stablecoin, wrapped, bridged)
- Identity anchor: `coingecko_id` is the primary cross-source join key
- Demo API key required (`x-cg-demo-api-key` header)

### Artemis
- On-chain usage metrics: transactions (raw and adjusted/real), volume (raw and adjusted), DAU, active addresses
- Quality metrics: `percent_gamed_txns`, `percent_gamed_volume`, real/total ratio
- Network data: used for the NetRel factor (coin vs related coins in network)
- Stablecoin supply and flows (macro regime signal)
- REST base URL: `https://data-svc.artemisxyz.com`
- Auth: `ARTEMIS_API_KEY` query param

### DeFiLlama
- Protocol TVL (used for TVLC factor)
- Fees and revenue (monetization quality)
- Stablecoin macro panel (system liquidity regime)
- Free API, no auth required: `https://api.llama.fi`

All credentials stored in `~/.hermes/.env`. Never committed to repo.

---

## Research stages

### Stages 01–08 (archive — research history)

| Stage | What was done |
|---|---|
| 01 Data Collection | Raw data pull scripts for all four sources, snapshot storage, cross-source identity mapping |
| 02 Research | Early exploratory research, literature review, initial factor ideas |
| 03 Analysis | Ad-hoc analysis of data quality, return distributions, preliminary factor tests |
| 04 Factors | First factor prototypes — momentum, size, volatility |
| 05 BTC Direction | Bitcoin directional model experiments (separate from cross-sectional factor work) |
| 06 Artemis Econometrics | Econometric experiments using Artemis on-chain data as factor inputs |
| 07 Hidden Factor Pricing | Early latent factor pricing experiments (precursor to GX pricing) |
| 08 NALFP | Base "Not A Long-Factor Portfolio" build — first full weekly long-short backtest |

### Stage 09 — NALFP Additional (production data pipeline)

The core data and validation engine. Produces all the inputs that downstream stages depend on.

Scripts (in run order):
- `03_reconstruct_mcap_panel.py` — reconstructs historical market cap using price × emissions-anchored supply. Deep history before ~2025 uses a Tier-3 backfill: log-linear supply growth estimated from last 365 days of CoinGecko data, drift clamped to −3%/yr to +50%/yr per-day equivalent. The SMBC factor uses log-mcap ranks not levels, so residual reconstruction error has limited impact.
- `05_returns_and_reference.py` — computes weekly returns and reference panel
- `06_sparse_pca.py` — Sparse PCA for latent factor extraction
- `09c_gx_pricing_full.py` — Giglio-Xiu latent-factor pricing with proper week-by-week Fama-MacBeth regressions and Newey-West standard errors. **This is the only valid GX pricing script.** `09_gx_pricing.py` (single-cross-section FMB shortcut) is deprecated.
- `08_factor_validation.py` — IC tests, ASD (Almost Stochastic Dominance) tests, MispricingM composite construction

Key outputs (in `09_nalfp_add/artifacts/`):
- `price_mcap_panel_weekly.parquet`
- `returns_weekly.parquet`
- `factor_validation_stats.parquet`
- `gx5y_full_factor_zoo` (GX pricing results)
- `universe_manifest.json`

**Factors validated here:**

| Factor | IC result | GX t-stat | ASD vs BTC | Grade |
|---|---|---:|---|---|
| VolC | IS −3.32, OOS −4.31 | −5.05 | No | Confirmed |
| MAXRET | IS −3.49, OOS −4.05 | +5.52 | No | Confirmed |
| RMOM1w | Weak IC | +1.86 | Yes | Priced risk |
| RMOM2w | IS IC, weak OOS | +1.05 | Yes | Suggestive |
| SMBC | Weak IC | +0.36 | Yes | Suggestive |
| NetRel | Weak IC | −0.01 | Yes | Suggestive |
| MispricingM | Composite | n/a | Yes (all 3 windows) | Composite |

**MispricingM** = equal-weight average of RMOM1w, RMOM2w, SMBC, NetRel. Selected because these four factors almost-stochastically dominate Bitcoin. Confirmed to dominate BTC in the IS window, full sample, and OOS window separately (ε₂ = 0.000 in all three).

### Stage 10 — Behavioral GX Search (production)

Searched 182 candidate long-short factor specifications (91 price-based features × 2 directions). Each candidate was added to the Stage-09 GX factor zoo and tested for |t| ≥ 2.0. 102 of 182 passed the uncorrected bar — correctly interpreted as exploratory mining, not reliable signal.

Multiple-testing discipline applied: only factors surviving **both** Bonferroni family-wise correction (|t| > 3.64 across all 182 tests) **and** Benjamini-Hochberg FDR correction (q < 0.001) are reported. Four factors survived both:

| Factor | GX t-stat | Economic story |
|---|---:|---|
| CRASH8 | +4.79 | Rebound from deeply crashed coins |
| BETA26 | +4.60 | High-beta risk compensation |
| SKEW52 | +3.44 | Lottery/skewness demand |
| NEWC | +3.43 | Newer-coin seasoning premium |

These are used only as a small capped Priced Tilt sleeve — their standalone single-window IS/OOS premia are weak, justifying the cap.

### Stage 12 — Factor Visualizations (production)

Per-factor visualization scripts producing figures used in the research report. Also contains `RESULTS.md` — plain-language summaries of all factor-level statistics.

Factors covered: VolC, MAXRET, MispricingM, CRASH8, BETA26, SKEW52, NEWC.

### Stage 13 — RCFP (Appendix A in report)

Regime-conditioned factor portfolio experiments. Tested two approaches:
- Plan A: economic classifier based on cross-sectional dispersion and BTC dominance changes
- Plan B: Hidden Markov Model (3 observable signals: market momentum, dispersion, BTC dominance — note: a 4th signal `netentropy_z` is mentioned in the RCFP_REPORT.md but was dropped from the code)

Results (OOS 79 weeks): Plan A Sharpe +0.19, Plan B Sharpe +0.36. Both positive vs BTC −0.33 and EW −0.51, but not enough standalone alpha.

**Lesson:** regime conditioning helps risk control but cannot be the entire strategy.

### Stage 14 — Regime Factor Strategy (Appendix B in report)

XGBoost regime classifier (RiskOff / Neutral / RiskOn states) using features: market momentum, cross-sectional dispersion, BTC dominance, realized volatility. Tested multiple portfolio optimization variants:

| Variant | OOS Sharpe |
|---|---:|
| Sharpe-optimized | +0.61 |
| Return-optimized | −0.52 |
| Balanced | −0.53 |
| Neural-network optimizer | −0.46 |

**Lesson:** model complexity did not improve OOS robustness. More complex → worse. The Sharpe-optimized variant (+0.61) carried forward as the baseline that Stage 15 improved upon.

### Stage 15 — Factor Ensemble Strategy (production, final)

The final submission strategy. Three sub-books combined with a causal rolling-performance allocator plus XGBoost regime sizing.

**Sub-books:**

| Book | Inputs | Economic role |
|---|---|---|
| MispricingM | RMOM1w, RMOM2w, SMBC, NetRel | Main alpha source |
| Core Rank | VolC, MAXRET | Statistically strongest weekly rankers |
| Priced Tilt | CRASH8, BETA26, TVLC, SKEW52, NEWC | Small capped risk-premia sleeve |

**Allocator:** causal (no look-ahead). Each week looks back at prior sub-book returns, estimates recent usefulness, blends with conservative base allocation, applies regime sizing from XGBoost probabilities.

**Ensemble variants:**

| Variant | MispricingM weight | Core Rank weight | Priced Tilt weight |
|---|---:|---:|---:|
| Sharpe Ensemble (SE) | 80.8% | 15.3% | 3.9% |
| Balanced Ensemble (BE) | 54.8% | 36.7% | 8.5% |
| Defensive Ensemble (DE) | 60.4% | 35.7% | 3.9% |

**Out-of-sample results (79 weeks, 2024-11-25 to 2026-05-25):**

| Strategy | Sharpe | Annual return | Volatility | Max drawdown |
|---|---:|---:|---:|---:|
| SE | +0.84 | +29.9% | 35.8% | −24.7% |
| BE | +0.68 | +18.8% | 27.6% | −18.3% |
| DE | +0.75 | +21.6% | 29.0% | −19.7% |
| MispricingM alone | +0.85 | +37.2% | 44.1% | −29.9% |
| Bitcoin | −0.33 | −12.3% | 37.7% | −46.7% |
| Equal-weight market | −0.51 | −34.4% | 67.2% | −68.3% |

**Ablation results:**

| Variant | OOS Sharpe | Note |
|---|---:|---|
| SE (headline) | +0.84 | Three-book ensemble |
| SE Priced-Tilt Off | +0.90 | Sleeve removed entirely |
| SE Priced-Tilt 5% cap | +0.87 | Cap cut from 18% to 5% |
| SE No Regime Tilt | +0.80 | Regime multipliers = 1.0 |
| MispricingM Only | +0.85 | Single factor |

Three honest findings from ablation:
1. Priced Tilt is a **net OOS drag** — removing it raises Sharpe
2. Regime conditioning adds a small measured benefit (+0.84 vs +0.80)
3. The strategy is **effectively a single-factor strategy** — MispricingM carries it; other books control vol and drawdown

The improvement over Stage 14 (Sharpe +0.61 → +0.84) came from **simplification**, not new signal.

---

## Reports (Stage 16)

| File | Contents |
|---|---|
| `Artemis_Track1_Research_Report.md` | Final competition report — full methodology, results, ablations, critical evaluation, bibliography |
| `Artemis_Track1_Research_Report.docx` | Rendered `.docx` build of the report |
| `AUDIT_AND_FINDINGS_REPORT.md` | Independent audit of Stages 09–15: 13 findings, all production-pipeline findings resolved |

Key audit findings and resolutions: multiple-testing corrections (Bonferroni + BH) added for behavioral search; supply drift clip bug fixed; ASD now split IS/OOS; regime-tilt priors documented with sensitivity grid; FMB deprecated in favour of proper week-by-week implementation; leakage-free forward-fill added; pipeline provenance documented.

---

## Presentation (Stage 17)

HTML presentation deck in `17_presentation_slides/`. Target audience: competition judges. Should cover: competition objective, data and universe, factor framework, strategy construction, key results, honest limitations.

---

## Statistical methods used

| Method | Where used | Purpose |
|---|---|---|
| Spearman IC with Newey-West t-stats | Stage 09 | Weekly ranking power test |
| Almost Stochastic Dominance (ASD/ASSD) | Stage 09 | Distributional test for fat-tailed crypto returns |
| Giglio-Xiu latent-factor pricing (week-by-week FMB) | Stage 09, 10 | Risk premium test controlling for hidden factors |
| Sparse PCA | Stage 09 | Latent common factor extraction |
| Benjamini-Hochberg FDR correction | Stage 10 | Multiple-testing correction for 182-candidate search |
| Bonferroni correction | Stage 10 | Family-wise error control |
| Hidden Markov Model | Stage 13 | Regime classification (appendix only) |
| XGBoost | Stages 14, 15 | Regime probability estimation |
| Causal rolling-performance allocator | Stage 15 | Look-ahead-free book allocation |
| Portfolio Sharpe optimization | Stage 15 | Ensemble weight derivation |

---

## Known limitations

- **OOS window is short** (79 weeks ≈ 1.5 years) — one holdout is not proof of production readiness
- **Single-factor dependency** — MispricingM carries the strategy; factor crowding risk is real
- **Selection in research process** — final strategy was designed after seeing what failed; IS/OOS splits and multiple-testing corrections partially address this but do not eliminate it
- **Transaction costs are simplified** — real slippage, borrow costs, and exchange fees could meaningfully reduce returns, especially for smaller assets
- **Regime model is heuristic** — XGBoost labels are useful for sizing, not ground truth
- **Universe construction risk** — if historical universe is not fully point-in-time, survivorship bias inflates results
