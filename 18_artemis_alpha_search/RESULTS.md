# Stage 18 - Artemis Alpha Search

Universe source: `09_nalfp_add/artifacts/manifests/universe_manifest.json`.

Split: IS before 2024-11-18, OOS from 2024-11-18 onward. Returns are next-week Binance returns with 10 bps turnover cost.

## Positive On-Chain Result

The cleanest positive broad-coverage on-chain result is weekly **fee growth**: long coins with the strongest 4-week Artemis fee growth and short the weakest. Static FunC fee yield did not survive OOS, but fee growth did.

| Candidate | IS Sharpe | OOS Sharpe | IS Ann Ret | OOS Ann Ret | OOS Max DD |
|---|---:|---:|---:|---:|---:|
| fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 | 34.1% | 9.2% | -10.7% |
| fees_growth_4w|dir=+1|top=0.25 | 1.42 | 0.83 | 31.0% | 10.1% | -8.6% |
| fees_growth_12w|dir=+1|top=0.20 | 1.00 | 0.17 | 19.3% | 2.4% | -8.4% |
| volume_growth_4w|dir=+1|top=0.30 | 0.98 | 0.21 | 16.3% | 2.3% | -7.4% |
| transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 | 16.3% | 0.5% | -9.8% |
| real_transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 | 16.3% | 0.5% | -9.8% |
| real_volume_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 | 16.3% | 0.5% | -9.8% |
| fees_growth_4w|dir=+1|top=0.30 | 0.97 | 0.10 | 22.4% | 1.1% | -11.7% |
| tx_to_mcap|dir=+1|top=0.30 | 0.79 | 0.28 | 13.2% | 3.5% | -9.3% |
| real_tx_to_mcap|dir=+1|top=0.30 | 0.79 | 0.28 | 13.2% | 3.5% | -9.3% |

Caution: this is still an exploratory factor search. The result is positive in both windows, but it should be presented as supporting evidence, not as a replacement for the Stage 15 headline strategy.

Selection note: the naive on-chain-only ensemble selected purely by top IS Sharpe overweights revenue growth and fails OOS; the positive result to show is the fee-growth factor, plus the mixed 12-signal ensemble below.

TVLC note: local DeFiLlama TVL coverage is only about 4 names per week, so TVLC is too sparse in this local cleaned panel for a broad-universe portfolio.

## Sparse TVLC Diagnostic

This lowers the TVL test gate to 4 names/week. Treat it as a diagnostic only, not a production broad-universe factor.

| Candidate | IS Sharpe | OOS Sharpe | IS Ann Ret | OOS Ann Ret | OOS Max DD |
|---|---:|---:|---:|---:|---:|
| tvlc_defillama_to_mcap|dir=+1|top=0.25 | 0.03 | 1.53 | 1.4% | 45.4% | -17.6% |
| defillama_tvl_usd_growth_12w|dir=+1|top=0.25 | -0.33 | 1.14 | -12.8% | 33.5% | -19.6% |
| tvlc_defillama_to_mcap|dir=+1|top=0.50 | 0.32 | 1.12 | 10.2% | 30.5% | -16.9% |
| defillama_tvl_usd_growth_12w|dir=+1|top=0.50 | -0.73 | 0.62 | -20.9% | 16.5% | -27.1% |
| defillama_tvl_usd_growth_4w|dir=-1|top=0.50 | -0.17 | 0.42 | -5.8% | 9.6% | -22.5% |
| defillama_tvl_usd_growth_4w|dir=-1|top=0.25 | 0.13 | 0.03 | 6.7% | 0.8% | -30.2% |
| defillama_tvl_usd_growth_4w|dir=+1|top=0.25 | -0.21 | -0.15 | -10.7% | -4.3% | -36.3% |
| defillama_tvl_usd_growth_12w|dir=-1|top=0.50 | 0.68 | -0.45 | 19.4% | -11.7% | -28.8% |

## Best Single-Factor Candidates by OOS Sharpe

