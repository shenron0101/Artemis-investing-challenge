# Research Plan: Network-Augmented Latent Factor Portfolio (NALFP)

## Context

The project already has three independent research lines:
- **06_artemis_econometrics**: Weekly cross-sectional Fama-MacBeth panel with network features (correlation-based clustering, degree centrality, within/cross-cluster momentum)
- **07_hidden_factor_pricing**: Latent factor extraction via PCA/SVD from the weekly return panel; observed factors (market, SMB, momentum, TVL); two-pass pricing
- **04_factors + RAAM v2**: IC-scored factor signals (V=+0.21, C=+0.18, S=+0.12, M=+0.06); IC-weighted composite rank

None of these lines currently feed into a unified, executable portfolio. The goal is to build one novel integrated system — **NALFP** — that:
1. Treats the time-varying correlation network as a source of factors (not just a constraint)
2. Uses IPCA-style expected-return estimation with characteristic-driven latent loadings
3. Constructs a weekly-rebalanced long-short portfolio whose weights adapt to regime signals

---

## Research Thesis

**Cryptocurrency cross-sectional returns are better predicted by the interaction of community structure and fundamental factor exposure than by either alone.** When the correlation network is fragmenting (clusters diverging), within-cluster momentum is strongest. When the network is converging (broad risk-on/risk-off), latent common factors dominate. An adaptive weighting scheme that detects the regime and shifts factor weights accordingly should produce a long-short portfolio with higher risk-adjusted returns than a static composite.

---

## Architecture Overview

```
Weekly data pull (Monday)
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  PILLAR 1: Time-Varying Network                                 │
│  Rolling 12-week return correlation → Louvain community         │
│  detection → cluster membership matrix C_t                      │
│  Derives: within_cluster_mom, cross_cluster_rel,                │
│           network_entropy (fragmentation signal)                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  PILLAR 2: Hidden Factor Pricing (IPCA)                         │
│  Instruments = observable characteristics at t-1                │
│  (M, V, C, F, S, within_cluster_mom, network_entropy)           │
│  → time-varying factor loadings β_it(Z_it)                      │
│  → latent risk premia λ_t via cross-sectional Fama-MacBeth      │
│  Output: expected_return_it for each asset each week            │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  PILLAR 3: Adaptive Portfolio Construction                      │
│  Regime detector: network_entropy + stablecoin_inflow_z         │
│  → shift factor weights (network-dominant vs. macro-dominant)   │
│  → long top quintile of expected_return, short bottom quintile  │
│  → constrain: cluster diversification, turnover ≤ 30%,         │
│               vol-target 15%, max weight 5% per asset           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
08_nalfp/
  RESEARCH_PLAN.md              This document
  01_network_dynamics.py        Pillar 1: time-varying network + community detection
  02_ipca_pricing.py            Pillar 2: IPCA expected-return estimation
  03_regime_detector.py         Regime signal: network entropy + macro state
  04_portfolio_construction.py  Pillar 3: long-short portfolio + constraints
  05_backtest.py                Full OOS walk-forward backtest
  06_report.py                  IC decomposition, attribution, Sharpe, drawdown
```

---

## Step 1 — Pillar 1: Time-Varying Network (`01_network_dynamics.py`)

**Inputs**: `coingecko_daily_ticks.parquet` (prices), `asset_master.parquet`

**Procedure**:
1. Compute weekly log-returns for all 113 assets (Monday-to-Monday, consistent with panels in 06)
2. Each Monday: build rolling 12-week pairwise Spearman correlation matrix Σ_t using only data through t-1 (strict no-lookahead)
3. Convert to distance matrix: `d_ij = √(2(1 − ρ_ij))` — standard correlation-to-distance transform from the crypto network paper
4. Run Louvain community detection on the minimum spanning tree (MST) of the correlation graph — MST reduces noise from spurious correlations
5. Assign each asset to cluster k at time t: produces membership vector C_t ∈ {1..K}
6. Compute three network-derived signals per asset per week:
   - `within_cluster_mom_it` = rank of asset i's 4-week return within its cluster k (higher = outperforming its community)
   - `cross_cluster_rel_it` = asset's 4-week return minus its cluster's average return
   - `network_entropy_t` = Shannon entropy of cluster size distribution = −Σ p_k log(p_k) (high = fragmented, low = concentrated)
7. Track cluster membership transition matrix week-over-week

