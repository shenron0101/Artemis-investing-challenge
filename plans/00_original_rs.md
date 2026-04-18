Research plan for a crypto cross-sectional strategy notebook
Objective

Build a monthly-rebalanced long/short strategy on the top 50 coins that combines:

Macro regime filter
Correlation / network structure
Centrality and dynamic clustering
Usage / fundamentals / stablecoin / market-structure factors
Cross-sectional portfolio construction and backtesting

Use:

CoinGecko for price, market cap, volume, exchange/derivatives metadata
Artemis for crypto fundamentals and on-chain usage metrics such as users, transactions, fees, revenue, TVL, and stablecoin data, which Artemis explicitly markets as core series available through its platform/API. CoinGecko’s API explicitly supports market data and historical chart data for coins.
High-level research hypothesis
Main story

Your framework is:

Macro regime tells you whether risk conditions are loose or tight
Clusters tell you which coins currently move together
Centrality tells you which coins are leaders / bridges / systemic nodes
Usage and fundamentals tell you whether activity is real
Market structure tells you whether the move is crowded, healthy, or fragile

That is a strong and coherent research narrative.

Notebook structure
Notebook 0 — Setup and config
Goal

Create a single source of truth for:

API keys
date ranges
universe rules
file paths
factor settings
Sections
imports
env loading
config dict
helper functions
cache directory setup
Output

A reusable config object for all later notebooks.

Notebook 1 — Universe construction
Goal

Define the top 50 coin universe each rebalance date.

Data source

CoinGecko

Use CoinGecko to fetch:

coin list / IDs
market cap
price
24h volume

CoinGecko’s /coins/markets endpoint is designed for querying listed coins with price, market cap, volume, and related market fields. Historical market chart endpoints are also documented.

Universe rule

At each month-end:

Pull market caps
Filter out:
stablecoins
wrapped assets if needed
obvious duplicate tickers / synthetic assets
Take top 50 by market cap or top 50 by volume among sufficiently large caps
Freeze that universe for the next month
Why

This avoids lookahead and survivorship mistakes.

Save
universe_monthly.parquet
Notebook 2 — Market data panel
Goal

Create a daily market panel for all coins in the rolling universe.

Data source

CoinGecko

Pull

For each coin:

daily price
market cap
24h volume

CoinGecko documents historical market chart/range endpoints for time series of price, market cap, and volume.

Derived features
daily returns
weekly returns
monthly returns
realized volatility
dollar volume momentum
turnover proxy
downside volatility
beta to crypto market index
Save
panel_market_daily.parquet
Notebook 3 — Artemis fundamentals / usage panel
Goal

Build daily or weekly fundamental time series.

Data source

Artemis

Artemis publicly describes coverage of:

revenue
fees
users
TVL
stablecoin metrics
prices
protocol / chain dashboards and API-driven workflows.
Pull groups
A. Usage factors
transactions
active users
activity growth
B. Fundamental factors
fees
revenue
TVL
protocol KPIs available for that asset / chain
C. Stablecoin / flow factors
stablecoin supply
transfer activity
adoption proxies
D. Market structure factors
exchange share if available
volume-related Artemis series if available
Derived features

For each metric:

7d growth
30d growth
90d growth
z-score vs own history
percentile rank vs cross-section

acceleration:

Δ
30d
	​

−Δ
7d
	​

Important handling

Many metrics will exist for chains/protocols but not every token. So define:

token-level factors
ecosystem-level factors mapped back to tokens

Example:

SOL token gets Solana chain metrics
JUP gets Solana ecosystem metrics plus token market data
Save
panel_artemis_daily.parquet
Notebook 4 — Macro regime filter
Goal

Build a monthly macro state variable.

Inputs

You mentioned “funding rates from banks,” so in practice this likely means:

policy rate
front-end rates
dollar liquidity proxy
2y yield / real yield / credit spread
Regime examples
Loose
Neutral
Tight
Simple version

Use one scalar monthly regime score:

RegimeScore
t
	​


Then:

trade full risk in loose regimes
cut gross exposure in tight regimes
optionally tilt toward defensive / high-quality factors in tight regimes
Output
macro_regime_monthly.parquet
Notebook 5 — Correlation network and dynamic clustering
Goal

Build the market graph each month.

Inputs

From CoinGecko market panel:

rolling 60d daily returns

Optional later:

volume correlations
volatility similarity
Artemis feature similarity
Step 1 — Correlation matrix

For each rebalance date:

compute rolling correlation matrix for top 50 coins
Step 2 — Convert to graph

Nodes:

coins

Edges:

correlation above threshold
or
weighted edges using:
w
ij
	​

