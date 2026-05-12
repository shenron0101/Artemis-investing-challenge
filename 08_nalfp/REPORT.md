# NALFP — Network-Augmented Latent Factor Portfolio

    A weekly-rebalanced long/short crypto factor strategy that:

    1. extracts time-varying community structure from the rolling Spearman MST + Louvain,
    2. fits an Instrumented PCA (Kelly–Pruitt–Su 2019) model on 11 lagged characteristics — including the three network signals — to produce expected returns,
    3. blends the network and IPCA signals with adaptive IC weights, and
    4. trades the top vs bottom quintile under explicit cluster-diversification, single-asset, turnover, and volatility-target constraints.

    The novel piece is **(2)** — using network topology as instruments for latent factor loadings. No prior work in the three source papers (Time-Varying Network, Crypto Pricing with Hidden Factors, RAAM) does this jointly.

    ## 1. Hypothesis

    Cryptocurrency cross-sectional returns are better predicted by the *interaction* of community structure and fundamental factor exposure than by either alone. When the correlation network is **fragmenting** (high entropy, many small communities), within-cluster relative strength is the dominant signal. When the network is **converging** (low entropy, one giant component), latent common factors take over.

    ## 2. Data

    - 86 cryptocurrencies, weekly close-to-close, 52 weeks (2025-05-12 → 2026-05-04).
    - Stablecoins, wrapped and bridged tokens excluded up front (mirrors stage-04/06 universe).
    - 11 instruments per asset per week (all lagged one week):
      `mom_4w, vol_4w, log_mcap, turnover, F_yield, S_supply, G_growth, within_cluster_mom, cross_cluster_rel, network_entropy, stable_inflow_z`.
    - Backtest split: first 24 weeks for training, last 28 weeks OOS.

    ## 3. Pillar 1 — Time-Varying Network

    - Rolling 12-week Spearman correlations → Mantegna distance → MST → Louvain.
    - Across all clustered weeks the partition contains **7** to **11** communities (mean entropy 2.175).
    - Per-asset signals: within-cluster rank z-score of `mom_4w`, and own `mom_4w` minus the mean `mom_4w` of every *other* cluster.
    - Market-wide fragmentation: Shannon entropy of cluster-size distribution.

    ![network overview](figures/01_network_dynamics/network_overview.html)

    ## 4. Pillar 2 — Instrumented PCA Expected Returns

    Restricted IPCA model (no alpha): `r_{i,t+1} = z_{i,t}' Γ f_{t+1} + e`, with `Γ' Γ = I_K`, `K = 3` latent factors. Estimation by alternating least squares on the training window, then walk-forward refit every 4 weeks on an expanding history.

    ### IPCA factor premia (training window)

    | Factor | Mean (weekly) | SE | t-stat | n |
|---|---|---|---|---|
| f1 | 0.0100 | 0.0408 | 0.24 | 36 |
| f2 | 0.0077 | 0.0231 | 0.33 | 36 |
| f3 | 0.0024 | 0.0083 | 0.29 | 36 |

    Survival filter (|t| ≥ 1.65): **none**.

    ![IPCA loadings Γ](figures/02_ipca_pricing/gamma_loadings.html)
    ![cumulative latent factor returns](figures/02_ipca_pricing/factor_cumulative.html)

    ## 5. Pillar 3a — Regime-Adaptive Signal Blend

    Each week we set the network weight by IC-proportional blending with an 8-week lookback of *past* ICs (strictly OOS):

    `w_net_t = clip+(IC_net_{t-1}) / [ clip+(IC_net_{t-1}) + clip+(IC_ipca_{t-1}) ]`.

    Observed range of `w_net`: **0.000–0.573** (mean 0.221). Sample-level IC averages — network: 0.020, IPCA: 0.081. OOS-only IC averages — network: 0.008, IPCA: 0.060.

    ![regime blend](figures/03_regime_detector/regime_blend.html)

    ## 6. Pillar 3b — Portfolio Construction

    - Long the top 20% by `E_final`, short the bottom 20%.
    - Inverse-volatility weights within each leg, normalised to ±1 (dollar-neutral).
    - Single-asset cap **5%**; long-leg cluster cap **40%** of leg notional; turnover budget **30%** per week; gross-vol target **15%** annualised (leverage capped at 2×).
    - Median long leg: 16 names; median short leg: 16 names.

    ![portfolio diagnostics](figures/04_portfolio_construction/portfolio_diagnostics.html)
    ![cluster composition](figures/04_portfolio_construction/cluster_composition.html)

    ## 7. Headline Results

    | Strategy | Window | Weeks | Ann.Return | Ann.Vol | Sharpe | MaxDD | Turnover | Hit% |