**Key Design Choices**:
- 12-week rolling window: balances responsiveness with noise (tested in 06_artemis_econometrics)
- Louvain on MST not full graph: prevents spurious clusters from weak correlations
- Spearman not Pearson: robust to fat-tailed crypto returns

**Reuses**: `06_artemis_econometrics/03_network_features.py` pairwise correlation logic — extend it

---

## Step 2 — Pillar 2: IPCA Expected-Return Estimation (`02_ipca_pricing.py`)

**Inputs**: Weekly return panel from 06, factor signals from 04, network signals from Step 1

The key innovation over existing 07_hidden_factor_pricing work is replacing static beta estimation with **Instrumented PCA** (Kelly, Pruitt & Su 2019):

1. Assemble instrument matrix **Z_it** (N×L), each row = asset i's observable characteristics at t-1:
   - Existing factors: M (4-week momentum), V (volatility rank), C (correlation rank), F (fundamental yield), S (supply absorption)
   - Pillar 1 outputs: `within_cluster_mom`, `cross_cluster_rel`
   - Macro: `stable_inflow_z` (stablecoin inflow z-score from 06 panel)
   - Total L ≈ 8 instruments

2. Factor loadings time-vary: β_it = Z_it × Γ, where Γ (L×K) maps characteristics to K latent factors

3. Estimate Γ and latent factors F_t jointly by alternating least squares:
   - For fixed Γ: F_t = (Z_t Γ)ᵀ R_t via OLS cross-sectionally each week
   - For fixed F_t: update Γ by regressing returns onto Z_t-implied loadings
   - K=3 latent factors (consistent with PCA analysis in 07)

4. Expected return: `E[r_it+1] = Z_it × Γ × λ` where λ = latent risk premia estimated from time series of F_t

5. Survival filter: retain factor k only if |t(λ_k)| ≥ 1.65 (same rule used in 07_hidden_factor_pricing)

**Why IPCA over standard PCA**: Static PCA (as in 07) uses fixed loadings and cannot use time-varying characteristics to predict future returns. IPCA loadings vary with characteristics — when an asset's momentum rank changes, its effective beta changes automatically.

**Reuses**: `07_hidden_factor_pricing/04_price_models.py` Fama-MacBeth step; `06_artemis_econometrics/01_build_panel.py` weekly panel

---

## Step 3 — Regime Detector (`03_regime_detector.py`)

**Purpose**: Determine each week whether the market is in a *network-fragmented* regime (cluster structure dominates) or a *macro-driven* regime (common latent factors dominate), then blend the two signal streams accordingly.

**Procedure**:
1. Compute rolling 8-week IC for two signal streams:
   - `IC_net_t` = rolling mean IC of `within_cluster_mom` against h=1w forward returns
   - `IC_ipca_t` = rolling mean IC of IPCA expected-return against h=1w forward returns
2. Adaptive weight: `w_net_t = IC_net_t / (IC_net_t + IC_ipca_t)` — IC-proportional blend (same validated approach as RAAM v2 IC-weighting)
3. Final expected return: `E_final_it = w_net_t × E_net_it + (1 − w_net_t) × E_ipca_it`

The weights are determined by *out-of-sample predictive accuracy* (rolling IC), not by subjective tuning — scientifically clean.

---

## Step 4 — Adaptive Portfolio Construction (`04_portfolio_construction.py`)

**Long-Short Construction**:
1. Rank all non-excluded assets by `E_final_it` each week
2. Long: top quintile (~22 assets); Short: bottom quintile (~22 assets)
3. Liquidity screen for shorts: require 30-day average dollar volume > $1M

**Position Sizing**:
- Within each leg: weight by inverse realized volatility (4-week): `w_i ∝ 1/σ_i`
- Normalize: long leg sums to +1, short leg sums to −1 (dollar-neutral)

**Constraints (applied sequentially)**:
1. **Cluster diversification**: no single cluster > 40% of long-leg weight (prevents narrative-bubble concentration — the key improvement over RAAM v2)
2. **Turnover budget**: if new portfolio requires turnover > 30%, trim smallest |Δw| trades first (greedy control, consistent with Waterfall rebalancing paper)
3. **Max single-asset weight**: 5% of total portfolio value per leg
4. **Volatility target**: scale to 15% annualized realized vol (4-week rolling)

---

## Step 5 — Walk-Forward Backtest (`05_backtest.py`)

