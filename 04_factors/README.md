# 04_factors — Three Novel Crypto Factors + RAAM v2

Three economically-grounded factors designed to fill the gaps in the existing
RAAM (M / V / C / T) model from `02_Research/rank.md`. RAAM v1 is entirely
price-derived; v2 adds the value, supply, and fundamental-momentum dimensions
that the research synthesis identified as missing.

Run from the project root:
```bash
01_Data_Collection/.venv/bin/python 04_factors/01_F_fundamental_yield.py
01_Data_Collection/.venv/bin/python 04_factors/02_S_supply_absorption.py
01_Data_Collection/.venv/bin/python 04_factors/03_G_activity_growth.py
01_Data_Collection/.venv/bin/python 04_factors/04_RAAM_v2_composite.py
```

Each script writes PNG + interactive HTML to `04_factors/figures/<stem>/`.

## The factors

| Factor | Economic mechanism | Formula | Equity analog |
|---|---|---|---|
| **F** Fundamental Yield | Real cash-flow yield = implicit downside support | `(annualised fees + 0.5 × revenue) / market_cap` | P/S, P/E |
| **S** Supply Absorption | Mechanical dilution drag; tokens absorbing supply outperform | `−z(emission_90d)` | Issuance factor (Pontiff & Woodgate 2008) |
| **G** Activity-Validated Growth | Fundamental momentum; price w/o usage growth is a bubble flag | `mean(z[Δdau, Δfees, Δrev]) − 0.5 z(log_ret_90d)` | Earnings revision (Bernard & Thomas 1989) |

## Files

| Path | Outputs |
|---|---|
| [`_common.py`](_common.py) | Shared helpers: `exclude_symbols`, `prices_wide`, `log_returns_wide`, `forward_returns`, `cross_sectional_rank`, `spearman_ic`, `ic_summary`, `save`, `load` |
| [`01_F_fundamental_yield.py`](01_F_fundamental_yield.py) | `01_yield_distribution`, `02_F_rank_heatmap`, `03_F_vs_M_scatter`, `04_F_information_coefficient` |
| [`02_S_supply_absorption.py`](02_S_supply_absorption.py) | `01_implied_supply_sanity`, `02_emission_distribution`, `03_emission_vs_overhang`, `04_S_information_coefficient` |
| [`03_G_activity_growth.py`](03_G_activity_growth.py) | `01_growth_quadrant`, `02_per_metric_growth_heatmap`, `03_G_vs_F_scatter`, `04_G_information_coefficient` |
| [`04_RAAM_v2_composite.py`](04_RAAM_v2_composite.py) | `01_factor_correlation`, `02_v1_vs_v2_top25`, `03_per_factor_cumulative_ic`, `04_composite_v1_vs_v2_ic` |

## Key findings from the IC scoreboard

(`figures/04_RAAM_v2_composite/03_per_factor_cumulative_ic.png`, h=30d, full sample)

> **Pre-fix values** — table reflects results before the A1/A2 correctness fixes.
> See `figures/04_RAAM_v2_composite/03_per_factor_cumulative_ic.png` for current values after re-running.

| Factor | mean IC | IR | Verdict |
|---|---:|---:|---|
| **V** Volatility | +0.21 | +0.98 | Workhorse |
| **C** Correlation | +0.18 | +0.67 | Workhorse |
| **S** Supply Absorption | +0.12 | +0.79 | New independent signal |
| **M** Momentum | +0.06 | +0.34 | Weakly useful |
| **F** Fundamental Yield | +0.02 | +0.09 | Neutral on h=30d (positive at h=60/90) |
| **T** ATR Trend | +0.00 | +0.03 | Veto-only, no cross-sectional alpha |
| **G** Growth | −0.04 | −0.30 | Negative — current formulation hurts |

Equal-weighting all seven into v2 *dilutes* v1's signal (composite IC drops
from +0.195 to +0.156). The honest read: the next iteration should **IC-weight**
the composite, not equal-weight, and either reformulate or drop G.

## Conventions

Same as `03_analysis/`: VS Code `# %%` cells, `save()` writes PNG (kaleido) and
HTML; stable / wrapped / bridged tickers excluded via `exclude_symbols()`;
palettes `Set2 / Viridis / RdBu`; no matplotlib.

Stable/wrapped/bridged exclusion is critical — `coingecko_coin_details.symbol`
is lowercased while every other table is uppercase, so the helper upper-cases
on the way out (lesson from `03_analysis/05_factor_signals.py`).

## Caveats

- **Sample**: 12 months of daily data → ICs come from at most ~330 daily
  cross-sections of ≤80 symbols. Treat magnitudes as directional, not as
  out-of-sample alpha.
- **Coverage**: F and G are computable for ~30–40 symbols (the protocols with
  Artemis fee/revenue/DAU coverage); S covers ~80 symbols.
- **Implied supply**: derived from `market_cap_usd / price_usd`. Sanity checked
  against BTC (~3% annual drift), ETH (~flat), ARB/OP (visible step-ups at
  unlocks). Susceptible to CoinGecko mid-period revisions.
- **FDV missing**: BTC/ETH/USDT have no FDV cap → overhang z-score is
  back-filled to 0 (neutral) so they aren't dropped from S.
- **FDV-overhang removed from S IC test**: only the latest CoinGecko snapshot
  is available — tiling it across history introduces look-ahead. The snapshot
  is still visualised in `02_S_supply_absorption/03_emission_vs_overhang` as a
  cross-sectional descriptive. S is now `−z(emission_90d)` only.
