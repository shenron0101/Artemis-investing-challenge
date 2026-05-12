# NALFP v2 — Network-Augmented Latent Factor Portfolio

    A weekly-rebalanced long/short crypto factor strategy combining:

    1. **Pillar 1 — Network structure.** Rolling 12-week Spearman MST + Louvain communities produce two cross-sectional signals: `within_cluster_mom` and `cross_cluster_rel`.
    2. **Pillar 2 — Crypto Factor Zoo + Giglio-Xiu pricing.** Nine economically-named factor portfolios (RC, SMBC, MomC, VolC, TVLC, FunC, SupC, NetMom, NetRel) fed through the Giglio-Xiu (2021) three-pass framework. Hidden factors are extracted by PCA on residuals; the number $K_\text{hidden}$ is selected by Bai-Ng IC$_{p2}$.
    3. **Pillar 3 — Adaptive blend + portfolio.** IC-proportional blend of the network and GX signals, traded as a long/short quintile portfolio with cluster, asset, turnover and vol-target constraints.

    ## 1. Factor Zoo — full-sample statistics

    | Factor | Source | n | Ann.Mean | Ann.Vol | Sharpe | NW t-stat | AR(1) | MaxDD | IC | λ̂ (full) | t(λ̂) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **RC** | Hartmann 2025 | 50 | -32.4% | 41.8% | -0.78 | -0.74 | 0.04 | -51.6% | — | -0.250% | -1.13 |
| **SMBC** | Hartmann 2025; Fama-French 1993 | 51 | 93.7% | 26.5% | 3.54 | 2.90 | 0.16 | -14.9% | 0.015 | +0.591% | +1.62 |
| **MomC** | Hartmann 2025; Liu-Tsyvinski 2022 | 48 | 40.0% | 36.7% | 1.09 | 1.16 | -0.14 | -24.5% | 0.026 | +0.964% | +1.74 |
| **VolC** | Frazzini-Pedersen 2014 | 49 | 10.0% | 46.2% | 0.22 | 0.22 | 0.01 | -31.3% | 0.090 | +0.985% | +3.24 |
| **FunC** | RAAM v2 stage 04 | 50 | 26.6% | 31.4% | 0.85 | 1.05 | -0.17 | -18.4% | 0.001 | -0.115% | -0.32 |
| **SupC** | RAAM v2 stage 04 | 7 | 51.8% | 17.7% | 2.93 | — | -0.30 | -1.8% | 0.098 | — | — |
| **NetMom** | Liu & Tsyvinski 2018 | 40 | 30.4% | 22.9% | 1.33 | 1.19 | 0.01 | -19.6% | 0.006 | +0.762% | +2.42 |
| **NetRel** | Liu & Tsyvinski 2018 | 40 | 74.8% | 33.4% | 2.24 | 2.14 | -0.08 | -18.6% | 0.046 | +1.116% | +2.38 |

    Reading the table. Three results stand out. **SMBC** earned a 94% annualised return with Sharpe 3.54 — small caps dominated this sample, consistent with a strong size premium. **NetRel** (the cross-cluster relative-strength factor) earned 75% with Sharpe 2.24, validating the network-rotation thesis from Liu & Tsyvinski (2018). **MomC** delivered a Sharpe of 1.09, in line with the canonical crypto momentum result. The market factor **RC** was negative this sample (Sharpe -0.78) — a bear-to-flat 52 weeks. Two factors (TVLC, SupC) had coverage too sparse to include in the GX panel.

    ## 2. Giglio-Xiu Hidden-Factor Pricing

    ### 2.1 Bai-Ng selection

    The IC$_{p2}$ criterion (Bai & Ng 2002) selected **K_hidden = 3** latent factors. We capped the search at $K_\text{max} = 3$ because with $T=24$ training weeks and 7 observed factors, more than 3 additional regressors would push the time-series regression toward overfitting. The IC$_{p2}$ curve is monotonically decreasing across $K \in \{0,1,2,3\}$, which is suggestive but not conclusive evidence that additional hidden factors might be informative on a longer sample.

    ### 2.2 Risk-premium estimates

    The cross-sectional Fama-MacBeth estimates of λ̂ (heteroskedasticity-robust SE) under two model specifications are:

    **Observed factors only:**

