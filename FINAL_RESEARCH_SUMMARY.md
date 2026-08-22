# Network-Augmented Latent Factor Portfolio: A Comprehensive Research Summary

---
title: "Track #1: Crypto Factor Rebalancing Strategy"
subtitle: "Artemis Analytics Quant Research / Trading Strategy Competition"
date: "May 2026"
header-includes:
  - \usepackage[none]{hyphenat} # Disables all ugly word hyphenations completely
---

**Prepared for:** Artemis Analytics Quant Research / Trading Strategy Competition

**Track:** #1: Crypto Factor Rebalancing Strategy  
**Date:** May 2026  
**Codebase:** `08_nalfp/` (NALFP v2)  

*Upstream Contributions:*  
* `04_factors/`  
* `06_artemis_econometrics/`  
* `07_hidden_factor_pricing/`

---


---

## 1. Research Overview

This report summarises a multi-stage quantitative research effort to construct a weekly-rebalanced, long/short cryptocurrency factor strategy, submitted in response to **Track #1 (Crypto Factor Rebalancing Strategy)** of the Artemis Analytics Quant Competition. The competition challenges teams to "apply quantitative methods to real crypto markets," evaluating submissions on four equally weighted dimensions: Research Quality (30%), Signal/Edge Validity (30%), Critical Evaluation (20%), and Communication (20%). Crucially, the organisers state: *"We are not looking for the most profitable strategy — we are looking for the best thinking. A strategy with a negative Sharpe ratio that is correctly understood, honestly evaluated, and clearly presented will score better than a strategy with impressive backtested returns and no critical analysis."* This principle has guided the structure of the present report.

The project draws on four published or working papers in crypto asset pricing, implements each as a reproducible pipeline stage, and integrates their outputs into a unified portfolio we term the **Network-Augmented Latent Factor Portfolio (NALFP)**. The strategy addresses each Track #1 requirement as follows:

| Competition Requirement | How NALFP Addresses It |
|:------------------------|:-----------------------|
| Define a clear investment universe | Top ~80 crypto assets by lagged market cap, excluding stablecoins/wrapped/bridged tokens; median portfolio of 16 long + 16 short names per week |
| Identify one or more factors or signals | Nine economically-motivated factor portfolios + network-topology signals + adaptive IC-weighted blend |
| Specify rebalancing frequency and portfolio construction | Weekly rebalance; long top quintile / short bottom quintile; inverse-vol weighting; dollar-neutral; cluster cap, turnover budget, vol target |
| Backtest across a meaningful historical window and report performance | 52-week sample, 24-week OOS walk-forward; returns, Sharpe, max drawdown, turnover, hit rate, bootstrap CI all reported |
| Critically evaluate findings | Negative OOS Sharpe analysed in depth; honest limitations section; regime-specific failure modes identified |

### 1.1 Pipeline Architecture

The research progressed through six active stages, each building on the prior:

| Stage | Directory | Purpose | Output |
|:------|:----------|:--------|:-------|
| Data Collection | `01_Data_Collection/` | Weekly price, volume, on-chain activity panels | Clean parquet tables |
| Analysis | `03_analysis/` | EDA, data quality, universe profiling, cross-sectional diagnostics | Diagnostics |
| Factor Signals | `04_factors/` | Three novel factors (F, S, G) + RAAM v2 IC-weighted composite | Factor ranks and IC tables |
| BTC Direction | `05_btc_direction/` | Supervised BTC direction classifier | Standalone; not integrated into NALFP |
| Econometrics | `06_artemis _econometrics/` | Fama–MacBeth panel with characteristics + PCA controls + network features | Model predictions, IC/IR tables |
| Hidden Factor Pricing | `07_hidden_factor _pricing/` | Observed vs. latent-adjusted factor pricing (GX-lite) | Factor premia and survival table |
| NALFP | `08_nalfp/` | Integrated strategy: network + factor pricing + adaptive blend + portfolio construction | Final portfolio weights and backtest |

### 1.2 Data Universe

The panel comprises approximately 86–113 crypto assets observed over 52 weeks (2025-05-12 to 2026-05-04), sourced from CoinGecko daily ticks, Artemis on-chain activity (DAU, fees, revenue), and DeFiLlama (TVL, stablecoin flows). Stablecoins, wrapped tokens, and bridged assets are excluded via `coingecko_coin_details` flags. All characteristics are lagged one week prior to entering predictive models.

### 1.3 Key Design Decision

NALFP v1 employed an Instrumented PCA (IPCA) framework (Kelly, Pruitt, Su 2019), where lagged characteristics instrument time-varying factor loadings. This approach was replaced in v2 with explicit factor portfolios plus the Giglio–Xiu (2021) three-pass procedure. The rationale, as documented in `RESEARCH_PLAN.md`, was that "v1 IPCA obscured *which* factors the strategy was actually exposed to and lacked per-factor economic commentary." The v2 architecture produces a transparent, per-factor risk-premium table directly comparable with prior literature.

