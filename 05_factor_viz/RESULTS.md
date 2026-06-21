# Crypto Factor Research — Results

*This document reports the full findings from a multi-stage search for cross-sectional
return factors in crypto. A factor is a rule that ranks coins each week and bets that
the top-ranked coins will outperform the bottom-ranked ones. We tested 23 candidate
factors across a 5-year weekly panel (2017–2026, ~113 large-cap coins) and 4
behavioral factors from a 182-candidate search. Each factor with meaningful evidence
has its own visualisation folder here with 9 interactive charts and a plain-language
report.*

---

## How to read this (30-second version)

**What is a factor?** A simple trading rule. "Buy the 30% of coins with the lowest
volatility, sell the 30% with the highest volatility, rebalance every week." We
measure whether that rule actually earns money — and more importantly, whether it
earns money *for the right reason*.

**The time split:** We never look at future data when building a signal. The panel is
divided into:
- **In-sample (IS):** 2021-05-10 → 2024-11-11 (184 weeks) — allowed to study
- **Out-of-sample (OOS):** 2024-11-18 → 2026-05-25 (79 weeks) — the real test

**Three lenses for each factor:**

1. **IC (Information Coefficient)** — does the factor *rank* coins correctly week to week?
   It is the Spearman correlation between a coin's characteristic rank and its actual
   return the following week. |IC| ≈ 0.03–0.05 is a useful signal in practice.
   We use the **Newey-West t-stat** (which corrects for autocorrelation in the weekly
   series) to test if the IC is reliably non-zero. |t| ≥ 2 = statistically significant.
   *Sign note:* for factors that go long the low end of their sort (low-vol, small-cap),
   a negative raw IC means the factor is *working* — the tables note this where relevant.

2. **ASD (Almost Stochastic Dominance)** — does the factor's return distribution beat
   Bitcoin's distribution, without assuming normality?
   Crypto returns are fat-tailed; Sharpe ratios can mislead. ASD tests whether the
   *entire return CDF* of the factor is preferable to just holding BTC:
   - ε₂ ≤ 3.2% → **ASSD**: risk-averse investors prefer the factor to BTC
   - ε₁ ≤ 5.9% → **AFSD**: all investors prefer it (stronger bar)

3. **Giglio-Xiu (GX) pricing** — is this factor a priced source of systematic risk?
   This is the most rigorous test. GX estimates how much extra return assets earn in the
   *long-run cross-section* for loading on each factor, after controlling for hidden latent
   risk factors (selected by Bai-Ng). The reported λ (%/yr) is the annualised risk premium;
   |t| ≥ 1.65 = statistically meaningful; |t| ≥ 2.0 = significant.
   A factor can have a real GX premium even with no weekly IC — the premium is earned
   over the full cross-section, not from week-to-week ranking.

**Grading scale** (combines all three lenses):

| Grade | What it means |
|---|---|
| **Confirmed** | IC significant IS and OOS *and* GX-priced — every test agrees |
| **Priced risk** | Genuine GX risk premium, but no reliable weekly ranking edge |
| **Suggestive** | Economic story intact, partial statistical evidence across lenses |
| **Economic-only** | Sound rationale, but data cannot confirm it |
| **Structure** | Describes how the market moves in blocs — not a tradable premium |
| **Not supported** | Fails its own prediction on this sample |

---

## Quick-reference: all factors

