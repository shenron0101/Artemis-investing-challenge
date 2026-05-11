# Stage 06 - Hidden Factor Pricing

Repo-native pipeline for `Crypto Pricing with Hidden Factors`.

The stage builds a weekly crypto asset-pricing panel, constructs observed crypto factors, keeps external paper-parity inputs separable, and compares Fama-MacBeth premia with a PCA latent-control extension.

## Run Order

```bash
./.venv/bin/python 06_hidden_factor_pricing/01_build_panel.py
./.venv/bin/python 06_hidden_factor_pricing/02_observed_factors.py
./.venv/bin/python 06_hidden_factor_pricing/03_external_inputs.py
./.venv/bin/python 06_hidden_factor_pricing/04_price_models.py
./.venv/bin/python 06_hidden_factor_pricing/05_report.py
```

## Outputs

- `artifacts/data/weekly_asset_panel.parquet`: weekly returns and lagged characteristics.
- `artifacts/data/observed_factor_returns.parquet`: market, SMB, momentum, TVL, and market-orthogonal TVL factor returns.
- `artifacts/data/external_and_regime_inputs.parquet`: repo-native regime proxies plus optional user-supplied external CSVs.
- `artifacts/data/latent_factor_returns.parquet`: PCA latent return factors.
- `artifacts/tables/04_factor_premia.parquet`: Fama-MacBeth and latent-adjusted premia.
- `artifacts/tables/04_factor_survival.parquet`: whether observed factors survive latent controls by a simple sign and t-stat rule.
- `REPORT.md`: generated summary of the latest run.

## External Input Convention

Drop weekly CSVs into `06_hidden_factor_pricing/inputs/`. Each CSV must include a `week`, `date`, or `timestamp` column. Other numeric columns are loaded with an `external_<file>_<column>` prefix so paper-parity equity, sentiment, volatility, and hack variables remain separate from repo-native proxies.

## Scope Notes

This implementation uses the clean data already present in the repo: CoinGecko, Artemis, and DeFiLlama. It does not clone external repositories or download new data in the default path, because the current workspace already contains enough data for a transparent first pass and network access is restricted.

The latent-adjusted model is a practical approximation: it adds PCA factors extracted from the asset return matrix as cross-sectional controls. It is not a full Giglio-Xiu three-pass estimator with moving-block bootstrap p-values.