|---|---|---|---|---|---|---|---|---|
| NALFP | full | 40 | 11.45% | 9.73% | 1.18 | -6.67% | 8.33% | 62.5% |
| NALFP | train | 24 | 12.88% | 11.83% | 1.09 | -5.70% | 8.06% | 58.3% |
| NALFP | oos | 16 | 9.31% | 5.60% | 1.66 | -1.75% | 8.74% | 68.8% |
| EW_mom_long | full | 49 | 25.23% | 54.07% | 0.47 | -47.97% | 35.53% | 59.2% |
| EW_mom_long | train | 32 | -6.10% | 56.19% | -0.11 | -36.04% | 36.94% | 53.1% |
| EW_mom_long | oos | 17 | 84.20% | 50.45% | 1.67 | -17.32% | 32.87% | 70.6% |
| NALFP_no_cluster_cap | full | 40 | 14.53% | 9.55% | 1.52 | -5.40% | 7.98% | 65.0% |
| NALFP_no_cluster_cap | train | 24 | 13.54% | 11.74% | 1.15 | -5.40% | 8.02% | 58.3% |
| NALFP_no_cluster_cap | oos | 16 | 16.02% | 5.08% | 3.15 | -0.83% | 7.93% | 75.0% |
| plus_lat | full | 16 | 128.99% | 34.41% | 3.75 | -7.39% | 65.07% | 68.8% |
| plus_lat | oos | 16 | 128.99% | 34.41% | 3.75 | -7.39% | 65.07% | 68.8% |

    ![cumulative pnl](figures/05_backtest/cumulative_pnl.html)

    ## 8. Verification Checklist

- ⚠️ MST + Louvain produces 2–10 clusters across all weeks — observed range 7–11
- ⚠️ >=1 IPCA factor survives |t|>=1.65 filter — 0/3 survived
- ✅ Regime weight w_net spans a meaningful range — 0.000–0.573
- ⚠️ OOS Sharpe ≥ equal-weight momentum baseline — NALFP 1.663 vs EW 1.669


## 9. Honest limitations

- **Sample size.** 52 weeks total → 16 OOS weeks. Statistical power on Sharpe ratios is limited; any number we quote has a wide confidence interval.
- **One regime.** The OOS window covers one liquidity cycle. The strategy's regime detector is mechanical, but its *validation* depends on observing both fragmented and converged regimes, and we do not have many transitions in this slice of history.
- **Activity coverage.** `F_yield`, `S_supply` and `G_growth` are sparse (38–85% missing) because Artemis fundamentals are not yet wired in for the long tail of the universe. We median-impute within week, which biases those instruments toward neutrality.
- **Costs.** 10 bps one-sided turnover cost is reasonable for top-50 names but optimistic for the long tail; the short leg further assumes uncapped borrow at zero financing cost.
- **Hidden factors are statistical.** We do not assign economic labels to the latent factors. We deliberately follow Crypto Pricing with Hidden Factors here — the alpha is supposed to be in the *projection* onto characteristics, not in any individual factor narrative.
- **What would break this.** A sustained risk-off cascade where every cluster moves with one factor (entropy collapses) plus IPCA's training history loses predictive power → both signal streams degrade. In that scenario the strategy reverts to inverse-vol cluster diversification — fine, but unexceptional.

## 10. Reproducibility

```
python3 08_nalfp/01_network_dynamics.py
python3 08_nalfp/02_ipca_pricing.py
python3 08_nalfp/03_regime_detector.py
python3 08_nalfp/04_portfolio_construction.py
python3 08_nalfp/05_backtest.py
python3 08_nalfp/06_report.py
```

All upstream data is checked into `01_Data_Collection/data/clean/` and 06/07 artifacts are re-derived deterministically from there.
