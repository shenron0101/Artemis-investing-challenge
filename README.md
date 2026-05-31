# Artemis Quant Competition — Track 1: Crypto Factor Rebalancing Strategy

A systematic, weekly-rebalanced long–short crypto factor portfolio over ~113
large-cap assets. The goal is cross-sectional ranking power, regime robustness,
turnover control, and economic interpretability — not single-asset prediction.

The final competition deliverable is **`Artemis_Track1_Research_Report.md`**
(and its `.docx` build). This README documents the pipeline and, in particular,
how factors flow from discovery to the final strategy — the trace the audit
(`AUDIT_AND_FINDINGS_REPORT.md`, Finding 12) found was undocumented.

## Production pipeline (Stages 09 → 10 → 12 → 15)

These four stages produce everything in the final report. Earlier stages
(01–08, in their folders) are data collection and prior research iterations;
Stages 13–14 are regime-experiment appendices.

| Stage | Folder | Produces | Consumed by |
|---|---|---|---|
| 09 | `09_nalfp_add/` | 5-year universe + reconstructed mcap panel, weekly returns, Sparse-PCA factors, **factor validation (IC / ASD / GX)**, MispricingM composite | 10, 12, 15 |
| 10 | `10_behavioral_gx/` | 182-candidate behavioral factor search + GX pricing → 4 selected priced-risk factors (CRASH8, BETA26, SKEW52, NEWC) | 12, 15 |
| 12 | `12_factor_viz/` | Per-factor visualizations + plain-language `RESULTS.md` (presentation layer over 09/10 numbers) | report figures |
| 15 | `15_factor_ensemble_strategy/` | Three-book ensemble (MispricingM / Core Rank / Priced Tilt), causal allocator, backtest, ablations | report |

Run order:

```bash
# Stage 09 — data + validation (03 fetches live Binance/CoinGecko/CoinMetrics)
python3 09_nalfp_add/03_reconstruct_mcap_panel.py
python3 09_nalfp_add/05_returns_and_reference.py
python3 09_nalfp_add/06_sparse_pca.py
python3 09_nalfp_add/09c_gx_pricing_full.py     # proper week-by-week FMB (NOT 09_gx_pricing.py)
python3 09_nalfp_add/08_factor_validation.py    # IC + ASD (IS/full/OOS) + MispricingM
# Stage 10 — behavioral search with FDR + IS/OOS robustness
python3 10_behavioral_gx/01_behavioral_gx_search.py
# Stage 15 — ensemble (imports Stage 14 run.py + reads its factor/regime panels)
python3 15_factor_ensemble_strategy/run.py
```

`09_gx_pricing.py` is **deprecated** (single-cross-section FMB shortcut with
wrong standard errors); all reported GX t-stats come from `09c_gx_pricing_full.py`.

## How factors are selected (the 182 → 4 trace)

1. **Stage 09** validates a panel of economic factors on three lenses: weekly
   ranking power (IC), distributional dominance over Bitcoin (ASD, reported for
   IS / full / OOS windows), and Giglio-Xiu risk pricing. The factors that
   ASD-dominate BTC form the **MispricingM** composite (RMOM1w, RMOM2w, SMBC,
   NetRel). VolC and MAXRET are the IC-robust **Core Rank** factors.
2. **Stage 10** searches 182 price-only behavioral specifications, pricing each
   with the Stage-09 GX engine. 102 clear an uncorrected |t| ≥ 2.0 bar — read as
   exploratory mining. The four carried forward (CRASH8, BETA26, SKEW52, NEWC)
   survive a **Bonferroni** correction (|t| > 3.64) and **Benjamini-Hochberg**
   FDR (q < 0.001) across all 182 tests, and are re-priced on separate IS/OOS
   windows. They are used only as a small **capped Priced-Tilt sleeve**, never as
   core alpha, because their standalone single-window premia are weak.
3. **Stage 15** assigns each factor group to a sub-book and allocates between the
   books with a causal rolling-performance rule plus regime sizing.

## Audit remediation

The findings raised in `AUDIT_AND_FINDINGS_REPORT.md` for Stages 09/10/12/15 are
resolved in code and in the stage `RESULTS.md` files; a per-finding summary is in
**Appendix D** of the final report. Highlights: multiple-testing corrections
(Findings 1–2), supply-clip fix (3), IS/OOS ASD split (4), regime-tilt
documentation + sensitivity grid (5), Priced-Tilt ablation showing it is a net OOS
drag (6), FMB deprecation (8), leakage-free fill (9), and this pipeline doc (12).

## Key result

Out-of-sample (final 79 weeks, a bull→bear transition) the Sharpe Ensemble holds
+0.84 Sharpe / +29.9% annualized while Bitcoin (−0.33) and the equal-weight market
(−0.51) both lose money. Ablations show the priced-risk sleeve is a net drag
(removing it lifts OOS Sharpe to +0.90) and the ensemble is effectively a
single-factor (MispricingM) strategy — both stated openly in the report.