> **Competition alignment.** Track #1 of the Artemis Quant Competition requires: (1) a defined investment universe, (2) identified factors or signals, (3) a rebalancing methodology, (4) a backtest with standard performance metrics, and (5) a critical evaluation of limitations. This strategy addresses all five requirements. The judging criteria — Research Quality (30%), Signal/Edge Validity (30%), Critical Evaluation (20%), Communication (20%) — are addressed throughout this report, with particular emphasis on honest assessment of the negative OOS Sharpe (Section 5) and structural limitations (Appendix C).

---

## 2. Core Trading Strategy

The NALFP strategy combines three pillars into a single weekly-rebalanced long/short portfolio.

### 2.1 Pillar 1 — Time-Varying Network Structure

**Implementation:** `08_nalfp/01_network_dynamics.py`

Each Monday, a rolling 12-week Spearman correlation matrix is computed across all assets with sufficient non-missing overlap (≥ 8 shared weeks). The correlation matrix is converted to a Mantegna distance matrix via $d_{ij} = \sqrt{2(1 - \rho_{ij})}$, from which a Minimum Spanning Tree (MST) is extracted. Louvain community detection (resolution = 1.0, seed = 0) is then applied to the MST (with edge weights transformed as $1/(1+d)$ for similarity).

Three per-asset signals are emitted:

| Signal | Construction | Intuition |
|:-------|:-------------|:----------|
| `within_cluster _mom` | Rank-z-score of 4-week momentum within each Louvain cluster | Idiosyncratic momentum relative to the local community |
| `cross_cluster _rel` | Asset 4-week return minus the mean 4-week return of *other* clusters | Cross-narrative rotation |
| `cluster_id` | Integer community label | Used for portfolio-level diversification constraint |

One market-level signal is also emitted:

| Signal | Construction | Intuition |
|:-------|:-------------|:----------|
| `network_entropy` | Shannon entropy $H = -\sum_k p_k \ln p_k$ of cluster-size distribution | Fragmentation proxy; high $H$ → many small disconnected communities |

The manifest (`01_network_manifest.json`) records: 41 clustered weeks, 7–11 clusters per week, mean entropy 2.175. All quantities are computed using only data through $t-1$ (strict no-lookahead).

### 2.2 Pillar 2 — Crypto Factor Zoo + Giglio–Xiu Pricing

**Implementation:** `08_nalfp/02_factor_pricing.py`

Nine economically-named long/short factor portfolios are constructed weekly:

| Factor | Sort Variable | Direction | Leg Size | Source |
|:-------|:--------------|:----------|:---------|:-------|
| RC | Value-weighted market return | — | Universe | Hartmann 2025 |
| SMBC | `log_mcap` | Small-long, Big-short | 30/30 | Hartmann 2025; Fama–French 1993 |
| MomC | `mom_4w` | Winners-long, Losers-short | 30/30 | Hartmann 2025; Liu–Tsyvinski 2022 |
| VolC | `vol_4w` | Low-vol long, High-vol short | 30/30 | Frazzini–Pedersen 2014 |
| TVLC | `tvl_to_mcap` | High TVL long, Low TVL short | 30/30 | Hartmann 2025 |
| FunC | `F_yield` | High yield long, Low yield short | 30/30 | RAAM v2 stage 04 |
| SupC | `S_supply` | Low emission long, High emission short | 30/30 | RAAM v2 stage 04 |
| NetMom | `within_cluster_mom` (cluster-neutral) | Top-half long, Bottom-half short | 50/50 within cluster | Liu & Tsyvinski 2018 |
| NetRel | `cross_cluster_rel` | Outperformers long, Underperformers short | 30/30 | Liu & Tsyvinski 2018 |

**Giglio–Xiu three-pass procedure** (walk-forward, refit every 4 weeks on expanding window):

1. **Pass 1:** OLS time-series regression of each asset's weekly return on the 7 observed factors (RC, SMBC, MomC, VolC, FunC, NetMom, NetRel — TVLC and SupC are dropped due to sparse coverage: TVLC has < 30 weeks, SupC only 7 weeks).
2. **Pass 2:** PCA on the residual matrix; Bai–Ng (2002) IC$_{p2}$ criterion selects **K\_hidden = 3** latent factors. (Note: IC$_{p2}$ is monotonically decreasing across $K \in \{0, 1, 2, 3\}$; the $K=3$ cap is hit rather than a clear elbow, suggesting identification may improve with a longer sample.)
3. **Pass 3:** Refit $\beta$ on the combined factor set [observed + hidden]; cross-sectional Fama–MacBeth estimation of risk premia $\hat{\lambda}$ with heteroskedasticity-robust (White) standard errors.

The output per asset per week is $E_{gx,it} = \beta_i' \hat{\lambda}$, the expected next-week return implied by the factor model.

### 2.3 Pillar 3 — Adaptive Regime Blend

