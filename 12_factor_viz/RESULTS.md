# Factor Research: Combined Results

*This document merges the findings from two research stages:*
- **Stage 09** (`09_nalfp_add`) — 5-year cross-sectional factor validation across the full 263-week panel. Tests: IC ranking power, ASD distributional dominance, Giglio-Xiu pricing.
- **Stage 10** (`10_behavioral_gx`) — Behavioral factor search. 182 candidate definitions tested one-by-one through the GX engine. Shortlist of 4 factors jointly validated at |t| ≥ 2.0.

*Each factor in this folder has its own `*_visualisation/` subfolder with 9 Plotly charts and a plain-language report.*

---

## Quick-reference: all factors by verdict

| Factor | Stage | Verdict | GX t | IC (IS/OOS) | Visualisation |
|---|---|---|---|---|---|
| **VolC** | 09 | **Confirmed** | −5.05 | −3.32 / −4.31 | `volc_visualisation/` |
| **MAXRET** | 09 | **Confirmed** | +5.52 | −3.49 / −4.05 | `maxret_visualisation/` |
| **CRASH8** | 10 | **Priced risk** | +4.79 | — | `crash8_visualisation/` |
| **BETA26** | 10 | **Priced risk** | +4.60 | — | `beta26_visualisation/` |
| **TVLC** | 09 | **Priced risk** | −4.71 | — | `tvlc_visualisation/` |
| **SKEW52** | 10 | **Priced risk** | +3.44 | — | `skew52_visualisation/` |
| **NEWC** | 10 | **Priced risk** | +3.43 | — | `newc_visualisation/` |
| **RC** | 09 | **Priced risk** | +3.92 | — | *(market benchmark)* |
| **RMOM1w** | 09 | **Priced risk** | +1.86 | −1.07 / −0.27 | `rmom1w_visualisation/` |
| **RMOM2w** | 09 | Suggestive | +1.05 | −2.46 / −0.24 | `rmom2w_visualisation/` |
| **SMBC** | 09 | Suggestive | +0.36 | +1.49 / +1.25 | `smbc_visualisation/` |
| **NetRel** | 09 | Suggestive | −0.01 | −1.72 / −0.10 | `netrel_visualisation/` |
| **MispricingM** | 09 | Suggestive | — | — | `mispr_visualisation/` |
| **FunC** | 09 | Economic-only | +0.40 | — | `func_visualisation/` |
| MomC | 09 | Not supported | −0.10 | −1.66 / +0.13 | `momc_visualisation/` |
| NetMom | 09 | Not supported | +0.37 | −0.15 / −0.81 | `netmom_visualisation/` |
| RMOM4w | 09 | Not supported | +1.24 | −2.61 / −0.86 | *(no viz folder)* |
| SPC1–4, CCA1–3 | 09 | Structure | varies | — | *(no viz folder)* |

**GX t is the Giglio-Xiu full-model t-stat** (hidden-factor robust, K=2 latent factors). For Stage-10 factors this is the *joint* model — tested simultaneously with all Stage-09 factors and each other. |t| ≥ 2.0 = significant; |t| ≥ 1.65 = priced-risk bar.

**IC t (IS/OOS)** is the Newey-West t-stat on the weekly Information Coefficient (Spearman rank correlation between characteristic and forward return). Negative values mean the factor works with a "short the signal" direction (see sign convention in Stage-09 note below).

---

---

# Part A — Stage 09: 5-Year Cross-Sectional Factor Validation

*Source: `09_nalfp_add/RESULTS.md`*

## How to read the Stage-09 results

- A **factor** is a rule like "buy small coins, sell big coins, rebalance weekly." Its **return** is what that rule would have earned each week.
- We split history into two halves we *never mix*:
  - **In-sample (IS):** 2021-05-10 → 2024-11-11 (184 weeks)
  - **Out-of-sample (OOS):** 2024-11-18 → 2026-05-25 (80 weeks)
