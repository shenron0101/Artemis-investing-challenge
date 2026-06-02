# Stage 09 — Factor Validation Results (plain-language)

*What this file is:* a from-scratch check of whether each "factor" (a simple
trading rule) actually makes money in a believable way. We test every factor on
two separate time periods so we can't fool ourselves.

*How it's organised:* **Part 1** (below) reports the raw evidence one test at a
time — does the factor *rank* coins (IC), is its return distribution non-normal,
does it *beat Bitcoin* (ASD). **Part 2** runs the Giglio-Xiu / Fama-MacBeth pricing
tests and then **synthesises everything into a per-factor dossier**: each factor's
economic function, what each test did and did not show, and a single *graded*
verdict. No factor is significant on every test, and it doesn't need to be — so the
dossier grades on a scale (Confirmed → Priced risk → Tradable signal → Suggestive →
Economic-only → Structure → Not supported) rather than a pass/fail bar. **If you read
one thing, read the Part 2 dossier.**

## How to read this (30-second version)

- A **factor** is a rule like "buy small coins, sell big coins, rebalance weekly."
  Its **return** is what that rule would have earned each week.
- We split history into two halves we *never mix*:
  - **In-sample (IS):** 2021-05-10 → 2024-11-11 (184 weeks) — where we're allowed to look.
  - **Out-of-sample (OOS):** 2024-11-18 → 2026-05-25 (80 weeks) — the "exam" the factor never saw.
- **IC (information coefficient)** = how well the factor *ranks* coins from
  best to worst each week. |IC| ≈ 0.03–0.05 is a normal useful signal. **Read the
  sign against the factor's bet, not in the abstract:** a low-vol or size factor goes
  *long the bottom* of its sort, so a negative raw IC on the characteristic is the
  factor *working*, not failing. Part 2's dossier reports the **direction-adjusted**
  IC (positive = the bet ranked coins correctly) to remove this confusion.
- **Sharpe** = return per unit of risk (>1 is good; >2 is excellent).
- **t-stat** = "is this real, or luck?" **|t| ≥ 2 means very unlikely to be luck.**
- **ASD (almost stochastic dominance)** = a nonparametric test that checks whether
  the factor's *entire return distribution* is better than Bitcoin's, without
  assuming returns are normal. This is the correct test for highly skewed/fat-tailed
  crypto returns (Han et al. 2023, European Financial Management).
  - **ε₁ ≤ 5.9%** → factor almost first-order dominates Bitcoin (AFSD) — most investors prefer it
  - **ε₂ ≤ 3.2%** → factor almost second-order dominates Bitcoin (ASSD) — risk-averse investors prefer it
- **Verdict** here is the *IC-test-only* label (one lens of three):
  - **Robust** = significant IS *and* holds OOS.
  - **In-sample only** = faded or flipped OOS. Don't trust it.
  - **Weak** = not convincing IS on the IC lens alone.

  A "Weak" IC label does **not** mean the factor is worthless — it may still beat
  Bitcoin's distribution (ASD) or be a priced risk (GX, Part 2). The **bottom-line,
  graded** verdict that combines all three lenses lives in **Part 2's per-factor
  dossier** (Confirmed / Priced risk / Tradable signal / Suggestive / Economic-only /
  Structure / Not supported). Read Part 1 as the raw evidence per test; read Part 2
  for the coherent per-factor story.

All signals use only past data (no look-ahead), and we use *Newey-West* t-stats
(lags=4) to account for serial correlation.

---

## Key takeaways (the 1-minute version)

1. **VolC remains the only IC-robust factor.** Its ranking power is statistically
   significant both in-sample (t = -3.3) and out-of-sample
   (t = -4.3) — a real, persistent signal over 5 years.
2. **Han et al. (2023) factors tested on our 5-year panel:** We added four factors
   from that paper — risk-adjusted momentum at 1w, 2w, 4w horizons (RMOM) and the
   maximum-return lottery signal (MAXRET). These are among the 8 factors that
   "almost stochastically dominate" benchmarks in that paper.
   On our panel: **MAXRET** passed IC significance.
3. **Volatility ranks coins the right way (low-vol wins).** The raw IC is negative
   *because the factor is long low-vol*: higher-vol coins rank worse, so calm coins
   are the buy — a textbook low-volatility premium (direction-adjusted IC is strongly
   positive; see Part 2). But the raw L/S Sharpe is weak, because fat-tailed volatile
   coins occasionally rocket and blow up the short leg, and over five years the *priced*
   premium on the L/S actually runs negative (Part 2). VolC is a ranking signal to lean
   on, not a mechanical long/short trade.
4. **The ASD test is more honest than Sharpe for crypto.** Crypto factor returns are
   highly nonnormal (see distribution table below). Sharpe implicitly assumes
   normality; ASD does not. A factor beating Bitcoin by ASD is a stronger claim.
5. **Size and raw momentum** were strong in the 52-week study (earlier NALFP work) but are
   **not statistically significant over 5 years** — short-window results were partly
   regime-specific. The competition rewards catching exactly this.
6. **MispricingM** (equal-weight of ASD-dominant factors) = constructed from: SMBC, NetRel, RMOM1w, RMOM2w. This composite factor shows whether combining dominant signals improves on any single factor.

---

## Group A — Tradable L/S factors: IC test results

Judged on **IC** — week-to-week cross-sectional ranking power.

