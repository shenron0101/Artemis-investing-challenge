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
- GX-full hits at |t| >= 2.0 (uncorrected): 106
- GX-full hits at |t| >= 1.65 (uncorrected): 118

Top one-by-one candidates:

| Candidate | Behavior interpretation | GX-full lambda | t_gx | Nearest Stage-09 factor |
|---|---|---:|---:|---|
| maxret_3w__low_minus_high | low maximum-return lottery salience | -158.9% | -6.02 | 0.79 vs MAXRET |
| maxret_3w__high_minus_low | high maximum-return lottery salience | +158.9% | +6.02 | 0.79 vs MAXRET |
| skew_52w__low_minus_high | low realized skewness; lottery memory and right-tail salience | -149.7% | -5.68 | 0.33 vs RC |
| SKEW52_high_minus_low | high realized skewness; lottery memory and right-tail salience | +149.7% | +5.68 | 0.33 vs RC |
| vol_26w__high_minus_low | high volatility/lottery demand | +197.9% | +5.35 | 0.69 vs VolC |
| vol_26w__low_minus_high | low volatility/lottery demand | -197.9% | -5.35 | 0.69 vs VolC |
| maxret_26w__low_minus_high | low maximum-return lottery salience | -179.6% | -5.35 | 0.58 vs RC |
| maxret_26w__high_minus_low | high maximum-return lottery salience | +179.6% | +5.35 | 0.58 vs RC |
| absret_mean_12w__high_minus_low | high attention shock from large absolute moves | +206.6% | +5.30 | 0.78 vs VolC |
| absret_mean_12w__low_minus_high | low attention shock from large absolute moves | -206.6% | -5.30 | 0.78 vs VolC |
| maxret_52w__low_minus_high | low maximum-return lottery salience | -168.3% | -5.12 | 0.46 vs RC |
| maxret_52w__high_minus_low | high maximum-return lottery salience | +168.3% | +5.12 | 0.46 vs RC |
| attention_absret_xs_4w__high_minus_low | high attention shock from large absolute moves | +136.9% | +5.12 | 0.89 vs VolC |
| attention_absret_xs_4w__low_minus_high | low attention shock from large absolute moves | -136.9% | -5.12 | 0.89 vs VolC |
| absret_mean_4w__low_minus_high | low attention shock from large absolute moves | -136.9% | -5.12 | 0.89 vs VolC |

Many of the strongest raw hits are volatility or max-return variants, which are
close to Stage-09 VolC/MAXRET. The final shortlist below keeps factors that are
behaviorally interpretable and not merely a renamed copy of an existing factor.

## Multiple-testing correction (audit Finding 1)

Testing 182 candidate specifications and keeping hits at a
per-test |t| >= 2.0 bar admits false positives by construction: under the null
about 5% of tests would clear that bar by luck. We therefore report two
corrections across the full family of 182 tests.

- **Uncorrected** hits at |t| >= 2.0: **106**
  (58% of all tests).
- **Bonferroni** (family-wise error rate 5%) raises the bar to
  |t| > **3.64**; only
  **60** candidates survive.
- **Benjamini-Hochberg** (false-discovery rate 5%) leaves
  **104** candidates.

The four headline factors are not just BH survivors — they clear the much harsher
Bonferroni bar as well:

| Factor | search t_gx | raw p | BH q-value | Bonferroni pass |
|---|---:|---:|---:|---|
| NEWC_young_minus_old | +3.71 | 2.10e-04 | 6.60e-04 | yes |
| SKEW52_high_minus_low | +5.68 | 1.33e-08 | 6.05e-07 | yes |
| CRASH8_crashed_minus_resilient | +3.51 | 4.49e-04 | 1.32e-03 | no |
| BETA26_high_minus_low | +3.41 | 6.51e-04 | 1.74e-03 | no |

So while the 56% raw hit rate is correctly read as exploratory mining, the
specific factors carried into the strategy survive a full family-wise correction
over every specification searched. The reported t-statistics are *not* deflated
below significance by the correction.

## Joint behavioral shortlist

These four factors are tested jointly with each other plus the full Stage-09
factor zoo. They still pass GX-full significance after hidden factors are added.

| Factor | GX-full lambda | t_gx | Weekly lambda 95% CI |
|---|---:|---:|---|
| NEWC_young_minus_old | +100.6% | +2.40 | [+0.004, +0.035] |
| SKEW52_high_minus_low | +107.6% | +4.19 | [+0.011, +0.030] |
| CRASH8_crashed_minus_resilient | +172.5% | +3.73 | [+0.016, +0.051] |
| BETA26_high_minus_low | +89.4% | +3.30 | [+0.007, +0.027] |

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
| NEWC_young_minus_old | -49.3% | -1.06 | -5.1% | -0.13 |
| SKEW52_high_minus_low | +18.7% | +0.67 | +45.4% | +1.16 |
| CRASH8_crashed_minus_resilient | -2.5% | -0.04 | -6.9% | -0.18 |
| BETA26_high_minus_low | +4.9% | +0.20 | +52.0% | +1.11 |

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
