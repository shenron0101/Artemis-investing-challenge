# Stage 06 - Hidden Factor Pricing

This stage implements a repo-native version of `Crypto Pricing with Hidden Factors`.
It compares observed crypto factors against the same factors after PCA latent-return controls are added to the Fama-MacBeth cross-section.

## Data Window
- Rows: 4,217
- Symbols: 86
- Weeks: 52
- Dates: 2025-05-12 00:00:00 to 2026-05-04 00:00:00
- Scope: raw weekly crypto returns from clean repo data; no risk-free, Kenneth French, CVX, Fear & Greed, Altseason, or hack-loss series are bundled.

## Observed Factors
- Columns: `crypto_market`, `crypto_smb`, `crypto_mom`, `crypto_tvl`, `crypto_tvl_orth`
- Market is value-weighted by lagged market cap.
- SMB is small-minus-big by lagged market cap.
- Momentum is winner-minus-loser using prior five-week cumulative return.
- TVL is high-minus-low by lagged TVL / market cap and is also market-orthogonalized as `crypto_tvl_orth`.

## External Inputs
Default regime inputs are repo-native proxies: `native_btc_ret`, `native_alt_equal_weight_ret`, `native_alt_minus_btc_ret`, `native_market_vol_4w`, `native_stablecoin_supply_chg`, `native_stablecoin_inflow_usd`, `native_defi_tvl_chg`.
Paper-parity CSVs can be added under `06_hidden_factor_pricing/inputs/`; loaded files are tracked in `07_hidden_factor_pricing/artifacts/manifests/03_external_inputs_manifest.json`.

## Scope of This Test
This is an **in-sample asset-pricing inference test**, not a predictive backtest. Following Giglio & Xiu, the latent factor SVD is fit on the full panel and the same panel is priced — appropriate for testing whether observed factor premia survive latent controls, not for trading. The t-stats below cannot be read as out-of-sample alpha.

## Pricing Results
| Model | Factor | Weekly lambda | t-stat | p-value |
|---|---:|---:|---:|---:|
| fama_macbeth | `crypto_market` | -0.60% | -0.671 | 0.502 |
| latent_adjusted | `crypto_market` | 2.02% | 0.771 | 0.440 |
| fama_macbeth | `crypto_mom` | 1.92% | 1.934 | 0.053 |
| latent_adjusted | `crypto_mom` | 1.23% | 0.822 | 0.411 |
| fama_macbeth | `crypto_smb` | 1.91% | 2.189 | 0.029 |
| latent_adjusted | `crypto_smb` | 2.32% | 1.970 | 0.049 |
| fama_macbeth | `crypto_tvl_orth` | 0.19% | 0.087 | 0.931 |
| latent_adjusted | `crypto_tvl_orth` | 1.55% | 0.735 | 0.463 |

## Latent-Control Survival
- `crypto_market` does not survive: FMB t=-0.671, latent-adjusted t=0.771, delta=2.62%.
- `crypto_mom` does not survive: FMB t=1.934, latent-adjusted t=0.822, delta=-0.69%.
- `crypto_smb` survives: FMB t=2.189, latent-adjusted t=1.970, delta=0.41%.
- `crypto_tvl_orth` does not survive: FMB t=0.087, latent-adjusted t=0.735, delta=1.36%.

The survival rule is intentionally simple: the latent-adjusted premium must keep the Fama-MacBeth sign and have |t| >= 1.65. This is a diagnostic threshold, not a claim of strict paper parity.

_Caveat: latent factors are extracted from the full sample; survival here means in-sample robustness, not predictive survival._

## Links Back To Artemis
- `04_factors/04_RAAM_v2_composite.py` remains the cross-sectional signal layer for M/V/C/T plus F/S/G. Stage 06 tests whether broad crypto factor premia remain visible once latent return structure is included.
- `05_btc_direction/04_train_eval.py` remains the supervised BTC-direction layer. Stage 06 is inference-first and does not feed that classifier automatically.

## Outputs
- Weekly panel: `07_hidden_factor_pricing/artifacts/data/weekly_asset_panel.parquet`
- Observed factors: `07_hidden_factor_pricing/artifacts/data/observed_factor_returns.parquet`
- Factor premia: `07_hidden_factor_pricing/artifacts/tables/04_factor_premia.parquet`
- Survival table: `07_hidden_factor_pricing/artifacts/tables/04_factor_survival.parquet`

## Method Note
Fama-MacBeth two-pass estimates are compared with a PCA latent-control extension. This is a transparent repo-native approximation, not a full Giglio-Xiu three-pass/bootstrap implementation.
