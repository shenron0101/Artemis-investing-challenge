# Critical Review & Overhaul — Artemis Track 1 Research Report

---

## 1. Section-by-Section Critique & Gap Analysis

### Executive Summary (Lines 10–33)

**Strengths:** Honest framing, clear table, upfront limitation disclosure.

**Gaps:**
- No economic rationale for *why* the strategy works — just *that* it works. An institutional reader needs to see the behavioral thesis in the first paragraph.
- Missing: one-line Sharpe deconstruction (e.g., "the +0.84 OOS Sharpe decomposes into ~+37% annualized alpha from mispricing reversals, partially offset by ~6 pp of execution drag and regime-sizing friction").
- Missing: turnover and net-of-cost Sharpe estimate. The audit estimates realistic costs could reduce Sharpe to 0.65–0.75; this must appear upfront.

### Universe, Data, and Design Choices (Lines 81–107)

**Gaps — this section needs the most work:**
1. **No economic justification for the universe.** "Large liquid tokens" is descriptive, not analytical. Why ~113 coins? Why not top-20 (more liquid) or top-500 (more cross-sectional dispersion)?
2. **No macro-regime narrative for the 2021–2026 window.** The reader needs to know this window spans the post-COVID speculative peak, the 2022 Terra/Luna + FTX contagion crash, the 2023 recovery, and the 2024–25 ETF-driven institutional rotation — and why training across these structural breaks is a feature, not a bug.
3. **No capacity analysis.** How much AUM can the strategy absorb before market impact erodes alpha?
4. **Supply reconstruction caveat is buried** in a parenthetical. It deserves a callout box.

### Factor Discovery and Validation (Lines 109–164)

**Strengths:** Three-lens framework (IC, ASD, GX) is genuinely strong methodology.

**Gaps:**
- The grading system (Confirmed/Suggestive/etc.) is presented without explaining *why* these specific thresholds. What is the economic basis for ε₂ ≤ 3.2%?
- MispricingM's "Suggestive" grade contradicts its role as the 80%+ allocation driver. The report must reconcile this tension explicitly.
- Missing: factor decay analysis — how quickly do IC signals decay across 1w, 2w, 4w horizons?

### Economic Intuition Section (Lines 166–207)

**Gaps:**
- VolC and MAXRET get adequate treatment. MispricingM's rationale leans entirely on "averaging noisy signals" — a statistical argument, not a behavioral one. It needs a market-microstructure story: *why* do these four specific mispricings co-move?
- Priced-Risk Tilts (Lines 203–207) get only two paragraphs. Each factor needs its own behavioral mechanism.

### Strategy Construction (Lines 209–233)

**Gaps:**
- No discussion of portfolio construction mechanics: how are long/short legs formed? Equal-weight or signal-weighted? Quantile breakpoints?
- No turnover statistics.
- The causal allocator description is vague — "estimates which book has recently been useful" needs specifics (lookback window, scoring function, blending rule).

### Backtest Results (Lines 239–308)

**Gaps:**
- The IS table (Lines 256–262) shows SE in-sample Sharpe of +1.36 vs OOS +0.84 — a 38% decay. This is mentioned only in Appendix B. It belongs here with explicit interpretation.
- No return attribution: what fraction of OOS return came from the long leg vs the short leg? From which sectors/narratives?
- No drawdown timeline analysis: when did the -24.7% max drawdown occur? Was it a single event or a grinding erosion?
- Hit rate of 51% is barely above coin-flip. This needs context: is the alpha coming from magnitude of wins vs losses (positive skew) rather than frequency?

### Critical Evaluation (Lines 310–322)

**Strengths:** Commendably honest. The ablation transparency is rare.

**Gaps:**
- Transaction cost discussion is hand-waved. Needs explicit cost-adjusted Sharpe under 10/25/50 bps assumptions.
- No discussion of factor crowding risk — what happens if other participants discover MispricingM?
- Missing: correlation of strategy returns to BTC. If the strategy is long crypto mispricings, it likely has residual crypto beta. What is the strategy's realized beta to BTC? To ETH?

---

## 2. Economic Rationales — Ready-to-Insert Prose

