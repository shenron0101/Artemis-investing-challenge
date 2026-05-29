# Project Proposal: Network-Augmented Latent Factor Portfolio — A Weekly-Rebalanced Long/Short Crypto Factor Strategy

**Module:** Quantitative Trading Strategy  
**Date:** May 2026  

---

## 1. Project Title

**Network-Augmented Latent Factor Portfolio (NALFP): A Systematic Long/Short Cryptocurrency Factor Strategy with Network Topology and Adaptive Regime Blending**

## 2. Executive Summary

This project develops and critically evaluates a weekly-rebalanced, long/short cryptocurrency factor strategy that integrates three pillars: (1) cross-sectional factor portfolios grounded in published asset-pricing literature, (2) time-varying network topology derived from minimum spanning trees and community detection on return correlation matrices, and (3) adaptive signal blendingweighted by out-of-sample Information Coefficient (IC). The strategy is backtested over 48 weeks (24 in-sample, 24 out-of-sample) on a universe of approximately 80 crypto assets, with robust performance reporting, ablation analysis, and an honest assessment of a negative out-of-sample Sharpe ratio. The project openly documents where the strategy fails and why, in line with the principle that rigorous critical evaluation is more valuable than inflated backtested returns.

## 3. Investment Universe

The strategy operates on a dynamic universe of approximately 80–113 crypto assets, selected weekly as follows:

- **Eligibility:** Top assets by lagged market capitalisation, excluding stablecoins, wrapped tokens, and bridged assets (flagged via CoinGecko metadata).
- **Data sources:** CoinGecko (daily OHLCV), Artemis on-chain activity (DAU, fees, revenue), and DeFiLlama (TVL, stablecoin flows).
- **Minimum history:** Assets must have ≥ 8 overlapping weeks with sufficient price history for correlation matrix construction.
- **Median portfolio size:** 16 long + 16 short positions per week (top and bottom quintiles).

This universe construction avoids survivorship bias by using lagged market cap for inclusion and excluding synthetic/stablecoin assets that would distort factor signals.

## 4. Factor Identification and Economic Justification

### 4.1 Core Factor Zoo

Nine economically-motivated long/short factor portfolios are constructed weekly. Each factor has a clear theoretical foundation drawn from published research in both traditional equities and crypto asset pricing:

| Factor | Sort Variable | Direction | Economic Rationale | Key Reference |
|--------|-------------|-----------|-------------------|---------------|
| **RC** | Value-weighted market return | Market factor | Broad risk premium; analogous to equity market factor | Hartmann 2025 |
| **SMBC** | `log_mcap` | Small-long, Big-short | Small-cap premium: compensation for higher information asymmetry, lower liquidity, and greater fundamental risk in crypto | Fama & French 1993; Hartmann 2025 |
| **MomC** | `mom_4w` | Winners-long, Losers-short | Momentum: investors underreact to news; recent winners continue outperforming due to slow information diffusion and positive feedback trading | Jegadeesh & Titman 1993; Liu & Tsyvinski 2022 |
| **VolC** | `vol_4w` | Low-vol long, High-vol short | Betting-against-beta: leverage-constrained investors overbid high-beta assets, depressing their risk-adjusted returns | Frazzini & Pedersen 2014 |
| **TVLC** | `tvl_to_mcap` | High-TVL long, Low-TVL short | Network value: high TVL-to-market-cap ratios signal genuine usage relative to speculative valuation | Hartmann 2025 |
| **FunC** | `F_yield` | High-yield long, Low-yield short | Fundamental yield: crypto analogue of earnings yield (E/P); protocols generating real fees relative to market cap | RAAM v2 (this project) |
| **SupC** | `S_supply` | Low-emission long, High-emission short | Supply absorption: tokens with low net new supply face less structural selling pressure | RAAM v2 (this project) |
| **NetMom** | `within_ cluster_mom` | Top-half long, Bottom-half short (within cluster) | Cluster-neutral momentum: isolates idiosyncratic momentum from broad-market trend by ranking within Louvain communities | Liu & Tsyvinski 2018 |
| **NetRel** | `cross_ cluster_rel` | Outperformers long, Underperformers short | Cross-cluster relative strength: captures narrative rotation between crypto thematic clusters | Liu & Tsyvinski 2018 |

### 4.2 Network Topology Pillar