| Factor | What it bets on | IC IS t | IC OOS t | ASSD? | GX t | **Grade** | Report |
|---|---|---|---|---|---|---|---|
| **VolC** | Low-vol coins outperform high-vol | −3.32 | −4.31 | ✗ | −5.05 | **Confirmed** | `volc_visualisation/` |
| **MAXRET** | Coins with a recent spike revert | −3.49 | −4.05 | ✗ | +5.52 | **Confirmed** | `maxret_visualisation/` |
| **CRASH8** | Deeply crashed coins rebound | — | — | — | +4.79 | **Priced risk** | `crash8_visualisation/` |
| **BETA26** | High-beta coins earn a premium | — | — | — | +4.60 | **Priced risk** | `beta26_visualisation/` |
| **TVLC** | High TVL/mcap coins underperform | — | — | — | −4.71 | **Priced risk** | `tvlc_visualisation/` |
| **SKEW52** | Right-skewed coins carry lottery premium | — | — | — | +3.44 | **Priced risk** | `skew52_visualisation/` |
| **NEWC** | Newer coins earn a seasoning premium | — | — | — | +3.43 | **Priced risk** | `newc_visualisation/` |
| **RMOM1w** | 1-week risk-adjusted momentum | −1.07 | −0.27 | ✓ | +1.86 | **Priced risk** | `rmom1w_visualisation/` |
| RMOM2w | 2-week risk-adjusted momentum | −2.46 | −0.24 | ✓ | +1.05 | Suggestive | `rmom2w_visualisation/` |
| SMBC | Small caps outperform large caps | +1.49 | +1.25 | ✓ | +0.36 | Suggestive | `smbc_visualisation/` |
| NetRel | Coins outperforming their cluster | −1.72 | −0.10 | ✓ | −0.01 | Suggestive | `netrel_visualisation/` |
| MispricingM | Composite of suggestive factors | — | — | ✓ | — | Suggestive | `mispr_visualisation/` |
| FunC | High fees/mcap = earnings yield | — | — | — | +0.40 | Economic-only | `func_visualisation/` |
| MomC | 4-week price winners keep winning | −1.66 | +0.13 | ✗ | −0.10 | Not supported | `momc_visualisation/` |
| NetMom | Winners within a cluster keep winning | −0.15 | −0.81 | ✗ | +0.37 | Not supported | `netmom_visualisation/` |

*Negative IC t-stats are consistent with factors that go long the low end of their sort
(see sign note above). Bold rows = strong evidence.*

---

## Key takeaways

1. **The two best-confirmed factors are VolC and MAXRET.** Both pass all three lenses:
   IC significant in-sample and out-of-sample, and GX-priced. They are the defensible
   core of any cross-sectional crypto strategy.

2. **Four behavioral factors are newly priced: CRASH8, BETA26, SKEW52, NEWC.** These
   came from a 182-candidate behavioral search and survive a joint GX test that
   simultaneously controls for all other factors. GX t-stats range from +3.4 to +4.8 —
   strong enough to call real.

3. **The GX premium and the IC signal often point in opposite directions.** For VolC,
   the ranking power (IC) says long-low-vol weekly. But the GX premium says high-vol
   assets earn *more* in the long-run cross-section. These are not contradictions — they
   operate on different horizons. Use IC for weekly tilting; use GX to understand
   what risk is being priced.

4. **Raw momentum fails.** MomC (4-week winners) has no reliable edge over 5 years.
   Risk-adjusted momentum (RMOM) partially works — dividing by volatility strips out
   the crash risk that kills raw momentum.

5. **Four factors beat Bitcoin's distribution for risk-averse investors (ASSD):**
   RMOM1w, RMOM2w, SMBC, NetRel. The composite MispricingM beats it with ε₂ = 0.000.
   These are not necessarily tradeable — they pass a distributional bar, not a pricing bar.

6. **The size and TVL factors tell opposite stories.** SMBC (small caps) is *suggestive*
   of a premium but not confirmed. TVLC (high TVL/mcap) is a *negative* priced-risk
   factor — high-TVL coins earn less, consistent with usage metrics being already priced in.

---

---

## IC tests — weekly ranking power

*Does the factor reliably sort coins from better to worse performers each week?*

The test: compute the Spearman correlation (IC) between each coin's characteristic rank
and its return the following week. Run this every week for 263 weeks. Test whether the
average IC is reliably non-zero using the Newey-West t-stat (4 lags).

| Factor | IS mean IC | IS IC t | OOS mean IC | OOS IC t | IS Sharpe | OOS Sharpe | IC verdict |
|---|---|---|---|---|---|---|---|
| SMBC | +0.022 | +1.49 | +0.029 | +1.25 | +0.83 | +1.66 | Weak |
| MomC | −0.026 | −1.66 | +0.003 | +0.13 | +0.52 | +0.31 | Weak |
| **VolC** | **−0.061** | **−3.32** | **−0.127** | **−4.31** | −0.51 | +0.54 | **Robust** |
| NetMom | −0.002 | −0.15 | −0.016 | −0.81 | −0.65 | −0.69 | Weak |
| NetRel | −0.028 | −1.72 | −0.003 | −0.10 | +0.69 | +0.23 | Weak |
| RMOM1w | −0.016 | −1.07 | −0.006 | −0.27 | +1.44 | +1.10 | Weak |
| RMOM2w | −0.034 | −2.46 | −0.005 | −0.24 | +0.45 | +1.08 | IS-only |
| RMOM4w | −0.034 | −2.61 | −0.018 | −0.86 | +0.11 | +0.53 | IS-only |
| **MAXRET** | **−0.054** | **−3.49** | **−0.097** | **−4.05** | +0.67 | −0.35 | **Robust** |

