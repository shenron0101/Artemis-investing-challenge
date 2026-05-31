# Audit & Findings Report: Artemis Track 1 Research Project (Stages 09–15)

---

## 1. Executive Summary

This audit covers the end-to-end pipeline from Stage 09 (NALFP additions, universe curation, factor validation, GX pricing) through Stage 10 (behavioral factor search), Stage 12 (factor visualization), Stage 13 (regime-conditioned factor portfolios), Stage 14 (XGBoost regime-aware strategy), and Stage 15 (factor ensemble strategy), culminating in the synthesis document `Artemis_Track1_Research_Report.md`.

**Overall Assessment:** The project is methodologically ambitious, self-critical in its written narrative, and numerically consistent — every metric in the final report has been verified against the underlying code and data artifacts within rounding tolerance. The three-book ensemble architecture (MispricingM, Core Rank, Priced Tilt) is economically motivated and the OOS outperformance over BTC and the equal-weight market during a drawdown period is a genuine result. However, the work carries meaningful risks from: (1) a massive uncontrolled multiple-testing problem in Stage 10; (2) hardcoded priors that were never independently validated; (3) a very short OOS window (79 weeks ≈ 1.5 years); and (4) a single-factor dependency — MispricingM carries the ensemble, and the Priced Tilt sub-book is catastrophically bad OOS. The project should be viewed as a disciplined research prototype, not a production-ready strategy.

---

## 2. Macro-Consistency Matrix

| Stage -> Stage | Pipeline Link | Status |
|---|---|---|
| 09 → 10 | Stage 10 imports `gx5y_full_factor_zoo`, `price_mcap_panel_weekly`, `returns_weekly` from Stage 09 artifacts and dynamically loads Stage 09's GX pricing engine | **Verified Consistent** |
| 09 → 12 | Stage 12 reads `factor_validation_stats.parquet`, `price_mcap_panel_weekly`, `returns_weekly`, `universe_manifest.json` from Stage 09 | **Verified Consistent** |
| 09 → 13 | Stage 13 reads `price_mcap_panel_weekly`, `returns_weekly`, `fundamentals_weekly`, `network_panel` from Stages 08/09 | **Verified Consistent** |
| 13 → 14 | Stage 14 does not directly depend on Stage 13 outputs; it rebuilds the factor pipeline from Stage 09 data | **Verified Consistent** |
| 14 → 15 | Stage 15 dynamically imports `run.py` from Stage 14 and reads `factor_panel.parquet` and `regime_panel.parquet` from Stage 14 artifacts | **Verified Consistent** |
| 10 → 12 | Visualization scripts for CRASH8, BETA26, SKEW52, NEWC use Stage 10's factor definitions and GX pricing results | **Verified Consistent** |
| 12 → Report | All factor-level metrics (IC t-stats, GX t-stats, ASD epsilons, Sharpe, returns) in the report match `RESULTS.md` and viz reports within rounding | **Verified Consistent** |
| 13 → Report | Appendix A Plan A (Sharpe +0.19, Ann +2.6%) and Plan B (Sharpe +0.36, Ann +4.6%) match `a_metrics.json` and `b_metrics.json` | **Verified Consistent** |
| 14 → Report | Appendix B Sharpe-optimized (OOS Sharpe +0.61, Ann +26.8%) and other variants match `metrics.json` | **Verified Consistent** |
| 15 → Report | Final ensemble tables (SE OOS Sharpe +0.84, Ann +29.9%, etc.) match `metrics.json` within rounding | **Verified Consistent** |
| 09 → 09 (internal) | `09_gx_pricing.py` uses a single-cross-section FMB shortcut; `09c_gx_pricing_full.py` corrects this with proper week-by-week FMB | **Discrepancy Detected** (internal, resolved by 09c) |
| 13 report vs 13 code | `RCFP_REPORT.md` lists 4 HMM observation signals but code uses only 3 (netentropy_z dropped) | **Discrepancy Detected** |

---

## 3. Deep-Dive Findings

### Finding 1: Uncontrolled Multiple Testing in Behavioral Factor Search