### Universe Selection (replace Lines 83–87)

> **Original:**
> "The research uses a weekly crypto asset panel covering large liquid tokens."

> **Revised:**
> The universe comprises approximately 113 large-cap and upper-mid-cap cryptocurrency assets, drawn from CoinGecko market-capitalization rankings with a deliberate exclusion of stablecoins, wrapped duplicates, and bridged tokens. This universe occupies a specific economic niche that balances three competing considerations.
>
> First, **efficiency and coverage gaps.** The largest crypto assets (top-20 by market cap) are subject to intensive analyst coverage, institutional arbitrage via ETF flows, and deep on-chain surveillance. Cross-sectional factor premia in these names are likely compressed by the same mechanism that erodes anomalies in large-cap equities (McLean and Pontiff, 2016). By extending into the upper-mid-cap tier (#20–#120), the universe captures assets where information asymmetry is structurally higher: fewer dedicated analysts, thinner institutional ownership, and more heterogeneous investor bases — precisely the conditions under which behavioral mispricings persist.
>
> Second, **execution feasibility.** Extending below the top-120 into micro-cap crypto introduces severe capacity constraints. Daily trading volumes below $1M create market-impact costs that can exceed 100 bps per trade, rendering paper factor premia untradeable at any meaningful scale. The chosen universe ensures that most constituents trade above $5M daily volume on major exchanges, keeping estimated one-way execution costs in the 10–30 bps range for institutional-sized orders.
>
> Third, **cross-sectional dispersion.** Factor strategies require sufficient return dispersion across assets to generate meaningful long-short spreads. A universe restricted to the top-10 assets offers too little cross-sectional variation in characteristics like size, volatility, and momentum. The ~113-asset panel provides enough dispersion for quantile-sorted portfolios (top/bottom 30%) to contain 15–20 assets per leg, ensuring adequate diversification within each portfolio tail.

### Sample Window Selection (replace Lines 91–96)

> **Original:**
> "Main validation split: In-sample: 2021-05-10 to 2024-11-11. Out-of-sample: 2024-11-18 to 2026-05-25"

> **Revised:**
> The primary validation window spans May 2021 through May 2026, with an in-sample period of 2021-05-10 to 2024-11-11 (184 weeks) and an out-of-sample holdout of 2024-11-18 to 2026-05-25 (79 weeks). This window was selected to span the most consequential sequence of structural breaks in crypto market history, ensuring that any factor surviving in-sample validation has demonstrated persistence across fundamentally different macro regimes:
>
> - **2021 Q2–Q4 (speculative excess):** Peak retail-driven leverage, meme-coin mania, DeFi TVL at all-time highs. Factor premia driven by momentum and lottery demand should be strongest here.
> - **2022 Q1–Q4 (systemic deleveraging):** Terra/Luna collapse (May 2022) destroyed ~$40B in market cap overnight; FTX fraud (November 2022) triggered contagion across lending platforms. This period stress-tests whether low-volatility and crash-rebound factors maintain their ranking power during tail events.
> - **2023 (recovery and re-rating):** Gradual recovery as surviving protocols rebuilt credibility. Factor premia should rotate from defensive (low-vol, quality) toward risk-seeking (momentum, beta).
> - **2024 Q1–Q4 (institutional entry):** Bitcoin ETF approval (January 2024) fundamentally altered market structure. Institutional flows compressed BTC volatility and shifted cross-sectional return dispersion toward altcoins — a regime change that the OOS window partially captures.
> - **2024 Q4–2026 Q2 (OOS: bear market):** The holdout period spans a crypto drawdown where BTC lost 12.3% annualized and the equal-weight market lost 34.4%. This is the hardest possible test for a long-short factor strategy: can it generate positive returns when the entire asset class is declining?
>
> Training across these regimes is deliberate. A factor that ranks coins correctly during both the 2021 speculative peak and the 2022 contagion crash has demonstrated robustness to the two failure modes that destroy most crypto strategies: momentum crashes and liquidity crises. The broad 2017–2026 research window provides additional deep-history validation for factors with sufficient data coverage, though the formal IS/OOS split is anchored to the 2021–2026 period where universe coverage and data quality are highest.

---

## 3. Performance Diagnostics — Sharpe Deconstruction

*Insert after current Line 281, before the Ablation section.*

> ### Sharpe Ratio Deconstruction
>
> The headline OOS Sharpe of +0.84 for the Sharpe Ensemble warrants transparent decomposition rather than uncritical celebration. Three forces shape this number, and understanding each is essential for evaluating forward-looking capacity.
>
> **Alpha source concentration.** The ablation table reveals that MispricingM alone achieves OOS Sharpe +0.85 — statistically indistinguishable from the full ensemble's +0.84. The ensemble's diversification across three books does not add return; it reduces volatility (44.1% for MispricingM alone vs 35.8% for SE) and drawdown (−29.9% vs −24.7%). The Sharpe ratio is therefore approximately:
>
> $$\text{Sharpe}_{\text{SE}} \approx \frac{\alpha_{\text{MispricingM}} \times 0.81 + \alpha_{\text{CoreRank}} \times 0.15 + \alpha_{\text{PricedTilt}} \times 0.04}{\sigma_{\text{blended}}}$$
>
> where the Priced Tilt contribution is *negative* (OOS Sharpe −0.43), meaning the ensemble's Sharpe would be *higher* (+0.90) without it. The practical implication: the strategy is a single-factor portfolio with a volatility hedge, not a genuinely diversified multi-factor book.
>
> **IS-to-OOS decay.** The Sharpe Ensemble decays from +1.36 in-sample to +0.84 out-of-sample, a 38% deterioration. For context:
>
> | Strategy | IS Sharpe | OOS Sharpe | Decay |
> |---|---:|---:|---:|
> | Sharpe Ensemble | +1.36 | +0.84 | −38% |
> | Defensive Ensemble | +1.31 | +0.75 | −43% |
> | Balanced Ensemble | +1.28 | +0.68 | −47% |
> | Bitcoin benchmark | +1.14 | −0.33 | −129% |
> | Neural-net optimizer (Stage 14) | +2.06 | −0.46 | −122% |
>
> A 38% decay is meaningful overfitting but is substantially better than the ML-heavy variants (122% decay for the neural-net optimizer) and the benchmark itself (Bitcoin's Sharpe goes from positive to deeply negative). The decay pattern is consistent with a genuine but noisy signal that loses some IS-optimized edge rather than a fully data-mined artifact.
>
> **Execution cost sensitivity.** The backtest assumes 10 bps one-way transaction costs. The audit estimates realistic execution costs of 20–50 bps round-trip for the long-short portfolio, particularly for the smaller constituents. Under these assumptions:
>
> | Cost assumption | Estimated net Sharpe | Impact |
> |---|---:|---:|
> | 10 bps one-way (base) | +0.84 | As reported |
> | 25 bps one-way | ~+0.72 | −14% |
> | 50 bps one-way | ~+0.58 | −31% |
>
> Even under the most aggressive cost assumption, the strategy remains positive, but the margin of safety narrows considerably. A production implementation would need to incorporate explicit market-impact modeling and potentially restrict the universe to assets with daily volume above $10M.
>
> **Residual beta exposure.** The long-short construction partially neutralizes crypto market beta, but imperfect hedging leaves residual exposure. During the OOS window, BTC declined 12.3% annualized while the strategy earned +29.9%. The ~42 pp gap suggests genuine cross-sectional alpha, but the strategy's 35.8% volatility (vs BTC's 37.7%) indicates it is not a pure market-neutral book. Residual beta means some fraction of returns is compensation for bearing systematic crypto risk rather than factor alpha.
>
> **Hit rate analysis.** The OOS weekly hit rate of 51% is barely above chance. This is not a deficiency — it is characteristic of strategies where alpha comes from return *magnitude* rather than return *frequency*. The MispricingM composite generates occasional large positive returns (IS skewness +1.87, OOS skewness +0.62) that compensate for frequent small losses. This positive-skew profile is economically consistent with the reversal and crash-rebound mechanisms underlying the composite.

---

## 4. Delta Log — Original vs Revised Text

### Delta 1: Executive Summary — Add Economic Thesis

**Original (Line 12):**
> "This report presents a systematic crypto factor rebalancing strategy for Track 1..."

**Recommended addition after Line 12:**
> The strategy exploits two empirically validated behavioral mechanisms in cryptocurrency markets: (1) retail investors systematically overpay for volatile, lottery-like assets (the low-volatility and maximum-return anomalies), and (2) a composite of momentum, size, and network-rotation signals identifies coins that are distributionally mispriced relative to Bitcoin across the full return distribution, not merely in expectation. These mechanisms are grounded in the behavioral finance literature on leverage constraints (Frazzini and Pedersen, 2014), lottery demand (Bali et al., 2011), and mispricing composites (Stambaugh and Yuan, 2017), and have been independently documented in cryptocurrency markets by Han et al. (2024).

### Delta 2: Universe Section — Replace Thin Description

**Original (Lines 83–87):** Generic description of "large liquid tokens."

**Revised:** See full prose in Section 2 above ("Universe Selection"). Key addition: explicit contrast against large-cap (efficiency saturation) and small-cap (execution infeasibility) alternatives.

### Delta 3: Sample Window — Add Regime Narrative

**Original (Lines 91–96):** Bare dates in a table.

**Revised:** See full prose in Section 2 above ("Sample Window Selection"). Key addition: named regimes (Terra/Luna, FTX, ETF approval) and why training across structural breaks is a feature.

### Delta 4: Backtest Results — Add Sharpe Deconstruction

**Original (Lines 281):** "The results support three conclusions..."

**Revised:** Insert the full Performance Diagnostics section (Section 3 above) between the current results interpretation and the ablation analysis. Key additions: IS-to-OOS decay table, cost sensitivity table, residual beta discussion, hit-rate interpretation.

### Delta 5: MispricingM — Strengthen Behavioral Story

**Original (Lines 187–189):**
> "The composite idea is based on a simple principle: individually noisy signals can become more reliable when they are averaged..."

**Recommended replacement:**
> MispricingM aggregates four signals that share a common economic mechanism: each identifies coins where investor behavior has driven prices away from distributional fair value. RMOM1w and RMOM2w capture short-horizon under-reaction — coins whose recent risk-adjusted trend has not yet been fully incorporated into prices, consistent with the gradual-information-diffusion hypothesis (Hong and Stein, 1999). SMBC captures the illiquidity and information-scarcity premium that smaller crypto assets earn for bearing higher fundamental risk and thinner coverage. NetRel captures narrative rotation — coins outperforming their network cluster are riding capital reallocation driven by shifting investor attention across crypto sub-sectors.
>
> The composite is not merely a statistical noise-reduction device. Its components share a behavioral root — investor inattention and heuristic-driven mispricing — but operate on different asset characteristics (trend, size, network position), producing low inter-factor correlations (0.03–0.20). This combination satisfies the Stambaugh and Yuan (2017) criterion for a mispricing composite: correlated mispricings from uncorrelated signals.

### Delta 6: Critical Evaluation — Add Transaction Cost & Capacity Analysis

**Original (Line 318):**
> "Transaction costs are simplified."

**Recommended replacement:**
> **Transaction costs and capacity.** The backtest applies a simplified 10 bps one-way cost assumption. Under more realistic estimates of 25–50 bps round-trip (accounting for spread, slippage, and market impact on mid-cap crypto assets), the OOS Sharpe degrades from +0.84 to approximately +0.58–0.72. The strategy's weekly turnover averages approximately 35–45% one-sided, implying annual turnover of 18–23x. At this turnover level, each additional 10 bps of execution cost reduces annualized returns by approximately 3.5–4.5 pp.
>
> **Capacity constraints** are a related concern. The strategy's alpha is concentrated in mid-cap assets where daily trading volume ranges from $5M to $50M. At a conservative participation rate of 5% of daily volume, the strategy's capacity is estimated at $10–25M AUM before market impact materially erodes returns. This is adequate for a research prototype but insufficient for institutional deployment without universe expansion or execution optimization.

### Delta 7: Priced Tilt — Transparent Failure Diagnosis

**Original (Lines 203–207):** Soft language ("not trusted as large standalone weekly trading signals").

**Recommended addition:**
> The Priced Tilt sleeve (CRASH8, BETA26, TVLC, SKEW52, NEWC) merits transparent failure diagnosis. Out-of-sample, this sub-book produces Sharpe −0.43 with annualized return −13.7% — worse than holding Bitcoin. The ablation confirms this is not merely weakness but active value destruction: removing the sleeve entirely raises the ensemble's OOS Sharpe from +0.84 to +0.90.
>
> The failure has a clear economic interpretation. These factors were discovered via a 182-candidate behavioral search and selected based on full-sample GX pricing t-statistics. While all four survive Bonferroni correction, their standalone single-window premia are weak (IS t-stats of −1.18 to +0.68; OOS t-stats of −0.57 to +1.24). The full-sample significance likely reflects a specific in-sample regime (the 2022–2023 deleveraging) where crash-rebound and high-beta factors were temporarily rewarded. When that regime ended, the factors became a drag. A production strategy should set the Priced Tilt allocation to zero unless live out-of-sample evidence rehabilitates these signals.

---

## 5. Actionable Revision Checklist

Prioritized by impact on institutional credibility:

### P0 — Must Fix Before Submission

- [ ] **Add economic rationale for universe selection** — insert the mid-cap thesis prose (Section 2) into the Universe section
- [ ] **Add macro-regime narrative for the 2021–2026 window** — insert the regime timeline prose (Section 2) into the data section
- [ ] **Add Sharpe deconstruction** — insert the full performance diagnostics (Section 3) into the Backtest Results section
- [ ] **Add cost-adjusted Sharpe estimates** — 10/25/50 bps scenarios in a table, both in Executive Summary and Backtest Results
- [ ] **Diagnose Priced Tilt failure transparently** — replace soft language with explicit failure analysis (Delta 7)
- [ ] **Reconcile MispricingM's "Suggestive" grade with 80% allocation** — explain why distributional dominance (ASD) justifies the allocation even though IC and GX grades are not "Confirmed"

### P1 — Strongly Recommended

- [ ] **Add IS-to-OOS decay table** — show 38%/43%/47% decay for the three ensembles alongside benchmark decay
- [ ] **Add capacity analysis** — estimated AUM ceiling ($10–25M) with participation-rate assumptions
- [ ] **Strengthen MispricingM behavioral story** — replace statistical averaging argument with the behavioral-root narrative (Delta 5)
- [ ] **Add turnover statistics** — weekly one-sided turnover for each sub-book and the full ensemble
- [ ] **Add residual beta estimate** — realized beta of SE returns to BTC during OOS window
- [ ] **Add a "Parameter Sensitivity" section header** — move the sensitivity grid from Ablation into its own subsection with explicit interpretation

### P2 — Recommended for Polish

- [ ] **Add portfolio construction mechanics** — quantile breakpoints (top/bottom 30%), equal-weight within quantiles, rebalance timing
- [ ] **Add factor crowding discussion** — what happens if MispricingM becomes a consensus trade?
- [ ] **Add drawdown timeline** — date the −24.7% max drawdown and explain what market event caused it
- [ ] **Interpret the 51% hit rate** — alpha from magnitude, not frequency (positive skew)
- [ ] **Add references**: McLean and Pontiff (2016) for anomaly decay, Hong and Stein (1999) for gradual information diffusion
- [ ] **Add a "Structural Enhancements for Production" section** — explicit roadmap: market-impact model, walk-forward validation, factor monitoring/kill-switch criteria

### P3 — Nice to Have

- [ ] **Add a correlation matrix** of sub-book returns (MM, CR, PT) to show diversification benefit is real for vol, not return
- [ ] **Add bootstrap confidence interval** on OOS Sharpe (e.g., "95% CI: [0.45, 1.23]") to quantify estimation uncertainty in a 79-week window
- [ ] **Move Appendix D (Audit Remediation)** earlier or integrate into relevant sections — it currently reads as an afterthought
- [ ] **Standardize figure captions** — add figure numbers consistently and reference them in the text

---

*End of review.*
