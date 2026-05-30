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
- GX-full hits at |t| >= 2.0: 102
- GX-full hits at |t| >= 1.65: 112

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

## Joint behavioral shortlist

These four factors are tested jointly with each other plus the full Stage-09
factor zoo. They still pass GX-full significance after hidden factors are added.

| Factor | GX-full lambda | t_gx | Weekly lambda 95% CI |
|---|---:|---:|---|
| NEWC_young_minus_old | +114.1% | +3.43 | [+0.009, +0.034] |
| SKEW52_high_minus_low | +96.9% | +3.44 | [+0.008, +0.029] |
| CRASH8_crashed_minus_resilient | +177.9% | +4.79 | [+0.020, +0.048] |
| BETA26_high_minus_low | +122.8% | +4.60 | [+0.014, +0.034] |

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

- This is exploratory factor mining. The hit count is not a claim that all 102
  strict hits are independent discoveries.
- The strongest volatility and max-return variants are intentionally not the
  final headline because they overlap Stage-09 VolC/MAXRET.
- The data are weekly, so intraday/daily attention mechanisms are proxied by
  weekly returns, skewness, crashes, beta, and age.