- **Location:** `10_behavioral_gx/01_behavioral_gx_search.py` (lines 35–436)
- **Severity:** Critical
- **Description:** Stage 10 tests 182 candidate long-short factor specifications (91 features × 2 directions) by adding each one-by-one to the Stage-09 GX factor zoo and checking whether the candidate's GX pricing t-statistic exceeds |2.0|. Of the 182 candidates, 102 pass this bar — a 56% hit rate. Under a proper Bonferroni correction at the 5% significance level, the threshold would need to be approximately |t| ≈ 3.35 (assuming two-sided tests). The four "behavioral" factors (NEWC, SKEW52, CRASH8, BETA26) are then hand-picked from these 102 hits on lines 433–436 with no formal selection criterion. This is a specification search by construction.
- **Impact:** The reported GX t-statistics for the four selected factors (+4.79, +4.60, +3.44, +3.43) are inflated by selection bias. Even though these t-values are high, the false discovery rate among 102 hits at |t|≥2.0 is likely substantial. The strongest factors (VolC at t=−5.05, MAXRET at t=+5.52) come from the Stage-09 validation pipeline that used far fewer specifications, which makes their evidence stronger by comparison.
- **Recommended Remediation:** (1) Apply a Benjamini-Hochberg or Bonferroni correction to the 182 tests and report the adjusted significance levels. (2) Replace the hand-picked shortlist with an objective pre-specified rule (e.g., "the top-4 by t-stat after FDR correction that pass a correlation threshold of 0.7 with existing factors"). (3) Reserve a genuine holdout period (e.g., the last 79 weeks) for the behavioral factor search itself, not just the final strategy. (4) Raise the near-duplicate threshold from 0.995 to 0.70 or 0.80 to filter more aggressively.

### Finding 2: No Out-of-Sample Holdout for Behavioral Factor Discovery

- **Location:** `10_behavioral_gx/01_behavioral_gx_search.py`, lines 75, 35–36
- **Severity:** Major
- **Description:** The variable `OOS_END = "2026-05-25"` is labeled "out-of-sample end" but is used as the terminal date of the **full estimation sample** in `load_inputs()` (line 75). There is no out-of-sample holdout within the behavioral factor search itself — the entire 2021-05-10 to 2026-05-25 window is used for both candidate evaluation and reporting. The IS/OOS split exists only in Stages 13–15, after factor selection has already occurred.
- **Impact:** This compounds the multiple-testing problem (Finding 1). Factors that appear significant in the full window may not hold up in an unseen period. The OOS validation in Stages 14–15 partially mitigates this, but the factor selection was already informed by the full sample.
- **Recommended Remediation:** Re-run the behavioral search using only the IS period (2021-05-10 to 2024-11-11) for candidate evaluation, then verify the selected factors on the OOS period (2024-11-18 onward). This is the most important single remediation for improving the credibility of the behavioral factor evidence.

### Finding 3: Supply Backfill Look-Ahead Bug

- **Location:** `09_nalfp_add/03_reconstruct_mcap_panel.py`, function `supply_backfill`
- **Severity:** Major
- **Description:** The Tier-3 supply reconstruction fits a log-linear growth model using the **last 365 days of CoinGecko mcap/price data** and then extrapolates backward for up to 5 years. This means the deep-history supply estimates are conditioned on 2025–2026 information. More critically, the drift clip has an asymmetric bug: `b = np.clip(b, -0.03/30.0, 0.05)`. The upper bound clips per-day drift to 0.05 (5% per day, or ~1500% annualized), while the lower bound clips per-day drift to −0.03/30 ≈ −0.001 (−3% per year). The intended upper bound was likely 0.05/30 ≈ 0.0017 (5% per year), not 0.05 (5% per day).
- **Impact:** The Tier-3 supply series (used for ~42 of 61 trading coins) may be unrealistically steep in early years, affecting market-cap-dependent factors like SMBC. However, since the factor uses log-market-cap ranks rather than levels, and the ranking is weekly cross-sectional (within the same time period), the practical impact may be limited.
- **Recommended Remediation:** (1) Fix the drift clip to `np.clip(b, -0.03/365.0, 0.05/365.0)` or equivalent per-day values. (2) Consider using a walk-forward supply estimate (e.g., expanding window rather than backward extrapolation). (3) Add a unit test verifying that the reconstructed supply drift stays within reasonable annual bounds.

