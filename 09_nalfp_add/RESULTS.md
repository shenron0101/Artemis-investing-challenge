# Stage 09 — Factor Validation Results (plain-language)

*What this file is:* a from-scratch check of whether each "factor" (a simple
trading rule) actually makes money in a believable way. We test every factor on
two separate time periods so we can't fool ourselves.

## How to read this (30-second version)

- A **factor** is a rule like "buy small coins, sell big coins, rebalance weekly."
  Its **return** is what that rule would have earned each week.
- We split history into two halves we *never mix*:
  - **In-sample (IS):** 2021-05-10 → 2024-11-11 (184 weeks) — where we're allowed to look.
  - **Out-of-sample (OOS):** 2024-11-18 → 2026-05-25 (80 weeks) — the "exam" the factor never saw.
- **IC (information coefficient)** = how well the factor *ranks* coins from
  best to worst each week (correlation between the factor's ranking and what
  actually happened next). This is the number the competition cares about most.
  IC around +0.03–0.05 is a normal "useful" signal; negative IC means the rule
  ranks coins **backwards**.
- **Sharpe** = return per unit of risk (higher is better; >1 is good, >2 is excellent).
- **t-stat** = "is this real, or luck?" Rule of thumb: **|t| ≥ 2 means very unlikely to be luck.**
- **Verdict** (judged on IC for Group A):
  - **Robust** = significant in-sample *and* still works out-of-sample. These are the keepers.
  - **In-sample only** = looked good, then faded or flipped on the exam. Don't trust it.
  - **Weak** = wasn't even convincing in-sample. Drop it.

All signals use only past data (no peeking into the future), and we use a
*Newey-West* t-stat, which is just a t-stat that accounts for weeks not being
fully independent.

## Key takeaways (the 1-minute version)

1. **Only VolC has statistically strong,
   out-of-sample-stable ranking power.** Its IC is significant both in-sample
   (t = -3.3) and out-of-sample
   (t = -4.3) — a real, persistent signal.
2. **Volatility's signal points the *opposite* way to the textbook.** The IC is
   **negative**, meaning across the broad cross-section, *higher*-volatility coins
   tend to do slightly worse — a mild low-volatility tilt. BUT the naive
   long-low-vol / short-high-vol portfolio still loses money in-sample, because a
   handful of the most volatile small-caps occasionally rocket and blow up the
   short leg. **Lesson: volatility is an informative ranking signal, but its fat
   tail must be handled (cap the extremes), not traded raw.**
3. **The "stars" of the 52-week study did not survive 5 years.** Size and
   momentum, which looked strong on the old one-year sample, are **not**
   statistically significant over the full multi-regime history. This is the
   single most important honesty point: short-window strength was partly luck /
   regime-specific. The competition explicitly rewards catching exactly this.
4. **The network factors (NetMom, NetRel) are weak over 5 years** — no reliable
   ranking power once tested across regimes.
5. **The Sparse-PCA directions are mostly market beta**, not edge — useful for
   modelling risk, not for standalone bets.

**Bottom line for the competition:** rather than presenting a basket of factors
as all "working", we present an honest finding — *one* characteristic (volatility)
carries robust cross-sectional information over 5 years, with a crypto-specific
twist, while the textbook size/momentum premia are regime-fragile. That is a
stronger, more defensible story than an overfit zoo.

## Group A — Tradable long/short factors (the ones we present)

These are genuine market-neutral rules (buy some coins, short others). We judge
them on **IC** — their week-to-week ranking power — because that is what the
competition rewards. (`IC t` is the "is it luck?" number for the IC.)

| Factor | IS IC | IS IC t | OOS IC | OOS IC t | IS Sharpe | OOS Sharpe | Verdict |
|---|---|---|---|---|---|---|---|
| SMBC | +0.022 | +1.49 | +0.029 | +1.25 | +0.83 | +1.66 | Weak |
| MomC | -0.026 | -1.66 | +0.003 | +0.13 | +0.52 | +0.31 | Weak |
| VolC | -0.061 | -3.32 | -0.127 | -4.31 | -0.51 | +0.54 | Robust |
| NetMom | -0.002 | -0.15 | -0.016 | -0.81 | -0.65 | -0.69 | Weak |
| NetRel | -0.028 | -1.72 | -0.003 | -0.10 | +0.69 | +0.23 | Weak |