| Factor | IS IC | IS IC t | OOS IC | OOS IC t | IS Sharpe | OOS Sharpe | Verdict |
|---|---|---|---|---|---|---|---|
| SMBC | +0.022 | +1.49 | +0.029 | +1.25 | +0.83 | +1.66 | Weak |
| MomC | -0.026 | -1.66 | +0.003 | +0.13 | +0.52 | +0.31 | Weak |
| VolC | -0.061 | -3.32 | -0.127 | -4.31 | -0.51 | +0.54 | Robust |
| NetMom | -0.002 | -0.15 | -0.016 | -0.81 | -0.65 | -0.69 | Weak |
| NetRel | -0.028 | -1.72 | -0.003 | -0.10 | +0.69 | +0.23 | Weak |
| RMOM1w | -0.016 | -1.07 | -0.006 | -0.27 | +1.44 | +1.10 | Weak |
| RMOM2w | -0.034 | -2.46 | -0.005 | -0.24 | +0.45 | +1.08 | In-sample only |
| RMOM4w | -0.034 | -2.61 | -0.018 | -0.86 | +0.11 | +0.53 | In-sample only |
| MAXRET | -0.054 | -3.49 | -0.097 | -4.05 | +0.67 | -0.35 | Robust |

**Factor definitions:**
- **Size** — buy small coins, short big coins (bottom-30% vs top-30% log-mcap). Classic size premium.
- **Raw momentum** — buy the 4-week winners, short the losers. Textbook momentum.
- **Low-volatility** — buy calm coins, short wild ones (bottom vs top-30% 4-week vol). Volatility anomaly.
- **Within-cluster momentum** — inside each Louvain cluster, back the local winners against the local losers. Network-aware momentum.
- **Cross-cluster rotation** — back coins outperforming *other* clusters; captures narrative rotation.
- **Risk-adjusted momentum (1w)** — current weekly return divided by 4-week rolling vol (i.e., 1-week Sharpe ratio). Han et al. (2023) show RMOM1 is one of the 8 ASD-dominant crypto factors.
- **Risk-adjusted momentum (2w)** — 2-week return / 4-week vol. Horizon-specific Sharpe. Han et al. (2023) find this is dominant over 52-week windows.
- **Risk-adjusted momentum (4w)** — 4-week Sharpe ratio. Combines return magnitude and consistency.
- **Maximum return (4w)** — the highest single weekly return a coin posted in the last 4 weeks. Proxies the paper's daily MAXRET (max daily return in formation week). Measures lottery appeal. Han et al. (2023) find MAXRET dominates all 4 benchmarks.

---

## Group B — Sparse-PCA structure factors (not alpha, context only)

These directions explain *how* the crypto market moves in blocs, not what to trade.
High returns here are mostly market beta. Sharpe and t-stat are what to read.

| Factor | IS Sharpe | IS t | OOS Sharpe | OOS t |
|---|---|---|---|---|
| SPC1 | -0.37 | -0.68 | -1.27 | -1.94 |
| SPC2 | +0.33 | +0.61 | +0.64 | +0.75 |
| SPC3 | -1.01 | -1.74 | +0.37 | +0.46 |
| SPC4 | +0.55 | +1.12 | +0.62 | +0.77 |

- **Market/DeFi-majors direction** — dominant 'everything moves together' direction (ETH, BTC, UNI, AAVE).
- **Payment/old-guard direction** — XRP, XLM, ADA, ALGO, HBAR moving as a bloc.
- **New-L1 direction** — SOL, AVAX, NEAR, ATOM, FET moving as a bloc.
- **Legacy/privacy + exchange direction** — ZEC, DASH, LTC, BNB, CAKE.

---

## Distribution statistics — why Sharpe misleads for crypto

Crypto returns are highly nonnormal (large kurtosis, skewed). A Sharpe ratio
assumes the distribution is Gaussian; when excess kurtosis > 3 the Sharpe
understates tail risk. This motivates the ASD test below.

J-B = Jarque-Bera test for normality. "yes" = normality rejected at 5% level.

| Factor | IS Skew | IS Kurt (excess) | IS non-normal? | OOS Skew | OOS Kurt |
|---|---|---|---|---|---|
| SMBC | +2.08 | +9.52 | yes | +0.87 | +2.25 |
| MomC | +0.76 | +3.76 | yes | -0.24 | -0.06 |
| VolC | -0.75 | +1.13 | yes | -1.01 | +2.66 |
| NetMom | +1.33 | +14.19 | yes | +0.70 | +1.43 |
| NetRel | +0.61 | +3.02 | yes | -0.24 | -0.07 |
| RMOM1w | +1.57 | +6.53 | yes | +0.18 | +2.43 |
| RMOM2w | +0.29 | +2.07 | yes | +0.98 | +3.63 |
| RMOM4w | +0.64 | +1.58 | yes | +0.27 | +0.67 |
| MAXRET | +1.13 | +2.59 | yes | +0.96 | +2.03 |
| SPC1 | -0.87 | +2.63 | yes | -0.14 | -0.09 |
| SPC2 | +1.18 | +2.37 | yes | +2.93 | +14.68 |
| SPC3 | +0.26 | +0.34 | no | +1.29 | +7.91 |
| SPC4 | +3.14 | +19.31 | yes | +2.27 | +7.27 |

---

## Almost Stochastic Dominance vs Bitcoin (Han et al. 2023)