### Finding 4: ASD Test Computed on Full Sample, Not IS/OOS

- **Location:** `09_nalfp_add/08_factor_validation.py`, ASD computation section
- **Severity:** Major
- **Description:** The almost stochastic dominance (ASD) test is computed on the full sample (2021–2026), not separately for IS and OOS periods. This means the factor selection for MispricingM — which explicitly uses ASD dominance as one of its criteria — is informed by future data.
- **Impact:** MispricingM's factor composition (RMOM1w, RMOM2w, SMBC, NetRel) was partly determined by ASD dominance, which used the full sample. This is a form of look-ahead in the factor selection step.
- **Recommended Remediation:** Re-run the ASD test separately for IS and OOS periods. Report both sets of results. If different factors pass ASD in IS vs. OOS, discuss the implications for the composite's robustness.

### Finding 5: Hardcoded Activation Matrices Without Validation

- **Location:** `14_regime_factor_strategy/run.py` lines 110–125 (`ACTIVATION` dict); `15_factor_ensemble_strategy/run.py` `regime_tilt()` function
- **Severity:** Major
- **Description:** The factor-regime activation matrices in Stage 14 (14 factors × 3 regimes) and the regime-tilt coefficients in Stage 15 (3 books × 3 regimes) are completely hardcoded economic priors. For example, BETA26 gets activation 1.65 in RiskOn and 0.15 in RiskOff; the priced_tilt allocation scales with `(0.55 + 0.35 * p_RiskOn)` in Stage 15. None of these values have been cross-validated or sensitivity-tested.
- **Impact:** These priors directly control how much capital flows to each factor each week. If any prior is substantially wrong (e.g., if TVLC should not be amplified in RiskOff), the strategy is systematically misallocating. The OOS results for the priced_tilt sub-book (Sharpe −0.43) suggest the TVLC/BETA26/SKEW52 activation priors may indeed be harming performance.
- **Recommended Remediation:** (1) Perform a grid search or Bayesian optimization over activation values using only IS data, validating on OOS. (2) At minimum, run a sensitivity analysis perturbing each activation value by ±0.25 and report how much the OOS Sharpe changes. (3) Report the "neutral" (all activations = 1.0, no regime tilt) portfolio as a baseline.

### Finding 6: Priced Tilt Sub-Book Is Catastrophically Bad OOS

- **Location:** `15_factor_ensemble_strategy/RESULTS.md`; Report Section "Backtest Results" line 241
- **Severity:** Major
- **Description:** The Priced Tilt sub-book (CRASH8, BETA26, TVLC, SKEW52, NEWC) produces an OOS Sharpe of −0.43 with an annualized return of −13.7% and max drawdown of −32.6%. This is worse than Bitcoin (−0.33 Sharpe) and worse than the equal-weight market (−0.51 Sharpe, but with much higher vol). The report acknowledges this in the text ("the Priced Tilt sub-book is economically interesting but weak as a standalone weekly strategy") but does not flag the severity: the priced-risk factors are not merely weak — they are actively destructive OOS.
- **Impact:** The 18% cap on priced_tilt allocation (hardcoded in Stage 15, line 235) limits the damage, but the strategy is still dragging. If mispricing were to weaken during a different OOS period, the ensemble's performance could deteriorate materially because there is no robust backup alpha source.
- **Recommended Remediation:** (1) Consider removing the Priced Tilt book entirely and redistributing its allocation to Core Rank (the second-best book at OOS Sharpe +0.11). (2) Alternatively, cap Priced Tilt at 5% instead of 18%. (3) Report a "Pure Mispricing + Core Rank" variant to show how much the Priced Tilt contributes (or destroys).

### Finding 7: Documentation Inconsistency — HMM Signal Count

- **Location:** `13_rcfp/RCFP_REPORT.md` line 13 vs `13_rcfp/b01_regime_hmm.py`
- **Severity:** Minor
- **Description:** The report states the HMM observation vector is `[CSD_z, ΔBTCdom_z, netentropy_z, mktmom_z]` (4 signals), but the actual code uses only 3 signals (`csd_z`, `dbtc_z`, `mktmom_z`). `netentropy_z` was dropped because the network panel has only ~52 weeks of data, leaving insurmountable data limitations after 52-week rolling z-scoring and 1-week lag. The report text was not updated after this change.
- **Impact:** Readers of the report will believe a 4-signal HMM was used, which overstates the model's input dimensionality. This is a documentation error, not a code error.
- **Recommended Remediation:** Update `RCFP_REPORT.md` line 13 to reflect the actual 3-signal observation vector, and add a footnote explaining why `netentropy_z` was dropped.