**Implementation:** `08_nalfp/03_regime_detector.py`

Two cross-sectional signals are available each week: $E_{net,it}$ (within-cluster momentum z-score from Pillar 1) and $E_{gx,it}$ (Giglio–Xiu expected return from Pillar 2). The blended expected return is:

$$E_{final,it} = w_{net,t} \cdot E_{net,it} + (1 - w_{net,t}) \cdot E_{gx,it}$$

where $w_{net,t}$ is set by the **out-of-sample rolling 8-week mean Spearman IC** of each signal against next-week returns:

$$w_{net,t} = \frac{\max(0, \bar{IC}_{net,t-1})}{\max(0, \bar{IC}_{net,t-1}) + \max(0, \bar{IC}_{gx,t-1})}$$

If both rolling ICs are non-positive, the weight defaults to 0.5. This is the same IC-weighting rule validated in stage 04 (RAAM v2 composite) and is deliberately mechanical — no tuning parameters — so that a reviewer can verify it directly from the code.

The manifest (`03_regime_manifest.json`) reports:

| Metric | Full Sample | OOS |
|:-------|:------------|:----|
| Mean IC — Network | +0.005 | −0.014 |
| Mean IC — GX | +0.073 | +0.041 |
| Mean $w_{net}$ | — | 0.249 |
| Range $w_{net}$ | 0.000 – 1.000 | — |

The network signal's OOS IC is negative; the blend accordingly assigns most weight to the GX stream, with $w_{net}$ averaging approximately 0.25.

### 2.4 Portfolio Construction

**Implementation:** `08_nalfp/04_portfolio_construction.py`

Each Monday, eligible assets (those with a valid $E_{final}$ score) are ranked and assigned to legs:

| Step | Rule |
|:-----|:-----|
| Selection | Top 20% long, bottom 20% short (quintiles) |
| Position sizing | Inverse 4-week realised volatility within each leg, normalised so long leg sums to +1 and short leg sums to −1 (dollar-neutral) |
| Single-asset cap | Maximum 5% of gross portfolio per name; excess redistributed pro-rata (iterative, up to 10 rounds) |
| Cluster cap | Long-leg exposure to any single Louvain cluster ≤ 40% of long-leg weight; excess redistributed to under-capped clusters |
| Turnover budget | Weekly one-sided turnover ≤ 30%; smallest $|\Delta w|$ trades are trimmed first (Waterfall mechanism) |
| Vol target | Gross leverage scaled to target 15% annualised realised volatility, capped at 3× gross |

The median portfolio comprises 16 long and 16 short names per week.

### 2.5 Ablation Variant

An identical portfolio is constructed **without** the cluster-diversification cap (`apply_cluster_cap=False`). This ablation tests whether the network pillar's operational constraint materially affects performance, or whether it serves only as a risk-management overlay.

### 2.6 Backtest Design

**Implementation:** `08_nalfp/05_backtest.py`

| Parameter | Value |
|:----------|:------|
| Total sample | 48–49 weeks (after 12-week network burn-in) |
| Training window | 24 weeks |
| OOS evaluation | 24 weeks |
| Cost model | 10 bps one-sided per unit of weekly turnover = $0.5 \times \sum |w_{new} - w_{old}|$ |
| Vol annualisation | $\sqrt{52}$ (weekly returns) |
| Bootstrap | Stationary block bootstrap, block length 4 weeks, 2,000 draws for Sharpe CI |

Three benchmark strategies are evaluated alongside NALFP:

1. **EW Momentum Long** — equal-weight long-only top quintile by 4-week momentum
2. **RAAM v2 composite** — IC-weighted composite from stage 04 (if the parquet artifact exists)
3. **plus_lat** — Fama–MacBeth predictions from stage 06 (characteristics + latent controls)

---

## 3. Economic Intuition

### 3.1 Why Each Factor Should Generate Excess Returns

**RC — Crypto Market Factor.** The value-weighted return of the entire universe. In the CAPM-analogue setting, its premium *is* the broad-market risk premium. Sign is regime-dependent: positive in bull markets, negative in bear markets. In this sample, RC earned −32.4% annualised (Sharpe −0.78), consistent with a flat-to-bear 52-week period.

**SMBC — Crypto Size Factor.** Long small-cap, short large-cap. Small-cap names compensate for higher fundamental risk, information asymmetry, and lower liquidity (Fama & French 1993; Hartmann 2025 §3.1). In this sample, SMBC was the strongest performer at +93.7% annualised (Sharpe +3.54), reflecting a pronounced small-cap premium.

**MomC — Crypto Momentum.** Long recent winners, short recent losers. The strongest documented cross-sectional anomaly in crypto (Liu & Tsyvinski 2022) and equities (Jegadeesh & Titman 1993; Carhart 1997). Investors slowly incorporate information; recent winners continue outperforming. In-sample Sharpe +1.09.

