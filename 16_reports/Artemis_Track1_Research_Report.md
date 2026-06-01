---
title: "Separating Alpha, Risk Premia, and Regime Sizing in Crypto Factor Portfolios"
subtitle: "A systematic weekly crypto rebalancing strategy based on validated factor signals"
author: "shenron0101"
date: "May 31, 2026"
---

\newpage

# Executive Summary

This report presents a systematic crypto factor rebalancing strategy[^factor] for Track 1 of the Artemis Quant Competition. The goal is to build a rules-based portfolio that can be explained economically, tested statistically, and rebalanced on a fixed weekly schedule.

The final strategy is called the Stage 15 Factor Ensemble. It combines three different types of evidence rather than forcing every signal into one score:

1. **Mispricing signals**: factors that look attractive when the whole return distribution is evaluated.
2. **Weekly ranking signals**: factors that reliably sort coins from better to worse performers over the next week.
3. **Priced-risk tilts**: factors that appear to earn compensation as systematic risks, but are not strong enough to dominate the weekly trading rule.

The key result is that the final ensemble remained positive out-of-sample[^oos] during a difficult crypto market period when Bitcoin and the equal-weight crypto market both lost money. In the performance tables, **SE** means Sharpe Ensemble, **BE** means Balanced Ensemble, **DE** means Defensive Ensemble, **MM** means MispricingM, **CR** means Core Rank, **PT** means Priced Tilt, **EW** means equal-weight market, and **BTC** means Bitcoin.

| Strategy | Sharpe | Annual return | Volatility | Max drawdown | Weeks |
|---|---:|---:|---:|---:|---:|
| SE | +0.84 | +29.9% | 35.8% | -24.7% | 79 |
| DE | +0.75 | +21.6% | 29.0% | -19.7% | 79 |
| BE | +0.68 | +18.8% | 27.6% | -18.3% | 79 |
| BTC | -0.33 | -12.3% | 37.7% | -46.7% | 78 |
| EW | -0.51 | -34.4% | 67.2% | -68.3% | 78 |

The main limitation is that the final test period is only 79 weeks. The results are encouraging, but they should be read as a disciplined research backtest rather than proof of a finished production strategy.

[^factor]: A factor is a measurable asset characteristic used to explain or predict returns. The idea is central to modern asset-pricing research, including Fama and French (1993), Carhart (1997), and the crypto studies reviewed in this report.
[^oos]: Out-of-sample means a time period reserved for testing after the strategy design is chosen. This is the standard way to reduce the risk of overfitting, although one holdout window is still not definitive.

\newpage

# Reader Guide and Glossary

This report is written to be self-contained. The reader does not need access to the project code or notebooks. All strategy claims are supported by tables or figures included in the document.