Beyond static cross-sectional factors, the strategy incorporates time-varying network structure as a novel signal source:

- **Construction:** Each week, a 12-week rolling Spearman correlation matrix is computed across all eligible assets. This is converted to a Mantegna distance matrix, from which a Minimum Spanning Tree (MST) is extracted. Louvain community detection (resolution = 1.0) then partitions the MST into 7–11 thematic clusters per week.
- **Signals:** Three per-asset signals (within-cluster momentum, cross-cluster relative strength, cluster label) and one market-level signal (Shannon entropy of cluster-size distribution as a fragmentation proxy).
- **Economic thesis:** When the correlation network is fragmented (many small clusters), narratives are localised and within-cluster relative performance is more informative. When the network converges, common latent factors dominate. The adaptive blend operationalises this thesis without discretionary parameters.

### 4.3 Latent Factor Pricing (Giglio–Xiu Three-Pass Procedure)

To address omitted-variable bias in observed factor premia, the strategy applies the Giglio & Xiu (2021) three-pass procedure in walk-forward mode:

1. **Pass 1:** Time-series regression of each asset's weekly return on the 7 observed factors with sufficient coverage.
2. **Pass 2:** PCA on the residual matrix; Bai–Ng IC<sub>p2</sub> criterion selects K<sub>hidden</sub> = 3 latent factors.
3. **Pass 3:** Cross-sectional Fama–MacBeth estimation of risk premia λ̂ on the combined observed + latent factor set, with heteroskedasticity-robust (White) standard errors.

This produces per-asset expected returns (E<sub>gx,it</sub>) that are debiased for latent factor exposure — a significant methodological improvement over raw factor sort returns.

### 4.4 Adaptive Regime Blend

The final signal combines the network momentum stream and the GX expected-return stream using out-of-sample IC-proportional weighting:

$$E_{final,it} = w_{net,t} \cdot E_{net,it} + (1 - w_{net,t}) \cdot E_{gx,it}$$

where w<sub>net,t</sub> is set by the rolling 8-week mean Spearman IC of each stream against next-week returns. If both ICs are non-positive, the weight defaults to 0.5. This is a mechanical, parameter-free blend — no optimisation or discretionary choices.

## 5. Portfolio Construction Methodology

| Step | Rule | Rationale |
|------|------|-----------|
| **Selection** | Top 20% long, bottom 20% short (quintile cut on E<sub>final</sub>) | Extracts signal from cross-sectional dispersion while limiting portfolio size |
| **Position sizing** | Inverse 4-week realised volatility within each leg, normalised to long = +1, short = −1 (dollar-neutral) | Low-vol names receive larger weights; dollar-neutral construction removes directional market exposure |
| **Single-asset cap** | Maximum 5% of gross portfolio per name; excess redistributed pro-rata (iterative, up to 10 rounds) | Prevents concentration in any single asset |
| **Cluster diversification cap** | Long-leg exposure to any single Louvain cluster ≤ 40% | Limits thematic overconcentration; tested via ablation |
| **Turnover budget** | Weekly one-sided turnover ≤ 30%; smallest |Δw| trades trimmed first (waterfall mechanism) | Controls transaction costs and prevents excessive churn |
| **Vol target** | Gross leverage scaled to target 15% annualised realised volatility, capped at 3× gross | Risk-management overlay; constrains portfolio to pre-specified risk budget |

The strategy rebalances weekly on Monday at market close.

## 6. Backtest Design and Implementation

### 6.1 Walk-Forward Framework

| Parameter | Value | Justification |
|-----------|-------|---------------|
| Total sample | 48–49 weeks (after 12-week network burn-in) | 52-week full panel minus burn-in |
| Training window | 24 weeks | Expanding window for factor premia estimation |
| OOS evaluation | 24 weeks | Holdout for genuine out-of-sample performance |
| Re-estimation frequency | Every 4 weeks | Walk-forward; expanding window, not rolling |
| Cost model | 10 bps one-sided per unit of weekly turnover | Conservative for median-name liquidity; = 0.5 × Σ|w<sub>new</sub> − w<sub>old</sub>| |
| Vol annualisation | √52 (weekly returns) | Standard for weekly return compounding |
| Bootstrap | Stationary block bootstrap, block length 4 weeks, 2,000 draws | For Sharpe ratio confidence intervals |

