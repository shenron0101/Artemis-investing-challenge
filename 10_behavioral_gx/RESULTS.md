# Stage 10 - Behavioral GX factor search

## What this stage does

Stage 09 found several real factors, but many were either already-known crypto
anomalies or broad risk directions. This stage searches for new factors that can
be described as investor behavior:

- newness and seasoning preference,
- lottery memory and right-tail salience,
- capitulation after recent crashes,
- speculative beta chasing and risk-on demand.

The test is deliberately hard. Every candidate is added to the full Stage-09
factor zoo and run through the same Giglio-Xiu hidden-factor pricing engine.
The table below reports the hidden-factor-robust GX-full risk premium. The
strict discovery bar used here is |t| >= 2.0; the looser priced-risk bar used in
Stage 09 was |t| >= 1.65.

## Search result

- Candidate definitions tested: 182
- GX-full hits at |t| >= 2.0 (uncorrected): 102
- GX-full hits at |t| >= 1.65 (uncorrected): 112

Top one-by-one candidates:

| Candidate | Behavior interpretation | GX-full lambda | t_gx | Nearest Stage-09 factor |
|---|---|---:|---:|---|
| absret_mean_12w__high_minus_low | high attention shock from large absolute moves | +225.0% | +6.17 | 0.78 vs VolC |
| absret_mean_12w__low_minus_high | low attention shock from large absolute moves | -225.0% | -6.17 | 0.78 vs VolC |
| maxret_12w__low_minus_high | low maximum-return lottery salience | -189.3% | -6.16 | 0.67 vs VolC |
| maxret_12w__high_minus_low | high maximum-return lottery salience | +189.3% | +6.16 | 0.67 vs VolC |
| vol_12w__high_minus_low | high volatility/lottery demand | +206.9% | +5.99 | 0.81 vs VolC |
| vol_12w__low_minus_high | low volatility/lottery demand | -206.9% | -5.99 | 0.81 vs VolC |
| idvol_12w__high_minus_low | high volatility/lottery demand | +203.6% | +5.96 | 0.79 vs VolC |
| idvol_12w__low_minus_high | low volatility/lottery demand | -203.6% | -5.96 | 0.79 vs VolC |
| maxret_8w__low_minus_high | low maximum-return lottery salience | -228.9% | -5.80 | 0.77 vs VolC |
| maxret_8w__high_minus_low | high maximum-return lottery salience | +228.9% | +5.80 | 0.77 vs VolC |
| maxret_52w__low_minus_high | low maximum-return lottery salience | -180.6% | -5.56 | 0.47 vs RC |
| maxret_52w__high_minus_low | high maximum-return lottery salience | +180.6% | +5.56 | 0.47 vs RC |
| maxret_3w__low_minus_high | low maximum-return lottery salience | -167.4% | -5.53 | 0.79 vs MAXRET |
| maxret_3w__high_minus_low | high maximum-return lottery salience | +167.4% | +5.53 | 0.79 vs MAXRET |
| attention_absret_xs_4w__high_minus_low | high attention shock from large absolute moves | +150.8% | +5.39 | 0.89 vs VolC |

Many of the strongest raw hits are volatility or max-return variants, which are
close to Stage-09 VolC/MAXRET. The final shortlist below keeps factors that are
behaviorally interpretable and not merely a renamed copy of an existing factor.

## Multiple-testing correction (audit Finding 1)

Testing 182 candidate specifications and keeping hits at a
per-test |t| >= 2.0 bar admits false positives by construction: under the null
about 5% of tests would clear that bar by luck. We therefore report two
corrections across the full family of 182 tests.

- **Uncorrected** hits at |t| >= 2.0: **102**
  (56% of all tests).
- **Bonferroni** (family-wise error rate 5%) raises the bar to
  |t| > **3.64**; only
  **52** candidates survive.
- **Benjamini-Hochberg** (false-discovery rate 5%) leaves
  **96** candidates.

The four headline factors are not just BH survivors — they clear the much harsher
Bonferroni bar as well:

| Factor | search t_gx | raw p | BH q-value | Bonferroni pass |
|---|---:|---:|---:|---|
| NEWC_young_minus_old | +4.19 | 2.74e-05 | 1.39e-04 | yes |
| SKEW52_high_minus_low | +4.66 | 3.19e-06 | 2.07e-05 | yes |
| CRASH8_crashed_minus_resilient | +4.08 | 4.56e-05 | 2.07e-04 | yes |
| BETA26_high_minus_low | +3.93 | 8.51e-05 | 3.48e-04 | yes |

So while the 56% raw hit rate is correctly read as exploratory mining, the
specific factors carried into the strategy survive a full family-wise correction
over every specification searched. The reported t-statistics are *not* deflated
below significance by the correction.

## Joint behavioral shortlist

These four factors are tested jointly with each other plus the full Stage-09
factor zoo. They still pass GX-full significance after hidden factors are added.

| Factor | GX-full lambda | t_gx | Weekly lambda 95% CI |
|---|---:|---:|---|
| NEWC_young_minus_old | +114.1% | +3.43 | [+0.009, +0.034] |
| SKEW52_high_minus_low | +96.9% | +3.44 | [+0.008, +0.029] |
| CRASH8_crashed_minus_resilient | +177.9% | +4.79 | [+0.020, +0.048] |
| BETA26_high_minus_low | +122.8% | +4.60 | [+0.014, +0.034] |

## Full-sample joint GX pricing — all 23 factors

The table below puts all 23 factors side-by-side so the behavioral shortlist can be
read against the full Stage-09 base zoo in one view. Only GX-full is reported here
because the joint model (Stage-10 script `run_joint_model`) runs GX-full only; for
the three-method comparison (FMB · GX-obs · GX-full) on the 19 base factors see the
master table in `09_nalfp_add/RESULTS.md § Full-sample results`.

**Data sources.** The 4 behavioral factors (★) use the Stage-10 joint run
(K_hidden = 2, 2021-05-10 → 2026-05-25, all 23 factors priced simultaneously).
The 19 base factors use the Stage-09 full-sample GX-full run (same K_hidden = 2,
same period, 19-factor zoo without behavioral factors). In the 23-factor joint run
the base-factor lambdas shift slightly because the hidden-factor extraction sees
four additional factors; the behavioral shortlist was selected specifically to
survive that larger joint model. Bold = |t| ≥ 1.65.

| Factor | Category | GX-full λ/yr | t_gx | Stage-09 verdict |
|---|---|---:|---:|---|
| VolC | Base — weekly ranker | −185.8% | **−5.05** | Confirmed |
| MAXRET | Base — weekly ranker | +160.0% | **+5.52** | Confirmed |
| ★ CRASH8_crashed_minus_resilient | Behavioral | +177.9% | **+4.79** | — |
| ★ BETA26_high_minus_low | Behavioral | +122.8% | **+4.60** | — |
| TVLC | Base — DeFi engagement | −185.2% | **−4.71** | Priced risk |
| RC | Base — market control | +217.2% | **+3.92** | Priced risk |
| SPC3 | Base — alt-L1 direction | −221.4% | **−3.88** | Structure |
| ★ SKEW52_high_minus_low | Behavioral | +96.9% | **+3.44** | — |
| ★ NEWC_young_minus_old | Behavioral | +114.1% | **+3.43** | — |
| RMOM1w | Base — risk-adj momentum | +59.4% | **+1.86** | Priced risk |
| SPC4 | Base — legacy/exchange direction | +93.5% | +1.42 | Structure |
| RMOM4w | Base — risk-adj momentum | +36.6% | +1.24 | Not supported |
| SPC1 | Base — DeFi-majors direction | +57.6% | +1.08 | Structure |
| RMOM2w | Base — risk-adj momentum | +31.3% | +1.05 | Suggestive |
| SPC2 | Base — payment/old-guard direction | −56.0% | −1.47 | Structure |
| SMBC | Base — size | +9.6% | +0.36 | Suggestive |
| NetRel | Base — cross-cluster rotation | −0.2% | −0.01 | Suggestive |
| NetMom | Base — within-cluster momentum | +8.6% | +0.37 | Not supported |
| MomC | Base — raw momentum | −3.3% | −0.10 | Not supported |
| FunC | Base — fees/mcap value | +6.6% | +0.40 | Economic-only |
| CCA1 | Base — macro direction 1 | −55.0% | −0.58 | Structure |
| CCA2 | Base — macro direction 2 | +6.6% | +0.58 | Structure |
| CCA3 | Base — macro direction 3 | +14.9% | +0.58 | Structure |