| Term | Plain-language meaning | Main reference |
|---|---|---|
| Factor | A rule that ranks or tilts assets using a characteristic such as volatility, size, momentum, or drawdown | Fama and French (1993); Han et al. (2024) |
| Rebalancing | Periodically updating portfolio weights. This project rebalances weekly | DeMiguel, Garlappi, and Uppal (2009) |
| IC | Information coefficient, the rank correlation between a factor score and next-period returns | Spearman (1904); Grinold and Kahn (2000) |
| Newey-West t-stat | A statistical significance measure adjusted for autocorrelation and heteroskedasticity | Newey and West (1987) |
| ASD | Almost stochastic dominance, a distributional test that is useful when returns are non-normal | Leshno and Levy (2002); Han et al. (2024) |
| GX pricing | Giglio-Xiu latent-factor pricing, used to test risk premia while controlling for hidden common factors | Giglio and Xiu (2021) |
| Sharpe ratio | Return per unit of volatility | Sharpe (1966) |
| Max drawdown | Largest peak-to-trough portfolio loss during the test window | Magdon-Ismail and Atiya (2004) |
| XGBoost | A gradient-boosted tree model used here to estimate market regime probabilities | Chen and Guestrin (2016) |
| Risk premium | Extra expected return for bearing a systematic risk | Fama and French (1993); Giglio and Xiu (2021) |
| Latent factor | A hidden common risk extracted statistically from returns rather than named directly | Giglio and Xiu (2021) |
| Overfitting | A model fitting historical noise rather than a repeatable relationship | Chen and Guestrin (2016); Brigida (2026) |
| Survivorship bias | A data problem where failed or delisted assets are missing from the historical universe | Han et al. (2024); Brigida (2026) |
| TVL | Total value locked, a DeFi usage measure that is not reliable as a standalone alpha signal | Brigida (2025); Brigida (2026) |
| VolC | Volatility characteristic, used here as a low-volatility crypto ranker | Frazzini and Pedersen (2014) |
| MAXRET | Maximum recent return, used here as a lottery-reversal signal | Bali, Cakici, and Whitelaw (2011); Han et al. (2024) |
| RMOM | Risk-adjusted momentum, meaning recent return scaled by recent volatility | Han et al. (2024) |
| SMBC | Small-minus-big crypto size factor | Fama and French (1993); Brigida (2026) |
| NetRel | Network-relative signal comparing a coin with related coins | Guo, Haerdle, and Tao (2024) |
| CRASH8 | Rebound signal for deeply crashed coins | Han et al. (2024) |
| BETA26 | High-beta crypto risk tilt | Frazzini and Pedersen (2014); Brigida (2026) |
| SKEW52 | Skewness or lottery-like payoff tilt | Bali, Cakici, and Whitelaw (2011) |
| NEWC | Newer-coin seasoning tilt | Han et al. (2024); Brigida (2026) |

The report uses **in-sample** to mean the research window used to study and build the model. It uses **out-of-sample** to mean the later window used to test whether the model still works after design choices have already been made.

# Competition Objective

Track 1 asks for a systematic crypto factor rebalancing strategy. In practical terms, this means:

1. Define a tradable crypto universe.
2. Build factor signals with a clear economic story.
3. Rebalance the portfolio on a consistent schedule.
4. Evaluate returns, risk, turnover, drawdown, and robustness.
5. Critically explain what could fail.

This submission focuses on the last three points as much as the first two. A high return backtest is not enough. The strategy needs to be simple enough to explain, statistically defensible, and honest about the limits of the test.

# Universe, Data, and Design Choices

The research uses a weekly crypto asset panel covering large liquid tokens. The broad factor validation work covers the 2017 to 2026 period and uses about 113 large-cap coins. The final strategy is evaluated on a weekly panel with a final 79-week out-of-sample window ending on May 25, 2026.

Weekly rebalancing is used because most of the signals are cross-sectional factors rather than intraday trading signals. A weekly horizon is long enough to reduce daily noise and short enough to capture short-term crypto reversals.

The strategy is designed to exclude stablecoins, wrapped duplicates, and very low-quality assets where possible. Stablecoins do not have the same risk-return profile as normal crypto assets. Wrapped assets can duplicate exposures already in the universe. Very illiquid assets can create paper profits that may not be tradable after slippage.

| Design item | Choice |
|---|---|
| Broad research period | 2017 to 2026 |
| Main validation split | In-sample: 2021-05-10 to 2024-11-11. Out-of-sample: 2024-11-18 to 2026-05-25 |
| Final strategy split | In-sample before 2024-11-25. Out-of-sample final 79 weeks |
| Approximate asset count | About 113 large-cap coins in the factor validation panel |
| Rebalancing frequency | Weekly |
| Trading-cost discipline | Research backtests include simplified turnover-cost assumptions, but real execution costs could be higher |

The factor validation, universe reconstruction, and Giglio-Xiu pricing that
underpin every factor claim below are produced in the Stage 09 pipeline
(`09_nalfp_add/`); the behavioral factor search is Stage 10; the per-factor
visualizations are Stage 12; and the final ensemble is Stage 15. One data-integrity
note: deep-history market cap before ~2025 is reconstructed as price × an
emissions-anchored supply estimate, with per-day supply drift clamped to a
realistic annual band (−3% to +50% per year) so backward extrapolation cannot
produce runaway early-period supply. Because the size factor (SMBC) sorts on
*cross-sectional log-mcap ranks* rather than levels, residual reconstruction error
has limited effect on the ranking.

