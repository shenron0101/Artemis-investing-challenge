# Slide Deck Blueprint — Copy-Paste Ready

Every number below is pulled directly from `Artemis_Track1_Report.tex`. Figure paths are absolute.

---

## SLIDE 1 — Title

**Layout:** Template Slide 1 (full-bleed minimalist)

**Title:** Crypto Factor Rebalancing Portfolios

**Subtitle:** A Systematic Weekly Strategy for Artemis Track 1

**Bottom:** Shobhit Gupta · Aryan Narayanan · June 2026

---

## SLIDE 2 — Headline Result

**Layout:** Template Slide 2 (dual-column)

**Action title:** OOS Sharpe +0.84 While Bitcoin Lost 12% — Driven by a Single Mispricing Composite

**Left column — table:**

| Strategy | Sharpe | Ann. Return | Max DD |
|---|---:|---:|---:|
| Sharpe Ensemble | +0.84 | +29.9% | −24.7% |
| Defensive Ensemble | +0.75 | +21.6% | −19.7% |
| Balanced Ensemble | +0.68 | +18.8% | −18.3% |
| Bitcoin | −0.33 | −12.3% | −46.7% |
| Equal-Weight | −0.51 | −34.4% | −68.3% |

*79 weeks OOS: Nov 2024 – May 2026*

**Right column — 3 bullets:**

- **Core thesis:** Behavioral mispricings persist in crypto's upper-mid-cap tier because information asymmetry and retail-dominated order flow create repeatable short-horizon reversals.
- **Key design choice:** Factors are routed to different portfolio roles by the type of evidence they produce — not blended into one master score.
- **Honest caveat:** The strategy is effectively a single-factor portfolio (MispricingM) with volatility and drawdown controls. All limitations are discussed openly.

---

## SLIDE 3 — Roadmap

**Layout:** Minimal, 6 section markers

**Action title:** Presentation Roadmap

**Body — numbered list:**

1. Universe & Design Choices
2. Three-Test Validation Framework
3. Factor Economics & Evidence
4. Strategy Construction
5. Results & Sharpe Deconstruction
6. Limitations & Lessons

---

## SLIDE 4 — Universe

**Layout:** Template Slide 3 (tiled cards) or Slide 2 (dual-column)

**Action title:** ~113 Large/Upper-Mid-Cap Coins Balance Information Gaps Against Execution Cost

**Three cards or panels:**