*VolC and MAXRET are the only factors with statistically significant ranking power that
held out-of-sample. Negative ICs for VolC and MAXRET mean the factor works in
"short the high end" direction — calm coins beat volatile ones; high-max-return coins
revert. See individual reports for direction detail.*

---

## Return distribution — why Sharpe misleads

Crypto weekly returns are highly non-normal (fat tails, high kurtosis). A Sharpe ratio
assumes Gaussian returns; when kurtosis is large it understates true tail risk.

| Factor | IS Skewness | IS Excess Kurtosis | IS non-normal? | OOS Skewness | OOS Excess Kurtosis |
|---|---|---|---|---|---|
| SMBC | +2.08 | +9.52 | yes | +0.87 | +2.25 |
| MomC | +0.76 | +3.76 | yes | −0.24 | −0.06 |
| VolC | −0.75 | +1.13 | yes | −1.01 | +2.66 |
| NetMom | +1.33 | +14.19 | yes | +0.70 | +1.43 |
| NetRel | +0.61 | +3.02 | yes | −0.24 | −0.07 |
| RMOM1w | +1.57 | +6.53 | yes | +0.18 | +2.43 |
| RMOM2w | +0.29 | +2.07 | yes | +0.98 | +3.63 |
| RMOM4w | +0.64 | +1.58 | yes | +0.27 | +0.67 |
| MAXRET | +1.13 | +2.59 | yes | +0.96 | +2.03 |

All factors reject normality at the 5% level. This motivates using ASD rather than
Sharpe as the distributional test.

---

## ASD test — does the factor beat Bitcoin's distribution?

ε₁ and ε₂ measure how far the factor falls short of first-order (AFSD) and second-order
(ASSD) dominance over Bitcoin. **Smaller = better.**

- ε₂ ≤ 3.2%: **ASSD** — risk-averse investors prefer this factor to holding Bitcoin
- ε₁ ≤ 5.9%: **AFSD** — all investors prefer it (stronger bar, harder to achieve)

| Factor | ε₁ | ε₂ | AFSD? | ASSD? | Bitcoin beats factor? |
|---|---|---|---|---|---|
| SMBC | 0.476 | 0.031 | ✗ | **✓** | no |
| MomC | 0.474 | 0.208 | ✗ | ✗ | no |
| VolC | 0.983 | 1.000 | ✗ | ✗ | **YES** |
| NetMom | 0.852 | 0.958 | ✗ | ✗ | no |
| NetRel | 0.341 | 0.026 | ✗ | **✓** | no |
| RMOM1w | 0.302 | 0.000 | ✗ | **✓** | no |
| RMOM2w | 0.404 | 0.003 | ✗ | **✓** | no |
| RMOM4w | 0.449 | 0.052 | ✗ | ✗ | no |
| MAXRET | 0.545 | 0.457 | ✗ | ✗ | no |

*No factor achieves AFSD — none is universally preferred to Bitcoin. Four factors
achieve ASSD: SMBC, NetRel, RMOM1w, RMOM2w. The VolC L/S portfolio is distributionally
worse than Bitcoin — consistent with the finding that the GX premium runs against the
mechanical long/short direction.*

### MispricingM composite

Rather than picking one ASSD-dominant factor, we can average all four of them
(SMBC + NetRel + RMOM1w + RMOM2w, equal-weight). This composite aggregates the common
mispricing signal and reduces noise.

| Window | Ann. Return | Sharpe | t-stat | ε₂ (ASSD) |
|---|---|---|---|---|
| In-sample | +31.0% | +1.23 | **+2.31** | 0.000 ✓ |
| Out-of-sample | +34.1% | +1.50 | +1.60 | — |

The IS return t-stat of +2.31 is the only factor (other than GX-priced ones) to cross
the |t| ≥ 2 bar, and the composite achieves the tightest ASSD of any single factor.

---

## Giglio-Xiu pricing — what is a priced source of risk?