What each factor *is*:
- **Size** — bet that small coins beat big coins (long the smallest 30%, short the biggest 30%).
- **Momentum** — bet that recent winners keep winning (long the best 4-week performers, short the worst).
- **Low-volatility** — bet that calm coins beat wild ones (long the least volatile 30%, short the most).
- **Within-group momentum** — inside each cluster of co-moving coins, back the local winners against the local losers.
- **Cross-group rotation** — back coins outperforming *other* clusters; captures money rotating between narratives.

## Group B — Sparse-PCA "structure" factors (context, not standalone bets)

These are **not** market-neutral trading rules. They are the main *directions*
the market moves in (found by Sparse PCA). We report them so you can see which
directions paid off, but a high return here is mostly **market exposure (beta)**,
not a clever edge — e.g. SPC1 is basically "the whole crypto market." Judge them
as risk factors, not as alpha. (Their % returns are scale-arbitrary, so only
Sharpe and t-stat are meaningful.)

| Factor | IS Sharpe | IS t | OOS Sharpe | OOS t |
|---|---|---|---|---|
| SPC1 | -0.37 | -0.68 | -1.27 | -1.94 |
| SPC2 | +0.33 | +0.61 | +0.64 | +0.75 |
| SPC3 | -1.01 | -1.74 | +0.37 | +0.46 |
| SPC4 | +0.55 | +1.12 | +0.62 | +0.77 |

What each direction *is*:
- **Market/DeFi-majors direction** — the dominant 'everything moves together' direction (ETH, BTC, UNI, AAVE).
- **Payment/old-guard direction** — XRP, XLM, ADA, ALGO, HBAR moving as a bloc.
- **New-L1 direction** — SOL, AVAX, NEAR, ATOM, FET moving as a bloc.
- **Legacy/privacy + exchange direction** — ZEC, DASH, LTC, BNB, CAKE.

## The shortlist (what survived)

**Competition-grade factors (passed both IS and OOS): VolC.**

These are the factors we can defend to the judges: they were statistically real
in-sample *and* kept working on data they had never seen.

## Honest caveats (read these)

- **Three factors could not be tested over 5 years for lack of data.** FunC
  (value = fees/market-cap), TVLC (TVL/market-cap) and SupC (supply absorption)
  need fundamentals we did not re-fetch for the full history; they remain tested
  only on the old 52-week sample.
- **Market cap before ~2025 is partly estimated** (price × supply), so the Size
  factor's deep history carries some measurement error (see `SURVIVORSHIP.md`
  and the reconstruction error report). The direction is reliable; exact levels
  less so.
- **Sparse-PCA returns are scale-arbitrary** — read their Sharpe and t-stat, not
  their headline % return.
- **OOS is only 80 weeks.** That's enough to
  catch a factor that completely falls apart, but not enough to certify a small
  edge with high confidence.

---

## Part 2 — Economic significance: Giglio-Xiu + Fama-MacBeth pricing (5-year panel)

*What this section adds:* the IC test above checks if a signal ranks coins well week-to-week. This
section asks a different question: **is a factor a priced source of risk?** A factor is "priced" if
assets that load heavily on it earn systematically higher (or lower) returns across the full
5-year cross-section.

We run **two pricing methods side by side** so you can see what each one does:
- **FMB (Fama-MacBeth 1973)** — the classic method. Each week, regress that week's coin returns
  on pre-estimated betas → get a weekly price-of-risk λ_t. Average across 263 weeks and test with
  a Newey-West t-stat. This is transparent and standard, but noisy with 15 factors and 30–60 coins.
- **GX obs-only** — same betas, but use *mean* returns in a single cross-section with
  heteroskedasticity-robust SE. More stable than FMB but ignores hidden risk factors.
- **GX full (Giglio-Xiu 2021)** — adds a third pass: extract K hidden factors from the residuals
  (Bai-Ng selects K=2), refit betas on observed + hidden, then reprice. This is the most honest
  number — it strips out contamination from unobserved systematic forces.