# Factor Discovery and Validation Framework

The strategy starts with factor discovery. A factor is useful only if it passes at least one clear test:

1. **Ranking power**: does the signal rank coins correctly from one week to the next?
2. **Distributional robustness**: does the whole return distribution look attractive, not just the average return?
3. **Risk premium evidence**: does the signal represent a priced source of systematic risk?

These tests answer different questions. The information coefficient test measures short-horizon ranking power. The almost stochastic dominance test checks whether a return distribution is attractive for risk-averse investors, which is important because crypto returns are fat-tailed and non-normal.[^asd] The Giglio-Xiu pricing test asks whether a factor is compensated as a systematic risk after accounting for hidden common risks.[^gx]

[^asd]: Han, Newton, Platanakis, Sutcliffe, and Ye (2024) apply almost stochastic dominance to cryptocurrency factor portfolios and show why standard mean-variance metrics can be incomplete for crypto.
[^gx]: Giglio and Xiu (2021) develop a latent-factor asset-pricing framework that helps avoid overstating a factor premium when hidden common risks are omitted.

| Factor group | Factors | How the group is used |
|---|---|---|
| Weekly rankers | VolC, MAXRET | Used as the Core Rank book |
| Mispricing composite | RMOM1w, RMOM2w, SMBC, NetRel | Combined into MispricingM |
| Priced-risk tilts | CRASH8, BETA26, TVLC, SKEW52, NEWC | Kept as a capped risk-premia sleeve |

The strongest single-factor evidence is for VolC and MAXRET. VolC favors lower-volatility coins. MAXRET fades coins with large recent return spikes. Both factors have statistically significant information coefficient results in-sample and out-of-sample.

| Factor | Evidence summary | GX t-stat | ASD result | Grade |
|---|---|---:|---|---|
| VolC | IC t-stat: IS -3.32, OOS -4.31 | -5.05 | No | Confirmed |
| MAXRET | IC t-stat: IS -3.49, OOS -4.05 | +5.52 | No | Confirmed |
| CRASH8 | Priced-risk evidence | +4.79 | n/a | Priced risk |
| BETA26 | Priced-risk evidence | +4.60 | n/a | Priced risk |
| TVLC | Priced-risk evidence | -4.71 | n/a | Priced risk |
| SKEW52 | Priced-risk evidence | +3.44 | n/a | Priced risk |
| NEWC | Priced-risk evidence | +3.43 | n/a | Priced risk |
| RMOM1w | Weak weekly IC, but useful in distributional tests | +1.86 | Yes | Priced risk |
| RMOM2w | In-sample IC, weak OOS IC, useful in distributional tests | +1.05 | Yes | Suggestive |
| SMBC | Weak IC, useful in distributional tests | +0.36 | Yes | Suggestive |
| NetRel | Weak IC, useful in distributional tests | -0.01 | Yes | Suggestive |
| MispricingM | Composite of RMOM1w, RMOM2w, SMBC, and NetRel | n/a | Yes | Suggestive |

**Multiple-testing discipline (priced-risk factors).** The four behavioral
priced-risk factors come from a search over 182 candidate specifications, of which
102 cleared an uncorrected |t| ≥ 2.0 bar. That 56% raw hit rate is correctly read
as exploratory mining, so the four headline factors are held to a far harsher
standard: across all 182 tests they survive both a **Benjamini-Hochberg** false-
discovery-rate correction (q < 0.001) and a **Bonferroni** family-wise correction
(threshold |t| > 3.64; all four exceed it). Their reported significance is not an
artifact of the correction. Re-pricing each factor separately on the in-sample and
out-of-sample windows shows the priced-tilt factors are weak as *standalone*
single-window additions (short-window GX premia, signs mostly consistent IS→OOS) —
which is precisely why they are used only as a small capped sleeve, never as core
alpha. Full detail: `10_behavioral_gx/RESULTS.md`.