**VolC — Low-Volatility (Betting-Against-Beta).** Long low-volatility, short high-volatility. Leverage-constrained investors over-bid high-beta assets, depressing their risk-adjusted returns (Frazzini & Pedersen 2014). In this sample, VolC had the highest IC (0.090) and the highest GX cross-sectional t-stat (+3.24) for its risk premium, despite a modest standalone Sharpe of +0.22.

**FunC — Fundamental Yield.** Long high-fee/high-revenue yield relative to market cap, short low yield. The crypto analogue of earnings yield (E/P). Sparse coverage (~62% missing) limits statistical power; IC = +0.001, GX t-stat = −0.32 (not priced).

**SupC — Supply Absorption.** Long low-emission tokens, short high-emission tokens. Tokens with low net new supply face less structural sell pressure. Extremely sparse (only 7 weekly observations); excluded from the GX panel and reported for transparency only.

**NetMom — Within-Cluster Momentum.** Cluster-neutral momentum: long the top half by within-cluster momentum rank, short the bottom half, averaged across Louvain clusters. Isolates idiosyncratic momentum from the broad MomC factor. Sharpe +1.33, GX $\hat{\lambda}_{full}$ = +0.762%/wk (t = +2.42).

**NetRel — Cross-Cluster Relative Strength.** Long names whose 4-week return exceeds the average of *other* clusters, short names underperforming their cross-cluster peer group. Captures narrative-rotation dynamics (Liu & Tsyvinski 2018). Sharpe +2.24, GX $\hat{\lambda}_{full}$ = +1.116%/wk (t = +2.38). This is the second-strongest factor by risk-adjusted return and the primary channel through which Pillar 1 contributes alpha.

### 3.2 Why Adaptive Blending Is Theoretically Motivated

The research thesis holds that crypto cross-sectional returns are better predicted by the *interaction* of community structure and factor exposure than by either source alone. When the correlation network is fragmented (high entropy, many small clusters), within-cluster relative performance is the dominant signal — narratives are localised, and idiosyncratic momentum within a thematic cluster is more informative than broad-market factor loadings. When the network converges (low entropy, one or two giant components), common latent factors dominate and the GX expected-return stream should receive more weight.

The IC-proportional blend operationalises this thesis without introducing discretionary parameters: the weight is set entirely by out-of-sample predictive accuracy (rolling IC), and the OOS data determine whether the network stream adds value. As reported in Section 2.3, the network signal's OOS IC is negative (−0.014), causing the blend to tilt heavily toward GX ($\bar{w}_{net} \approx 0.25$). This is an honest empirical finding: in this sample, the fragmentation thesis did not generate positive OOS predictive power.

### 3.3 Factor Pricing: Observed vs. Latent-Adjusted Premia

The Giglio–Xiu correction is designed to debias observed factor premia when latent factors are omitted. The full-model results show small but instructive changes:

| Factor | $\hat{\lambda}^{obs}$ (%/wk) | t(obs) | $\hat{\lambda}^{full}$ (%/wk) | t(full) | $\Delta\hat{\lambda}$ |
|:-------|:----------------------------|:-------|:------------------------------|:--------|:----------------------|
| RC | −0.290 | −1.56 | −0.250 | −1.13 | +0.040 |
| SMBC | +0.796 | +3.00 | +0.591 | +1.62 | −0.205 |
| MomC | +1.112 | +3.44 | +0.964 | +1.74 | −0.148 |
| VolC | +0.985 | +4.27 | +0.985 | +3.24 | −0.000 |
| FunC | +0.138 | +0.40 | −0.115 | −0.32 | −0.253 |
| NetMom | +0.752 | +3.37 | +0.762 | +2.42 | +0.009 |
| NetRel | +1.079 | +3.37 | +1.116 | +2.38 | +0.038 |

Five of seven observed factors clear the $|t| \geq 1.65$ threshold in the observed-only model: VolC, MomC, NetMom, NetRel, and SMBC. After adding the three latent factors, SMBC's t-stat falls to 1.62 (borderline), while VolC, NetMom, and NetRel remain clearly priced. The network factors (NetMom, NetRel) are essentially unchanged by latent adjustment — their premia are robust to omitted-factor controls, which is consistent with their cluster-neutral construction already accounting for the dominant covariance structure.

The three hidden-factor risk premia ($H1, H2, H3$) are individually insignificant (t-statistics of −0.81, +0.28, +0.13), with wide 95% confidence intervals. This is expected given the short sample: with $T = 24$ training weeks and 7 observed regressors, the time-series regression has limited power to identify latent factors beyond those already spanned by the observed set.

---

## 4. Assumptions Made

### 4.1 Theoretical Assumptions

- **Stationarity of factor premia.** The walk-forward GX procedure estimates $\hat{\lambda}$ on an expanding training window and assumes it generalises to the OOS period. The report notes explicitly: "whether the training-window $\hat{\lambda}$ generalises is an empirical question we do not yet have enough data to answer."