### Finding 8: Stage 09 FMB Shortcut in 09_gx_pricing.py

- **Location:** `09_nalfp_add/09_gx_pricing.py`, function `fama_macbeth_lambda`
- **Severity:** Minor (resolved by 09c)
- **Description:** The initial GX pricing script uses a single cross-sectional regression (average returns on betas) rather than the proper week-by-week Fama-MacBeth procedure. This is corrected in `09c_gx_pricing_full.py`, which implements proper week-by-week FMB with Newey-West standard errors.
- **Impact:** None on the final results, since the graded factor system and all reported t-statistics come from `09c_gx_pricing_full.py`. However, if anyone uses `09_gx_pricing.py` standalone, they will get incorrect standard errors.
- **Recommended Remediation:** Add a deprecation warning to `09_gx_pricing.py` directing users to `09c_gx_pricing_full.py`.

### Finding 9: fillna(mean) Introduces Mild Look-Ahead

- **Location:** `09_nalfp_add/09_gx_pricing.py` and `09_nalfp_add/09c_gx_pricing_full.py`
- **Severity:** Minor
- **Description:** Factor series with missing observations are imputed using `fillna(column.mean())` computed over the entire estimation window. This uses future data within the window to fill past gaps. For factors with sparse data (TVLC, FunC with ~37 assets), this could meaningfully distort the factor's mean and variance.
- **Impact:** The effect on pricing t-statistics is likely small because the mean fillna primarily shifts the level without changing the cross-sectional ranking. However, for TVLC and FunC where coverage is sparse, the effect could be non-trivial.
- **Recommended Remediation:** Use forward-fill (`fillna(method='ffill')`) or a rolling mean instead. Alternatively, drop observations with missing factor data rather than imputing.

### Finding 10: XGBoost Regime Classifier — Modest Out-of-Sample Accuracy

- **Location:** `14_regime_factor_strategy/run.py`, XGBoost configuration; `14_regime_factor_strategy/artifacts/manifests/metrics.json`
- **Severity:** Minor
- **Description:** The XGBoost regime classifier achieves 74.9% accuracy on training data but only 58.2% on test data (macro F1 = 0.591) for a 3-class problem. Random guessing would yield ~33%, so the model is better than random but not dramatically so. The classifier's regime target is constructed from contemporaneous market variables via heuristic tertile thresholds.
- **Impact:** The regime probabilities are used for risk sizing, not direct alpha generation. Modest accuracy is therefore acceptable — the model correctly shifts exposures on average. However, the gap between train and test accuracy (75% vs 58%) suggests some overfitting.
- **Recommended Remediation:** (1) Consider a simpler regime model (e.g., rolling z-score thresholds like Plan A in Stage 13, which achieved similar OOS performance with no ML). (2) Reduce XGBoost depth from 2 to 1, or increase regularization. (3) Evaluate whether regime conditioning adds value beyond a fixed-mix benchmark by running a "no regime" variant.

### Finding 11: Stage 14 Appendix B Numbers — Consistent but Troubling

- **Location:** `Artemis_Track1_Research_Report.md` lines 289–294
- **Severity:** Optimization Opportunity
- **Description:** The report's Appendix B presents Stage 14 results showing that only the Sharpe-optimized variant is positive OOS (+0.61 Sharpe), while the Return-optimized (−0.52), Balanced (−0.53), and Neural Network (−0.46) variants all lose money OOS. These numbers are verified as correct against `metrics.json`. The report uses this as evidence that "more model complexity did not improve out-of-sample robustness," which is a fair and honest interpretation. However, the IS→OOS Sharpe decay ratios are dramatic: 42% for Sharpe-optimized, 47% for Balanced, and 78% for the Neural Network (from 2.06 to −0.46). This suggests the grid search introduced meaningful IS optimization even in the "best" variant.
- **Impact:** The report's narrative is honest, but a reader could overestimate the robustness of the final strategy because it passes through Stage 14 (which has poor OOS results) into Stage 15 (which has better OOS results). The improvement from Stage 14 to 15 is primarily due to removing the multi-sleeve complexity and focusing on MispricingM.
- **Recommended Remediation:** Add a line in the report explicitly comparing the OOS-only Sharpe of Stage 14's best variant (+0.61) vs. Stage 15's Sharpe Ensemble (+0.84) and noting that the improvement comes from simplification, not from additional signal discovery.