**MispricingM dominance is not a full-sample artifact.** The composite is selected
from factors that almost-stochastically dominate Bitcoin on the full sample, but
re-running the ASSD test split by window shows MispricingM dominates BTC
(ε₂ = 0.000) in the in-sample window, the full sample, *and* the out-of-sample
window. Two of its four components (RMOM1w, SMBC) dominate in all three windows;
NetRel and RMOM2w each carry a single-window flag, but the diversified composite is
stable across the split. Full detail: `09_nalfp_add/RESULTS.md`.

# Economic Intuition and Factor Evidence

## Core Weekly Rankers

**VolC** is the low-volatility factor. It ranks coins by recent realized volatility and favors calmer coins. This is related to the low-volatility anomaly in equities, where investors may overpay for exciting high-risk assets and underpay for less volatile assets.[^lowvol]

**MAXRET** is a lottery-reversal factor. It identifies coins with a very large recent weekly return and expects some of that excitement to reverse the following week. The intuition comes from lottery-demand and investor-attention research: assets with extreme recent payoffs can become overpriced when investors chase them.[^lottery]

[^lowvol]: The low-volatility interpretation is related to Frazzini and Pedersen (2014), who argue that leverage constraints can make safer assets earn better risk-adjusted returns than standard theory predicts.
[^lottery]: Bali, Cakici, and Whitelaw (2011) study lottery-like payoffs in equities. Han et al. (2024) extend related factor ideas to cryptocurrency portfolios.

![](12_factor_viz/volc_visualisation/artifacts/figures/volc_07_is_oos_comparison.png)

Figure 1. VolC remains statistically meaningful out-of-sample. The negative information coefficient is expected because the strategy favors the low-volatility side of the ranking.

![](12_factor_viz/maxret_visualisation/artifacts/figures/maxret_07_is_oos_comparison.png)

Figure 2. MAXRET has robust weekly ranking evidence. The factor is best understood as a short-term reversal signal rather than a simple momentum signal.

## Mispricing Composite

MispricingM averages four signals: RMOM1w, RMOM2w, SMBC, and NetRel. RMOM means risk-adjusted momentum. SMBC means small-minus-big crypto, a size signal adapted from the classic equity size factor.[^smb] NetRel compares a coin to related coins in its network or cluster.

The composite idea is based on a simple principle: individually noisy signals can become more reliable when they are averaged, as long as they are not all making the same error. Stambaugh and Yuan (2017) show this idea for equity mispricing factors, and Han et al. (2024) apply closely related mispricing logic to crypto factor portfolios.[^mispr]

[^smb]: Fama and French (1993) introduce size and value factors in equities. In this project, SMBC adapts the size idea to crypto by comparing smaller and larger crypto assets.
[^mispr]: Stambaugh and Yuan (2017) build a mispricing composite in equities. Han et al. (2024) show that a crypto mispricing factor based on size and risk-adjusted momentum improves cryptocurrency asset-pricing performance.

| Window | Annual return | Sharpe | Return t-stat | ASD epsilon 2 |
|---|---:|---:|---:|---:|
| In-sample | +31.0% | +1.23 | +2.31 | 0.000 |
| Out-of-sample | +34.1% | +1.50 | +1.60 | n/a |

![](12_factor_viz/mispr_visualisation/artifacts/figures/mispr_07_is_oos_comparison.png)

Figure 3. MispricingM is the strongest composite signal. It becomes the largest sub-book in the final strategy.

## Priced-Risk Tilts

CRASH8, BETA26, TVLC, SKEW52, and NEWC are treated as priced-risk tilts. This means they may describe risks that earn compensation over longer horizons, but they are not trusted as large standalone weekly trading signals.

This distinction matters. A factor can be economically real but still be hard to trade weekly. The final strategy therefore caps the Priced Tilt sleeve instead of letting it dominate the portfolio.

# Final Strategy Construction

The final strategy separates factor roles into three books:

| Book | Inputs | Role in portfolio |
|---|---|---|
| MispricingM | RMOM1w, RMOM2w, SMBC, NetRel | Main alpha source |
| Core Rank | VolC, MAXRET | Statistically strongest weekly rankers |
| Priced Tilt | CRASH8, BETA26, TVLC, SKEW52, NEWC | Small capped risk-premia sleeve |