- **IC (information coefficient)** = how well the factor *ranks* coins from best to worst each week. |IC| ≈ 0.03–0.05 is a normal useful signal. **Sign convention:** a low-vol or size factor goes *long the bottom* of its sort, so a negative raw IC is the factor *working*, not failing. The dossier (Part 2) reports direction-adjusted ICs.
- **Sharpe** = return per unit of risk (>1 is good; >2 is excellent).
- **t-stat** = "is this real, or luck?" |t| ≥ 2 means very unlikely to be luck.
- **ASD (almost stochastic dominance)** = a nonparametric test whether the factor's *entire return distribution* beats Bitcoin's, without assuming normality (Han et al. 2023). ε₁ ≤ 5.9% → AFSD (all investors prefer it). ε₂ ≤ 3.2% → ASSD (all risk-averse investors prefer it).

---

## Stage-09 Key Takeaways

1. **VolC remains the only IC-robust factor** — significant IS (t = −3.3) and OOS (t = −4.3).
2. **MAXRET** (lottery/max-return) is the second IC-robust factor and also the largest GX-priced signal (t = +5.52).
3. **Volatility ranks coins correctly, but the L/S spread is a weak trade.** The GX pricing premium on VolC runs *opposite* to the IC signal direction — it is a ranking tool, not a mechanical long/short.
4. **The ASD test is more honest than Sharpe for crypto.** Four factors (SMBC, NetRel, RMOM1w, RMOM2w) and the composite MispricingM are ASSD-dominant over Bitcoin — a stronger claim than Sharpe-based comparisons.
5. **Size and raw momentum are regime-specific.** Strong in the 52-week Stage-08 window; not significant over 5 years.

---

## Group A — Tradable L/S factors: IC test results

| Factor | IS IC | IS IC t | OOS IC | OOS IC t | IS Sharpe | OOS Sharpe | Verdict |
|---|---|---|---|---|---|---|---|
| SMBC | +0.022 | +1.49 | +0.029 | +1.25 | +0.83 | +1.66 | Weak |
| MomC | −0.026 | −1.66 | +0.003 | +0.13 | +0.52 | +0.31 | Weak |
| VolC | −0.061 | −3.32 | −0.127 | −4.31 | −0.51 | +0.54 | **Robust** |
| NetMom | −0.002 | −0.15 | −0.016 | −0.81 | −0.65 | −0.69 | Weak |
| NetRel | −0.028 | −1.72 | −0.003 | −0.10 | +0.69 | +0.23 | Weak |
| RMOM1w | −0.016 | −1.07 | −0.006 | −0.27 | +1.44 | +1.10 | Weak |
| RMOM2w | −0.034 | −2.46 | −0.005 | −0.24 | +0.45 | +1.08 | In-sample only |
| RMOM4w | −0.034 | −2.61 | −0.018 | −0.86 | +0.11 | +0.53 | In-sample only |
| MAXRET | −0.054 | −3.49 | −0.097 | −4.05 | +0.67 | −0.35 | **Robust** |

Negative ICs are consistent with factors that go *long the low end* of the sort (VolC, MAXRET reversal, RMOM at horizon > 1w).

---

## Almost Stochastic Dominance vs Bitcoin

| Factor | ε₁ (AFSD) | ε₂ (ASSD) | ASSD ✓? | BTC dom. factor? |
|---|---|---|---|---|
| SMBC | 0.476 | 0.031 | ✓ | no |
| MomC | 0.474 | 0.208 | ✗ | no |
| VolC | 0.983 | 1.000 | ✗ | **YES** |
| NetMom | 0.852 | 0.958 | ✗ | no |
| NetRel | 0.341 | 0.026 | ✓ | no |
| RMOM1w | 0.302 | 0.000 | ✓ | no |
| RMOM2w | 0.404 | 0.003 | ✓ | no |
| RMOM4w | 0.449 | 0.052 | ✗ | no |
| MAXRET | 0.545 | 0.457 | ✗ | no |
| MispricingM | 0.429 | 0.000 | ✓ | no |

ASSD ✓ (ε₂ ≤ 3.2%) = risk-averse investors prefer the factor's return distribution to holding Bitcoin. VolC is the only factor where Bitcoin's distribution is clearly better than the L/S portfolio.

---

## MispricingM Composite Factor

**Components:** SMBC + NetRel + RMOM1w + RMOM2w (equal-weight average of ASSD-dominant factors, Stambaugh-Yuan 2017).

| Window | Ann. Return | Sharpe | t-stat | Skew | Excess Kurt |
|---|---|---|---|---|---|
| IS | +31.0% | +1.225 | **+2.312** | +1.868 | +7.666 |
| OOS | +34.1% | +1.495 | +1.600 | +0.615 | +2.601 |