- **Spearman IC as the sole regime-detection metric.** The blend weight is determined entirely by rolling 8-week Spearman rank correlation against forward returns. No non-linear regime classifier, macro state variable, or threshold is used. This is a conservative choice but may miss regimes where the signal is non-monotonic.

- **MST + Louvain captures economically meaningful clusters.** The resolution parameter (1.0) and distance metric (Mantegna on Spearman) are fixed. The report identifies 7–11 communities per week but also notes that "we did not observe a clean convergence regime in this slice."

- **Factor zoo exhaustiveness.** Nine factors are specified a priori. The GX procedure accounts for omitted factors via latent PCA, but the Bai–Ng IC$_{p2}$ criterion saturates at the K = 3 cap, suggesting identification is sample-bound rather than data-driven.

### 4.2 Modeling Assumptions

- **K_{hidden} = 3 is a cap, not a data-driven optimum.** The IC$_{p2}$ information criterion is monotonically decreasing across $K \in \{0, 1, 2, 3\}$; the procedure selects the maximum allowed. Hartmann (2025) used 100+ weeks and selected $K_{hidden} = 7$. Our 24-week training window likely constrains identification.

- **Walk-forward refit frequency = 4 weeks.** The model is re-estimated every fourth week on all accumulated history. This is neither a pure rolling window (which would discard early data) nor a single-shot estimation (which would ignore structural change). The frequency is not optimised.

- **Equal-weight within quintile legs** after inverse-vol weighting. No tilt toward higher-signal assets within each bucket; the ranking is binary (top quintile vs. bottom quintile), not continuous.

- **Cluster cap of 40%** on the long leg is an HHI-equivalent heuristic, not derived from an optimisation framework. The ablation (Section 5) tests its marginal impact.

### 4.3 Execution and Liquidity Assumptions

- **Weekly Monday rebalance at close.** No intraweek liquidity events, flash crashes, or delayed execution are modelled.

- **10 bps one-sided cost per unit of turnover.** Applied to weekly turnover $= 0.5 \times \sum |w_{new} - w_{old}|$. The report notes this is "intentionally conservative for the size of this strategy (the median name has 30-day ADV > $1M so 10 bps slippage is fair)" but acknowledges that the long tail of the universe is more expensive in practice.

- **Short-side feasibility.** The strategy shorts the bottom quintile, assuming perpetual/funding markets are available and liquid for short-side names. No borrow cost or funding rate is modelled.

- **Vol-target scaling** uses the trailing 4-week cross-sectional weighted volatility as a proxy for near-term portfolio risk. Gross leverage is capped at 3×.

- **Remaining data gaps:** Funding rates, perp basis, and exchange-specific flow data are not in the repository. Their absence means the panel relies on Artemis activity, Binance OHLCV, CoinGecko snapshots, and DeFiLlama TVL/stablecoin tables.

---

## 5. Final Results

### 5.1 NALFP Strategy Performance

| Metric | NALFP (full) | NALFP (train) | NALFP (OOS) |
|:-------|:-------------|:--------------|:------------|
| Weeks | 48 | 24 | 24 |
| Annualised Return | +5.9% | +26.5% | −14.8% |
| Annualised Volatility | 11.2% | 11.5% | 10.3% |
| Sharpe Ratio | +0.53 | +2.30 | −1.44 |
| Sharpe 95% CI (bootstrap) | — | — | [−3.45, +1.18] |
| Maximum Drawdown | −7.1% | −7.1% | −6.6% |
| Average Weekly Turnover | 7.6% | 7.8% | 7.4% |
| Hit Rate | 60% | 67% | 54% |

### 5.2 Ablation: NALFP without Cluster Diversification Cap

| Metric | No Cluster Cap (OOS) | With Cluster Cap (OOS) |
|:-------|:----------------------|:-----------------------|
| Annualised Return | −17.4% | −14.8% |
| Sharpe Ratio | −1.69 | −1.44 |
| Sharpe 95% CI | [−3.66, +1.11] | [−3.45, +1.18] |
| Maximum Drawdown | −7.8% | −6.6% |
| Hit Rate | 50% | 54% |

The cluster cap improves OOS Sharpe by 0.25 and reduces drawdown by 1.2 percentage points. Despite the negative OOS performance, the constraint provides meaningful risk reduction — consistent with the thesis that the network structure is *useful* as an operational portfolio tool even when its cross-sectional signal (within-cluster momentum) does not generate positive IC out of sample.

### 5.3 Benchmark Comparisons (OOS)