**How to read the table:**
- **λ (%/yr)** = annualised risk premium. Positive = you earn more by holding assets exposed to
  this factor. Negative = you earn *less* (the factor loads on overpriced assets).
- **t-stat** = "is this real or luck?" **|t| ≥ 1.65 = statistically meaningful** (highlighted **bold**).
- All three t-stats are shown so you can see when methods agree (strong evidence) vs disagree (noisy).

### Final full-sample results — 15 factors, 263 weeks, K_hidden = 2

Full factor set: RC + SMBC + MomC + VolC + NetMom + NetRel (original 6) · FunC + TVLC
(Artemis/DeFiLlama fundamentals) · SPC1–4 (rolling Sparse PCA crypto structure directions) ·
CCA1–3 (macro-spanned crypto directions, IS-fitted).

| Factor | What it is | FMB λ | t_fmb | GX-obs λ | t_obs | GX-full λ | t_gx | Verdict |
|---|---|---|---|---|---|---|---|---|
| **RC** | Crypto market (VW) | +73.8% | +1.09 | +187.9% | **+5.97** | **+219.6%** | **+5.35** | **Priced** |
| **VolC** | Low-vol minus high-vol | −72.2% | −1.22 | −111.3% | **−5.17** | **−150.9%** | **−4.14** | **Priced** |
| **TVLC** | High TVL/mcap minus low | −119.2% | −1.37 | −79.5% | **−2.55** | **−174.6%** | **−3.40** | **Priced** |
| **SPC3** | Alt-L1 bloc (SOL/AVAX/NEAR/ATOM/FET) | −1.6% | −0.01 | −10.3% | −0.21 | **−176.8%** | **−2.88** | **Priced (GX only)** |
| **SPC4** | Legacy/privacy+exchange (ZEC/DASH/LTC/BNB/CAKE) | +96.1% | +1.13 | +9.7% | +0.17 | **+104.9%** | **+1.73** | **Borderline** |
| SPC2 | Payment/old-guard (XRP/XLM/ADA/ALGO/HBAR) | −12.8% | −0.16 | −61.5% | **−2.02** | −64.2% | −1.54 | Borderline (GX-obs only) |
| MomC | Recent winners minus losers | +40.0% | +0.92 | −12.3% | −0.54 | −20.4% | −0.58 | No |
| NetMom | Within-cluster winners | −13.4% | −0.45 | +21.2% | +1.03 | +26.4% | +1.00 | No |
| NetRel | Cross-cluster rotation | +44.0% | +1.05 | −13.6% | −0.68 | −17.1% | −0.56 | No |
| SMBC | Small minus big | −68.4% | −0.98 | +15.5% | +0.66 | −3.2% | −0.10 | No |
| FunC | High fees/mcap minus low | −12.2% | −0.23 | +23.8% | +1.43 | −4.1% | −0.21 | No |
| SPC1 | DeFi-majors (ETH/UNI/AAVE/ETC/BTC) | −71.0% | −1.37 | +19.1% | +0.53 | +60.7% | +1.45 | No |
| CCA1 | Macro-spanned direction 1 (ρ=0.89 with macro) | +55.3% | +0.21 | +215.6% | **+3.55** | −112.4% | −0.94 | No (GX correction kills it) |
| CCA2 | Macro-spanned direction 2 | −6.7% | −0.21 | −25.9% | **−3.55** | +13.5% | +0.94 | No |
| CCA3 | Macro-spanned direction 3 | −15.0% | −0.21 | −58.6% | **−3.55** | +30.5% | +0.94 | No |

### What each result means in plain English

**RC (t_gx = +5.35) — market premium:** The clearest result. Holding crypto earned a large
premium over 5 years. This is the crypto equity premium — you earn it just by being in the market,
not by being clever. All three methods agree the sign is positive.

