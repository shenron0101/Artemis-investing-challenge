# Stage 06 — Artemis Econometrics: Run Report

## Setup

- **cutoff_week**: 2026-01-19
- **n_train_weeks**: 36
- **n_test_weeks**: 16

## Model Comparison (out-of-sample)

| model | ic_mean | ic_ir | ls_mean | ls_sharpe_annual | turnover_mean | alpha | t_alpha | n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| plus_lat | +0.0890 | +0.5404 | +0.0265 | +3.7366 | +0.2980 | +0.0266 | +1.9427 | 15 |
| base_pool | +0.0872 | +0.5943 | +0.0287 | +3.4646 | +0.2784 | +0.0292 | +1.8488 | 15 |
| base_fm | +0.0848 | +0.4629 | +0.0335 | +3.8958 | +0.3725 | +0.0351 | +2.3678 | 15 |
| plus_net | +0.0418 | +0.2019 | +0.0070 | +0.6766 | +0.3176 | +0.0069 | +0.3462 | 15 |

Reading the table:
- `ic_mean` — mean weekly Spearman correlation between predicted ranking and realized next-week return.
- `ic_ir` — IC mean divided by IC std (information ratio of the ranking signal).
- `ls_mean` — mean weekly Q5 minus Q1 log return.
- `ls_sharpe_annual` — annualised Sharpe of the long-short portfolio (√52).
- `turnover_mean` — average week-on-week churn fraction in the top quintile.
- `alpha` / `t_alpha` — intercept of long-short return regressed on equal-weight market return (no contemporaneous momentum control).

_`base_lasso` (ElasticNetCV) removed this iteration — degenerate (all-zero) coefficients on 36 weeks × 12 features; kept as a known limitation rather than tuned._

## Fama-MacBeth t-stats (base characteristics)

| feature | t_stat |
| --- | --- |
| intercept | -0.64 |
| log_mcap | -0.19 |
| log_dollar_vol | -0.37 |
| turnover | -0.02 |
| tvl_to_mcap | +0.92 |
| mom_1w | +1.25 |
| mom_4w | +1.16 |
| mom_12w | -0.40 |
| vol_4w | -0.94 |
| F_yield | -0.16 |
| G_growth | -0.88 |
| S_supply | +0.63 |
| stable_inflow_z | +nan |

These t-stats use the time-series of weekly cross-sectional slopes on the training window. They tell us which Artemis-style characteristics actually drove the cross-section before adding latent / network adjustments.

## Coefficients across models

| feature | base_fm | base_pool | plus_lat | plus_net |
| --- | --- | --- | --- | --- |
| intercept | -0.0077 | -0.0079 | -0.0079 | -0.0079 |
| log_mcap | -0.0004 | -0.0016 | -0.0018 | -0.0021 |
| log_dollar_vol | -0.0011 | -0.0009 | -0.0006 | -0.0006 |
| turnover | -0.0001 | +0.0005 | +0.0007 | +0.0009 |
| tvl_to_mcap | +0.0060 | +0.0045 | +0.0043 | +0.0048 |
| mom_1w | +0.0053 | +0.0019 | +0.0015 | +0.0012 |
| mom_4w | +0.0056 | +0.0029 | +0.0027 | +0.0051 |
| mom_12w | -0.0015 | -0.0011 | -0.0015 | -0.0014 |
| vol_4w | -0.0044 | -0.0026 | -0.0018 | -0.0018 |
| F_yield | -0.0005 | -0.0008 | -0.0012 | -0.0016 |
| G_growth | -0.0021 | -0.0017 | -0.0012 | -0.0012 |
| S_supply | +0.0003 | +0.0060 | +0.0059 | +0.0057 |
| stable_inflow_z | +0.0000 | +0.0000 | -0.0000 | +0.0000 |
| pc1_load | — | — | -0.0016 | -0.0023 |
| pc2_load | — | — | -0.0030 | -0.0026 |
| pc3_load | — | — | -0.0070 | -0.0077 |
| within_cluster_mom | — | — | — | +0.0007 |
| cross_cluster_rel | — | — | — | -0.0082 |

## Figures

- `figures/06_backtest/01_cumulative_long_short.html` — cumulative Q5-Q1 trajectory by model.
- `figures/06_backtest/02_ic_distribution.html` — weekly IC distribution by model.

## Next Iteration Ideas

- Replace the rolling-correlation cluster with a Granger-style predictive link network and re-run the `plus_net` model.
- Swap the single-shot train/test split for a rolling (expanding) walk-forward fit when compute allows.
- Add a perp basis / funding-rate feature once that feed lands in `01_Data_Collection/data/clean/`.
- Repeat the comparison on `residual_ret` (latent-factor adjusted) as the target — this directly tests whether Artemis characteristics carry signal *beyond* common crypto risks.