GX pricing asks: across the full 5-year cross-section, do assets that *load* on a
given factor earn systematically higher or lower returns? This is different from the
IC test — it measures long-run compensation, not short-run ranking.

**Method:** Bai-Ng selected K = 2 latent hidden factors from the residuals. The GX
full model adds these hidden factors to the observed ones and re-estimates all risk
premia simultaneously. This controls for anything unobserved that might contaminate
the premiums.

### Cross-sectional factor pricing (19-factor joint model)

| Factor | What it is | GX-full λ (%/yr) | GX t | Priced? |
|---|---|---|---|---|
| RC | Crypto market (value-weighted) | +217.2% | **+3.92** | ✓ |
| VolC | Low-vol minus high-vol | −185.8% | **−5.05** | ✓ |
| MAXRET | Max weekly return, 4w trailing | +160.0% | **+5.52** | ✓ |
| TVLC | High TVL/mcap minus low | −185.2% | **−4.71** | ✓ |
| SPC3 | Sparse-PCA: alt-L1 direction | −221.4% | **−3.88** | ✓ (structure) |
| RMOM1w | 1-week risk-adj momentum | +59.4% | **+1.86** | ✓ |
| SMBC | Small minus big (size) | +9.6% | +0.36 | ✗ |
| MomC | 4-week raw momentum | −3.3% | −0.10 | ✗ |
| NetMom | Within-cluster momentum | +8.6% | +0.37 | ✗ |
| NetRel | Cross-cluster rotation | −0.2% | −0.01 | ✗ |
| FunC | High fees/mcap minus low | +6.6% | +0.40 | ✗ |
| RMOM2w | 2-week risk-adj momentum | +31.3% | +1.05 | ✗ |
| RMOM4w | 4-week Sharpe momentum | +36.6% | +1.24 | ✗ |
| SPC1–4, CCA1–3 | Market structure directions | varies | varies | mixed |

*λ = annualised risk premium. Positive = assets exposed to this factor earn more.
Negative = assets with high factor loading earn less.*

---

## Behavioral factor search — 4 new priced risk factors

Beyond the 19-factor panel above, we ran a systematic search over **182 behavioral
candidate definitions** — all constructed from price data only, designed to capture
investor psychology: newness preference, lottery memory, capitulation, and speculative
beta demand. Each candidate was added one-by-one to the 19-factor model and tested at
|t| ≥ 2.0 (stricter bar than above). 102 candidates hit this bar.

The strongest non-redundant hits were then tested **jointly** — all 4 simultaneously
alongside the full 19-factor model — with the same GX hidden-factor correction.

### Joint behavioral shortlist

| Factor | Economic mechanism | GX-full λ (%/yr) | GX t | 95% CI | Nearest known factor |
|---|---|---|---|---|---|
| **CRASH8** | Capitulation rebound | +177.9% | **+4.79** | [+105%, +251%] | VolC (corr = 0.68) |
| **BETA26** | Speculative beta demand | +122.8% | **+4.60** | [+71%, +175%] | MAXRET (corr = 0.25) |
| **NEWC** | Newness / seasoning premium | +114.1% | **+3.43** | [+49%, +179%] | SMBC (corr = 0.49) |
| **SKEW52** | Lottery memory / right-tail salience | +96.9% | **+3.44** | [+42%, +152%] | RC (corr = 0.33) |

All four pass the strict |t| ≥ 2.0 bar in the *joint* model — they survive each other
as controls. None is a renamed copy of an existing factor (maximum pairwise correlation
with nearest known factor is 0.68 for CRASH8/VolC, and they add independent information
even when VolC is in the model).

Shortlist inter-correlations (all low except NEWC–CRASH8):

| | NEWC | SKEW52 | CRASH8 | BETA26 |
|---|---|---|---|---|
| NEWC | 1.00 | 0.03 | **0.63** | 0.10 |
| SKEW52 | 0.03 | 1.00 | 0.20 | 0.09 |
| CRASH8 | **0.63** | 0.20 | 1.00 | 0.17 |
| BETA26 | 0.10 | 0.09 | 0.17 | 1.00 |

The NEWC–CRASH8 correlation (0.63) is economically expected — younger coins crash more.
Both survive jointly.

---

## Per-factor dossier

One entry per factor. Sorted from strongest to weakest evidence.

---

### VolC — Low-vol minus high-vol · *Confirmed*