### 6.2 No-Lookahead Guarantees

- All characteristics are lagged one week prior to entering predictive models.
- Portfolio weights at week t use only information available at t − 1.
- Factor premia are estimated on expanding training windows only.
- The 12-week correlation window for network construction uses only historical returns.

### 6.3 Benchmarks

Three benchmark strategies are evaluated alongside NALFP:

1. **Equal-Weight Momentum Long** — naive long-only top-quintile momentum strategy (no short leg, no vol targeting).
2. **RAAM v2 Composite** — IC-weighted multi-signal composite from the upstream factor signal stage.
3. **plus_lat** — Fama–MacBeth predictions from the stage-06 econometrics model (characteristics + PCA latent controls).

### 6.4 Summary Statistics Reported

For all strategies and factors:

- Annualised return, annualised volatility, Sharpe ratio
- Maximum drawdown
- Average weekly turnover
- Hit rate (% of positive-return weeks)
- Newey–West t-statistics on factor premia
- Bootstrap 95% confidence intervals for Sharpe ratios
- Cross-sectional Information Coefficient (IC) and IC Information Ratio (IR)

### 6.5 Ablation Analysis

An ablation variant removes the cluster diversification cap (`apply_cluster_cap=False`) to test whether the network pillar's operational constraint materially affects performance or merely serves as risk management.


## 7. Alignment with Module Assessment Criteria

| Criterion | How This Project Addresses It |
|-----------|-------------------------------|
| **(i) Fundamental economic justification** | Each of the nine factors is grounded in published asset-pricing literature. The network pillar is motivated by the thesis that crypto market structure is organised into thematic communities rather than a single latent factor. The adaptive blend is theoretically motivated by the interaction between network fragmentation and factor dominance. Factor premia are estimated via the Giglio–Xiu three-pass procedure, which corrects for omitted-variable bias — not merely pattern-fitting. |
| **(ii) Implementation of actual strategy** | The strategy is fully implemented in a reproducible Python pipeline (six sequential scripts). Portfolio construction includes position sizing, concentration limits, cluster diversification caps, turnover budgets, and volatility targeting. All code is version-controlled and artefacts are archived as parquet/CSV/JSON manifests. |
| **(iii) Quality and realism of backtest** | Walk-forward estimation with expanding training windows; no lookahead bias; 10 bps transaction costs; bootstrap confidence intervals for Sharpe ratios; ablation analysis testing the marginal impact of the cluster cap; three benchmark strategies for comparison; honest reporting of negative OOS performance. |
| **(iv) Discussion of performance metrics** | Comprehensive reporting of Sharpe ratios, maximum drawdown, turnover, hit rate, Newey–West t-statistics, IC/IR, and bootstrap CIs. An entire section is devoted to what failed and why, with structural limitations explicitly catalogued. The negative OOS Sharpe is not hidden — it is analysed in depth as the most important finding of the project. |

## 8. References

- Bai, J. & Ng, S. (2002). "Determining the Number of Factors in Approximate Factor Models." *Econometrica*, 70(1), 191–221.
- Carhart, M. (1997). "On Persistence in Mutual Fund Performance." *Journal of Finance*, 52(1), 57–82.
- Fama, E. & French, K. (1993). "Common Risk Factors in the Returns on Stocks and Bonds." *Journal of Financial Economics*, 33(1), 3–56.
- Frazzini, A. & Pedersen, L. (2014). "Betting Against Beta." *Journal of Financial Economics*, 111(1), 1–25.
- Giglio, S. & Xiu, D. (2021). "Portfolio Selection with Asset Pricing Factors." *Review of Financial Studies*, 34(8), 3816–3847.
- Hartmann, B. (2025). "Crypto Factors." Working paper.
- Jegadeesh, N. & Titman, S. (1993). "Returns to Buying Winners and Selling Losers." *Journal of Finance*, 48(1), 65–91.
- Kelly, B., Pruitt, S. & Su, Y. (2019). "Characteristics Are Covariances." *Journal of Finance*, 74(4), 1809–1854.
- Liu, Y. & Tsyvinski, A. (2022). "Risks and Returns of Cryptocurrency." *Review of Financial Studies*, 34(6), 2689–2727.
- Mantegna, R. (1999). "Hierarchical Structure in Financial Markets." *European Physical Journal B*, 11(1), 193–197.