| Candidate | IS Sharpe | OOS Sharpe | OOS Ann Ret | OOS Max DD | OOS weeks |
|---|---:|---:|---:|---:|---:|
| log_mcap_neg|dir=+1|top=0.20 | 0.50 | 2.15 | 42.0% | -11.3% | 76 |
| log_mcap_neg|dir=+1|top=0.25 | 0.67 | 2.15 | 40.2% | -13.5% | 76 |
| log_mcap_neg|dir=+1|top=0.30 | 0.76 | 2.02 | 33.1% | -9.7% | 76 |
| revenue_growth_12w|dir=-1|top=0.30 | -0.59 | 1.98 | 22.4% | -6.8% | 76 |
| revenue_growth_12w|dir=-1|top=0.25 | -0.72 | 1.82 | 24.8% | -6.6% | 76 |
| volume_growth_4w|dir=+1|top=0.20 | -0.13 | 1.49 | 20.4% | -10.9% | 76 |
| transactions_growth_12w|dir=+1|top=0.20 | 0.12 | 1.39 | 20.3% | -10.8% | 76 |
| real_transactions_growth_12w|dir=+1|top=0.20 | 0.12 | 1.39 | 20.3% | -10.8% | 76 |
| volume_growth_12w|dir=+1|top=0.20 | 0.12 | 1.39 | 20.3% | -10.8% | 76 |
| real_volume_growth_12w|dir=+1|top=0.20 | 0.12 | 1.39 | 20.3% | -10.8% | 76 |
| real_tx_ratio|dir=+1|top=0.20 | -0.06 | 1.36 | 19.3% | -11.1% | 76 |
| real_volume_ratio|dir=+1|top=0.20 | -0.06 | 1.36 | 19.3% | -11.1% | 76 |
| revenue_growth_12w|dir=-1|top=0.20 | -0.79 | 1.29 | 18.3% | -9.8% | 76 |
| transactions_growth_4w|dir=+1|top=0.20 | -0.13 | 1.25 | 17.1% | -10.9% | 76 |
| real_transactions_growth_4w|dir=+1|top=0.20 | -0.13 | 1.25 | 17.1% | -10.9% | 76 |

## Best Single-Factor Candidates Selected by IS Sharpe

| Candidate | IS Sharpe | OOS Sharpe | IS Ann Ret | OOS Ann Ret |
|---|---:|---:|---:|---:|
| revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 | 32.5% | -10.3% |
| fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 | 34.1% | 9.2% |
| fees_growth_4w|dir=+1|top=0.25 | 1.42 | 0.83 | 31.0% | 10.1% |
| rmom_1w|dir=+1|top=0.30 | 1.34 | 1.06 | 22.8% | 18.6% |
| dau_growth_4w|dir=+1|top=0.25 | 1.28 | -0.50 | 27.2% | -8.5% |
| dau_growth_4w|dir=+1|top=0.20 | 1.27 | -0.54 | 34.1% | -10.3% |
| rmom_1w|dir=+1|top=0.25 | 1.21 | 0.69 | 23.7% | 13.8% |
| revenue_growth_4w|dir=+1|top=0.25 | 1.21 | -0.94 | 26.5% | -10.9% |
| revenue_growth_4w|dir=+1|top=0.30 | 1.20 | -1.05 | 22.9% | -12.7% |
| rmom_1w|dir=+1|top=0.20 | 1.18 | 0.62 | 26.8% | 14.3% |
| dau_growth_4w|dir=+1|top=0.30 | 1.05 | -0.14 | 18.6% | -2.2% |
| fees_growth_12w|dir=+1|top=0.20 | 1.00 | 0.17 | 19.3% | 2.4% |
| volume_growth_4w|dir=+1|top=0.30 | 0.98 | 0.21 | 16.3% | 2.3% |
| transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 | 16.3% | 0.5% |
| real_transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 | 16.3% | 0.5% |

## IS-Selected Ensembles