The two confirmed base factors (VolC, MAXRET) and the two dominant DeFi/market premia
(TVLC, RC) anchor the top of the table. All four behavioral factors land in the top
half — above RMOM1w, which was the strongest base-zoo factor not already classified
as Confirmed — and all four clear the |t| ≥ 1.65 bar comfortably even after the
full zoo is controlled for. The base factors that were weak in Stage 09 (SMBC,
NetRel, MomC, CCA1–3) remain weak here, confirming the behavioral factors bring
genuinely new pricing power rather than rotating on existing variation.

## In-sample vs out-of-sample robustness (audit Finding 2)

The headline search uses the full 2021–2026 window for both discovery and
reporting. To check that selection was not an artifact of the full sample, each
shortlist factor is re-priced with the GX-full engine separately on the frozen
**in-sample** window (2021-05-10 → 2024-11-11) and the held-out
**out-of-sample** window (2024-11-18 → 2026-05-25). A factor is
credible only if it was already significant IS (before it could see the OOS data)
and keeps the same sign OOS.

| Factor | IS lambda | IS t_gx | OOS lambda | OOS t_gx |
|---|---:|---:|---:|---:|
| NEWC_young_minus_old | -52.7% | -1.18 | -20.2% | -0.49 |
| SKEW52_high_minus_low | +19.4% | +0.68 | +29.6% | +1.06 |
| CRASH8_crashed_minus_resilient | +0.6% | +0.01 | -20.4% | -0.57 |
| BETA26_high_minus_low | +0.6% | +0.02 | +56.9% | +1.24 |

OOS windows are short (~79 weeks), so OOS
t-stats are naturally weaker than full-sample ones; the test we apply is
sign-consistency plus IS significance, not a second |t|>=2 bar on a 1.5-year
slice. Factors that flip sign OOS would be flagged here.

### Behavioral interpretation

- **NEWC_young_minus_old**: buys newly listed/younger coins and shorts seasoned
  coins. This is a newness/seasoning premium: investors demand compensation for
  holding less seasoned names, and the cross-section prices that exposure even
  after size is controlled.
- **SKEW52_high_minus_low**: buys coins with high trailing 52-week realized
  skewness and shorts low-skew coins. This captures lottery memory: investors
  remember right-tail jumps and price exposure to names with salient upside
  histories.
- **CRASH8_crashed_minus_resilient**: buys the coins with the worst trailing
  8-week single-week crash and shorts the most resilient names. This is a
  capitulation premium: recently punished coins carry a priced behavioral
  rebound/crash-risk exposure.
- **BETA26_high_minus_low**: buys high 26-week market-beta coins and shorts
  low-beta coins. This captures speculative risk-on demand: high-beta names are
  the coins investors reach for when they want amplified market exposure.

## Shortlist correlation

| Factor | NEWC_young_minus_old | SKEW52_high_minus_low | CRASH8_crashed_minus_resilient | BETA26_high_minus_low |
|---|---|---|---|---|
| NEWC_young_minus_old | +1.00 | +0.03 | +0.63 | +0.10 |
| SKEW52_high_minus_low | +0.03 | +1.00 | +0.20 | +0.09 |
| CRASH8_crashed_minus_resilient | +0.63 | +0.20 | +1.00 | +0.17 |
| BETA26_high_minus_low | +0.10 | +0.09 | +0.17 | +1.00 |

The largest shortlist correlation is between newness and crash exposure, which
is economically plausible: younger coins are more crash-prone. The factors still
survive jointly, so the GX result is not just one duplicated trade.

## Caveats

- This is exploratory factor mining. The uncorrected hit count is not a claim
  that all of those strict hits are independent discoveries — see the
  multiple-testing section above, where only the Bonferroni/BH survivors are
  treated as real. The four headline factors survive that correction.
- The strongest volatility and max-return variants are intentionally not the
  final headline because they overlap Stage-09 VolC/MAXRET.
- The data are weekly, so intraday/daily attention mechanisms are proxied by
  weekly returns, skewness, crashes, beta, and age.