The IS t-stat crosses the |t| ≥ 2 bar — the only factor (besides GX-priced ones) to do so on the return lens.

---

## Giglio-Xiu + Fama-MacBeth Pricing (Stage-09, 19-factor joint model)

K_hidden = 2 latent factors selected by Bai-Ng.

| Factor | GX-full λ (%/yr) | t_gx | Verdict |
|---|---|---|---|
| RC | +217.2% | **+3.92** | Priced |
| VolC | −185.8% | **−5.05** | Priced |
| MAXRET | +160.0% | **+5.52** | Priced |
| TVLC | −185.2% | **−4.71** | Priced |
| SPC3 | −221.4% | **−3.88** | Priced (structure) |
| RMOM1w | +59.4% | **+1.86** | Priced |
| SMBC | +9.6% | +0.36 | No |
| MomC | −3.3% | −0.10 | No |
| NetMom | +8.6% | +0.37 | No |
| NetRel | −0.2% | −0.01 | No |
| FunC | +6.6% | +0.40 | No |
| RMOM2w | +31.3% | +1.05 | No |
| RMOM4w | +36.6% | +1.24 | No |

---

## Per-Factor Dossier (Stage-09) — Graded Verdict

Grading scale: **Confirmed** → **Priced risk** → **Tradable signal** → **Suggestive** → **Economic-only** → **Structure** → **Not supported**

#### MAXRET — *Confirmed*
Short-term reversal (IC significant IS+OOS) + long-run lottery risk premium (GX t = +5.52). Two lenses agree the factor is real but disagree in direction: the weekly signal bets against high-max-return coins; the multi-year premium rewards exposure to them.

#### VolC — *Confirmed*
Ranking power IS+OOS (IC t ≥ 3.3 in both) + negative volatility premium (GX t = −5.05). Use as a weekly ranker; the L/S itself is a weak trade because high-vol coins occasionally rocket.

#### TVLC — *Priced risk*
High TVL/mcap exposure earns less (GX t = −4.71), supporting the "TVL Irrelevance" thesis. No weekly ranking power.

#### RC — *Priced risk*
Market portfolio earns the equity-premium analogue (GX t = +3.92). Not alpha — every long-only holder already earns it.

#### RMOM1w — *Priced risk*
Long-run risk premium (GX t = +1.86) + ASSD-dominant over Bitcoin (ε₂ = 0.000). No weekly ranking power.

#### RMOM2w — *Suggestive*
ASSD-dominant (ε₂ = 0.003) + IS IC significant (reversed direction, fades OOS). Not GX-priced.

#### SMBC — *Suggestive*
ASSD-dominant (ε₂ = 0.031) + economically sound size story. IC and GX not significant.

#### NetRel — *Suggestive*
ASSD-dominant (ε₂ = 0.026) + narrative rotation mechanism. IC borderline IS, fades OOS.

#### MispricingM — *Suggestive*
ASSD-dominant (ε₂ = 0.000) + IS t-stat = +2.31 (significant). Best composite result.

#### FunC — *Economic-only*
Fees/mcap = crypto earnings yield. Sound thesis, underpowered data (~37 symbols).

#### SPC3 — *Structure* (and SPC2, SPC4, SPC1, CCA1–3)
Sparse-PCA and macro-spanned risk directions explain how the market moves. Not alpha.

#### MomC, NetMom, RMOM4w — *Not supported*
Fail their own predictions on this 5-year sample.

---

## Stage-09 Honest Caveats

- **FunC and TVLC excluded from IC tests** — tested only via GX pricing (fundamental/structure factors).
- **MAXRET is a weekly proxy** for Han et al.'s daily MAXRET (different granularity).
- **OOS is only 80 weeks** — enough to catch collapse, not enough to certify a small edge.
- **ASD is a full-sample test** (not IS/OOS split) due to CDF estimation requirements.

---

---

# Part B — Stage 10: Behavioral Factor Search

*Source: `10_behavioral_gx/RESULTS.md`*

## What this stage did

Stage-09 found real factors but many were already-known anomalies or broad risk directions. Stage-10 searched for new factors describable as **investor behavior**:

- newness and seasoning preference
- lottery memory and right-tail salience
- capitulation after recent crashes
- speculative beta chasing and risk-on demand

**Test protocol:** every candidate is added to the full Stage-09 factor zoo and run through the same Giglio-Xiu engine. The strict discovery bar is |t| ≥ 2.0 (vs |t| ≥ 1.65 for Stage-09 priced-risk bar).

**Search result:** 182 candidate definitions tested. 102 hit |t| ≥ 2.0 in GX-full.

---

## Stage-10 Top One-by-One Hits

The strongest raw hits are volatility/max-return variants close to Stage-09 VolC/MAXRET:

| Candidate | Behavior interpretation | GX-full λ | t_gx | Nearest Stage-09 |
|---|---|---|---|---|
| absret_mean_12w__high_minus_low | High attention shock | +225.0% | +6.17 | 0.78 vs VolC |
| maxret_12w__low_minus_high | Low lottery salience | −189.3% | −6.16 | 0.67 vs VolC |
| vol_12w__high_minus_low | High lottery demand | +206.9% | +5.99 | 0.81 vs VolC |
| maxret_3w__low_minus_high | Low short-term lottery | −167.4% | −5.53 | 0.79 vs MAXRET |

These are intentionally excluded from the final shortlist — they are renamed VolC/MAXRET variants.

---

## Stage-10 Joint Behavioral Shortlist

These four factors survive the **joint** test (all 4 tested simultaneously alongside the full Stage-09 zoo + K=2 latent factors):

| Factor | GX-full λ (%/yr) | t_gx | 95% CI | Nearest Stage-09 | Corr |
|---|---|---|---|---|---|
| **CRASH8** (crashed − resilient) | +177.9% | **+4.79** | [+105%, +251%] | VolC | 0.677 |
| **BETA26** (high − low market beta) | +122.8% | **+4.60** | [+71%, +175%] | MAXRET | 0.249 |
| **NEWC** (young − old coins) | +114.1% | **+3.43** | [+49%, +179%] | SMBC | 0.489 |
| **SKEW52** (high − low 52w skewness) | +96.9% | **+3.44** | [+42%, +152%] | RC | 0.333 |

Shortlist inter-correlation (no factor is a proxy for another):

| | NEWC | SKEW52 | CRASH8 | BETA26 |
|---|---|---|---|---|
| NEWC | +1.00 | +0.03 | **+0.63** | +0.10 |
| SKEW52 | +0.03 | +1.00 | +0.20 | +0.09 |
| CRASH8 | **+0.63** | +0.20 | +1.00 | +0.17 |
| BETA26 | +0.10 | +0.09 | +0.17 | +1.00 |

The NEWC–CRASH8 correlation (0.63) is economically expected: younger coins are more crash-prone. Both still survive jointly.

---

## Stage-10 Factor Interpretations

#### CRASH8 — Capitulation Premium · *Priced risk*
Buys coins with the worst single-week crash in the trailing 8 weeks; shorts the most resilient. **Mechanism:** forced selling and behavioral over-extrapolation of bad news create transient undervaluation in punished coins. Investors who bear capitulation-crash risk earn +177.9%/yr. **Note:** correlated with VolC (0.677) but adds independent information — CRASH8 targets the *left tail specifically* while VolC measures symmetric volatility level.

#### BETA26 — Speculative Beta Demand · *Priced risk*
Buys high 26-week market-beta coins; shorts low-beta. **Mechanism:** crypto investors use high-beta altcoins as natural leverage substitutes. Holding high-beta names requires bearing amplified drawdown risk; the cross-section prices that tolerance at +122.8%/yr. **Contrast with VolC:** VolC targets total volatility (negative premium); BETA26 targets systematic beta (positive premium) — they coexist because idiosyncratic and systematic volatility carry different risk prices.

#### NEWC — Newness / Seasoning Premium · *Priced risk*
Buys recently listed / younger coins; shorts seasoned coins. Characteristic: weeks since first appearance in the panel. **Mechanism:** younger coins carry Knightian uncertainty (shorter history, thinner coverage), survival risk, and wider spreads. Investors demand +114.1%/yr to hold unseasoned names. **Note:** correlated with SMBC (0.489) — new coins tend to be small — but NEWC adds information beyond market cap.

