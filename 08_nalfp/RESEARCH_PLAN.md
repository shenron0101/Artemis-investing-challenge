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

## Step 2 — Pillar 2: Crypto Factor Zoo + Giglio-Xiu Pricing (`02_factor_pricing.py`)

The first version of this pillar used Instrumented PCA (Kelly-Pruitt-Su 2019) on lagged characteristics. v2 replaces that with **explicit factor portfolios + Giglio-Xiu (2021) three-pass hidden-factor pricing**. The change is motivated by reviewer feedback that the v1 IPCA layer obscured *which* factors the strategy was actually exposed to and lacked per-factor economic commentary.

### 2.1 Factor zoo (9 named long/short portfolios)

| Factor | Construction | Source |
|---|---|---|
| RC | Value-weighted return of the universe | Hartmann 2025 |
| SMBC | Long bottom 30% by log-mcap, short top 30% | Hartmann 2025; FF 1993 |
| MomC | Long top 30% by mom_4w, short bottom 30% | Liu-Tsyvinski 2022 |
| VolC | Long bottom 30% by vol_4w (low-vol), short top 30% | Frazzini-Pedersen 2014 |
| TVLC | Long top 30% by tvl_to_mcap, short bottom 30% | Hartmann 2025; TVL Irrelevance 2025 |
| FunC | Long top 30% by F_yield = (fees+0.5·rev)/mcap, short bottom 30% | RAAM v2 stage 04 |
| SupC | Long top 30% by supply absorption, short bottom 30% | RAAM v2 stage 04 |
| NetMom | Within each cluster: long top half by within-cluster-momentum, short bottom half; average across clusters | Liu-Tsyvinski 2018 |
| NetRel | Long top 30% by (own 4w − mean 4w of other clusters), short bottom 30% | Liu-Tsyvinski 2018 |

Each factor is a *tradable* long/short equal-weight portfolio with a weekly return time series.

### 2.2 Giglio-Xiu three-pass framework

Pass 1 — for each asset, OLS time-series regression of returns on the 9 observed factor returns → β_i^obs and residuals ε_i.

Pass 2 — PCA on the residual matrix; choose the number of latent factors K_hidden by Bai-Ng (2002) IC_p2; the top K_hidden principal components are F^hidden_t.

Pass 3 — refit β on the combined factor matrix [F^obs, F^hidden]; run cross-sectional Fama-MacBeth to estimate λ̂ with heteroskedasticity-robust SE.

Walk-forward expected return: E[r_{i,t+1}] = β_i' λ̂, with β and λ̂ refit every 4 weeks on the expanding training window.

### 2.3 Why GX over IPCA

GX directly addresses *omitted factor bias* in observed-only Fama-MacBeth, which is the relevant econometric concern for crypto pricing (cf. Hartmann 2025). IPCA solves a different problem (time-varying loadings via characteristics) and was harder to interpret per-factor. GX gives us a clean per-factor risk-premium table that can be compared with prior literature.

**Reuses**: stage-07 already produces `crypto_market`, `crypto_smb`, `crypto_mom`, `crypto_tvl` — we recompute these inside `02_factor_pricing.py` for consistency with the network panel timing, and add the five new factors (VolC, FunC, SupC, NetMom, NetRel).

---

## Step 3 — IC-Weighted Factor Signal Combination (`03_signal_combination.py`)

**Purpose**: Combine the six tradeable factor characteristics (SMBC, MomC, VolC, FunC, NetMom, NetRel) into a single per-asset expected-return signal using rolling out-of-sample IC weights. This replaces the earlier two-stream GX-vs-network adaptive blend from v2.

**Procedure**:
1. Load per-week Spearman IC for each factor from `factor_ic_timeseries.parquet` (written by `02_factor_pricing.py`).
2. Rolling 8-week mean IC, lagged 1 week — strictly OOS. Each factor's IC is direction-signed so positive IC means the characteristic predicts returns in the intended direction.
3. Positive-clipped IC-proportional weights:
   - `w_{k,t} = clip+(IC_roll_{k,t}) / sum_j clip+(IC_roll_{j,t})`
   - If all factors have non-positive IC, fall back to equal weight (1/6 each).
4. Per-asset expected return:
   - `E_final_{i,t} = sum_k w_{k,t} * sign_k * z_cs(c_{k,i,t})`
   - `z_cs` is the cross-sectional z-score within week t; `sign_k` is the factor direction (+1 / −1).

**Why IC-weighting over training-window λ̂**: The GX Fama-MacBeth λ̂ from v2 overfits on 24 training weeks — the OOS Sharpe was −1.44. Rolling IC uses only 8 past weeks but works on *standardised characteristics*, avoiding the magnitude overfit. A factor whose 8-week rolling IC turns negative gets zero weight automatically (regime adaptation without a separate regime detector).

**RC excluded** (it's a level factor, not sortable). **TVLC and SupC excluded** for sparse coverage (< 30 weeks in the 52-week sample).

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