The allocator is causal, meaning it does not use future returns when setting current weights. Each week, it looks back at prior sub-book returns, estimates which book has recently been useful, blends that with a conservative base allocation, and then applies regime sizing.

Regime sizing uses XGBoost probabilities for RiskOff, Neutral, and RiskOn states.[^xgb] The model is used for risk sizing, not as a fully independent return predictor. This is an important constraint because complex machine-learning models can easily overfit in short crypto histories.

[^xgb]: Chen and Guestrin (2016) introduce XGBoost, a regularized gradient-boosted tree system. In this report it is used only to estimate market-state probabilities.

| Variant | MispricingM | Core Rank | Priced Tilt |
|---|---:|---:|---:|
| Sharpe Ensemble | 80.8% | 15.3% | 3.9% |
| Balanced Ensemble | 54.8% | 36.7% | 8.5% |
| Defensive Ensemble | 60.4% | 35.7% | 3.9% |

![](15_factor_ensemble_strategy/artifacts/figures/sharpe_ensemble_book_allocations.png)

Figure 4. Sharpe Ensemble allocation. The strategy gives most capital to MispricingM and keeps priced-risk exposure capped.

![](15_factor_ensemble_strategy/artifacts/figures/balanced_ensemble_book_allocations.png)

Figure 5. Balanced Ensemble allocation. This version gives more weight to Core Rank and is designed to reduce dependence on the mispricing sleeve.

# Backtest Results

The full-window results show that the final ensembles reduce drawdown materially compared with Bitcoin and the equal-weight market, while still earning attractive returns.

| Strategy | Sharpe | Annual return | Volatility | Max drawdown | Hit rate | Weeks |
|---|---:|---:|---:|---:|---:|---:|
| SE | +1.27 | +64.7% | 51.1% | -45.3% | 53% | 374 |
| BE | +1.18 | +51.1% | 43.4% | -41.4% | 54% | 374 |
| DE | +1.21 | +54.4% | 45.0% | -42.4% | 53% | 374 |
| MM | +1.24 | +76.5% | 61.9% | -46.6% | 54% | 374 |
| CR | +0.53 | +18.5% | 35.1% | -49.3% | 49% | 374 |
| PT | +0.30 | +11.1% | 36.9% | -49.1% | 47% | 374 |
| EW | +0.82 | +65.7% | 80.5% | -80.6% | 55% | 373 |
| BTC | +0.92 | +54.4% | 59.0% | -75.2% | 52% | 373 |

In-sample, the crypto market was strong. This makes the out-of-sample period more important for judging robustness.

| Strategy | Sharpe | Annual return | Volatility | Max drawdown | Hit rate | Weeks |
|---|---:|---:|---:|---:|---:|---:|
| SE | +1.36 | +74.0% | 54.4% | -45.3% | 54% | 295 |
| BE | +1.28 | +59.7% | 46.7% | -41.4% | 55% | 295 |
| DE | +1.31 | +63.2% | 48.4% | -42.4% | 53% | 295 |
| EW | +1.10 | +92.1% | 83.4% | -80.6% | 58% | 295 |
| BTC | +1.14 | +72.1% | 63.2% | -75.2% | 54% | 295 |

Out-of-sample, Bitcoin and the equal-weight market both lose money. All three ensembles remain positive with materially smaller drawdowns.

| Strategy | Sharpe | Annual return | Volatility | Max drawdown | Hit rate | Weeks |
|---|---:|---:|---:|---:|---:|---:|
| SE | +0.84 | +29.9% | 35.8% | -24.7% | 51% | 79 |
| BE | +0.68 | +18.8% | 27.6% | -18.3% | 53% | 79 |
| DE | +0.75 | +21.6% | 29.0% | -19.7% | 53% | 79 |
| MM | +0.85 | +37.2% | 44.1% | -29.9% | 52% | 79 |
| CR | +0.11 | +2.0% | 18.1% | -18.8% | 47% | 79 |
| PT | -0.43 | -13.7% | 31.8% | -32.6% | 39% | 79 |
| EW | -0.51 | -34.4% | 67.2% | -68.3% | 45% | 78 |
| BTC | -0.33 | -12.3% | 37.7% | -46.7% | 47% | 78 |