=max(ρ
ij
	​

,0)
Step 3 — Dynamic clustering

Run monthly clustering using one of:

hierarchical clustering
spectral clustering
Louvain / Leiden on graph
Outputs

For each month:

cluster ID for each coin
cluster size
cluster average return
cluster dispersion
cluster turnover from previous month
Research questions
Are cluster leaders stronger than followers?
Do cluster-relative winners persist?
Is one global cluster enough, or do dynamic clusters add alpha?
Save
network_clusters_monthly.parquet
Notebook 6 — Centrality features
Goal

Measure importance of each coin within the market graph.

Compute monthly
degree centrality
weighted degree
eigenvector centrality
betweenness centrality
closeness centrality
Derived features
centrality rank
centrality change over 1m / 3m
within-cluster centrality
market-wide centrality
bridge score:
high betweenness + cross-cluster links
Research questions
Do rising-centrality coins outperform?
Are highly central coins safer leadership assets?
Are bridge assets early narrative transmitters?
In tight regimes, do central coins hold up better?
Save
panel_centrality_monthly.parquet
Notebook 7 — Factor engineering
Goal

Turn all raw series into standardized factors.

Factor buckets
1. Momentum

From CoinGecko:

20d return
60d return
120d return
residual momentum if you want
2. Usage

From Artemis:

active users growth
transactions growth
activity acceleration
3. Fundamentals

From Artemis:

fees growth
revenue growth
fees / market cap
revenue / FDV or market cap
TVL growth
TVL / market cap
4. Stablecoin / flow

From Artemis:

stablecoin supply growth
transfer activity growth
adoption proxies
5. Market structure

Mainly CoinGecko, optionally Artemis:

volume growth
turnover
volatility
market cap rank
exchange / derivatives share if reliably available
6. Network structure

From graph work:

centrality
centrality momentum
cluster-relative rank
within-cluster momentum
cluster crowding / correlation density
Standardization

At each rebalance:

winsorize
z-score cross-sectionally
optionally neutralize by size or cluster
Save
factors_monthly.parquet
Notebook 8 — Research and IC testing
Goal

Check whether factors actually predict next-month returns.

Method

For each factor:

sort coins into quintiles or terciles
compute next-month forward returns
calculate:
mean spread return
hit rate
rank IC
t-stats
stability by regime
Key tests
A. Standalone factor tests
momentum only
usage only
fundamentals only
centrality only
B. Conditional tests
centrality within cluster
fundamentals conditional on loose/tight regime
momentum conditional on rising usage
high centrality + positive fundamentals
C. Interaction tests

Examples:

high usage growth + rising centrality
high fees growth + low crowding
cluster leader + positive stablecoin inflow
Output

A table like:

Factor	Mean IC	t-stat	Q5-Q1 spread	Tight regime	Loose regime
Save
factor_test_results.csv
Notebook 9 — Portfolio construction
Goal

Build the actual strategy.

Monthly rebalance

At month-end:

determine regime
define universe
compute factor scores
combine into composite alpha
rank coins
go:
long top decile/quintile
short bottom decile/quintile
Score example
AlphaScore=0.20⋅Momentum+0.20⋅Usage+0.20⋅Fundamental+0.15⋅StablecoinFlow+0.15⋅Centrality+0.10⋅ClusterRelative
Constraints
equal-weight within long and short
cap single-name weight
optional cluster neutrality
optional beta neutrality to crypto market
turnover penalty
Variants to compare
no clusters
clusters only
clusters + centrality
regime-aware vs no regime
Save
portfolio_weights_monthly.parquet
Notebook 10 — Backtest and diagnostics
Goal

Evaluate whether the strategy is investable.

Metrics
CAGR
annualized vol
Sharpe
max drawdown
hit rate
turnover
average gross exposure
exposure by cluster
exposure by size bucket
Diagnostics
cumulative PnL
long book return
short book return
contribution by factor sleeve
contribution by regime
contribution by cluster
Stress checks
remove top 5 largest coins
remove memecoins
add transaction cost haircut
lag fundamentals by a few days
lag monthly rebalance execution by 1 day
Data source mapping
CoinGecko

Use for:

universe selection
daily prices
daily market cap
daily volume
exchange / derivatives reference metadata if useful

CoinGecko explicitly provides market endpoints and historical chart endpoints for prices, market cap, and volume.

Artemis

Use for:

active users
transactions
fees
revenue
TVL
stablecoin metrics
chain/protocol KPI series

Artemis publicly positions itself as a source for users, fees, revenue, TVL, stablecoin analytics, prices, and protocol/chain comparisons.