#### SKEW52 — Lottery Memory · *Priced risk*
Buys coins with the highest trailing 52-week realized skewness; shorts the least skewed. **Mechanism:** salience theory (Bordalo-Gennaioli-Shleifer 2012) — investors remember right-tail jumps and price exposure to names with salient upside histories. Different horizon from MAXRET (52w vs 4w max return); captures long-term lottery memory rather than short-term reversal.

---

## Stage-10 Honest Caveats

- **This is exploratory factor mining.** The hit count (102 strict hits) is not a claim of independent discoveries — many are correlated variants.
- **The strongest volatility/max-return variants are intentionally excluded** — they overlap Stage-09 VolC/MAXRET.
- **Weekly data is a proxy** for attention, skewness, and beta mechanisms that would ideally be measured at daily granularity.

---

---

# Combined Master Summary

All factors from both stages, sorted by absolute GX t-stat. **Bold = Priced risk or Confirmed.**

| Factor | Stage | Economic mechanism | GX λ (%/yr) | GX t | IC IS t | IC OOS t | ASSD? | Grade |
|---|---|---|---|---|---|---|---|---|
| **VolC** | 09 | Low-vol premium (leverage constraints) | −185.8% | **−5.05** | −3.32 | −4.31 | ✗ | **Confirmed** |
| **MAXRET** | 09 | Lottery reversal / overpricing | +160.0% | **+5.52** | −3.49 | −4.05 | ✗ | **Confirmed** |
| **CRASH8** | 10 | Capitulation / forced-selling rebound | +177.9% | **+4.79** | — | — | — | **Priced risk** |
| **BETA26** | 10 | Speculative beta / risk-on demand | +122.8% | **+4.60** | — | — | — | **Priced risk** |
| **TVLC** | 09 | TVL irrelevance (usage already priced) | −185.2% | **−4.71** | — | — | — | **Priced risk** |
| **RC** | 09 | Crypto market risk premium | +217.2% | **+3.92** | — | — | — | **Priced risk** |
| **SKEW52** | 10 | Lottery memory / right-tail salience | +96.9% | **+3.44** | — | — | — | **Priced risk** |
| **NEWC** | 10 | Newness / seasoning uncertainty | +114.1% | **+3.43** | — | — | — | **Priced risk** |
| SPC3 | 09 | Alt-L1 direction (structure) | −221.4% | **−3.88** | — | — | ✗ | Structure |
| **RMOM1w** | 09 | Risk-adjusted momentum (1-week) | +59.4% | **+1.86** | −1.07 | −0.27 | ✓ | **Priced risk** |
| RMOM2w | 09 | Risk-adjusted momentum (2-week) | +31.3% | +1.05 | −2.46 | −0.24 | ✓ | Suggestive |
| SMBC | 09 | Size / illiquidity premium | +9.6% | +0.36 | +1.49 | +1.25 | ✓ | Suggestive |
| NetRel | 09 | Narrative rotation | −0.2% | −0.01 | −1.72 | −0.10 | ✓ | Suggestive |
| MispricingM | 09 | Composite mispricing | — | — | — | — | ✓ | Suggestive |
| FunC | 09 | Crypto earnings yield | +6.6% | +0.40 | — | — | — | Economic-only |
| MomC | 09 | Raw momentum | −3.3% | −0.10 | −1.66 | +0.13 | ✗ | Not supported |
| NetMom | 09 | Within-cluster momentum | +8.6% | +0.37 | −0.15 | −0.81 | ✗ | Not supported |
| RMOM4w | 09 | Risk-adjusted momentum (4-week) | +36.6% | +1.24 | −2.61 | −0.86 | ✗ | Not supported |
| SPC1–4, CCA1–3 | 09 | Market structure directions | varies | varies | — | — | ✗ | Structure |

**Confirmed = IC significant both IS and OOS, AND GX-priced.**
**Priced risk = GX |t| ≥ 1.65, significant cross-sectional premium, but no reliable weekly ranking.**
**Suggestive = partial evidence across IC / ASD / GX lenses; economic story intact.**

The strongest defensible factors across both stages: **VolC, MAXRET, CRASH8, BETA26, TVLC, NEWC, SKEW52** (all GX |t| ≥ 3.4 in their respective joint models).