![](15_factor_ensemble_strategy/artifacts/figures/cumulative_returns.png)

Figure 6. Cumulative returns. The final ensembles keep positive out-of-sample performance while Bitcoin and the equal-weight market decline.

The results support three conclusions. First, the Sharpe Ensemble has the best return and risk-adjusted return. Second, Balanced and Defensive variants reduce drawdown by shifting more capital toward Core Rank and risk control. Third, the Priced Tilt sub-book is economically interesting but weak as a standalone weekly strategy, which supports keeping it capped.

## Ablation and sensitivity analysis

To test how much the headline depends on the two hardcoded-prior knobs — the
priced-tilt cap and the regime tilt — each is isolated against the Sharpe Ensemble
base allocation (full detail in `15_factor_ensemble_strategy/RESULTS.md`):

| Variant | OOS Sharpe | OOS Annual return | Note |
|---|---:|---:|---|
| Sharpe Ensemble (headline) | +0.84 | +29.9% | three-book ensemble as presented |
| SE Priced-Tilt Off | +0.90 | +34.2% | priced-risk sleeve removed entirely |
| SE Priced-Tilt 5% cap | +0.87 | +31.8% | sleeve cap cut from 18% to 5% |
| SE No Regime Tilt | +0.80 | +27.9% | regime multipliers all set to 1.0 |
| MispricingM Only | +0.85 | +37.2% | mispricing book traded alone |

Three honest findings come out of this. **(1) The Priced Tilt sleeve is a net drag
out-of-sample**: removing it *raises* OOS Sharpe from +0.84 to +0.90. The audit's
recommendation to cut rather than merely cap it is therefore supported by the data,
and a production version should run the priced-risk factors at a near-zero
allocation. **(2) Regime conditioning adds a small, measured benefit** (+0.84 vs
+0.80 with no tilt) — real but modest, and not the source of the strategy's edge.
**(3) The ensemble is essentially a single-factor strategy**: MispricingM alone
earns OOS Sharpe +0.85, statistically indistinguishable from the full ensemble, so
the diversification across books mainly controls volatility and drawdown rather than
adding return. Across the full regime-tilt × priced-cap grid the OOS Sharpe stays in
a tight +0.80 to +0.91 band, so the headline is robust to these priors even though
the priors are not individually optimal.

# Critical Evaluation

The strongest weakness is sample length. The final out-of-sample test has only 79 weeks. That is useful, but it is not enough to prove the strategy will work across every future crypto cycle.

There is also selection risk. The final strategy was designed after earlier experiments showed what did not work. That is a normal research process, but it means the final result should not be described as a pure untouched holdout. Two specific selection concerns have been addressed directly: the behavioral factor search is now reported with Bonferroni and Benjamini-Hochberg multiple-testing corrections (the four selected factors survive both), and the factors plus the MispricingM composite are re-tested with explicit in-sample/out-of-sample splits rather than full-sample evidence alone. The single-factor dependency on MispricingM is real and is quantified in the ablation table above rather than hidden.

The regime model is heuristic. XGBoost regime labels are based on market-state features such as market momentum, cross-sectional dispersion, BTC dominance, and volatility. They are useful for sizing risk, but they are not ground truth.

Transaction costs are simplified. Real execution would depend on exchange venue, slippage, spreads, borrow availability, order size, and liquidity. This is especially important for smaller crypto assets.

Universe construction is another risk. If the historical universe is not fully point-in-time, survivorship bias can make results look better than they would have looked in real time.

The strategy would likely fail or weaken if MispricingM stopped working, small-cap liquidity disappeared, trading costs rose, factor crowding compressed returns, or the regime-sizing model became unreliable in a new market environment.

# Appendix A: Regime Conditioning Experiments

Before the final strategy, two simpler regime-conditioning plans were tested. Plan A used an economic classifier based on dispersion and BTC dominance changes. Plan B used a hidden Markov model, a statistical model that estimates unobserved market states from observed variables.[^hmm]