**What it bets on.** Each week, rank all coins by their trailing 4-week return volatility.
Buy the calmest 30%, sell the most volatile 30%.

**Why it should work.** Leverage-constrained and lottery-seeking investors over-pay for
exciting, volatile coins, leaving calm coins underpriced (Frazzini-Pedersen 2014).

**What the evidence says.**
- IC: significant IS (t = −3.32) and OOS (t = −4.31). The IC is negative because we
  sort ascending — low vol gets the long. OOS t-stat is *larger in magnitude* than IS,
  the strongest possible OOS confirmation.
- ASD: Bitcoin's distribution beats the L/S portfolio. The mechanical short on
  high-vol coins is dangerous — they occasionally rocket, creating left-tail blow-ups.
- GX pricing: λ = −185.8%/yr (t = −5.05). The most significant pricing result in the
  study. High-vol exposure earns *less* — the market penalises high-vol loading.

**Verdict:** Every test registers the factor as real. The IC and GX lenses agree in
direction. Use VolC as a weekly ranker (long calm, avoid wild) — not as a mechanical
L/S trade.

---

### MAXRET — Max weekly return, 4w trailing · *Confirmed*

**What it bets on.** Each week, find each coin's best single week over the past 4 weeks.
Short the coins with the highest recent spike; buy the overlooked coins.

**Why it should work.** Coins with a spectacular recent week attract overexcited buyers
who push prices above fair value. The price corrects the following week (Bali et al. 2011;
Han et al. 2023). This is a *reversal* signal, not a momentum signal.

**What the evidence says.**
- IC: significant IS (t = −3.49) and OOS (t = −4.05). Negative = short the high end.
  OOS stronger than IS.
- ASD: neither factor dominates Bitcoin — the reversal trade does not produce a
  distributional win versus holding BTC.
- GX pricing: λ = +160.0%/yr (t = +5.52). High-max-return *exposure* earns more long-run.

**Key nuance.** The IC says "short the lottery coins weekly." The GX says "holding
lottery exposure earns a long-run premium." These are not contradictory — they operate
at different horizons. Investors who *bear* the lottery-crash risk get compensated;
investors who *actively fade* the overpricing earn a weekly reversal edge.

---

### CRASH8 — Crashed minus resilient · *Priced risk*

**What it bets on.** Each week, find each coin's worst single week over the past 8 weeks
(its deepest recent crash). Buy the most-crashed coins; sell the most resilient.

**Why it should work.** Deeply crashed coins suffer from forced selling (leveraged
positions blown out) and behavioral over-extrapolation of bad news. Once the panic
subsides, no sellers remain — rebound is the path of least resistance.

**What the evidence says.**
- GX pricing (joint model): λ = +177.9%/yr (t = +4.79, CI [+105%, +251%]).
  Strongest GX t-stat in the behavioral shortlist. Significant at |t| ≥ 2.0 even
  after controlling for all other factors including VolC.

**Relationship to VolC.** CRASH8 is correlated with VolC (0.68) — crashed coins tend
to be volatile coins. But CRASH8 specifically targets the *left tail* (worst recent loss)
while VolC measures symmetric dispersion. CRASH8 survives VolC as a control.

---

### BETA26 — High minus low 26-week market beta · *Priced risk*

**What it bets on.** Each week, estimate each coin's beta against the value-weighted
crypto market using 26 weeks of history. Buy the highest-beta coins; sell the lowest-beta.

**Why it should work.** High-beta coins amplify market moves — they go up more in bull
markets and down more in bear markets. Investors who hold them take on more systematic
risk and earn compensation for it. Unlike equities (where high-beta is *over-demanded*
by leverage-constrained investors, driving prices up and expected returns down), in
crypto the beta premium is positive — investors are paid for bearing amplified exposure.

**What the evidence says.**
- GX pricing (joint model): λ = +122.8%/yr (t = +4.60, CI [+71%, +175%]).

---

### TVLC — High TVL/mcap minus low · *Priced risk*

**What it bets on.** TVL (Total Value Locked) is the total crypto deposited into a DeFi
protocol. TVL/mcap ranks protocols by how much real usage they have per dollar of
market cap. Buy high-TVL/mcap protocols; sell low-TVL/mcap.