### Finding 12: Missing Folder 11 and Implicit Pipeline Gaps

- **Location:** Directory structure
- **Severity:** Minor
- **Description:** The folder sequence jumps from `10_behavioral_gx` to `12_factor_viz` with no `11_*` folder. This creates a workflow gap: the behavioral factor search results (Stage 10) feed directly into the visualization stage (Stage 12) and then into the regime strategies (Stages 13–15). There is no intermediate integration/validation stage that documents how the Stage 10 factors were selected for inclusion in the final strategy.
- **Impact:** The pipeline is continuous in terms of data flow, but the documentation gap makes it harder to trace how the four behavioral factors transitioned from "182 candidates" to "4 selected for the final strategy."
- **Recommended Remediation:** Add a README or GOALS.md in the root directory explicitly documenting the Stage 10 → 12 → 14 pipeline and the factor selection rationale.

### Finding 13: `winsorization` Comment Without Implementation

- **Location:** `09_nalfp_add/05_returns_and_reference.py`
- **Severity:** Minor
- **Description:** The script contains a comment about "winsorize per-week cross-section at +/-3 MAD" but the actual code does not apply any winsorization. Returns are computed as raw `px.pct_change()` without outlier treatment.
- **Impact:** Extreme weekly returns (e.g., for micro-cap coins or during flash crashes) could dominate factor sorts and IC calculations. VolC and MAXRET specifically target extreme-return coins, so this is somewhat by design, but it could inflate IC estimates for other factors.
- **Recommended Remediation:** Either implement the ±3 MAD winsorization or remove the misleading comment. If no winsorization is intended, document why raw returns are preferred.

---

## 4. Assumption & Robustness Evaluation

### 4.1 Assumptions That Hold Strong

| Assumption | Justification |
|---|---|
| Weekly rebalancing is appropriate for cross-sectional crypto factors | Well-established in academic literature; daily noise is reduced, and most factors have IC horizons of 1–4 weeks |
| Forward returns `shift(-1)` correctly avoid look-ahead | Confirmed in Stages 09, 10, 14, and 15 — all use `.shift(-1)` for signal prediction |
| Value-weighted lagged market cap for RC portfolio | Standard Fama-MacBeth practice; .shift(1) is applied |
| Sparse PCA (K=4, α=1.2) produces interpretable hidden factors | Cumulative adjusted EVR ~70%; components are economically interpretable (market, size, momentum) |
| MispricingM composite of individually weak but uncorrelated signals | RMOM1w, RMOM2w, SMBC, NetRel have low inter-factor correlations (0.03–0.20) — the diversification logic is sound |
| Minimum cross-section size of 10–14 coins per week | Reasonable floor for meaningful long/short sorts |
| Transaction cost assumption of 10 bps one-way | Conservative for liquid pairs on major exchanges, though aggressive for small-cap names |
| The final strategy is causal (no future data in signal construction) | Confirmed: rolling window IC, lagged regime probabilities, and walk-forward allocator |

### 4.2 Assumptions That Require More Conservative Framing