**Card 1 — Efficiency gaps**
- Top-20 coins face intensive analyst coverage and ETF-driven institutional arbitrage
- Upper-mid-cap tier (#20–#120) has structurally higher information asymmetry — fewer analysts, thinner institutional ownership
- This is where behavioral mispricings persist

**Card 2 — Execution feasibility**
- Below top-120: daily volume < $1M, market impact > 100 bps
- Our universe: most constituents trade > $5M daily on major exchanges
- Estimated one-way execution cost: 10–30 bps

**Card 3 — Design rules**
- Stablecoins excluded (different risk-return profile)
- Wrapped duplicates excluded (duplicate exposure)
- Weekly rebalancing (captures short-term reversals, reduces daily noise)

**Footer text:** Universe from CoinGecko market-cap rankings. Exclusions: stablecoins, wrapped, bridged assets.

---

## SLIDE 5 — Timeline & Regimes

**Layout:** Template Slide 12 (data-first)

**Action title:** The Backtest Spans Every Major Crypto Regime Since 2021

**Body — timeline visual with these labels:**

| Period | Regime | Relevance |
|---|---|---|
| 2021 Q2–Q4 | Speculative excess, DeFi peak | Tests momentum/lottery factors at peak retail leverage |
| 2022 Q1–Q4 | Terra/Luna crash, FTX fraud | Stress-tests low-vol and crash-rebound during tail events |
| 2023 | Recovery & re-rating | Factor rotation from defensive to risk-seeking |
| 2024 Q1–Q4 | BTC ETF approval, institutional entry | Regime change: institutional flows compress BTC vol |
| 2024 Q4–2026 Q2 | **OOS: bear market** | BTC −12.3%, EW −34.4% — hardest possible test |

**Key dates box:**
- In-sample: 2021-05-10 → 2024-11-11 (184 weeks)
- Out-of-sample: 2024-11-25 → 2026-05-25 (79 weeks)

---

## SLIDE 6 — Three-Test Framework

**Layout:** Template Slide 3 (three tiled cards)

**Action title:** Three Independent Tests Route Each Factor to Its Correct Portfolio Role

**Card 1 — IC (Information Coefficient)**
- Spearman rank correlation: factor score at week *t* vs returns at week *t+1*
- Measures weekly ranking power
- Newey-West t-stats (4 lags) correct for serial correlation
- → Factors passing: routed to **Core Rank** book

**Card 2 — ASD (Almost Stochastic Dominance)**
- Compares *entire* return distributions, no normality assumption
- ε₂ ≤ 3.2% = factor dominates Bitcoin for all risk-averse investors
- The right test when crypto returns have excess kurtosis up to +19×
- → Factors passing: routed to **MispricingM** book

**Card 3 — GX (Giglio-Xiu Pricing)**
- Tests whether factor is a *priced systematic risk*
- Hidden-factor robust: controls for unobserved common risks
- |t| ≥ 1.65 = statistically meaningful risk premium
- → Factors passing: routed to **Priced Tilt** book

**Footer:** A factor does not need to pass all three — it needs to pass the right one for its job.

---

## SLIDE 7 — Master Evidence Table

**Layout:** Template Slide 12 (data table)

**Action title:** 24 Factors Tested, 12 Selected — Only the Grade Determines the Job

**Table (condensed to strategy-relevant factors):**

| # | Factor | Family | IC IS t | IC OOS t | ASD? | GX t | Grade |
|---|---|---|---:|---:|---|---:|---|
| 1 | VolC | Anomaly | −3.32 | −4.31 | No | −5.05 | Confirmed |
| 2 | MAXRET | Lottery | −3.49 | −4.05 | No | +5.52 | Confirmed |
| 3 | CRASH8 | Behavioral | — | — | — | +4.79 | Behavioral-confirmed |
| 4 | BETA26 | Behavioral | — | — | — | +4.60 | Behavioral-confirmed |
| 5 | TVLC | Fundamental | — | — | — | −4.71 | Priced risk |
| 6 | SKEW52 | Behavioral | — | — | — | +3.44 | Behavioral-confirmed |
| 7 | NEWC | Behavioral | — | — | — | +3.43 | Behavioral-confirmed |
| 8 | RMOM1w | Momentum | −1.07 | −0.27 | Yes | +1.86 | Priced risk |
| 9 | SMBC | Size | +1.49 | +1.25 | Yes | +0.36 | Suggestive |
| 10 | NetRel | Network | −1.72 | −0.10 | Yes | −0.01 | Suggestive |
| 11 | RMOM2w | Momentum | −2.46 | −0.24 | Yes | +1.05 | Suggestive |
| 12 | MispricingM | Composite | — | — | Yes | — | Suggestive |

**Footer:** Behavioral factors survived Bonferroni (|t| > 3.64) and Benjamini-Hochberg (q < 0.001) across 182 candidate tests. IC t-stats are Newey-West (4 lags), direction-raw.

---

## SLIDE 8 — Factor Router → Three Books

**Layout:** Template Slide 3 (tiled) or visual diagram

**Action title:** Factors Routed by Evidence Type, Not Blended Into One Score

**Figure:** `16_reports/figures/factor_routing_graph.png`

**Three cards below the diagram:**

| Book | Members | Role |
|---|---|---|
| **Core Rank** | VolC (0.55), MAXRET (0.45) | IC-robust weekly rankers. Defensive sleeve. |
| **MispricingM** | RMOM1w, RMOM2w, SMBC, NetRel (0.25 each) | ASSD-dominant composite. Main alpha source. |
| **Priced Tilt** | TVLC (0.25), CRASH8 (0.20), BETA26 (0.20), SKEW52 (0.20), NEWC (0.15) | GX-priced behavioral risks. Hard-capped at 18%. |

---

## SLIDE 9 — Why MispricingM Dominates

**Layout:** Template Slide 2 (dual-column)

**Action title:** Weekly Mispricing Signals Extract Weekly Alpha; Structural Premia Need Longer Horizons

**Left — MispricingM:**
- Components earn returns through **repeated short-horizon mispricing corrections** — each rebalance is an independent extraction opportunity
- All price-based signals (momentum, size, network rotation) — no exogenous data needed
- ASSD-dominates Bitcoin in IS, full sample, AND OOS windows (ε₂ = 0.000 in all three)
- IS Sharpe +1.23, OOS Sharpe +1.50

**Right — Priced Tilt:**
- **Compensated risk exposures** — premium accumulates over months and years
- Week-to-week IC is weak because the risk premium is *structural*, not episodic
- TVLC: GX |t| = 4.71 but zero weekly IC — the Artemis Terminal data confirms the usage signal is real; the market just prices it slowly
- OOS sub-book Sharpe: **−0.43** (actively destructive)

**Bottom callout:** The rolling-performance scorer learns this distinction from the data. MispricingM gets ~81% allocation; Priced Tilt gets ~4%.

---

## SLIDE 10 — Allocation Algorithm

**Layout:** Template Slide 2

**Action title:** A Look-Ahead-Free Allocator That Learns From Recent Book Performance

**5-step visual (flow diagram or numbered list):**

1. **Base allocation** — variant-specific prior (Sharpe: 92/8/0, Balanced: 55/35/10, Defensive: 65/35/0)
2. **Rolling score** — 26-week lookback: max(Sharpe, 0) × (1 + drawdown). Books that bleed get zero.
3. **Blend** — 35% anchored to base, 65% floats toward what's working
4. **Regime tilt** — XGBoost probabilities (RiskOn/Neutral/RiskOff) nudge book weights. Confidence-weighted so uncertain regimes pull toward base.
5. **Cap & normalize** — Priced Tilt hard-capped at 18%. All weights sum to 100%.

**Realized allocations table:**

| Variant | MispricingM | Core Rank | Priced Tilt |
|---|---:|---:|---:|
| Sharpe Ensemble | 80.8% | 15.3% | 3.9% |
| Balanced Ensemble | 54.8% | 36.7% | 8.5% |
| Defensive Ensemble | 60.4% | 35.7% | 3.9% |

**Figure:** `16_reports/figures/image5.png` *(Sharpe Ensemble allocation over time)*

---

## SLIDE 11 — OOS Performance

**Layout:** Template Slide 12 (data-first)

**Action title:** All Three Ensembles Remain Positive OOS While Bitcoin and the Market Decline

**Table:**

| Strategy | Sharpe | Ann. Return | Volatility | Max DD | Hit Rate | Weeks |
|---|---:|---:|---:|---:|---:|---:|
| Sharpe Ensemble | +0.84 | +29.9% | 35.8% | −24.7% | 51% | 79 |
| Balanced Ensemble | +0.68 | +18.8% | 27.6% | −18.3% | 53% | 79 |
| Defensive Ensemble | +0.75 | +21.6% | 29.0% | −19.7% | 53% | 79 |
| MispricingM | +0.85 | +37.2% | 44.1% | −29.9% | 52% | 79 |
| Core Rank | +0.11 | +2.0% | 18.1% | −18.8% | 47% | 79 |
| Priced Tilt | −0.43 | −13.7% | 31.8% | −32.6% | 39% | 79 |
| Bitcoin | −0.33 | −12.3% | 37.7% | −46.7% | 47% | 78 |
| Equal-Weight | −0.51 | −34.4% | 67.2% | −68.3% | 45% | 78 |

**Figure:** `16_reports/figures/image1.png` *(Cumulative returns chart)*

---

## SLIDE 12 — Sharpe Deconstruction

**Layout:** Template Slide 12

**Action title:** The +0.84 Sharpe Is a Single-Factor Result With a Volatility Hedge

**Three panels:**

**Panel 1 — Alpha concentration:**
- MispricingM alone: OOS Sharpe +0.85
- Full Sharpe Ensemble: OOS Sharpe +0.84
- Without Priced Tilt: OOS Sharpe **+0.90** (removing it *helps*)
- "The ensemble diversifies volatility, not return"

**Panel 2 — IS→OOS decay:**

| Strategy | IS Sharpe | OOS Sharpe | Decay |
|---|---:|---:|---:|
| Sharpe Ensemble | +1.36 | +0.84 | −38% |
| Defensive Ensemble | +1.31 | +0.75 | −43% |
| Balanced Ensemble | +1.28 | +0.68 | −47% |
| Bitcoin | +1.14 | −0.33 | −129% |
| Neural-net optimizer | +2.06 | −0.46 | −122% |

**Panel 3 — Cost sensitivity:**

| Assumption | Est. Net Sharpe | Impact |
|---|---:|---:|
| 10 bps one-way (base) | +0.84 | As reported |
| 25 bps one-way | ~+0.72 | −14% |
| 50 bps one-way | ~+0.58 | −31% |

---

## SLIDE 13 — Ablation

**Layout:** Template Slide 12

**Action title:** Removing the Priced Tilt Sleeve Raises OOS Sharpe From +0.84 to +0.90

**Table:**

| Variant | OOS Sharpe | OOS Return | Note |
|---|---:|---:|---|
| Sharpe Ensemble (headline) | +0.84 | +29.9% | Three-book ensemble |
| SE Priced-Tilt Off | **+0.90** | +34.2% | Sleeve removed entirely |
| SE Priced-Tilt 5% cap | +0.87 | +31.8% | Cap cut from 18% to 5% |
| SE No Regime Tilt | +0.80 | +27.9% | Regime multipliers = 1.0 |
| MispricingM Only | +0.85 | +37.2% | Mispricing book traded alone |

**Three findings (bold bullets):**

1. **Priced Tilt is a net OOS drag** — removing it raises Sharpe. Production should set allocation near zero.
2. **Regime conditioning adds a small measured benefit** — +0.84 vs +0.80 without tilt. Real but modest.
3. **The ensemble is effectively a single-factor strategy** — MispricingM alone earns +0.85, statistically indistinguishable from the full ensemble.

**Footer:** Across the full regime-tilt × priced-cap grid, OOS Sharpe stays in a tight +0.80 to +0.91 band — the headline is robust to these priors.

---

## SLIDE 14 — Sub-Book Decay Analysis

**Layout:** Template Slide 12

**Action title:** MispricingM Decays 36% IS→OOS — Core Rank and Priced Tilt Collapse

**Table:**

| Sub-book | IS Sharpe | OOS Sharpe | Decay |
|---|---:|---:|---:|
| MispricingM | +1.32 | +0.85 | −36% |
| Core Rank | +0.60 | +0.11 | −82% |
| Priced Tilt | +0.47 | −0.43 | −192% |

**Bullets:**

- **MispricingM** is the only book that remains strong in both windows — 36% decay is consistent with a genuine but noisy signal
- **Core Rank** is mediocre even IS; earns its place through low volatility and the shallowest OOS drawdown (−18.8%)
- **Priced Tilt** turns actively destructive OOS — the behavioral search factors describe real priced risks but their premia don't materialize at weekly frequency

**Figure (optional):** `16_reports/figures/image2.png` *(Balanced Ensemble allocation showing book weight shifts)*

---

## SLIDE 15 — Honest Limitations

**Layout:** Template Slide 2

**Action title:** 79 Weeks Is Encouraging, Not Definitive — Six Specific Risks Remain

**Six bullets:**

1. **Sample length** — 79-week OOS covers only one regime transition (bull→bear). Not proof across future cycles.
2. **Single-factor dependency** — MispricingM carries the strategy. If it stops working, there is no robust backup alpha.
3. **Transaction costs simplified** — 10 bps assumed; realistic 25–50 bps could reduce Sharpe to +0.58–0.72.
4. **Capacity ceiling** — Estimated $10–25M AUM at 5% participation rate before market impact erodes returns.
5. **Survivorship risk** — If the historical universe isn't fully point-in-time, results are inflated.
6. **Regime model is heuristic** — XGBoost test accuracy 58%; useful for sizing, not ground truth.

---

## SLIDE 16 — Lessons From Failed Approaches

**Layout:** Template Slide 2 (dual-column)

**Action title:** More Complexity Destroyed OOS Returns — Simplification Was the Alpha

**Left column — Regime-only strategies (Appendix A):**

| Plan | Sharpe | Ann. Return |
|---|---:|---:|
| Plan A (economic classifier) | +0.19 | +2.6% |
| Plan B (Hidden Markov Model) | +0.36 | +4.6% |

- Regime conditioning helped risk control but didn't create standalone alpha

**Right column — ML optimizers (Appendix B):**

| Variant | OOS Sharpe |
|---|---:|
| Sharpe optimized | +0.61 |
| Return optimized | −0.52 |
| Balanced | −0.53 |
| Neural network | −0.46 |

- 3 of 4 ML variants lose money OOS
- Neural-net decayed from IS +2.06 to OOS −0.46

**Bottom callout:** Stage 14 best: +0.61. Stage 15 final: +0.84. The +0.23 improvement came from *dropping complexity*, not adding signal.

**Figure:** `16_reports/figures/image6.png` *(XGBoost regime probabilities)*

---

## SLIDE 17 — Closing

**Layout:** Template Slide 1 style

**Action title:** Key Takeaways

**Three bullets:**

1. A single composite mispricing factor (MispricingM) generates OOS Sharpe +0.85 during a bear market where BTC lost 12% — the economic edge comes from behavioral mispricings in upper-mid-cap crypto.
2. The three-test framework (IC / ASD / GX) prevents factors from being misused — routing by evidence type, not blending into one score, is the core methodological contribution.
3. This is a disciplined research prototype, not a production strategy. 79 weeks, one regime, one dominant factor — encouraging, not definitive.

**Bottom:** Shobhit Gupta · Aryan Narayanan · Questions?

---

## Figure Reference Cheat Sheet

| Slide | Figure | File path |
|---|---|---|
| 8 | Factor routing diagram | `16_reports/figures/factor_routing_graph.png` |
| 10 | Sharpe Ensemble allocation | `16_reports/figures/image5.png` |
| 11 | Cumulative returns | `16_reports/figures/image1.png` |
| 14 | Balanced Ensemble allocation | `16_reports/figures/image2.png` |
| 16 | XGBoost regime probabilities | `16_reports/figures/image6.png` |

**Optional high-impact figures if you want to add backup/appendix slides:**

| Topic | File path |
|---|---|
| VolC cumulative return | `16_reports/figures/volc_01_cumulative_return.png` |
| VolC IS/OOS rolling IC | `16_reports/figures/volc_02_rolling_ic_significance.png` |
| MAXRET IS/OOS comparison | `12_factor_viz/maxret_visualisation/artifacts/figures/maxret_07_is_oos_comparison.png` |
| MispricingM cumulative return | `12_factor_viz/mispr_visualisation/artifacts/figures/mispr_01_cumulative_return.png` |
| MispricingM components | `12_factor_viz/mispr_visualisation/artifacts/figures/mispr_02_cumulative_components.png` |
| CRASH8 cumulative return | `16_reports/figures/crash8_01_cumulative_return.png` |
| Coin network clusters | `16_reports/figures/network_clusters.png` |
| NetMom/NetRel schematic | `16_reports/figures/netmom_netrel_schematic.png` |