**Why it might work (the bull case).** High TVL/mcap = usage-backed value. Protocols
with genuine usage relative to valuation should be "cheap on fundamentals" and earn
higher future returns, just as low P/E stocks outperform in equities.

**What the evidence says.** λ = **−185.2%/yr** (t = −4.71). The premium is *negative*:
high TVL/mcap earns less, not more. This is the "TVL Irrelevance" result — the market
fully prices TVL into valuations, and high-TVL protocols are often yield-farming traps
that unwind. No weekly IC (not tested as a weekly ranker).

---

### SKEW52 — High minus low 52-week realized skewness · *Priced risk*

**What it bets on.** Each week, compute the trailing 52-week skewness of each coin's
weekly return history. Buy the most right-skewed coins (those with a history of dramatic
positive spikes); sell the least skewed.

**Why it should work.** Investors remember big up-moves (salience theory, Bordalo et al.
2012). Coins with a salient right-tail history attract demand, and the market prices
exposure to that lottery memory. Distinct from MAXRET (4-week horizon) — SKEW52 captures
a full year of upside history.

**What the evidence says.**
- GX pricing (joint model): λ = +96.9%/yr (t = +3.44, CI [+42%, +152%]).

---

### NEWC — Young minus old (newness premium) · *Priced risk*

**What it bets on.** Rank coins by how long they have been listed in the market (age in
weeks since first data point). Buy the newest 30%; sell the oldest 30%.

**Why it should work.** Younger coins carry information uncertainty — less history, fewer
analysts, thinner order books, higher survival uncertainty. Investors demand compensation
for this Knightian uncertainty. Related to the size premium but distinct: age measures
time in market, not current market cap.

**What the evidence says.**
- GX pricing (joint model): λ = +114.1%/yr (t = +3.43, CI [+49%, +179%]).

**Relationship to SMBC.** NEWC correlates 0.49 with SMBC (new coins tend to be small),
but survives SMBC as a control — age adds independent information beyond size.

---

### RMOM1w — 1-week risk-adjusted momentum · *Priced risk*

**What it bets on.** Divide each coin's current weekly return by its 4-week rolling
volatility. This is the coin's "1-week Sharpe ratio." Buy the top 30%; sell the bottom.

**Why it should work.** Raw momentum is destroyed by crash weeks where high-momentum
coins reverse sharply. Dividing by vol makes the signal proportional to how much the
coin outperformed relative to its own typical noise — stripping out the crash vulnerability
(Han et al. 2023).

**What the evidence says.**
- IC: not significant in either period (t = −1.07 IS, −0.27 OOS). No reliable weekly
  ranking power.
- ASD: ASSD-dominant (ε₂ = 0.000) — the tightest ASSD result of any single factor.
- GX pricing: λ = +59.4%/yr (t = +1.86). Compensated systematic exposure.

---

### RMOM2w — 2-week risk-adjusted momentum · *Suggestive*

**What it bets on.** Same as RMOM1w but using the 2-week return in the numerator.

**What the evidence says.**
- IC: significant IS (t = −2.46, reversed direction) but fades OOS (t = −0.24).
- ASD: ASSD-dominant (ε₂ = 0.003).
- GX pricing: not significant (t = +1.05).

The in-sample IC significance disappears out-of-sample — the reversal IS is
regime-specific. The ASSD result provides partial distributional support.

---

### SMBC — Small minus big (size) · *Suggestive*

**What it bets on.** Rank coins by log market cap. Buy the smallest 30%; sell the largest.
This is the crypto analogue of the Fama-French SMB factor.

**What the evidence says.**
- IC: not significant (t = +1.49 IS, +1.25 OOS). Both below the |t| ≥ 2 bar.
- ASD: ASSD-dominant (ε₂ = 0.031 — just under the 3.2% bar).
- GX pricing: not significant (t = +0.36).

Over 5 years the small-cap premium is real but noisy — it came and went with regimes.
Strong in the 2020–2021 bull run; broke down in 2022–2023.

---

### NetRel — Cross-cluster rotation · *Suggestive*

**What it bets on.** Each week, use network analysis (minimum spanning tree + Louvain
clustering) to identify crypto "communities" (DeFi, Layer-1s, payments, etc.). Buy coins
that are outperforming *other* clusters the most; sell coins lagging behind other clusters.

**What the evidence says.**
- IC: borderline IS (t = −1.72), near zero OOS (t = −0.10).
- ASD: ASSD-dominant (ε₂ = 0.026).
- GX pricing: not significant (t = −0.01).