**Period**: 2025-05-12 to 2026-05-10 (52 weeks)
**Train window**: first 36 weeks (fit IPCA Γ, estimate λ)
**OOS evaluation**: last 16 weeks — consistent with 06_artemis_econometrics split

**Metrics**:
- Annualized return, Sharpe ratio, max drawdown
- Weekly IC (rolling 8-week average)
- Average weekly turnover (% of portfolio)
- Long-leg and short-leg P&L attribution separately
- Cluster HHI over time (diversification quality)
- Factor attribution: network signal vs. IPCA signal contribution

**Benchmarks**:
- RAAM v2 static composite (equal-weight, no network constraint) from 04
- plus_lat Fama-MacBeth from 06_artemis_econometrics (IC IR = +0.54, LS Sharpe = +3.74)
- Equal-weight long-only top quintile (momentum baseline)

---

## Step 6 — Report (`06_report.py`)

Ten-section research summary:
1. Hypothesis and motivation
2. Data summary (universe, coverage, exclusions)
3. Network dynamics over time (cluster count, entropy, MST visualization at 3 time points)
4. IPCA factor loadings (Γ heatmap, λ estimates with t-stats and survival filter)
5. Regime detector calibration (IC_net vs IC_ipca time series, adaptive weight w_net_t)
6. Expected-return signal quality (IC, rank autocorrelation)
7. Portfolio characteristics (turnover, HHI, vol-target compliance over OOS period)
8. OOS backtest performance vs. all three benchmarks
9. Factor attribution (network vs. IPCA marginal contribution)
10. Limitations: Artemis dimension API P0, DeFiLlama fees time series P1, short history

---

## Data Inputs Required

| Input | Source file | Status |
|---|---|---|
| Weekly log-returns, 113 assets | `coingecko_daily_ticks.parquet` | Ready |
| Factor signals M, V, C, F, S | `04_factors/`, `06_artemis_econometrics/02_characteristics.py` | Ready |
| Stablecoin inflow z-score | `06_artemis_econometrics/01_build_panel.py` | Ready |
| Asset exclusion flags | `coingecko_coin_details.parquet` | Ready |
| Artemis DAU/fees/revenue | `artemis_activity_long.parquet` | Ready (partial) |

No new data collection required.

---

## Files to Create / Modify

| File | Action |
|---|---|
| `08_nalfp/01_network_dynamics.py` | Create |
| `08_nalfp/02_ipca_pricing.py` | Create |
| `08_nalfp/03_regime_detector.py` | Create |
| `08_nalfp/04_portfolio_construction.py` | Create |
| `08_nalfp/05_backtest.py` | Create |
| `08_nalfp/06_report.py` | Create |
| `06_artemis_econometrics/03_network_features.py` | Extend: expose MST + Louvain as importable functions |
| `07_hidden_factor_pricing/04_price_models.py` | Extend: add IPCA alternating-LS estimator |

---

## Verification Checklist

- [ ] MST always produces connected graph across all 52 weeks
- [ ] Louvain cluster count is stable (2–6 clusters) — if K=1 or K=N, window length or distance metric is wrong
- [ ] IPCA in-sample R² > static PCA R² (K=3)
- [ ] λ signs are economically intuitive: momentum (+), high-vol (−), supply-absorbing (+)
- [ ] IC_net is higher in high-entropy weeks; IC_ipca higher in low-entropy weeks (regime thesis validation)
- [ ] Long leg is dollar-neutral vs. short leg at every rebalance date
- [ ] Cluster HHI < 0.40 on long leg at every rebalance date
- [ ] Weekly turnover ≤ 35% in all OOS weeks
- [ ] OOS IC IR > +0.54 (beats plus_lat benchmark) to justify the added complexity

---

## Scientific Novelty Statement

The three source papers are:
- *A Time-Varying Network for Cryptocurrencies* — community detection as portfolio constraint
- *Crypto Pricing with Hidden Factors* — latent factor pricing with external inputs
- *RAAM* — IC-weighted composite with turnover control

None of them use network community structure as an *instrument* for latent factor loadings. The novel contribution here is feeding network topology signals (within-cluster momentum, network entropy) into the IPCA characteristic matrix Z_it — so the topology of the correlation graph shapes how standard factors load onto latent risks, and the degree of network fragmentation determines which signal stream the portfolio trusts more each week.