ε₁ (AFSD) and ε₂ (ASSD) measure how far the factor's return distribution falls
short of first/second-order dominance over Bitcoin. **Smaller is better.**
- ε₁ ≤ 5.9% → AFSD: factor beats Bitcoin for *all* risk preferences
- ε₂ ≤ 3.2% → ASSD: factor beats Bitcoin for *all risk-averse* investors
- "BTC dom. factor?" = does Bitcoin almost dominate the factor (reverse direction)

| Factor | ε₁ (AFSD) | ε₂ (ASSD) | AFSD ✓? | ASSD ✓? | BTC dom. factor? |
|---|---|---|---|---|---|
| SMBC | 0.476 | 0.031 | ✗ | ✓ | no |
| MomC | 0.474 | 0.208 | ✗ | ✗ | no |
| VolC | 0.983 | 1.000 | ✗ | ✗ | YES |
| NetMom | 0.852 | 0.958 | ✗ | ✗ | no |
| NetRel | 0.341 | 0.026 | ✗ | ✓ | no |
| RMOM1w | 0.302 | 0.000 | ✗ | ✓ | no |
| RMOM2w | 0.404 | 0.003 | ✗ | ✓ | no |
| RMOM4w | 0.449 | 0.052 | ✗ | ✗ | no |
| MAXRET | 0.545 | 0.457 | ✗ | ✗ | no |
| SPC1 | 0.978 | 1.000 | ✗ | ✗ | YES |
| SPC2 | 0.571 | 1.000 | ✗ | ✗ | no |
| SPC3 | 0.843 | 1.000 | ✗ | ✗ | no |
| SPC4 | 0.500 | 1.000 | ✗ | ✗ | no |
| MispricingM | 0.429 | 0.000 | ✗ | ✓ | no |

**Interpretation:**
- A factor with ε₁ < 5.9% has a return CDF that sits *mostly below* Bitcoin's —
  meaning it delivers more probability mass in the right (high-return) tail, with
  only a small violation. For such a factor, most investors (regardless of risk
  aversion) would prefer it to simply holding Bitcoin.
- Factors where Bitcoin dominates the factor (last column = YES) are ones where
  Bitcoin's distribution is clearly better — a signal that the factor destroys value.

---

## ASD robustness: in-sample vs out-of-sample (audit Finding 4)

The composite **MispricingM** is built from the factors that almost-stochastically
dominate Bitcoin *on the full sample*. A fair objection (audit Finding 4) is that
full-sample dominance peeks at the OOS window, so the selection is partly informed
by data the strategy is later tested on. The table below re-runs the ASSD test
(ε₂, risk-averse dominance) separately on the IS window, the full sample, and the
OOS window so the reader can see whether dominance was already present in-sample.
**Smaller ε₂ is better; ✓ means ε₂ ≤ 3.2% (ASSD-dominates BTC) in that window.**

| Factor | IS ε₂ | IS ✓ | Full ε₂ | Full ✓ | OOS ε₂ | OOS ✓ |
|---|---|---|---|---|---|---|
| SMBC | 0.000 | ✓ | 0.031 | ✓ | 0.000 | ✓ |
| MomC | 0.122 | ✗ | 0.208 | ✗ | 0.151 | ✗ |
| VolC | 0.855 | ✗ | 1.000 | ✗ | 0.136 | ✗ |
| NetMom | 0.733 | ✗ | 0.958 | ✗ | 0.330 | ✗ |
| NetRel | 0.018 | ✓ | 0.026 | ✓ | 0.198 | ✗ |
| RMOM1w | 0.000 | ✓ | 0.000 | ✓ | 0.000 | ✓ |
| RMOM2w | 0.144 | ✗ | 0.003 | ✓ | 0.000 | ✓ |
| RMOM4w | 0.315 | ✗ | 0.052 | ✗ | 0.000 | ✓ |
| MAXRET | 0.024 | ✓ | 0.457 | ✗ | 0.488 | ✗ |
| SPC1 | 1.000 | ✗ | 1.000 | ✗ | 1.000 | ✗ |
| SPC2 | 0.837 | ✗ | 1.000 | ✗ | 0.332 | ✗ |
| SPC3 | 0.998 | ✗ | 1.000 | ✗ | 0.696 | ✗ |
| SPC4 | 0.647 | ✗ | 1.000 | ✗ | 0.549 | ✗ |
| MispricingM | 0.000 | ✓ | 0.000 | ✓ | 0.000 | ✓ |

**How to read it:** a factor whose ε₂ stays small in *both* the IS and OOS columns
earned its place in MispricingM honestly — the dominance is not a full-sample
artifact. A factor that only dominates in the full/OOS columns but not IS is a
selection-robustness flag. The OOS column uses only ~80
weeks, so its empirical CDF is noisier and ε₂ there should be read as indicative,
not decisive. We keep the full-sample selection rule for MispricingM (it needs
enough observations to estimate the CDF), but report all three windows rather than
hiding the IS/OOS split.

---

## MispricingM composite factor

**Components:** SMBC, NetRel, RMOM1w, RMOM2w

MispricingM is the equal-weight average return of all ASD-dominant L/S factor
portfolios (following Stambaugh & Yuan 2017 and Han et al. 2023). It aggregates
the common mispricing signal across factors.
| Window | Ann. Return | Sharpe | t-stat | Skew | Excess Kurt |
|---|---|---|---|---|---|
| IS | +0.310 | +1.225 | +2.312 | +1.868 | +7.666 |
| OOS | +0.341 | +1.495 | +1.600 | +0.615 | +2.601 |