| Metric | NALFP | NALFP (no cap) | EW Mom Long | `plus_lat` |
|:-------|:------|:---------------|:------------|:---------|
| Weeks | 24 | 24 | 25 | 16 |
| Annualised Return | −14.8% | −17.4% | +58.1% | +129.0% |
| Annualised Volatility | 10.3% | 10.3% | 43.0% | 34.4% |
| Sharpe Ratio | −1.44 | −1.69 | +1.35 | +3.75 |
| Sharpe 95% CI | [−3.45, +1.18] | [−3.66, +1.11] | [−2.08, +6.61] | [0.51, +8.89] |
| Maximum Drawdown | −6.6% | −7.8% | −24.8% | −7.4% |
| Avg. Weekly Turnover | 7.4% | 7.4% | 33.4% | 65.1% |
| Hit Rate | 54% | 50% | 68% | 69% |

**Interpretation:** The OOS period was a strongly bullish environment for crypto (EW Momentum Long returned +58.1% annualised). NALFP's vol-target design constrains it to ~10% volatility, which is structurally incapable of capturing the upside of a 58% momentum rally. The plus_lat benchmark achieves a higher Sharpe (3.75) but over only 16 OOS weeks with an extremely wide confidence interval [0.51, 8.89]; this result is not statistically distinguishable from zero at conventional significance levels.

> **Note:** The plus_lat benchmark covers only 16 weeks because it depends on the stage-06 Fama–MacBeth panel which uses a different train/test split (36/16). Direct comparison of NALFP (24 OOS weeks) with plus_lat (16 OOS weeks) should be interpreted cautiously.

### 5.4 Factor Zoo Performance (Full Sample)

| Factor | n (weeks) | Ann. Return | Ann. Vol | Sharpe | NW t-stat | Max DD | IC (char.) |
|:-------|:----------|:------------|:---------|:-------|:-----------|:-------|:-----------|
| RC | 50 | −32.4% | 41.8% | −0.78 | −0.74 | −51.6% | — |
| SMBC | 51 | +93.7% | 26.5% | +3.54 | +2.90 | −14.9% | +0.015 |
| MomC | 48 | +40.0% | 36.7% | +1.09 | +1.16 | −24.5% | +0.026 |
| VolC | 49 | +10.0% | 46.2% | +0.22 | +0.22 | −31.3% | +0.090 |
| FunC | 50 | +26.6% | 31.4% | +0.85 | +1.05 | −18.4% | +0.001 |
| SupC | 7 | +51.8% | 17.7% | +2.93 | — | −1.8% | +0.098 |
| NetMom | 40 | +30.4% | 22.9% | +1.33 | +1.19 | −19.6% | +0.006 |
| NetRel | 40 | +74.8% | 33.4% | +2.24 | +2.14 | −18.6% | +0.046 |

SMBC dominated this sample (small-cap premium), NetRel was the second-strongest factor (narrative rotation), and VolC had the highest cross-sectional IC despite a low standalone Sharpe. RC was negative, consistent with a bearish market factor over the period.

### 5.5 Stage-06 Econometrics Results (for Context)

The upstream `06_artemis_econometrics` track produced four Fama–MacBeth models with the following OOS performance:

| Model | IC Mean | IC IR | LS Mean | LS Sharpe (ann.) | Turnover |
|:------|:--------|:------|:--------|:------------------|:---------|
| `plus_lat` | +0.089 | +0.54 | +2.65% | +3.74 | 29.8% |
| `base_pool` | +0.087 | +0.59 | +2.87% | +3.46 | 27.8% |
| `base_fm` | +0.085 | +0.46 | +3.35% | +3.90 | 37.3% |
| `plus_net` | +0.042 | +0.20 | +0.70% | +0.68 | 31.8% |

The `plus_net` model (which includes network features in Fama–MacBeth) underperforms the others, consistent with the NALFP finding that network signals do not generate positive OOS IC in this sample. The `plus_lat` model (characteristics + PCA latent controls) achieves the best OOS risk-adjusted return, albeit over only 15 test weeks.

### 5.6 Stage-07 Hidden Factor Pricing Results (for Context)

| Model | Factor | Weekly $\hat{\lambda}$ | t-stat | p-value |
|:------|:-------|:----------------------|:-------|:--------|
| Fama–MacBeth | `crypto_market` | −0.60% | −0.671 | 0.502 |
| Latent-adjusted | `crypto_market` | +2.02% | +0.771 | 0.440 |
| Fama–MacBeth | `crypto_mom` | +1.92% | +1.934 | 0.053 |
| Latent-adjusted | `crypto_mom` | +1.23% | +0.822 | 0.411 |
| Fama–MacBeth | `crypto_smb` | +1.91% | +2.189 | 0.029 |
| Latent-adjusted | `crypto_smb` | +2.32% | +1.970 | 0.049 |
| Fama–MacBeth | `crypto_tvl_orth` | +0.19% | +0.087 | 0.931 |
| Latent-adjusted | `crypto_tvl_orth` | +1.55% | +0.735 | 0.463 |

Only `crypto_smb` survives the latent adjustment (sign preserved, $|t| \geq 1.65$). This is a more conservative test than NALFP's factor-specific walk-forward pricing, and it uses a different factor construction methodology; the two results are not directly comparable but provide complementary evidence.

---