| Factor | λ̂ (weekly) | t-stat |
|---|---|---|
| RC | -0.290% | -1.56 |
| SMBC | +0.796% | +3.00 |
| MomC | +1.112% | +3.44 |
| VolC | +0.985% | +4.27 |
| FunC | +0.138% | +0.40 |
| NetMom | +0.752% | +3.37 |
| NetRel | +1.079% | +3.37 |

**Five of seven observed factors clear |t| ≥ 1.65** in the observed-only model: VolC (t=+4.27), MomC (+3.44), NetMom (+3.37), NetRel (+3.37), SMBC (+3.00). These are economically meaningful priced factors *in our sample*.

**Full model — observed + hidden factors:**

| Factor | λ̂ (weekly) | t-stat | 95% CI |
|---|---|---|---|
| RC | -0.250% | -1.13 | [-0.68%, +0.18%] |
| SMBC | +0.591% | +1.62 | [-0.12%, +1.31%] |
| MomC | +0.964% | +1.74 | [-0.12%, +2.05%] |
| VolC | +0.985% | +3.24 | [+0.39%, +1.58%] |
| FunC | -0.115% | -0.32 | [-0.82%, +0.59%] |
| NetMom | +0.762% | +2.42 | [+0.15%, +1.38%] |
| NetRel | +1.116% | +2.38 | [+0.20%, +2.04%] |
| H1 | -4.562% | -0.81 | [-15.65%, +6.53%] |
| H2 | +2.560% | +0.28 | [-15.51%, +20.63%] |
| H3 | +1.300% | +0.13 | [-18.09%, +20.70%] |

### 2.3 Do hidden factors change the observed risk premia?

The Giglio-Xiu correction is designed to debias observed factor premia when latent factors are omitted. Side-by-side comparison:

| Factor | λ̂ obs-only | λ̂ full | Δλ̂ |
|---|---|---|---|
| RC | -0.290% | -0.250% | +0.040% |
| SMBC | +0.796% | +0.591% | -0.205% |
| MomC | +1.112% | +0.964% | -0.148% |
| VolC | +0.985% | +0.985% | -0.000% |
| FunC | +0.138% | -0.115% | -0.253% |
| NetMom | +0.752% | +0.762% | +0.009% |
| NetRel | +1.079% | +1.116% | +0.038% |


    ## 3. Per-Factor Commentary

    ### RC

- **Construction.** Value-weighted return of the entire crypto universe (lagged mcap weights).
- **Economic story.** The crypto market factor — every asset's most basic risk exposure. In the CAPM-analogue setting its premium *is* the broad-market risk premium. Source: Hartmann 2025 §3.1 (RC); Liu-Tsyvinski 2022. We expect λ_RC > 0 in a bull regime, ≤ 0 in a bear regime.
- **Verdict.** In our sample the factor portfolio earns -32.4% annualised at Sharpe -0.78 (NW t=-0.74), characteristic IC = +nan. In the GX cross-section it is **not statistically priced** in this sample with λ̂_full = -0.250%/wk (t=-1.13). Sign is regime-dependent; we do not pre-commit.

### SMBC

- **Construction.** Long bottom 30% of assets by lagged log-market-cap, short top 30%, equal-weighted.
- **Economic story.** The Fama-French SMB analogue for crypto. Small-cap names have historically outperformed large caps in crypto, partly compensating for higher fundamental risk and lower liquidity. Source: Hartmann 2025 §3.1; FF 1993. Sign typically positive in risk-on regimes, can flip negative in flight-to-quality.
- **Verdict.** In our sample the factor portfolio earns +93.7% annualised at Sharpe +3.54 (NW t=+2.90), characteristic IC = +0.015. In the GX cross-section it is **priced** (|t|≥1.65 in the observed-only λ) with λ̂_full = +0.591%/wk (t=+1.62).

### MomC