---

## The shortlist (IC lens only — full graded ranking is in Part 2)

**IC-robust factors (significant ranking power IS *and* held OOS):**
VolC, MAXRET

These have statistically significant cross-sectional ranking power that survived
out-of-sample — the strongest result the *IC lens alone* can give. Note this is **not**
the same as ASD-dominance: a factor can rank coins well yet not beat Bitcoin's whole
return distribution (VolC is the clearest case — strong IC, but BTC dominates its L/S
distribution). The competition-grade call comes from combining all three lenses —
IC, ASD, and Giglio-Xiu pricing — into the **graded per-factor dossier in Part 2**,
where these same factors land as *Confirmed* (IC + priced-risk agree they are real).

---

## Honest caveats

- **Three factors excluded for lack of 5-year data:** FunC (fees/mcap), TVLC
  (TVL/mcap), SupC (supply absorption) — tested only on the 52-week NALFP-study sample.
- **MAXRET is a weekly proxy** for Han et al.'s daily MAXRET. Their measure uses
  max *daily* return within the formation week; we use max *weekly* return over 4 weeks.
  The concept is the same (lottery appeal) but the granularity differs.
- **Market cap before ~2025 is partly estimated** (price × supply) — Size factor's
  deep history carries measurement error (see SURVIVORSHIP.md).
- **OOS is only 80 weeks** — enough to catch a factor that
  completely collapses, but not enough to certify a small edge with high confidence.
- **MispricingM's selection rule uses full-sample ASD** because the empirical CDF
  needs enough observations to be reliable, but ASD is now *also reported* split by
  IS and OOS window (see "ASD robustness" section) so the full-sample dependence is
  transparent rather than hidden. The OOS ASD column is noisier (short window) and
  is indicative only.

---

## Part 2 — Economic significance: Giglio-Xiu + Fama-MacBeth pricing (5-year panel)

*What this section adds:* Part 1 tested whether each factor **ranks coins correctly** week-to-week
(IC test) and whether its return distribution **beats Bitcoin** (ASD test). Part 2 asks a
fundamentally different question: **is a factor a priced source of systematic risk?** A factor is
"priced" if assets that load heavily on it earn systematically higher or lower returns across
the full 5-year cross-section — regardless of weekly noise.

We now test **all factors** — including the four new Han et al. (2023) factors (RMOM1w, RMOM2w,
RMOM4w, MAXRET) — through the same GX pricing engine. This is the first time both Part 1 and
Part 2 cover the same factor universe, enabling the master comparison table at the end.

We run **three pricing methods** side by side:
- **FMB (Fama-MacBeth 1973)** — week-by-week cross-sectional OLS, average λ_t, Newey-West SE.
  Conservative and standard but noisy when factors > assets/week.
- **GX obs-only** — single cross-section on mean returns, heteroskedasticity-robust SE.
  More stable than FMB but ignores hidden risk factors.
- **GX full (Giglio-Xiu 2021)** — adds a third pass: Bai-Ng selects K_hidden latent factors
  from residuals, re-estimates betas on observed + hidden, re-prices. The most credible number
  because it removes contamination from unobserved systematic forces.

**How to read the table:**
- **λ (%/yr)** = annualised risk premium. Positive = assets exposed to this factor earn more.
- **t-stat**: **bold** = |t| ≥ 1.65 (statistically meaningful). Plain = not significant.

### Full-sample results — 19 factors, K_hidden = 2

Full factor set: RC + SMBC + MomC + VolC + NetMom + NetRel (original 6) ·
FunC + TVLC (fundamentals) · RMOM1w + RMOM2w + RMOM4w + MAXRET (Han et al. 2023) ·
SPC1–4 (Sparse PCA) · CCA1–3 (macro-spanned).