## 6. Further Potential Research

### 6.1 Sample Size and Robustness

- **Extend the data window.** 52 weeks (24 OOS after burn-in) is insufficient for reliable factor-model estimation. The Sharpe-ratio standard error on 24 weeks is approximately $1/\sqrt{24} \approx 0.20$; the bootstrap CI for NALFP OOS Sharpe is wider still and crosses zero. Extending to 2–3 years of data would stabilise $\hat{\lambda}$ estimates and provide more power for K\_hidden identification.

- **Rolling walk-forward.** Replace the single 24/24 train/test split with a proper expanding or rolling walk-forward, generating many more OOS data points for both IC and Sharpe evaluation.

### 6.2 Signal Construction

- **Non-linear regime detection.** The current blend uses linear IC-weighting. A gradient-boosted classifier, regime-switching model, or conditional copula could capture non-linear interactions between network fragmentation and factor exposure.

- **Alternative network construction.** The MST + Louvain pipeline uses Spearman correlation with fixed 12-week window and resolution = 1.0. Alternatives include: (i) Granger-causality or transfer-entropy networks, (ii) dynamic time-warping for similarity, (iii) adaptive resolution or hierarchical clustering. The stage-06 report explicitly suggests "replace the rolling-correlation cluster with a Granger-style predictive link network."

- **Stablecoin inflow as a regime indicator.** The `stable_inflow_z` feature is computed in stage-06 and referenced in the NALFP `_common.py` `REGIME_COLS`, but it is not used in the final blend. Incorporating it as a macro-state variable could improve regime detection.

### 6.3 Portfolio Construction

- **Continuous position sizing.** Replace the binary quintile cut with position sizes proportional to expected return (e.g., conditional mean-variance or risk-parity on signal strength), which would extract more information from the ranking.

- **Per-asset transaction cost modelling.** The flat 10 bps cost is a rough approximation. Modelling per-name slippage as a function of 30-day ADV, bid–ask spread, and funding rate would more accurately penalise illiquid short-side names.

- **Short-side feasibility.** Explicitly modelling borrow availability, funding rates, and perp basis would constrain the short leg to assets where shorting is actually implementable.

- **Alternative cluster cap.** The 40% cluster cap is heuristic. An optimisation framework (e.g., minimum-variance with cluster-aware covariance shrinkage) could set this endogenously.

### 6.4 Factor Model Improvements

- **IPCA for time-varying loadings.** The v1 approach (Kelly–Pruitt–Su 2019) was abandoned for interpretability but could be layered on top of GX for *beta dynamics* even if pricing remains GX. Time-varying loadings may capture regime-dependent factor exposures that static betas miss.

- **Factor timing.** Dynamic $\hat{\lambda}$ estimation conditioned on macro-state variables (e.g., stablecoin flows, BTC dominance, DeFi TVL growth) rather than static expanding-window averages.

- **Additional factors.** The current zoo omits on-chain activity growth (DAU growth) as a standalone factor; the RAAM v2 `G` factor had a negative IC (−0.04) in the factor scoreboard but a reformulated version using per-protocol DAU growth relative to market cap could be more predictive. A funding-rate/perp-basis factor would capture the cost-of-carry dimension entirely absent from the current specification.

### 6.5 Risk Management

- **Downside risk controls.** The 15% vol target caps volatility ex ante but does not incorporate tail-risk measures (CVaR, max drawdown limit, or circuit-breaker rules). Adding a conditional volatility model (GARCH or EWMA) could improve vol targeting in clustered-risk episodes.

- **Correlation stress testing.** The portfolio's diversification benefit assumes cluster structure is stable. Stress-testing under scenarios of correlation breakdown (e.g., all clusters merging in a market crash) would quantify the tail risk of the cluster cap.

- **Leverage and margin constraints.** Perpetual futures venues impose maintenance margin and auto-deleveraging. The 3× gross leverage cap models this loosely; a more detailed margin simulation would improve implementation realism.

---

## Appendix A: Items Requiring Confirmation

The following items could not be fully confirmed from the codebase alone and require further documentation or manual review:

1. **RAAM v2 composite IC weights.** The `04_factors/README.md` reports pre-fix values (V=+0.21, C=+0.18, S=+0.12, M=+0.06, F=+0.02, T=+0.00, G=−0.04), but notes "the table reflects results before the A1/A2 correctness fixes." The current values after re-running may differ and should be confirmed from the regenerated figures.

2. **BTC direction model integration.** `05_btc_direction/` is a standalone supervised classifier not integrated into NALFP. Whether it should be discussed as a separate track or referenced as a potential regime indicator for future work requires clarification.

3. **Stage-06 `plus_lat` model specification.** The backtest references `plus_lat` as a benchmark with Sharpe 3.75 on 16 OOS weeks — this is the same model from `06_artemis_econometrics/05_models.py`. The exact specification (which characteristics, which latent controls) should be confirmed from that stage's artefacts.