| Assumption | Concern | Recommended Framing |
|---|---|---|
| The OOS period (79 weeks) is sufficient for strategy validation | 79 weekly observations ≈ 1.5 years is a very short window — it contains only one market regime transition (bull-to-bear). A single drawdown period inflates the relative performance of low-volatility and defensive factors. | State clearly: "The OOS results are encouraging but should be treated as a single-regime validation. A longer backtest spanning multiple crypto cycles is needed before drawdown conclusions are generalized." |
| The 5-year backbone of 32 coins is representative | A 32-coin survivor set (requiring 5 years of continuous data) excludes all coins that listed, failed, or were delisted between 2017 and 2026. The project acknowledges this but could go further. | Add a quantitative estimate: "If the 81 coins that didn't survive 5 years had systematically different returns, the backbone Sharpe ratios could be overstated by X%." |
| Factor invariance across market regimes | The activation matrices assume factor efficacy changes predictably with regime (e.g., BETA26 is strong in RiskOn, zero in RiskOff). But priced_tilt is catastrophically bad OOS, suggesting these priors are wrong for at least some factors. | Add a sensitivity analysis: "If all activations are set to 1.0 (no regime tilt), the Sharpe Ensemble OOS Sharpe changes from 0.84 to Y." |
| The MispricingM composite will remain effective | MispricingM (OOS Sharpe 0.85) drives the entire ensemble. If any component weakens — especially RMOM1w, which has weak standalone IC (OOS t = −0.27) — the composite could degrade. | Add a "what if MispricingM fails" stress test showing the ensemble performance with MispricingM set to zero allocation. |
| Cryptocurrency market structure is stationary | The 79-week OOS period saw a transition from a bull market (2024 Q4) to a bear market (2025–2026). Strategy performance is heavily regime-dependent. | Report the IS Sharpe decay: 1.36 → 0.84 for SE (38% decay). Note that a 38% decay is actually better than typical equity factor strategies, but still implies meaningful overfitting. |

### 4.3 Unrealistic or Unjustified Assumptions

| Assumption | Why It's Unrealistic | Impact |
|---|---|---|
| The 182-candidate behavioral search is not data-mining | 56% of candidates pass |t|≥2.0, far above the ~5% null rate. Without Bonferroni/BH correction, the false discovery rate is uncontrolled. The hand-picked shortlist of 4 factors has no pre-specified selection rule. | The behavioral factor evidence (CRASH8, BETA26, SKEW52, NEWC) is overstated. T-statistics should be deflated by a multiple-testing correction. |
| The supply backfill growth rate clamp of 0.05/day is intentional | The clip `np.clip(b, -0.03/30, 0.05)` allows 5% per day (1500% annualized) supply growth in backward extrapolation. This is almost certainly a bug — the intended bound is likely 0.05/30 ≈ 0.0017/day (5% annualized). | Tier-3 market cap reconstruction for ~42 coins may have unrealistic early-period supply growth, potentially affecting SMBC (size) rankings in early years. |
| 10 bps one-way covers all execution costs | No slippage, market impact, or borrow-cost model. For the top-25% long/short portfolio with some low-liquidity crypto names, real execution costs could be 2–5× higher. | Realistic costs of 20–50 bps round-trip could reduce the Sharpe Ensemble's net Sharpe from 0.84 to approximately 0.65–0.75. |

---

## 5. Polishing & Optimization Recommendations

### 5.1 Code Quality

1. **Fix the supply backfill bug** in `09_nalfp_add/03_reconstruct_mcap_panel.py`: Change `np.clip(b, -0.03/30.0, 0.05)` to `np.clip(b, -0.03/365.0, 0.05/365.0)` or equivalent annual bounds.
2. **Deprecate `09_gx_pricing.py`**: Add a comment at the top directing users to `09c_gx_pricing_full.py` for correct FMB implementation.
3. **Update `RCFP_REPORT.md` line 13**: Change the 4-signal HMM description to the actual 3-signal vector.
4. **Remove the misleading winsorization comment** from `05_returns_and_reference.py` or implement it.
5. **Add `.env` validation**: Several scripts fail silently if API keys are missing. Add early checks for `ARTEMIS_KEY`, `CG_KEY`, and `FRED_API_KEY`.

### 5.2 Reporting

6. **Add a multiple-testing adjustment table**: In the report or an appendix, show the behavioral factor t-statistics with Bonferroni and BH-adjusted p-values.
7. **Report a "no regime" baseline**: Show what happens when the XGBoost regime model is replaced with constant 1/3 probabilities (or no regime tilt at all). This isolates the value added by regime conditioning.
8. **Add a Priced Tilt sensitivity analysis**: Show the ensemble OOS performance with the Priced Tilt allocation set to zero. If performance improves, remove it.
9. **Report the IS→OOS Sharpe decay** explicitly: SE 1.36→0.84 (38% decay), BE 1.28→0.68 (47%), DE 1.31→0.75 (43%). Compare this to the BTC benchmark's decay (1.14→−0.33, which is infinite since BTC goes negative).
10. **Add a "single-factor dependency" stress test**: What happens if RMOM1w (the dominant MispricingM component with OOS IC t = −0.27) fails? Show ensemble performance with MispricingM set to 50% or 0% allocation.