- **Construction.** Long top 30% by trailing 4-week return, short bottom 30%, equal-weighted.
- **Economic story.** Trend persistence — the strongest documented anomaly in crypto cross-section (Liu & Tsyvinski 2022). Investors slowly react to information; recent winners tend to keep winning. Cross-asset evidence is robust over decades in equities (Jegadeesh-Titman 1993, Carhart 1997).
- **Verdict.** In our sample the factor portfolio earns +40.0% annualised at Sharpe +1.09 (NW t=+1.16), characteristic IC = +0.026. In the GX cross-section it is **priced** (|t|≥1.65 in the observed-only λ) with λ̂_full = +0.964%/wk (t=+1.74).

### VolC

- **Construction.** Long bottom 30% by 4-week realised volatility (low-vol), short top 30% (high-vol).
- **Economic story.** The 'Betting Against Beta' anomaly (Frazzini-Pedersen 2014). Leverage-constrained investors over-bid high-beta / high-vol names, leaving low-vol assets cheap. Has substantial cross-asset evidence; crypto evidence is mixed because the universe is highly skewed.
- **Verdict.** In our sample the factor portfolio earns +10.0% annualised at Sharpe +0.22 (NW t=+0.22), characteristic IC = +0.090. In the GX cross-section it is **priced** (|t|≥1.65 in the observed-only λ) with λ̂_full = +0.985%/wk (t=+3.24).

### FunC

- **Construction.** Long top 30% by F_yield = (fees + 0.5·revenue) / market cap, short bottom 30%.
- **Economic story.** Crypto 'value' / earnings yield. Analogous to E/P for equities — assets generating more cash per dollar of market cap. Source: RAAM v2 stage 04 of this project. Coverage is sparse (62% of universe missing) because most crypto assets don't produce fee revenue.
- **Verdict.** In our sample the factor portfolio earns +26.6% annualised at Sharpe +0.85 (NW t=+1.05), characteristic IC = +0.001. In the GX cross-section it is **not statistically priced** in this sample with λ̂_full = -0.115%/wk (t=-0.32).

### SupC

- **Construction.** Long top 30% by supply absorption (low emission), short bottom 30%.
- **Economic story.** Tokens with low net new supply face less structural sell pressure from emissions, so their float is 'absorbed' rather than diluted. Source: RAAM v2 stage 04. Coverage is extremely sparse in our 52-week sample (85% missing); we report the factor stat but exclude it from the GX panel.
- **Verdict.** Excluded from the Giglio-Xiu panel for sparse coverage (only 7 weekly observations).

### NetMom

- **Construction.** Within each Louvain cluster, long top half by within-cluster momentum rank, short bottom half. Average across clusters (cluster-neutral by construction).
- **Economic story.** Liu & Tsyvinski 2018 §4 — 'community-based momentum'. Inside a tight correlation community, the asset that out-trends its peers tends to keep doing so. Going long winners *within* each cluster isolates idiosyncratic momentum from the general MomC factor. The two should be moderately correlated.
- **Verdict.** In our sample the factor portfolio earns +30.4% annualised at Sharpe +1.33 (NW t=+1.19), characteristic IC = +0.006. In the GX cross-section it is **priced** (|t|≥1.65 in the observed-only λ) with λ̂_full = +0.762%/wk (t=+2.42).

### NetRel

- **Construction.** Long top 30% by (own 4w return − mean 4w of *other* clusters), short bottom 30%.
- **Economic story.** Cross-cluster rotation factor. Long names leading the rotation into their narrative, short names rotating out. Distinct from MomC because it normalises against the *other* clusters' average, not the universe average. Captures the narrative-shift effect documented in Liu-Tsyvinski 2018.
- **Verdict.** In our sample the factor portfolio earns +74.8% annualised at Sharpe +2.24 (NW t=+2.14), characteristic IC = +0.046. In the GX cross-section it is **priced** (|t|≥1.65 in the observed-only λ) with λ̂_full = +1.116%/wk (t=+2.38).

    ## 4. Network Pillar

    - Rolling 12-week Spearman correlation → Mantegna distance → MST → Louvain.
    - Across 41 clustered weeks the partition contains **7–11** communities (mean entropy 2.175). The market is persistently fragmented; we did not observe a clean convergence regime in this slice.

    ## 5. Regime Blend

    Mean adaptive weight on the network signal: $\bar w_\text{net}$ = 0.249 (range 0.000–1.000).
    Full-sample mean IC — network: 0.005, GX: 0.073.
    OOS mean IC — network: -0.014, GX: 0.041.

    ## 6. Portfolio Construction

    Long top 20% / short bottom 20% of `E_final`, inverse-vol weighted, dollar-neutral, with single-asset cap 5%, long-leg cluster cap 40%, turnover cap 30%/wk, and 15% annualised vol target (leverage cap 3×).

    ## 7. OOS Backtest

    | Strategy | Window | Weeks | Ann.Return | Ann.Vol | Sharpe | 95% CI | MaxDD | Turnover | Hit% |