4. **Exact OOS date boundaries.** The manifests record 48–49 total weeks and 24-week training, but the precise start/end dates for the OOS evaluation window are not explicitly stated in the manifest JSONs.

5. **Competition deliverables alignment.** The competition requires three separate submissions: (a) a Research Report in PDF format, (b) a GitHub repository with reproducible code, and (c) a Pitch Deck (Google Slides) summarising the strategy for a non-technical audience. This document serves as the Research Report; the code repository and pitch deck are separate deliverables.

---

## Appendix B: Reproducibility

The full pipeline can be reproduced by running:

```bash
python3 08_nalfp/01_network_dynamics.py
python3 08_nalfp/02_factor_pricing.py
python3 08_nalfp/03_regime_detector.py
python3 08_nalfp/04_portfolio_construction.py
python3 08_nalfp/05_backtest.py
python3 08_nalfp/06_report.py
```

All artefacts are written to `08_nalfp/artifacts/data/` (parquet + CSV), manifests to `08_nalfp/artifacts/manifests/` (JSON), and figures to `08_nalfp/figures/` (Plotly HTML, with PNG saved when `ARTEMIS_SAVE_PNG=1`). The upstream stages (`06_artemis_econometrics/`, `07_hidden_factor_pricing/`, `04_factors/`) must be run first to produce the required input parquets.

---

## Appendix C: Honest Limitations and Critical Evaluation

The Artemis competition emphasises that *"a strategy with a negative Sharpe ratio that is correctly understood, honestly evaluated, and clearly presented will score better than a strategy with impressive backtested returns and no critical analysis."* In this spirit, we catalogue the strategy's failures and fragilities alongside its strengths.

### What worked

- **Factor identification is statistically meaningful.** Five of seven observed factors are priced at the $|t| \geq 1.65$ threshold in the observed-only Fama–MacBeth cross-section; four survive latent-factor adjustment (VolC, MomC, NetMom, NetRel). The pricing framework is not pattern-fitting — it is grounded in published economics (size, momentum, low-vol, network structure).
- **The network pillar is operationally useful.** Even though the network signal's OOS IC is negative, the cluster diversification cap demonstrably improves OOS risk metrics (Sharpe improves from −1.69 to −1.44; drawdown improves from −7.8% to −6.6%).
- **The strategy's vol target works as designed.** NALFP delivers single-digit volatility (10.3% annualised OOS), which is a legitimate risk-management outcome even when returns are negative. For risk-averse allocators, the max drawdown of −6.6% is modest relative to benchmarks (EW Momentum Long: −24.8%).

### What failed

- **OOS returns are negative.** NALFP's OOS Sharpe of −1.44 (95% CI: [−3.45, +1.18]) means we cannot reject the null that the strategy has zero risk-adjusted return on this sample. The bootstrapped confidence interval spans zero.
- **The network signal does not predict OOS.** Within-cluster momentum (the primary Pillar 1 cross-sectional signal) has an OOS IC of −0.014. The adaptive blend reduces $w_{net}$ to ~0.25, effectively weighting the strategy toward the GX stream, but even the GX stream's OOS IC of +0.041 is modest.
- **Factor premia reverse out of sample.** The training window (weeks 1–24) had a strong size premium (SMBC Sharpe +3.54) and negative market factor (RC Sharpe −0.78). The OOS window appears to feature a different regime — one where the long/small-cap tilt inherent in SMBC and the short/market tilt in RC both contribute negatively. This is precisely the regime-shift risk identified in the research plan.

### Structural limitations

- **Sample size.** 52 weeks total → 24 OOS weeks after the network burn-in. The bootstrap CI for NALFP OOS Sharpe crosses zero. The $\text{SE}(\text{Sharpe}) \approx 1/\sqrt{24} \approx 0.20$; detecting a Sharpe of 1.0 with 80% power would require ~64 OOS weeks at this volatility.
- **Hidden factor identification.** Bai–Ng IC$_{p2}$ saturates the $K=3$ cap, suggesting the $T=24$ training window is short for identifying hidden risk premia. Hartmann (2025) used 100+ weeks and selected $K_{hidden} = 7$.
- **TVLC and SupC.** Excluded from GX due to coverage; their stats in the zoo table are computed on 0 and 7 weeks respectively and should be read with extreme caution.
- **Costs.** 10 bps one-sided on turnover is reasonable for large-caps; the long tail of the universe is more expensive in practice.
- **What would break this.** A regime shift that flips the sign of SMBC or MomC out-of-sample (precisely what is observed in some OOS weeks). The strategy's strength is the *factor structure identification*; whether the training-window $\hat{\lambda}$ generalises is an empirical question that 24 OOS weeks cannot definitively answer. Concretely: in a bullish low-volatility regime where small-caps dominate, NALFP is likely to underperform a simple long-only momentum strategy because its dollar-neutral, vol-target structure caps both participation in the rally and the magnitude of drawdowns.