### 5.3 Statistical Rigor

11. **Apply BH FDR correction** to the 182 behavioral candidates: Report the FDR-adjusted q-values for the four selected factors.
12. **Run a bootstrap or sub-sampling robustness check**: Randomly drop 10% of weeks, re-run the full Stage 15 pipeline, and show the distribution of OOS Sharpe across 100 bootstrap samples.
13. **Add a turnover analysis**: Report weekly portfolio turnover (one-sided) and the effective transaction cost under different assumptions (10 bps, 25 bps, 50 bps one-way).
14. **Separate ASD into IS and OOS**: Re-run the ASD test on both halves and report which factors maintain dominance in both periods.

### 5.4 Documentation

15. **Create a pipeline README**: Add a root-level README or GOALS.md documenting the full stage sequence (01→15), which stages produce which artifacts, and the factor selection rationale at each decision point.
16. **Document the activation matrix derivation**: Add comments or a companion document explaining the economic reasoning behind each value in the `ACTIVATION` dict. Currently these are unattributed magic numbers.
17. **Version the `metrics.json` files**: Include a `pipeline_version` or `timestamp` field in each manifest to enable reproducibility.

### 5.5 Performance Optimization

18. **Pre-filter low-IC factors from Priced Tilt**: The OOS data shows CRASH8, BETA26, TVLC, SKEW52, and NEWC all have negative or near-zero weekly IC. Consider replacing the Priced Tilt with a simple volatility-scaled bond or cash position during risk-off periods.
19. **Reduce ensemble complexity**: The 92%/8%/0% base allocation of the Sharpe Ensemble already reflects near-singular dependence on MispricingM. Officially acknowledge this by presenting a "MispricingM Only" baseline alongside the ensemble.
20. **Simplify the regime model**: Stage 13's Plan A (economic classifier with 2 signals) achieved OOS Sharpe +0.19, while Plan B (HMM) achieved +0.36. Stage 14's XGBoost achieved test accuracy of only 58%. Consider whether a simpler threshold model (2-state: risk-on/risk-off based on BTC drawdown) would achieve similar regime detection with less overfitting risk.

---

## 6. Summary Verdict

| Dimension | Rating | Justification |
|---|---|---|
| Numerical Consistency | **Excellent** | All reported metrics verified against source code and data within rounding tolerance |
| Pipeline Continuity | **Good** | Data flows correctly across all stages; one documentation inconsistency (HMM signal count); one internal redundancy (09 vs 09c FMB) |
| Statistical Rigor | **Fair** | Major concern: 182-candidate behavioral search with no multiple-testing correction; ASD computed on full sample; fillna(mean) introduces mild look-ahead |
| Assumption Robustness | **Fair** | Most assumptions are well-justified, but priced_tilt's catastrophic OOS performance, the behavioral search's data-mining risk, and the 79-week single-regime OOS period are significant concerns |
| Honesty of Narrative | **Good** | The report is commendably self-critical (79-week limitation, selection risk, simplified costs, survivorship bias) — the findings in this audit largely reinforce what the authors already acknowledge |
| Production Readiness | **Not Ready** | The strategy depends on a single alpha source (MispricingM), has unvalidated activation priors, uses a simplified cost model, and has been tested on only one OOS regime. Additional walk-forward validation across multiple market cycles and a realistic execution framework are needed. |

**Overall Health: Conditional Pass** — The project demonstrates strong research discipline and honest reporting. The key conditional is that the behavioral factor evidence is inflated by multiple testing, and the final strategy's success is concentrated in one composite signal during a single bearish OOS period. Before deployment, the team should: (1) apply FDR correction to the behavioral factor search, (2) run a bootstrap/sub-sampling robustness analysis, (3) stress-test with MispricingM disabled, (4) implement realistic transaction costs, and (5) extend the OOS validation with walk-forward testing if more data becomes available.