| Ensemble | Components | IS Sharpe | OOS Sharpe | OOS Ann Ret | OOS Max DD |
|---|---:|---:|---:|---:|---:|
| is_top12 | 12 | 1.13 | 1.10 | 15.5% | -10.5% |
| is_top8 | 8 | 1.11 | 0.86 | 12.7% | -11.0% |
| is_top2 | 2 | 1.30 | 0.73 | 10.0% | -11.2% |
| onchain_is_top2 | 2 | 1.30 | 0.73 | 10.0% | -11.2% |
| is_top3 | 3 | 1.17 | 0.71 | 15.8% | -21.8% |
| is_top5 | 5 | 1.39 | 0.70 | 12.3% | -12.5% |
| onchain_is_top5 | 5 | 1.03 | 0.05 | 0.7% | -12.7% |
| onchain_is_top3 | 3 | 1.78 | 0.01 | 0.1% | -15.6% |
| onchain_is_top8 | 8 | 0.95 | -0.37 | -4.8% | -9.8% |
| onchain_is_top12 | 12 | 0.79 | -0.84 | -10.4% | -15.5% |
| is_top1 | 1 | 1.25 | -0.89 | -12.0% | -25.7% |
| onchain_is_top1 | 1 | 1.25 | -0.89 | -12.0% | -25.7% |

## Baselines

| Baseline | IS Sharpe | OOS Sharpe | OOS Ann Ret | OOS Max DD |
|---|---:|---:|---:|---:|
| EW Market | 0.37 | -0.28 | -18.7% | -68.4% |
| BTC | 0.66 | -0.16 | -6.1% | -46.7% |

## Coverage

| Signal | Symbols | Weeks | Median names/week |
|---|---:|---:|---:|
| fees_per_tx | 61 | 260 | 41 |
| real_tx_ratio | 61 | 260 | 41 |
| real_volume_ratio | 61 | 260 | 41 |
| func_fees_to_mcap | 60 | 260 | 41 |
| revenue_to_mcap | 60 | 260 | 41 |
| active_revenue_to_mcap | 60 | 260 | 41 |
| tx_to_mcap | 60 | 260 | 41 |
| real_tx_to_mcap | 60 | 260 | 41 |
| real_volume_to_mcap | 60 | 260 | 41 |
| exchange_volume_to_mcap | 60 | 260 | 41 |
| log_mcap_neg | 60 | 260 | 41 |
| mom_4w | 61 | 256 | 41 |
| rmom_1w | 61 | 256 | 41 |
| maxret_4w_neg | 61 | 256 | 41 |
| vol_4w_neg | 61 | 256 | 41 |
| fees_growth_4w | 61 | 256 | 41 |
| revenue_growth_4w | 61 | 256 | 41 |
| transactions_growth_4w | 61 | 256 | 41 |
| real_transactions_growth_4w | 61 | 256 | 41 |
| volume_growth_4w | 61 | 256 | 41 |
| real_volume_growth_4w | 61 | 256 | 41 |
| fees_growth_12w | 60 | 248 | 41 |
| revenue_growth_12w | 60 | 248 | 41 |
| transactions_growth_12w | 60 | 248 | 41 |
| real_transactions_growth_12w | 60 | 248 | 41 |
| volume_growth_12w | 60 | 248 | 41 |
| real_volume_growth_12w | 60 | 248 | 41 |
| fees_per_dau | 41 | 260 | 27 |
| revenue_per_dau | 41 | 260 | 27 |
| dau_to_mcap | 40 | 260 | 27 |

## Ensemble Components