[^hmm]: Hidden Markov models are commonly used for regime-switching problems. In finance they are often used to classify markets into risk-on and risk-off states.

The result was useful but not sufficient. Regime conditioning helped risk control, but it did not create enough standalone alpha.

| Strategy | Sharpe | Annual return | Volatility | Max drawdown | Weeks |
|---|---:|---:|---:|---:|---:|
| Plan A | +0.19 | +2.6% | 13.4% | -16.7% | 79 |
| Plan B | +0.36 | +4.6% | 13.0% | -12.9% | 79 |
| EW | -0.51 | -34.4% | 67.2% | -68.3% | 78 |

The lesson is that regimes are useful for risk sizing, but they should not be the entire strategy.

# Appendix B: Machine-Learning Lessons

The next experiment used XGBoost regime probabilities and tested several optimizer variants. The best version stayed positive out-of-sample, but more aggressive and more complex versions failed.

![](14_regime_factor_strategy/artifacts/figures/xgboost_regimes.png)

Figure 7. XGBoost regime probabilities. The final strategy uses these probabilities for sizing risk, not as a complete return forecast.

| Strategy | Sharpe | Annual return | Volatility | Max drawdown | Weeks |
|---|---:|---:|---:|---:|---:|
| Sharpe optimized | +0.61 | +26.8% | 44.3% | -24.2% | 79 |
| Return optimized | -0.52 | -27.1% | 52.4% | -58.9% | 79 |
| Balanced | -0.53 | -29.7% | 55.6% | -62.8% | 79 |
| Neural network optimizer | -0.46 | -19.1% | 41.0% | -45.5% | 79 |

The lesson is that more model complexity did not improve out-of-sample robustness. The final strategy therefore constrains model freedom, separates factor roles, caps priced-risk exposure, and uses machine learning only for risk sizing.

To be explicit about where the gain comes from: Stage 14's best variant reaches OOS Sharpe +0.61, while Stage 15's Sharpe Ensemble reaches +0.84. That improvement is the result of *simplification* — dropping the multi-sleeve optimizer complexity and concentrating on the MispricingM composite — not of discovering additional signal. The IS→OOS Sharpe decay is also informative: the Sharpe Ensemble decays 1.36 → 0.84 (≈38%), the Defensive Ensemble 1.31 → 0.75 (≈43%), and the Balanced Ensemble 1.28 → 0.68 (≈47%), whereas Bitcoin goes from +1.14 in-sample to −0.33 out-of-sample. A ~38% decay is meaningful overfitting but is smaller than the decay typical of complex ML variants here (the neural-network optimizer decayed from +2.06 to −0.46).

# Appendix C: Reproducibility Note

This document is written so that the reader can evaluate the strategy without access to code. The tables and figures are included directly in the report. If the competition submission includes a code package, that package can be used to reproduce the numbers, but the report does not require readers to inspect the code to understand the method.

# Appendix D: Audit Remediation Summary

An independent audit (`AUDIT_AND_FINDINGS_REPORT.md`) raised thirteen findings.
Those touching the production pipeline (Stages 09, 10, 12, 15) have been resolved
as follows; the resolutions are reflected in the relevant stage `RESULTS.md` files
and in the sections above.