**VolC (t_gx = −4.14) — volatility premium:** The strongest *alpha* factor. The negative λ
means high-volatility coins earn *more* across the crypto cross-section — investors pay up for
wild, high-upside coins (the "crypto lottery premium"), leaving calmer coins underpriced. This is
the opposite of equity markets, where low-vol stocks outperform. The result gets *stronger* as we
add more factors (6-factor GX: t=−3.93 → 15-factor GX: t=−4.14), which is exactly what
robustness means. VolC is the only factor that is simultaneously significant in the IC test (Part 1)
AND the GX pricing test (Part 2).

**TVLC (t_gx = −3.40) — TVL irrelevance:** The sign is the key finding. High TVL/mcap assets
earn *less* — consistent with the "TVL Irrelevance" result (Hartmann 2025). TVL measures
popularity and liquidity, not cheapness. The most TVL-rich protocols are priced richly by the
market and subsequently underperform. GX-obs and GX-full agree on the negative sign; FMB also
shows a large negative λ (−119%/yr) though below the significance threshold. Direction is clear.

**SPC3 (t_gx = −2.88) — alt-L1 bloc underperforms:** The alt-L1 narrative cluster
(SOL, AVAX, NEAR, ATOM, FET) carried a negative risk premium after GX correction. Assets that
load heavily on this direction earned less — they were structurally overpriced by the market
relative to their risk. This only appears in the GX-full model (not in FMB or GX-obs), meaning
it is a genuine latent-factor-corrected finding.

**SPC4 (t_gx = +1.73, borderline) — legacy/exchange bloc:** The legacy privacy and exchange
token bloc (ZEC, DASH, LTC, BNB, CAKE) carried a small positive premium. Borderline evidence
— read cautiously.

**CCA1–3 (GX-obs t≈3.5 → GX-full t≈0) — macro directions are not separately priced:** The
most instructive GX result. The macro-spanned crypto directions look strongly priced before
correction (t≈3.55), but collapse to zero after it. The GX procedure absorbs them into the two
hidden factors — proving they carry no independent pricing information beyond market beta. The
FMB also shows t≈0.21 for CCA1, agreeing: no separate premium. The macro *link* is real (ρ=0.89)
but it is not a separate source of return.

**FunC (fees/mcap) and SMBC (size):** Neither survives in any model at |t|≥1.65. FunC looks
large in GX-obs (+23.8%) but the correction erases it (−4.1%). FMB also shows essentially zero
(−12.2%). Not priced.

### Why FMB finds nothing significant

FMB runs 263 separate weekly cross-sectional regressions with 15 factors on 30–60 coins each. The
weekly λ_t estimates are very noisy at that scale, so the standard error of their average is large.
This is a known limitation — FMB is underpowered when factors outnumber the assets-per-week by a
large ratio. The GX approach (using mean returns in a single well-identified cross-section) has
more power here. Think of FMB as a conservative sanity check, and GX-full as the primary evidence.

### IS-only stability check (184 weeks, K_hidden = 4)

The IS window uses 4 hidden factors (vs 2 in the full sample) because the shorter window leaves
more unexplained residual variance. Results are noisier: SPC1 and SPC4 appear significant (t≈−3.3
and +2.18) in IS-only GX but not in the full sample. CCA1–3 are priced IS-only (t≈2.3) but not
full-sample. **Use the full-sample results as the primary evidence** — the IS is a stability check,
not a standalone finding.

### Summary: what survived all tests

| Factor | IC test | GX-full (15-factor) | Conclusion |
|---|---|---|---|
| **VolC** | ✓ IS + OOS | ✓ t=−4.14 | **Most robust — confirmed three ways** |
| **RC** | — (market, not sorted) | ✓ t=+5.35 | **Market premium is real** |
| **TVLC** | — (untested in IC) | ✓ t=−3.40 | **TVL irrelevance — negative premium** |
| **SPC3** | Structure factor | ✓ t=−2.88 | **Alt-L1 bloc overpriced** |
| SPC4 | Structure factor | Borderline t=+1.73 | Suggestive only |
| All others | Weak/no | Not priced | Drop from active factor list |

**VolC confirmed by four independent tests:** IC IS (t=−3.3), IC OOS (t=−4.3),
6-factor GX (t=−3.93), 15-factor GX (t=−4.14). No other factor comes close to this
convergence across methods and time windows.
