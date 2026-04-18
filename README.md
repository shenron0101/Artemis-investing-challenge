# Artemis Quant Competition — Crypto Cross-Sectional Strategy

Systematic monthly-rebalanced long/short strategy on the top-50 crypto assets. Combines macro regime filtering, correlation network structure, on-chain fundamentals, and usage metrics into a cross-sectional factor model.

Submission track: **Artemis Analytics Quant Competition, Track #1**.

---

## Research narrative

| Layer | What it answers |
|-------|----------------|
| Macro regime | Are financial conditions loose, neutral, or tight? |
| Correlation clusters | Which coins move together this month? |
| Centrality | Which coins are leaders vs. followers in the network? |
| On-chain fundamentals | Is the activity real? (fees, revenue, DAU, TVL) |
| Cross-sectional tests | Which factors predict next-month returns, and does that change by regime? |
| Portfolio construction | Translate evidence into long/short weights |

---

## Setup

### 1. Prerequisites

- Python 3.12+
- Git

### 2. Clone and create a virtual environment

```bash
git clone https://github.com/shenron0101/Artemis-investing-challenge.git
cd Artemis-investing-challenge

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure API keys

Copy the example below into a file called `.env` at the repo root and fill in your keys. The `.env` file is git-ignored and will never be committed.

```dotenv
# CoinGecko Pro API key
# Pro plan base URL: https://pro-api.coingecko.com/api/v3/
COINGECKO_API_KEY=your_key_here

# Artemis API key
# Base URL: https://data-svc.artemisxyz.com
ARTEMIS_API_KEY=your_key_here

# FRED (Federal Reserve Economic Data) — free at https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY=your_key_here

# Binance (used for supplementary market data)
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_key_here
```

---

## Running the pipeline

All scripts live in `py/` and must be run in order from that directory. Each script reads from `data/processed/` and writes back to it.

```bash
cd py

python 00_fetch_data.py          # Fetch raw price, market cap, volume from CoinGecko + Artemis
python 00b_fetch_research_context.py  # Fetch FRED macro series (FEDFUNDS, DGS2, HY spread)
python 01_data_validation.py     # Validate coverage and flag gaps
python 02_macro_regime.py        # Build monthly tight/loose/neutral regime labels
python 03_market_structure_clusters.py   # 60-day rolling correlation -> hierarchical clusters
python 04_market_structure_centrality.py # Eigenvector + betweenness centrality per coin
python 05_factor_engineering.py  # Standardize all factors; merge regime into panel
python 06_cross_sectional_tests.py       # Spearman IC + regime-conditional IC table
python 07_portfolio_construction.py      # Long/short weights across strategy variants
python 08_backtest.py            # Performance metrics, stress tests, annual returns
```

Each script prints a completion message and the path of its output file.

---

## Repository layout

```
.
├── py/                          # Main research pipeline (run these)
│   ├── 00_fetch_data.py
│   ├── 00b_fetch_research_context.py
│   ├── 01_data_validation.py
│   ├── 02_macro_regime.py
│   ├── 03_market_structure_clusters.py
│   ├── 04_market_structure_centrality.py
│   ├── 05_factor_engineering.py
│   ├── 06_cross_sectional_tests.py
│   ├── 07_portfolio_construction.py
│   └── 08_backtest.py
├── data/
│   ├── raw/                     # API responses (git-ignored)
│   └── processed/               # Parquet panels + CSV results
├── reports/                     # Generated charts (PNG)
├── plans/
│   └── 00_original_rs.md        # Original research specification
├── notebooks/                   # Exploratory work (not part of main pipeline)
├── requirements.txt
└── .env                         # API keys — create this yourself, never commit it
```

---

## Key output files

| File | Description |
|------|-------------|
| `data/processed/macro_regime_monthly.parquet` | Monthly tight/loose/neutral labels |
| `data/processed/network_clusters_monthly.parquet` | Cluster IDs, within-cluster rank, crowding density, turnover |
| `data/processed/centrality_factors_monthly.parquet` | Eigenvector + betweenness centrality per coin per month |
| `data/processed/factors_monthly.parquet` | Full standardized factor panel (21 columns incl. regime) |
| `data/processed/factor_ic_results.csv` | IC, t-stat, Q5-Q1 spread, regime-conditional IC per factor |
| `data/processed/portfolio_weights_monthly.parquet` | Monthly long/short weights for 5 strategy variants |
| `reports/ic_by_period.png` | IC time series for top factors |
| `reports/cumulative_returns.png` | Cumulative PnL across variants vs. BTC and EW benchmark |

---

## Data sources

| Source | Used for |
|--------|----------|
| [CoinGecko](https://www.coingecko.com/en/api) | Price, market cap, 24h volume, universe selection |
| [Artemis](https://artemisxyz.com) | DAU, transactions, fees, revenue, TVL, stablecoin metrics |
| [FRED](https://fred.stlouisfed.org) | FEDFUNDS, DGS2 (2y yield), BofA HY spread for macro regime |
| Binance | Supplementary market data |