| # | Finding | Resolution |
|---|---|---|
| 1 | Uncontrolled multiple testing in the 182-candidate behavioral search | Bonferroni + Benjamini-Hochberg corrections added; all four selected factors survive both (Bonferroni |t| > 3.64; BH q < 0.001). Reported in Stage 10 RESULTS and above. |
| 2 | No IS/OOS holdout for behavioral factor discovery | Each shortlist factor re-priced on the frozen IS window and the held-out OOS window; standalone single-window premia shown to be weak, justifying the capped-sleeve treatment. |
| 3 | Supply backfill look-ahead / clip bug | Per-day log-supply drift clamp fixed to a realistic annual band (−3%/yr to +50%/yr), removing the unintended ~1500%/yr upper bound. |
| 4 | ASD computed on full sample only | ASSD test now also computed for the IS and OOS windows; MispricingM dominates BTC in all three windows. |
| 5 | Hardcoded activation/regime-tilt priors unvalidated | Priors documented with economic rationale; a "No Regime Tilt" baseline and a full regime-tilt × priced-cap sensitivity grid added (OOS Sharpe stays in +0.80–0.91). |
| 6 | Priced Tilt sub-book toxic OOS | Ablation added: removing the sleeve raises OOS Sharpe +0.84 → +0.90, supporting a near-zero allocation in production. |
| 8 | FMB shortcut in `09_gx_pricing.py` | Deprecation banner + runtime warning added; all reported GX t-stats come from `09c_gx_pricing_full.py`. |
| 9 | `fillna(mean)` mild look-ahead | Replaced with leakage-free forward-fill (mean only for unavoidable leading gaps) in the GX engine. |
| 11 | Stage 14 → 15 improvement framing | Clarified in Appendix B: the +0.61 → +0.84 OOS gain comes from simplification, not new signal. |
| 12 | Undocumented Stage 10 → 12 → 15 selection path | Documented in the root pipeline `README.md` and the provenance note in the data section. |
| 13 | Misleading winsorization comment | Comment corrected: returns are intentionally raw because VolC/MAXRET target the tails and downstream tests are rank-based. |

Findings 7 and 10 concern Stages 13–14 (the regime experiments in the appendices)
and do not affect the production pipeline; they are noted but not core to this
submission.

# Bibliography

Bali, T. G., Cakici, N., and Whitelaw, R. F. (2011). Maxing out: Stocks as lotteries and the cross-section of expected returns. *Journal of Financial Economics*, 99(2), 427-446.

Brigida, M. (2025). The surprising irrelevance of total-value-locked on cryptocurrency returns. *Economics Letters*, 257, 112673. DOI: 10.1016/j.econlet.2025.112673.

Brigida, M. (2026). *Crypto Pricing with Hidden Factors*. arXiv:2601.07664.

Carhart, M. M. (1997). On persistence in mutual fund performance. *Journal of Finance*, 52(1), 57-82.

Chen, T., and Guestrin, C. (2016). XGBoost: A scalable tree boosting system. *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*, 785-794.

DeMiguel, V., Garlappi, L., and Uppal, R. (2009). Optimal versus naive diversification: How inefficient is the 1/N portfolio strategy? *Review of Financial Studies*, 22(5), 1915-1953.

Fama, E. F., and French, K. R. (1993). Common risk factors in the returns on stocks and bonds. *Journal of Financial Economics*, 33(1), 3-56.

Frazzini, A., and Pedersen, L. H. (2014). Betting against beta. *Journal of Financial Economics*, 111(1), 1-25.

Giglio, S., and Xiu, D. (2021). Asset pricing with omitted factors. *Journal of Political Economy*, 129(7), 1947-1990.

Grinold, R. C., and Kahn, R. N. (2000). *Active Portfolio Management*. McGraw-Hill.

Han, W., Newton, D., Platanakis, E., Sutcliffe, C., and Ye, X. (2024). On the almost stochastic dominance of cryptocurrency factor portfolios and implications for cryptocurrency asset pricing. *European Financial Management*, 30, 1125-1164. DOI: 10.1111/eufm.12431.

Guo, L., Haerdle, W. K., and Tao, Y. (2024). A time-varying network for cryptocurrencies. *Journal of Business and Economic Statistics*, 42(2), 437-456.

Leshno, M., and Levy, H. (2002). Preferred by all and preferred by most decision makers: Almost stochastic dominance. *Management Science*, 48(8), 1074-1085.

Magdon-Ismail, M., and Atiya, A. F. (2004). Maximum drawdown. *Risk Magazine*, 17(10), 99-102.

Newey, W. K., and West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica*, 55(3), 703-708.

Sharpe, W. F. (1966). Mutual fund performance. *Journal of Business*, 39(1), 119-138.

Spearman, C. (1904). The proof and measurement of association between two things. *American Journal of Psychology*, 15(1), 72-101.

Stambaugh, R. F., and Yuan, Y. (2017). Mispricing factors. *Review of Financial Studies*, 30(4), 1270-1315.