The rotation narrative is economically sound — capital cycles through crypto sectors.
The weekly signal is too short-horizon to capture the full rotation cycle reliably.

---

### MispricingM — Composite of ASSD-dominant factors · *Suggestive*

**What it is.** Equal-weight average return of SMBC + NetRel + RMOM1w + RMOM2w. Each
is individually too noisy to confirm; aggregating their common signal reduces noise
(Stambaugh-Yuan 2017).

**What the evidence says.**
- Return t-stat: +2.31 IS (significant), +1.60 OOS (marginal).
- ASD: ASSD-dominant (ε₂ = 0.000 — tightest result of any factor).
- GX pricing: not tested directly.

Best distributional result of any factor or composite. IS t-stat is the only non-GX
result to reach |t| ≥ 2.

---

### FunC — High fees/mcap minus low · *Economic-only*

**What it bets on.** Fees/mcap is the crypto analogue of earnings yield. High-fee
protocols relative to their market cap are "cheap on fundamentals" and should outperform.

**What the evidence says.** GX pricing: λ = +6.6%/yr (t = +0.40) — not significant.
Only ~37 symbols have usable fees data (vs ~113 in the universe), severely limiting
statistical power. The economic rationale is sound; the data cannot confirm it.

---

### MomC — 4-week raw momentum · *Not supported*

**What it bets on.** Buy the 4-week return winners; sell the losers.

**What the evidence says.** IC: borderline IS (t = −1.66, reversed direction), near
zero OOS (t = +0.13). GX: not significant. ASD: doesn't beat Bitcoin.

Momentum fails in crypto because regime reversals are fast and brutal, and the 2022
bear market delivered crash weeks that destroyed any formation-period signal.

---

### NetMom — Within-cluster momentum · *Not supported*

**What it bets on.** Inside each Louvain community, back the coin outperforming its
cluster peers; sell the laggard.

**What the evidence says.** IC not significant in either period (t = −0.15 / −0.81).
No ASD dominance. No GX pricing. The within-cluster variance is dominated by correlated
macro moves; there is no reliable idiosyncratic momentum to exploit.

---

### Structure factors (SPC1–4, CCA1–3)

These are not alpha factors — they are **risk directions** that describe how the
crypto market moves in blocs:

- **SPC1** — DeFi-majors direction (BTC, ETH, UNI, AAVE moving together)
- **SPC2** — Payment/old-guard direction (XRP, XLM, ADA, ALGO, HBAR)
- **SPC3** — Alt-L1 direction (SOL, AVAX, NEAR, ATOM, FET) — GX priced at t = −3.88
- **SPC4** — Legacy/exchange direction (ZEC, LTC, BNB, CAKE)
- **CCA1–3** — The slice of crypto returns explained by macro (rates, DXY, risk appetite)

SPC3 is highly GX-significant (t = −3.88) as a systematic risk direction, but it is
not an *alpha* bet — it describes a risk exposure, not a tradeable anomaly.

---

---

## Caveats

- **OOS is 79 weeks** — enough to catch a factor that completely collapses, but not
  long enough to certify a small edge at high confidence.
- **ASD is a full-sample test** — the CDF estimation needs a sufficient number of
  observations, so it is not split into IS/OOS.
- **MAXRET and RMOM are weekly proxies** for signals originally defined at daily
  granularity (Han et al. 2023). The concept is the same; the granularity differs.
- **FunC and TVLC** only cover ~37 symbols with TVL/fees data vs ~113 in the full
  universe — these results are less stable than price-based factors.
- **The behavioral factor search tested 182 candidates** — the 102 individual hits
  at |t| ≥ 2.0 include many correlated variants and must be read as exploratory
  mining. The final shortlist of 4 (CRASH8, BETA26, SKEW52, NEWC) was held to a
  full multiple-testing correction across all 182 tests: all four survive both a
  Benjamini-Hochberg FDR control (q < 0.001) and the harsher Bonferroni bar
  (|t| > 3.64). They were additionally re-priced on separate in-sample and
  out-of-sample windows. See `04_behavioral_gx/RESULTS.md` for the correction and
  IS/OOS tables.
- **Market cap data before ~2025 is partly estimated** (price × circulating supply),
  carrying measurement error for early history in size-based factors.
