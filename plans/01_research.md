# Research plan — crypto cross-sectional factor strategy

## Objective

Monthly-rebalanced long/short strategy on the top-50 coins using on-chain
fundamentals and market data. Evaluate factor predictability, build a composite
alpha score, run a clean backtest, and produce a reproducible research artifact.

---

## Data reality (as of fetch)

All data comes from **Artemis** (primary) and **CoinGecko** (universe metadata only).

| File | Columns | Symbols | Window |
|---|---|---|---|
| `panel_artemis_daily.parquet` | symbol, date, dau, fees, mc, price, revenue, tvl, txns | 150 | 2021-01-01 → 2024-12-31 |
| `panel_market_daily.parquet` | symbol, date, price_usd, market_cap | 145 | 2021-01-01 → 2024-12-31 |
| `universe_monthly.parquet` | date, symbol, mcap_rank, market_cap | top 50 per month | 48 rebalance dates |

### Coverage caveats

- **No volume data** — Artemis does not expose a volume series in the fetched metrics.
- **No stablecoin supply series** — not in fetched metrics.
- **High null rates** for on-chain metrics: tvl (~88%), txns (~67%), revenue (~59%), fees (~62%), dau (~48%). Many coins are pure market assets with no on-chain activity.
- **CoinGecko key is Demo** — no historical chart data. Price/mc comes from Artemis.

### What this means for factors

- Momentum: available (price from Artemis, 2021–2024 ✓)
- Fundamentals (fees, revenue, TVL/mc): sparse but valid for L1/L2 chains
- Usage (dau, txns): sparse but valid where covered
- Volume-based factors: not available
- Stablecoin flow: not available
- Macro regime: no macro data fetched — **skip or stub**
- Network/centrality: computable from return correlations ✓

---

## Notebook structure

All notebooks live in `notebooks/`. Run in order.

| # | File | Status | Goal | Output |
|---|---|---|---|---|
| 00 | `00_fetch_data.py` | ✅ done | Fetch all raw data from APIs | All parquets in `data/` |
| 01 | `01_data_validation.ipynb` | 🔲 next | Inspect coverage, missingness, return sanity | Coverage report, return stats |
| 02 | `02_factors.ipynb` | 🔲 | Engineer standardized monthly factors | `factors_monthly.parquet` |
| 03 | `03_ic_tests.ipynb` | 🔲 | Factor IC / predictability tests | `factor_ic_results.csv` |
| 04 | `04_network_clusters.ipynb` | 🔲 | Monthly correlation graph + clustering | `network_clusters_monthly.parquet` |
| 05 | `05_portfolio.ipynb` | 🔲 | Composite alpha + long/short weights | `portfolio_weights_monthly.parquet` |
| 06 | `06_backtest.ipynb` | 🔲 | Backtest, diagnostics, stress tests | Plots + metrics |

Macro regime (original notebook 4) and centrality (original notebook 6) are
**deferred to Phase 2**. They require additional data or add complexity before
the base pipeline is working.

---

## Notebook 01 — Data validation

### Goal

Before building any factors, verify the data is usable.

### Sections

1. Load all three parquets
2. Universe coverage check — how many of the 48 month-ends have ≥ 40 coins with price
3. Artemis coverage heatmap — which symbols have fees, dau, tvl, txns (and for how many months)
4. Return sanity — compute daily and monthly returns; flag extreme outliers (>100% in a day)
5. Survivorship check — coins present in early vs late universe
6. Summary table: per-factor coverage count and median non-null months per symbol

### Output

Printed/displayed summary only. No parquet saved.

---

## Notebook 02 — Factor engineering

### Goal

Produce a clean `factors_monthly.parquet` with one row per (symbol, rebalance_date).

### Input

- `panel_artemis_daily.parquet`
- `universe_monthly.parquet`

### Rebalance convention

At each month-end date `t`:
- use data available up to and including `t` (no lookahead)
- all lookback windows use trailing calendar days ending at `t`

### Factor definitions

#### Group A — Momentum (from Artemis `price`)

| Factor | Definition |
|---|---|
| `mom_1m` | Return over trailing 30 days |
| `mom_3m` | Return over trailing 90 days |
| `mom_6m` | Return over trailing 180 days |
| `vol_30d` | Annualized realized volatility, trailing 30 days |

#### Group B — Fundamentals (from Artemis `fees`, `revenue`, `mc`)

| Factor | Definition |
|---|---|
| `fees_mc` | fees (30d avg) / market_cap |
| `rev_mc` | revenue (30d avg) / market_cap |
| `fees_growth_30d` | (fees_30d_avg / fees_30d_avg_lagged_30d) - 1 |
| `rev_growth_30d` | (rev_30d_avg / rev_30d_avg_lagged_30d) - 1 |

Only computed where fees/revenue coverage > 15 days in the 30-day window.

#### Group C — Usage (from Artemis `dau`, `txns`)