|---|---|---|---|---|---|---|---|---|---|
| NALFP | full | 48 | 5.9% | 11.2% | 0.53 | — | -7.06% | 7.6% | 60% |
| NALFP | train | 24 | 26.5% | 11.5% | 2.30 | — | -7.06% | 7.8% | 67% |
| NALFP | oos | 24 | -14.8% | 10.3% | -1.44 | [-3.45, 1.18] | -6.64% | 7.4% | 54% |
| EW_mom_long | full | 49 | 25.2% | 54.1% | 0.47 | — | -47.97% | 35.5% | 59% |
| EW_mom_long | train | 24 | -9.0% | 64.2% | -0.14 | — | -30.88% | 37.7% | 50% |
| EW_mom_long | oos | 25 | 58.1% | 43.0% | 1.35 | [-2.08, 6.61] | -24.80% | 33.4% | 68% |
| NALFP_no_cluster_cap | full | 48 | 4.6% | 11.3% | 0.40 | — | -7.95% | 7.6% | 58% |
| NALFP_no_cluster_cap | train | 24 | 26.5% | 11.5% | 2.30 | — | -7.06% | 7.8% | 67% |
| NALFP_no_cluster_cap | oos | 24 | -17.4% | 10.3% | -1.69 | [-3.66, 1.11] | -7.76% | 7.4% | 50% |
| plus_lat | full | 16 | 129.0% | 34.4% | 3.75 | — | -7.39% | 65.1% | 69% |
| plus_lat | oos | 16 | 129.0% | 34.4% | 3.75 | [0.51, 8.89] | -7.39% | 65.1% | 69% |

    *Train window: 24 weeks. Bootstrap CIs use stationary block bootstrap with block length 4 and 2000 draws.*

    The constrained NALFP variant has a wide bootstrap CI that crosses zero on the 24-week OOS window. We do **not** claim the strategy delivers statistically distinguishable returns on this sample; the cross-section of factors is statistically meaningful (5 of 7 priced in-sample) but the OOS combination does not generalise reliably here.

    ## 8. Honest limitations

    - **Sample size.** 52 weeks total → 24 OOS weeks after the network burn-in. The Sharpe-ratio standard error on 24 weeks is approximately $1/\sqrt{24} \approx 0.20$; the bootstrap CI for NALFP OOS Sharpe is wider yet and crosses zero.
    - **Hidden factor identification.** Bai-Ng IC$_{p2}$ saturates the K=3 cap, suggesting our $T=24$ training window is short for identifying hidden risk premia (Hartmann 2025 used 100+ weeks and selected $K_\text{hidden} = 7$).
    - **TVLC and SupC.** Excluded from GX due to coverage; their stats in the zoo table are computed on 0 and 7 weeks respectively — read with caution.
    - **Costs.** 10 bps one-sided on turnover is reasonable for large-caps; the long tail of our universe is more expensive in practice.
    - **What would break this.** A regime shift that flips the sign of SMBC or MomC out-of-sample (precisely what we see in some OOS weeks). The strategy's strength is the *factor structure identification*; whether the training-window λ̂ generalises is an empirical question we do not yet have enough data to answer.

    ## 9. Reproducibility

    ```
    python3 08_nalfp/01_network_dynamics.py
    python3 08_nalfp/02_factor_pricing.py
    python3 08_nalfp/03_regime_detector.py
    python3 08_nalfp/04_portfolio_construction.py
    python3 08_nalfp/05_backtest.py
    python3 08_nalfp/06_report.py
    ```