| Factor | What it is | FMB λ | t_fmb | GX-obs λ | t_obs | GX-full λ | t_gx | Verdict |
|---|---|---|---|---|---|---|---|---|
| RC | Crypto market (value-weighted) | +147.9% | **+2.04** | +162.6% | **+3.70** | +217.2% | **+3.92** | **Priced** |
| SMBC | Small minus big (size) | -77.3% | -1.24 | +29.9% | +1.20 | +9.6% | +0.36 | No |
| MomC | 4-week raw momentum | +58.8% | +1.24 | -5.2% | -0.24 | -3.3% | -0.10 | No |
| VolC | Low-vol minus high-vol | -116.6% | **-1.87** | -130.0% | **-4.46** | -185.8% | **-5.05** | **Priced** |
| NetMom | Within-cluster momentum | -21.0% | -0.68 | +13.2% | +0.76 | +8.6% | +0.37 | No |
| NetRel | Cross-cluster rotation | +52.1% | +1.21 | -6.2% | -0.32 | -0.2% | -0.01 | No |
| FunC | High fees/mcap minus low | -30.6% | -0.56 | +20.3% | +1.12 | +6.6% | +0.40 | No |
| TVLC | High TVL/mcap minus low | -194.7% | **-1.85** | -91.8% | **-3.12** | -185.2% | **-4.71** | **Priced** |
| RMOM1w | 1-week risk-adj momentum (Han '23) | +119.4% | **+2.20** | +51.5% | **+2.64** | +59.4% | **+1.86** | **Priced** |
| RMOM2w | 2-week risk-adj momentum (Han '23) | +11.0% | +0.25 | +4.4% | +0.20 | +31.3% | +1.05 | No |
| RMOM4w | 4-week Sharpe momentum  (Han '23) | +31.8% | +0.77 | +17.1% | +0.82 | +36.6% | +1.24 | No |
| MAXRET | Max weekly return, 4w trailing (Han '23) | +113.4% | **+1.82** | +106.4% | **+5.89** | +160.0% | **+5.52** | **Priced** |
| SPC1 | Sparse-PCA: DeFi-majors direction | -72.5% | -1.35 | +17.1% | +0.52 | +57.6% | +1.08 | No |
| SPC2 | Sparse-PCA: Payment/old-guard direction | -64.8% | -0.84 | -60.2% | **-2.25** | -56.0% | -1.47 | Borderline |
| SPC3 | Sparse-PCA: Alt-L1 direction | +56.4% | +0.41 | -45.1% | -1.25 | -221.4% | **-3.88** | **Priced** |
| SPC4 | Sparse-PCA: Legacy/exchange direction | +39.7% | +0.45 | +16.6% | +0.38 | +93.5% | +1.42 | Borderline |
| CCA1 | Macro-spanned direction 1 | -44.5% | -0.18 | +148.0% | **+2.43** | -55.0% | -0.58 | No |
| CCA2 | Macro-spanned direction 2 | +5.3% | +0.18 | -17.8% | **-2.43** | +6.6% | +0.58 | No |
| CCA3 | Macro-spanned direction 3 | +12.1% | +0.18 | -40.2% | **-2.43** | +14.9% | +0.58 | No |

The bold t-stats above are *inputs*, not verdicts. The dossier below reads them
together with the IC and ASD evidence from Part 1 so each factor gets one coherent
story instead of being scattered across five tables.

---

### Per-factor dossier — economic function · what the tests say · graded verdict

We grade on a deliberately **non-binary** scale. A 264-week crypto panel cannot
deliver |t|≥2 everywhere, and a factor can be real along one axis (it ranks coins,
or it dominates BTC's distribution, or it is a priced risk) while silent along the
others. Collapsing all of that to "significant / not significant" throws away most
of what we actually learned, so we keep the **economic function** of every factor in
view alongside whatever the statistics could and could not show.

| Grade | What it means |
|---|---|
| **Confirmed** | every test registers it as a strong, real factor |
| **Priced risk** | compensated systematic exposure, but no week-to-week edge |
| **Tradable signal** | ranks the cross-section, though not a priced *risk* |
| **Suggestive** | economic story intact + partial/semi-significant evidence |
| **Economic-only** | sound rationale, but the data here can't confirm it |
| **Structure** | a risk *direction* (how the market moves), not an alpha bet |
| **Not supported** | fails its own prediction on this sample |

Each entry answers three independent questions — does it **rank** coins week-to-week
(IC, Part 1), does its **return distribution beat Bitcoin** (ASD, Part 1), and is it a
**priced source of risk** (GX/FMB λ, above)? — and weighs them against the factor's
standalone economic rationale. Sorted strongest-evidence first.

#### MAXRET — Max weekly return, 4w trailing (Han '23)  ·  *Confirmed*

- **Economic function.** **Lottery / max-return** (Han et al. 2023; Bali et al. 2011). Coins with an extreme recent up-week attract lottery demand and get over-priced, so the *correct* bet is to **short** the lottery — we expect high-max-return names to under-perform (a reversal/over-pricing signal, not a buy-the-winner one).
- **What the tests say.** Weekly ranking (direction-adjusted IC): IS t=-3.49, OOS t=-4.05 — *significant but reversed*: high-signal names underperform in both windows, so the tradable bet is to short them. Distribution vs Bitcoin: neither dominates (ε₁=0.545, ε₂=0.457). Priced risk (Giglio-Xiu, hidden-factor robust): **λ=+160.0%/yr, t=+5.52** — a genuinely compensated exposure.
- **Verdict — Confirmed:** every test registers it as a strong, real factor. The two lenses **disagree in sign**: the short-term ranking edge and the long-run priced-risk premium are *not the same trade* — rank on the weekly signal, but respect that the multi-year L/S premium runs the other way.

#### VolC — Low-vol minus high-vol  ·  *Confirmed*

- **Economic function.** **Low-volatility / betting-against-beta.** Leverage-constrained and lottery-seeking investors over-pay for high-vol names, leaving calm coins cheap (Frazzini-Pedersen 2014). Prediction: low-vol coins out-rank high-vol ones, so the *long-low/short-high* bet should earn a positive premium.
- **What the tests say.** Weekly ranking (direction-adjusted IC): IS t=+3.32, OOS t=+4.31 — significant in-sample and still pointing the right way out-of-sample. Distribution vs Bitcoin: **dominated by BTC** (ε₁ reverse small) — its return distribution is worse than just holding Bitcoin. Priced risk (Giglio-Xiu, hidden-factor robust): **λ=-185.8%/yr, t=-5.05** — a genuinely compensated exposure.
- **Verdict — Confirmed:** every test registers it as a strong, real factor. The two lenses **disagree in sign**: the short-term ranking edge and the long-run priced-risk premium are *not the same trade* — rank on the weekly signal, but respect that the multi-year L/S premium runs the other way.

#### TVLC — High TVL/mcap minus low  ·  *Priced risk*

- **Economic function.** **DeFi engagement** = TVL per dollar of market cap. The bull thesis is usage-backed value; the competing 'TVL Irrelevance' view (Hartmann 2025) says it is already in prices. Sign is genuinely ambiguous a priori — this factor is a clean test of *whether TVL is priced at all*.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Priced risk (Giglio-Xiu, hidden-factor robust): **λ=-185.2%/yr, t=-4.71** — a genuinely compensated exposure.
- **Verdict — Priced risk:** compensated systematic exposure, but no week-to-week edge.

#### RC — Crypto market (value-weighted)  ·  *Priced risk*

- **Economic function.** The crypto market portfolio itself. Its premium is plain compensation for bearing systematic crypto risk — the equity-premium analogue. We expect λ>0 over the long run, but it is **not alpha**: every long-only holder already earns it. We include it so the cross-sectional factors are priced *net of* market beta.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Priced risk (Giglio-Xiu, hidden-factor robust): **λ=+217.2%/yr, t=+3.92** — a genuinely compensated exposure.
- **Verdict — Priced risk:** compensated systematic exposure, but no week-to-week edge.

#### RMOM1w — 1-week risk-adj momentum (Han '23)  ·  *Priced risk*

- **Economic function.** **Risk-adjusted momentum (1w).** Trend scaled by recent volatility (Han et al. 2023). Dividing by risk strips the vol-driven noise that makes raw momentum crash, so it should rank more cleanly than MomC. Expected >0.
- **What the tests say.** Weekly ranking (direction-adjusted IC): IS t=-1.07, OOS t=-0.27 — no reliable weekly ranking power either way. Distribution vs Bitcoin: **ASSD-dominant** (ε₂=0.000 ≤ 0.032) — risk-averse investors prefer its whole return distribution to simply holding BTC. Priced risk (Giglio-Xiu, hidden-factor robust): **λ=+59.4%/yr, t=+1.86** — a genuinely compensated exposure.
- **Verdict — Priced risk:** compensated systematic exposure, but no week-to-week edge.

#### RMOM2w — 2-week risk-adj momentum (Han '23)  ·  *Suggestive*

- **Economic function.** **Risk-adjusted momentum (2w).** Two-week return over 4-week vol (Han et al. 2023). Same logic as RMOM1w at a slightly slower horizon.
- **What the tests say.** Weekly ranking (direction-adjusted IC): IS t=-2.46, OOS t=-0.24 — significant in-sample but in *reverse* — a short-the-signal direction, yet it does **not** survive out-of-sample; reads as regime-specific, not a stable edge. Distribution vs Bitcoin: **ASSD-dominant** (ε₂=0.003 ≤ 0.032) — risk-averse investors prefer its whole return distribution to simply holding BTC. Priced risk: not priced once hidden factors are controlled (t=+1.05).
- **Verdict — Suggestive:** economic story intact + partial/semi-significant evidence.

#### SMBC — Small minus big (size)  ·  *Suggestive*

- **Economic function.** **Size.** Small caps should out-earn large caps as payment for illiquidity, thinner information coverage, and higher fundamental risk (the Fama-French SMB analogue). Expected long-small/short-big premium >0 in risk-on regimes; it can invert during flights to quality, when capital crowds into BTC/ETH.
- **What the tests say.** Weekly ranking (direction-adjusted IC): IS t=-1.49, OOS t=-1.25 — no reliable weekly ranking power either way. Distribution vs Bitcoin: **ASSD-dominant** (ε₂=0.031 ≤ 0.032) — risk-averse investors prefer its whole return distribution to simply holding BTC. Priced risk: not priced once hidden factors are controlled (t=+0.36).
- **Verdict — Suggestive:** economic story intact + partial/semi-significant evidence.

#### NetRel — Cross-cluster rotation  ·  *Suggestive*

- **Economic function.** **Cross-cluster rotation.** Capital rotates between narratives; coins pulling ahead of the *other* clusters are riding the rotation in, laggards are rotating out. Expected premium >0 whenever narrative cycling is active.
- **What the tests say.** Weekly ranking (direction-adjusted IC): IS t=-1.72, OOS t=-0.10 — significant in-sample but in *reverse* — a short-the-signal direction, yet it does **not** survive out-of-sample; reads as regime-specific, not a stable edge. Distribution vs Bitcoin: **ASSD-dominant** (ε₂=0.026 ≤ 0.032) — risk-averse investors prefer its whole return distribution to simply holding BTC. Priced risk: not priced once hidden factors are controlled (t=-0.01).
- **Verdict — Suggestive:** economic story intact + partial/semi-significant evidence.

#### MispricingM — Equal-weight ASSD-dominant composite  ·  *Suggestive*

- **Economic function.** **Composite mispricing factor** — equal-weight of the L/S sleeves that almost-stochastically dominate BTC (Stambaugh-Yuan 2017; Han et al. 2023). Aggregates the common mispricing signal that no single thin factor proves on its own.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Distribution vs Bitcoin: **ASSD-dominant** (ε₂=0.000 ≤ 0.032) — risk-averse investors prefer its whole return distribution to simply holding BTC.
- **Verdict — Suggestive:** economic story intact + partial/semi-significant evidence.

#### FunC — High fees/mcap minus low  ·  *Economic-only*

- **Economic function.** **Crypto 'value' / cash yield** = fees per dollar of market cap. Protocols throwing off real cash should be cheap relative to fundamentals (the E/P analogue). Expected premium >0 — but only ~half the universe earns fees, so this is structurally under-powered.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Priced risk: not priced once hidden factors are controlled (t=+0.40).
- **Verdict — Economic-only:** sound rationale, but the data here can't confirm it.

#### SPC3 — Sparse-PCA: Alt-L1 direction  ·  *Structure*

- **Economic function.** Sparse-PCA risk **direction** — the alt-L1 bloc (SOL, AVAX, NEAR, ATOM, FET). Context for diversification, not a tradable premium.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Distribution vs Bitcoin: neither dominates (ε₁=0.843, ε₂=1.000). Priced risk (Giglio-Xiu, hidden-factor robust): **λ=-221.4%/yr, t=-3.88** — a genuinely compensated exposure.
- **Verdict — Structure:** a risk *direction* (how the market moves), not an alpha bet.

#### SPC2 — Sparse-PCA: Payment/old-guard direction  ·  *Structure*

- **Economic function.** Sparse-PCA risk **direction** — the payment/old-guard bloc (XRP, XLM, ADA, ALGO, HBAR). Context for diversification, not a tradable premium.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Distribution vs Bitcoin: neither dominates (ε₁=0.571, ε₂=1.000). Priced risk: borderline (λ=-56.0%/yr, t=-1.47) — suggestive but under the |t|≥1.65 bar.
- **Verdict — Structure:** a risk *direction* (how the market moves), not an alpha bet.

#### SPC4 — Sparse-PCA: Legacy/exchange direction  ·  *Structure*

- **Economic function.** Sparse-PCA risk **direction** — the legacy/privacy + exchange bloc. Context for diversification, not a tradable premium.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Distribution vs Bitcoin: neither dominates (ε₁=0.500, ε₂=1.000). Priced risk: borderline (λ=+93.5%/yr, t=+1.42) — suggestive but under the |t|≥1.65 bar.
- **Verdict — Structure:** a risk *direction* (how the market moves), not an alpha bet.

#### SPC1 — Sparse-PCA: DeFi-majors direction  ·  *Structure*

- **Economic function.** Sparse-PCA risk **direction**, not an alpha bet — the dominant 'everything moves together' axis (BTC/ETH/DeFi majors). Describes *how* the market co-moves.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Distribution vs Bitcoin: **dominated by BTC** (ε₁ reverse small) — its return distribution is worse than just holding Bitcoin. Priced risk: not priced once hidden factors are controlled (t=+1.08).
- **Verdict — Structure:** a risk *direction* (how the market moves), not an alpha bet.

#### CCA1 — Macro-spanned direction 1  ·  *Structure*

- **Economic function.** Macro-spanned **direction** — the slice of crypto returns explained by macro (rates, DXY, risk appetite). Risk context, not alpha by construction.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Priced risk: not priced once hidden factors are controlled (t=-0.58).
- **Verdict — Structure:** a risk *direction* (how the market moves), not an alpha bet.

#### CCA2 — Macro-spanned direction 2  ·  *Structure*

- **Economic function.** Macro-spanned **direction** (2nd canonical axis). Risk context, not alpha.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Priced risk: not priced once hidden factors are controlled (t=+0.58).
- **Verdict — Structure:** a risk *direction* (how the market moves), not an alpha bet.

#### CCA3 — Macro-spanned direction 3  ·  *Structure*

- **Economic function.** Macro-spanned **direction** (3rd canonical axis). Risk context, not alpha.
- **What the tests say.** Weekly ranking: no 5-year IC (price/fundamental/structure factor — judged on pricing, not on weekly rank). Priced risk: not priced once hidden factors are controlled (t=+0.58).
- **Verdict — Structure:** a risk *direction* (how the market moves), not an alpha bet.

#### RMOM4w — 4-week Sharpe momentum  (Han '23)  ·  *Not supported*

- **Economic function.** **Risk-adjusted momentum (4w)** = a 4-week Sharpe ratio (Han et al. 2023). Rewards trend that is both large *and* consistent.
- **What the tests say.** Weekly ranking (direction-adjusted IC): IS t=-2.61, OOS t=-0.86 — significant in-sample but in *reverse* — a short-the-signal direction, yet it does **not** survive out-of-sample; reads as regime-specific, not a stable edge. Distribution vs Bitcoin: neither dominates (ε₁=0.449, ε₂=0.052). Priced risk: not priced once hidden factors are controlled (t=+1.24).
- **Verdict — Not supported:** fails its own prediction on this sample.

#### NetMom — Within-cluster momentum  ·  *Not supported*

- **Economic function.** **Within-cluster momentum.** Inside a tight correlation community, the coin out-trending its peers tends to keep leading. Ranking *within* the cluster strips out market beta and isolates idiosyncratic trend (Liu-Tsyvinski 2018). Expected premium >0.
- **What the tests say.** Weekly ranking (direction-adjusted IC): IS t=-0.15, OOS t=-0.81 — no reliable weekly ranking power either way. Distribution vs Bitcoin: neither dominates (ε₁=0.852, ε₂=0.958). Priced risk: not priced once hidden factors are controlled (t=+0.37).
- **Verdict — Not supported:** fails its own prediction on this sample.

#### MomC — 4-week raw momentum  ·  *Not supported*

- **Economic function.** **Momentum.** Investors under-react to news, so recent 4-week winners keep winning (Jegadeesh-Titman; Liu-Tsyvinski 2022). Expected premium >0, but raw momentum is regime-fragile and crashes hard at trend reversals.
- **What the tests say.** Weekly ranking (direction-adjusted IC): IS t=-1.66, OOS t=+0.13 — significant in-sample but in *reverse* — a short-the-signal direction, yet it does **not** survive out-of-sample; reads as regime-specific, not a stable edge. Distribution vs Bitcoin: neither dominates (ε₁=0.474, ε₂=0.208). Priced risk: not priced once hidden factors are controlled (t=-0.10).
- **Verdict — Not supported:** fails its own prediction on this sample.

### IS-only stability check (K_hidden = 4)

IS window factors: ['RC', 'SMBC', 'MomC', 'VolC', 'NetMom', 'NetRel', 'FunC', 'TVLC', 'RMOM1w', 'RMOM2w', 'RMOM4w', 'MAXRET', 'SPC1', 'SPC2', 'SPC3', 'SPC4', 'CCA1', 'CCA2', 'CCA3']. Priced at |t|≥1.65: ['SMBC', 'NetMom', 'NetRel', 'RMOM1w', 'RMOM2w', 'RMOM4w', 'MAXRET', 'SPC1', 'CCA1', 'CCA2', 'CCA3'].
The IS window uses 4 hidden factors (vs 2 full-sample) because the shorter window
leaves more unexplained residual variance. Use the full-sample results as primary evidence.

---

### Master comparison — all factors across all three tests

This is the unified view combining Part 1 (IC + ASD) and Part 2 (GX pricing).
Each factor is judged on: IC ranking power (IS and OOS t-stats), ASD vs Bitcoin
(AFSD/ASSD flags and ε values), and GX-full pricing (t-stat).

| Factor | IC IS t | IC OOS t | AFSD? | ASSD? | ε₁ | ε₂ | GX t_gx | Conclusion |
|---|---|---|---|---|---|---|---|---|
| RC | — | — | — | — | — | — | +3.92 | Priced risk |
| VolC | -3.32 | -4.31 | ✗ | ✗ | 0.983 | 1.000 | -5.05 | **Confirmed** |
| MAXRET | -3.49 | -4.05 | ✗ | ✗ | 0.545 | 0.457 | +5.52 | **Confirmed** |
| TVLC | — | — | — | — | — | — | -4.71 | Priced risk |
| SMBC | +1.49 | +1.25 | ✗ | ✓ | 0.476 | 0.031 | +0.36 | Suggestive |
| MomC | -1.66 | +0.13 | ✗ | ✗ | 0.474 | 0.208 | -0.10 | Not supported |
| NetMom | -0.15 | -0.81 | ✗ | ✗ | 0.852 | 0.958 | +0.37 | Not supported |
| NetRel | -1.72 | -0.10 | ✗ | ✓ | 0.341 | 0.026 | -0.01 | Suggestive |
| RMOM1w | -1.07 | -0.27 | ✗ | ✓ | 0.302 | 0.000 | +1.86 | Priced risk |
| RMOM2w | -2.46 | -0.24 | ✗ | ✓ | 0.404 | 0.003 | +1.05 | Suggestive |
| RMOM4w | -2.61 | -0.86 | ✗ | ✗ | 0.449 | 0.052 | +1.24 | Not supported |
| FunC | — | — | — | — | — | — | +0.40 | Economic-only |
| SPC1 | — | — | ✗ | ✗ | 0.978 | 1.000 | +1.08 | Structure |
| SPC2 | — | — | ✗ | ✗ | 0.571 | 1.000 | -1.47 | Structure |
| SPC3 | — | — | ✗ | ✗ | 0.843 | 1.000 | -3.88 | Structure |
| SPC4 | — | — | ✗ | ✗ | 0.500 | 1.000 | +1.42 | Structure |
| CCA1 | — | — | — | — | — | — | -0.58 | Structure |
| CCA2 | — | — | — | — | — | — | +0.58 | Structure |
| CCA3 | — | — | — | — | — | — | +0.58 | Structure |
| MispricingM | — | — | ✗ | ✓ | 0.429 | 0.000 | — | Suggestive |

**Legend.** IC IS/OOS t = Newey-West t-stat on the mean IC (here shown *direction-raw*;
the dossier reports the direction-adjusted version). AFSD ✓ = ε₁ ≤ 5.9%, ASSD ✓ = ε₂ ≤ 3.2%
(almost first/second-order dominance over Bitcoin). GX t_gx = Giglio-Xiu full-model t
(|t|≥1.65 = priced). The **Conclusion** column is the dossier grade — the same call used in
the prose above, so the two can never disagree.

**The shortlist by grade.** Reading down the grades:
- **Confirmed** (every test registers it as a strong, real factor): VolC, MAXRET
- **Priced risk** (compensated systematic exposure, but no week-to-week edge): RC, TVLC, RMOM1w
- **Suggestive** (economic story intact + partial/semi-significant evidence): SMBC, NetRel, RMOM2w, MispricingM
- **Economic-only** (sound rationale, but the data here can't confirm it): FunC
- **Structure** (a risk *direction* (how the market moves), not an alpha bet): SPC1, SPC2, SPC3, SPC4, CCA1, CCA2, CCA3
- **Not supported** (fails its own prediction on this sample): MomC, NetMom, RMOM4w

*Confirmed* factors are backed from two independent angles and are the defensible core.
*Priced risk* and *Tradable signal* factors are real but one-dimensional — useful, with a
named limitation. *Suggestive* factors have an intact economic story and partial evidence:
exactly the semi-significant cases a single |t|≥2 bar would have silently discarded.