| Factor | Definition |
|---|---|
| `dau_growth_30d` | (dau_30d_avg / dau_30d_avg_lagged_30d) - 1 |
| `txns_growth_30d` | (txns_30d_avg / txns_30d_avg_lagged_30d) - 1 |
| `dau_zscore` | z-score of dau vs own trailing 90-day history |

Only computed where coverage > 15 days in the window.

#### Group D — TVL (from Artemis `tvl`, `mc`)

| Factor | Definition |
|---|---|
| `tvl_mc` | tvl (30d avg) / market_cap |
| `tvl_growth_30d` | (tvl_30d_avg / tvl_30d_avg_lagged_30d) - 1 |

### Standardization

At each rebalance date:
1. Winsorize each factor at 1st/99th percentile across the universe
2. Z-score cross-sectionally (mean 0, std 1)
3. Fill remaining NaN with 0 (neutral score)

### Save

`data/processed/factors_monthly.parquet` — columns: symbol, date, [factor names]

---

## Notebook 03 — IC tests

### Goal

Check whether each factor predicts next-month returns before building a strategy.

### Method

For each factor at each rebalance date `t`:
- forward return = price return from `t` to `t+1` (next rebalance date)
- compute Spearman rank IC between factor score and forward return

### Summary statistics

For each factor:
- mean IC
- IC std
- IC t-stat (`mean / std * sqrt(N_periods)`)
- % periods positive IC
- Q5-Q1 spread (top 20% minus bottom 20% avg forward return)

### Output table

| Factor | Mean IC | IC Std | t-stat | Hit Rate | Q5–Q1 Spread |
|---|---:|---:|---:|---:|---:|

### Save

`data/processed/factor_ic_results.csv`

---

## Notebook 04 — Network clusters

### Goal

Add a cluster-relative momentum factor using return correlations.

### Method

At each rebalance date `t`:
1. Compute rolling 60-day return correlation matrix for universe coins
2. Run hierarchical clustering (ward linkage) to assign cluster IDs
3. For each coin: compute within-cluster rank (by that coin's 30d return vs cluster peers)

### Output

`data/processed/network_clusters_monthly.parquet` — columns: symbol, date, cluster_id, cluster_size, within_cluster_rank

Then feed `within_cluster_rank` back into notebook 02/05 as an additional factor.

---

## Notebook 05 — Portfolio construction

### Goal

Build long/short weights from factor scores.

### Composite alpha

Use only factors with mean IC t-stat > 1.0 (from notebook 03). Equal-weight the
selected factors into a composite score.

### Long/short rule

At each rebalance date:
- Long: top quintile by composite score (10 coins)
- Short: bottom quintile by composite score (10 coins)
- Equal-weight within each book

### Variants to evaluate

1. Momentum only (baseline)
2. Fundamentals + usage only
3. Full composite (all significant factors)
4. Full composite + within-cluster rank

### Save

`data/processed/portfolio_weights_monthly.parquet` — columns: symbol, date, weight, variant

---

## Notebook 06 — Backtest

### Goal

Compute returns, statistics, and diagnostics for each portfolio variant.

### Return calculation

At each rebalance date `t → t+1`:
- portfolio return = sum of (weight × forward return) for each coin
- no transaction costs in base case; add 10bps per leg as sensitivity

### Metrics (per variant)

- CAGR
- Annualized volatility
- Sharpe ratio (annualized, no risk-free rate or use 0)
- Max drawdown
- Average monthly turnover
- Hit rate (% months positive)

### Benchmarks

- Equal-weight top-50 universe (long only)
- BTC buy-and-hold

### Diagnostics

- Cumulative return chart (strategy vs benchmarks)
- Long vs short book contribution
- Rolling 12-month Sharpe
- Annual return table

### Stress tests

- Lag all fundamentals by 3 days
- Add 10bps one-way transaction cost
- Exclude top 5 coins by market cap
- Evaluate loose vs tight BTC regime (BTC trailing 90d return > 0 = loose)

---

## Factor data constraints

**Available for all coins**: price, market_cap → momentum, vol  
**Available for ~40–60 coins**: fees, revenue → fundamental factors  
**Available for ~30–50 coins**: dau, txns → usage factors  
**Available for ~15 coins**: tvl → TVL factors  

This is acceptable. Factors with sparse coverage are standardized over whoever
has data; coins without coverage get a neutral score of 0.

---

## What would break this strategy

- On-chain metrics available on Artemis may lag real activity or be restated
- Very high null rates in tvl/txns mean those factors only apply to DeFi/L1 chains
- Monthly rebalance on just 10 long / 10 short is concentrated — idiosyncratic risk is high
- Backtest window (2021–2024) includes one of the strongest bull markets in crypto history — momentum will look good regardless
- No transaction cost modeling beyond a haircut sensitivity

---

## Deliverables

1. `reports/research_report.md` — written after notebook 06
2. `reports/pitch_deck_outline.md` — summary for non-technical audience