| Ensemble | Candidate | IS Sharpe | OOS Sharpe |
|---|---|---:|---:|
| is_top1 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| is_top2 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| is_top2 | fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 |
| is_top3 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| is_top3 | fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 |
| is_top3 | rmom_1w|dir=+1|top=0.30 | 1.34 | 1.06 |
| is_top5 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| is_top5 | fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 |
| is_top5 | rmom_1w|dir=+1|top=0.30 | 1.34 | 1.06 |
| is_top5 | dau_growth_4w|dir=+1|top=0.25 | 1.28 | -0.50 |
| is_top5 | fees_growth_12w|dir=+1|top=0.20 | 1.00 | 0.17 |
| is_top8 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| is_top8 | fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 |
| is_top8 | rmom_1w|dir=+1|top=0.30 | 1.34 | 1.06 |
| is_top8 | dau_growth_4w|dir=+1|top=0.25 | 1.28 | -0.50 |
| is_top8 | fees_growth_12w|dir=+1|top=0.20 | 1.00 | 0.17 |
| is_top8 | transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| is_top8 | real_transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| is_top8 | volume_growth_4w|dir=+1|top=0.30 | 0.98 | 0.21 |
| is_top12 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| is_top12 | fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 |
| is_top12 | rmom_1w|dir=+1|top=0.30 | 1.34 | 1.06 |
| is_top12 | dau_growth_4w|dir=+1|top=0.25 | 1.28 | -0.50 |
| is_top12 | fees_growth_12w|dir=+1|top=0.20 | 1.00 | 0.17 |
| is_top12 | transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| is_top12 | real_transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| is_top12 | volume_growth_4w|dir=+1|top=0.30 | 0.98 | 0.21 |
| is_top12 | real_volume_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| is_top12 | transactions_growth_12w|dir=+1|top=0.30 | 0.95 | -0.01 |
| is_top12 | real_transactions_growth_12w|dir=+1|top=0.30 | 0.95 | -0.01 |
| is_top12 | volume_growth_12w|dir=+1|top=0.30 | 0.95 | -0.01 |
| onchain_is_top1 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| onchain_is_top2 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| onchain_is_top2 | fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 |
| onchain_is_top3 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| onchain_is_top3 | fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 |
| onchain_is_top3 | dau_growth_4w|dir=+1|top=0.25 | 1.28 | -0.50 |
| onchain_is_top5 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| onchain_is_top5 | fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 |
| onchain_is_top5 | dau_growth_4w|dir=+1|top=0.25 | 1.28 | -0.50 |
| onchain_is_top5 | fees_growth_12w|dir=+1|top=0.20 | 1.00 | 0.17 |
| onchain_is_top5 | transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| onchain_is_top8 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| onchain_is_top8 | fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 |
| onchain_is_top8 | dau_growth_4w|dir=+1|top=0.25 | 1.28 | -0.50 |
| onchain_is_top8 | fees_growth_12w|dir=+1|top=0.20 | 1.00 | 0.17 |
| onchain_is_top8 | transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| onchain_is_top8 | real_transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| onchain_is_top8 | volume_growth_4w|dir=+1|top=0.30 | 0.98 | 0.21 |
| onchain_is_top8 | real_volume_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| onchain_is_top12 | revenue_growth_4w|dir=+1|top=0.20 | 1.50 | -0.78 |
| onchain_is_top12 | fees_growth_4w|dir=+1|top=0.20 | 1.47 | 0.65 |
| onchain_is_top12 | dau_growth_4w|dir=+1|top=0.25 | 1.28 | -0.50 |
| onchain_is_top12 | fees_growth_12w|dir=+1|top=0.20 | 1.00 | 0.17 |
| onchain_is_top12 | transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| onchain_is_top12 | real_transactions_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| onchain_is_top12 | volume_growth_4w|dir=+1|top=0.30 | 0.98 | 0.21 |
| onchain_is_top12 | real_volume_growth_4w|dir=+1|top=0.30 | 0.98 | 0.05 |
| onchain_is_top12 | transactions_growth_12w|dir=+1|top=0.30 | 0.95 | -0.01 |
| onchain_is_top12 | real_transactions_growth_12w|dir=+1|top=0.30 | 0.95 | -0.01 |
| onchain_is_top12 | volume_growth_12w|dir=+1|top=0.30 | 0.95 | -0.01 |
| onchain_is_top12 | real_volume_growth_12w|dir=+1|top=0.30 | 0.95 | -0.01 |
