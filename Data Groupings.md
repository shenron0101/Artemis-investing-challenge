# Data Groupings — Artemis Track #1

---

## Coins / Tokens

- **Market & Price**
  - Price, market cap, 24h volume — CoinGecko (API)
  - Supply, FDV, circulating supply — CoinGecko (API)
  - ATH / ATL + dates — CoinGecko (browser)
  - OHLCV bars — Binance (API)
  - Quote volume, trade count — Binance (API)

- **Identity & Metadata**
  - CoinGecko ID, categories, chain tags — CoinGecko (API + browser)
  - Artemis ID / symbol mapping — Artemis (API `/asset/symbols/`)
  - Binance pair symbol — Binance (API)
  - Exclusion flags (stable, wrapped, bridged) — CoinGecko (browser)

- **Usage & Activity**
  - Transactions, real transactions — Artemis (API)
  - Volume, real volume — Artemis (API)
  - Cumulative buyers, cumulative sellers — Artemis (API)
  - % gamed transactions, % gamed volume — Artemis (API)
  - Avg transaction size — Artemis (API)
  - DAU, active addresses — Artemis (API)

- **Activity Breakdowns** (dimensions on usage metrics above)
  - By chain — Artemis (API `dimensionType=CHAIN`)
  - By facilitator / protocol — Artemis (API `dimensionType=PROTOCOL`)
  - By category — Artemis (API `dimensionType=CATEGORY`)
  - Real vs gamed split — Artemis (API `dimensionType=VERSION`)

- **Monetization**
  - Fees, revenue, active/passive revenue — Artemis (API)
  - Fees / revenue at 24h / 7d / 30d / annualized / cumulative — DeFiLlama (API + browser)
  - Holders revenue, incentives, earnings — DeFiLlama (browser)

- **Capital & Balance Sheet**
  - Protocol TVL — DeFiLlama (API)
  - Treasury total + composition (majors / stables / own tokens) — DeFiLlama (browser)
  - Total raised, fundraising history — DeFiLlama (browser)
  - Token unlocks — DeFiLlama (browser)
  - Staked amount — DeFiLlama (browser)

---

## Chains

- **Market (native token)**
  - Price, market cap — CoinGecko (API)
  - OHLCV — Binance (API)

- **Capital / TVL**
  - Chain TVL total (current) — DeFiLlama (API `/v2/chains`)
  - Chain TVL historical — DeFiLlama (API `/v2/historicalChainTvl/{chain}`)
  - TVL by protocol on chain — DeFiLlama (API `/protocol/{protocol}`)

- **Activity**
  - Transactions, real transactions — Artemis (API)
  - DAU, active addresses — Artemis (API)
  - % gamed — Artemis (API)

- **Monetization**
  - Fees / revenue — DeFiLlama (API `/overview/fees`) + Artemis (API)

- **Flows**
  - Netflow, inflow, outflow — Artemis (API `/flows/top/`)

- **Stablecoins on Chain**
  - Stablecoin supply by chain — Artemis (API, e.g. `usdc-eth`)
  - Stablecoin transfer volume by chain — Artemis (API, e.g. `payments-eth`)
  - Stablecoin inflows by chain — DeFiLlama (API `/stablecoincharts/{chain}`)

- **Classification**
  - Chain family (EVM / Non-EVM / Rollup / Cosmos / SVM / etc.) — DeFiLlama (browser)
  - Ecosystem grouping (Superchain, Arbitrum Chains, etc.) — DeFiLlama (browser)

---

## Protocols / Apps

- **Capital**
  - TVL total — DeFiLlama (API `/protocol/{protocol}`)
  - TVL by chain breakdown — DeFiLlama (API + browser)

- **Monetization**
  - Fees, revenue, holders revenue, incentives, earnings — DeFiLlama (API `/summary/fees/{protocol}` + browser)

- **Balance Sheet**
  - Treasury total + composition — DeFiLlama (browser)
  - Total raised — DeFiLlama (browser)
  - Token unlocks — DeFiLlama (browser)

- **Token / Market**
  - Price, market cap, FDV — CoinGecko (API) + DeFiLlama (browser)
  - CEX vs DEX volume split — DeFiLlama (browser)
  - Staked amount — DeFiLlama (browser)

---

## Sectors / Themes

- **Aggregate Activity**
  - Total and adjusted transactions, volume — Artemis (browser + API)
  - Market share by member — Artemis (browser)
  - % gamed — Artemis (browser + API)
  - Buyers, sellers — Artemis (API)

- **Members**
  - Constituent list — Artemis (browser)
  - Per-member metrics (same as Coins group above) — Artemis (API)

---

## Stablecoins *(macro signal layer, not investable)*

- **Supply**
  - Total supply — Artemis (API) + DeFiLlama (API `/stablecoins`)
  - Supply by chain — Artemis (API `usdc-eth` syntax)
  - Supply by category-chain — Artemis (API `payments-eth` syntax)

- **Activity**
  - Transfer volume — Artemis (API)
  - Transactions, DAU — Artemis (API)
  - Inflows (global + by chain) — DeFiLlama (API `/stablecoincharts/all` + `/{chain}`)

- **Market Health**
  - % off peg — DeFiLlama (browser + API)
  - USDT dominance — DeFiLlama (browser)
  - By backing type / peg type — DeFiLlama (browser)


# Data Sources Reference — Artemis Track #1

Scope: Artemis Track #1 (Crypto Factor Rebalancing). All four data sources in one place.

---

## 1) Division of labor

| Source | Best for |
|---|---|
| **Artemis** | Usage quality, adjusted vs gamed activity, sector/theme exploration, stablecoins, flows |
| **CoinGecko** | Price, market cap, volume, supply/FDV, categories, identity mapping |
| **Binance** | Clean OHLCV returns, exchange-traded liquidity proxies, intraday backfills |
| **DeFiLlama** | TVL, fees/revenue, treasury, stablecoin macro, protocol business metrics |

Natural stack:
- CoinGecko / Binance = market layer
- Artemis = usage-quality layer
- DeFiLlama = business / capital layer

---

## 2) What a Track #1 factor dataset needs

1. **Universe definition** — market cap, liquidity, exclusions (stables, wrapped, bridged)
2. **Returns** — daily or weekly price series
3. **Factor signals** — price-based, on-chain/usage, monetization, capital deployment
4. **Implementation controls** — volume, concentration, quality filters, spam/gamed-activity filters

---

## 3) Artemis

### 3.1 Access modes

| Mode | Best for | Credential |
|---|---|---|
| REST API | Systematic time-series pulls | `ARTEMIS_API_KEY` query param |
| Web UI (Terminal) | Sector/theme exploration, quick CSV exports | Login required |
| Python SDK (`pip install artemis`) | Simpler querying than raw REST | Same API key |
| Sheets plugin (`=ART(...)`) | Small comp tables | Same API key |
| Snowflake Data Share | Large-scale history, address-level stablecoin datasets | Separate share access |

REST base URL: `https://data-svc.artemisxyz.com`
Docs index: `https://app.artemis.xyz/docs/llms.txt`

### 3.2 Web dashboard structure

Top-level navigation: Home, Screener, Sectors, Themes, Research, Apps

The dashboard is not a black box — it calls `https://data-svc.artemisxyz.com/v2/data/...` endpoints that can be replicated directly via API.

#### Sector page (Agentic Payments)

URL: `https://www.artemis.ai/sectors/agentic-payments`
Description: "AI-driven payment protocols enabling autonomous machine-to-machine transactions across crypto rails."
Members: Machine Payments Protocol (`mpp`), x402 (`x402`)
Time controls: 1W, 1M, 3M, YTD, 1Y, 3Y, 5Y, Max (weekly granularity by default)
Export: Download as image / CSV per chart

Chart families exposed:
1. Total Transactions
2. Adjusted Transactions
3. Total Volume
4. Adjusted Volume
5. Adjusted Sellers
6. Adjusted Buyers
7. Market Share (Adjusted Transactions)
8. Market Share (Adjusted Volume)
9. % Gamed Transactions
10. % Gamed Volume
11. Average Txn Size

Live endpoint pattern observed:
```
GET /v2/data/txns?symbols=mpp,x402&startDate=...&endDate=...&granularity=WEEK
GET /v2/data/real_txns?...
GET /v2/data/volume?...
GET /v2/data/real_volume?...
GET /v2/data/cumulative_sellers?...
GET /v2/data/cumulative_buyers?...
GET /v2/data/percent_gamed_txns?...
GET /v2/data/percent_gamed_volume?...
GET /v2/data/avg_txn_size?...
```

Changing time window (1Y → Max) shifts `startDate` from `2025-05-06` to `2016-05-06` in the underlying requests.

#### Asset pages: x402

Tabs: Overview, Key Metrics, Breakdowns

**x402 overview (30D snapshot)**
- Transactions: 124.5K (+39.8%)
- Volume (USD): $66.6K (+61.9%)
- Avg Transaction Size: $0.53 (+15.9%)
- Cumulative Sellers: 5.5K (+8.5%)
- Cumulative Buyers: 534.1K (+44.7%)

x402: Open payment protocol incubated by Coinbase and Cloudflare. Lets web services charge for APIs/content without accounts or subscriptions. Positioned for AI agents and humans. Apache-2.0. Founded 2025.

**x402 breakdown endpoint patterns**
```
GET /v2/data/txns?symbols=x402&dimensionType=VERSION&granularity=DAY
GET /v2/data/real_txns?...&dimensionType=CHAIN...
GET /v2/data/real_txns?...&dimensionType=PROTOCOL...
GET /v2/data/real_txns?...&dimensionType=CATEGORY...
```

**x402 real transactions by chain (sampled cumulative)**
- Base: 5,142,960
- Solana: 1,432,533
- Polygon PoS: 405,989
- Avalanche C-Chain / Sei: negligible

**x402 facilitators observed**: Coinbase, Dexter, Payai, Virtuals Protocol, Polygon Labs, Corbits, Relai, Other

**x402 categories observed**: Agent to Agent Services, Data as a Service, Infrastructure & Utilities, AI Generated Content, Premium Content & Paywalls, Token Launches & Fair Mints, Other

#### Asset pages: MPP

**MPP overview (30D snapshot)**
- Transactions: 12.6K (+190.0%)
- Volume (USD): $2.5K (-68.2%)
- Cumulative Sellers: 110 (+37.5%)
- Cumulative Buyers: 5.3K (+109.1%)

MPP: Protocol by Stripe and Tempo for paying for services in the same HTTP request. Positioned for agents, apps, and humans. Founded 2026.

**MPP real vs gamed (sampled window)**
- Real txns: 172,847 | Gamed txns: 144,440
- Real volume: $33,473 | Gamed volume: $32,646

#### Latest sector-level weekly readings

| Metric | mpp | x402 |
|---|---|---|
| Transactions | 90,813 | 836,313 |
| Adjusted transactions | 28,135 | 696,522 |
| Volume (USD) | $18,338 | $410,818 |
| Adjusted volume (USD) | $1,292 | $299,068 |
| Cumulative sellers | 110 | 5,484 |
| Cumulative buyers | 5,136 | 525,331 |
| % gamed txns | 69.1% | 16.6% |
| % gamed volume | 92.4% | 27.3% |
| Avg txn size (USD) | $0.21 | $0.49 |

x402 dominates by activity and volume. MPP has far higher gamed share — raw growth factors are unreliable without adjusted filtering.

### 3.3 REST API endpoints

**A) List supported assets**
```
GET /asset/symbols/
```
Returns: `artemis_id`, `symbol`, `coingecko_id`, `title`, `color`

**B) List available metrics for a symbol**
```
GET /supported-metrics/?symbol=BTC
```
Returns per metric: label, unit, aggregation_type, description, methodology, source_link, tags, cuts/dimensions

**C) Fetch metric time series**
```
GET /data/api/{metricNames}/?symbols=BTC,ETH&startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&APIKey=...
```
- `metricNames` is comma-separated (e.g., `txns,real_txns,fees`)
- Response: `data.symbols.<symbol>.<metric> = [{date, val}, ...]`
- Supports `summarize=true` mode

**D) Stablecoin endpoints**
```
GET /data/api/STABLECOIN_SUPPLY
GET /data/api/STABLECOIN_TRANSFER_VOLUME
```
Symbol syntax:
- `usdc` — asset
- `usdc-eth` — asset on chain
- `payments-eth` — category on chain (directly relevant to agentic payments research)

**E) Flows endpoint**
```
GET /flows/top/?startDate=...&endDate=...&sourceChains=...&flowType=netflow|inflow|outflow&breakdown=chains&APIKey=...
```

### 3.4 Recommended pull pattern

1. Call `/asset/symbols/` once → build Artemis symbol universe
2. For symbols of interest, call `/supported-metrics/?symbol=...` → discover metric names + definitions
3. Pick a core set of factor metrics (usage + monetization + quality)
4. Pull time series in bulk via `/data/api/{metricNames}/...`
5. Store raw JSON as immutable snapshots (with params + timestamps)

Note: Artemis maintains a metric deprecation/migration guide. Core names like DAU/TXNS/FEES/REVENUE remain stable, but confirm aliases before building pipelines.

### 3.5 Available metric families (discover exact names via `/supported-metrics`)

- Adoption: DAU, TXNS, active addresses
- Monetization: FEES, REVENUE, ACTIVE_REVENUE, PASSIVE_REVENUE
- Quality: real/adjusted vs gamed split (`real_txns`, `real_volume`, `percent_gamed_txns`, `percent_gamed_volume`)
- Stablecoin activity: supply, transfer volume, txns, DAU
- Ecosystem flows: inflow/outflow/netflow by chain

### 3.6 Best Artemis-derived factor features

- Adjusted transaction growth
- Adjusted volume growth
- Real / total ratio
- Gamed share (penalty)
- Chain breadth / concentration (HHI across chains)
- Facilitator concentration
- Category mix and diversification

---

## 4) CoinGecko

### 4.1 Access

API root: `https://api.coingecko.com/api/v3/`
Auth header: `x-cg-demo-api-key: <KEY>` (or query param `x_cg_demo_api_key=<KEY>`)
Rate limit: ~30 calls/minute on demo tier (varies by traffic)

Treat as snapshot-only: cache every API pull with timestamp for reproducibility.

### 4.2 Dashboard surface (coin page fields)

Reference: `https://www.coingecko.com/en/coins/ethereum`

| Section | Fields |
|---|---|
| Price + ranking | Current price, rank, multi-horizon % changes, 24h range |
| Chart | 24H/7D/1M/3M/YTD/1Y/Max windows; Price/Price in BTC/Price in ETH/Market Cap; export PNG/SVG/JPEG/PDF |
| Compare | Selected, popular, similar, recently compared coins with metric selection |
| Statistics | Market Cap, Market Cap / FDV, FDV, 24H Volume, Circulating Supply, Total Supply, Max Supply, Treasury Holding |
| Identity | Website, explorers, wallets, community, source code, **API ID**, chains, categories |
| Historical | All-time high, all-time low, dates for both |
| News | "Why [asset] is moving," recent events, source links |
| Sentiment | Bullish / bearish community split |

### 4.3 Best CoinGecko-derived factor features

- Universe construction (top N by market cap, liquidity filter by 24h volume)
- Momentum, reversal, volatility, drawdown from ATH
- Category / chain labels for sector-neutral construction
- Exclusion flags (stables, wrapped, meme assets)
- Valuation denominators: market cap, FDV, supply fields
- Cross-source identity anchor: CoinGecko ID links to Artemis and Binance

CoinGecko is the market layer, not the fundamental layer.

---

## 5) Binance

### 5.1 Access modes

**Mode A: REST API** (no auth for market data)
```
GET /api/v3/klines
```
Params: `symbol` (e.g., `ETHUSDT`), `interval` (1d, 1h, ...), `startTime`, `endTime`, `timeZone`, `limit` (up to 1000)
Response columns: open time, O, H, L, C, volume, close time, quote asset volume, number of trades, taker buy base, taker buy quote, ignore

Market-data-only domain: `https://data-api.binance.vision`

**Mode B: Bulk data downloads** (best for backfills)
- `https://data.binance.vision/` — daily/monthly zip files for spot/futures klines
- `https://github.com/binance/binance-public-data/` — instructions and scripts

Gotcha: SPOT bulk file timestamps from Jan 1, 2025 onwards may be in microseconds.

### 5.2 Best Binance-derived factor features

- Close-to-close returns (lower noise than CoinGecko for listed assets)
- Realized volatility
- Turnover proxies
- Quote-volume liquidity
- Trade-count intensity

Binance only covers exchange-listed assets. Use CoinGecko for broader universe.

---

## 6) DeFiLlama

### 6.1 Access

Free API base URL: `https://api.llama.fi` — no auth required
Pro API is a separate product; do not mix them.

### 6.2 Dashboard surface

Reference pages:
- `https://defillama.com/protocol/aave` — protocol fundamentals
- `https://defillama.com/chains` — chain TVL rankings
- `https://defillama.com/stablecoins` — stablecoin market
- `https://defillama.com/fees` — protocol fee rankings

#### Protocol page (Aave example)

Tabs: TVL, Active Loans, Stablecoin Info, Treasury, Unlocks, Yields, Fees and Revenue, Token Rights, Governance

**TVL**: Total + breakdown by chain (Ethereum, Arbitrum, Base, Avalanche, BSC, Polygon, 15+ others)

**Fees/Revenue surface** (annualized / 30d / 7d / 24h / cumulative):
- Fees, Revenue, Holders Revenue, Incentives, Earnings

**Capital structure**: market cap, token price, ATH/ATL, FDV, outstanding FDV, token volume (CEX/DEX split), staked amount

**Treasury/balance sheet**: total, composition (majors, stables, own tokens, others), total raised, fundraising history

**Lending-specific**: Active Loans (credit demand, capital utilization)

#### Chains page

Chain rankings by TVL with taxonomy filters: EVM, Non-EVM, Rollup, Arbitrum Chains, Superchain, Bitcoin Sidechains, Cosmos, Parachain, SVM, etc.

Research use: peer grouping, cross-chain capital rotation, modular vs monolithic regime comparisons.

#### Stablecoins page

Fields: total stablecoin market cap, 7d/1d/30d changes, USDT dominance, market cap/volume/inflows view switching, filters (backing type, peg type), table with market cap changes, price, % off peg, chains.

Research use: system liquidity regime, depeg stress, risk-on confirmation.

#### Fees page

Fields: protocol rankings by fees, 24h/30d totals, weekly change, category filters, name/category/definition/fees-24h/7d/30d columns.

Research use: monetization leaderboard, sector-relative fee strength, Artemis cross-check.

### 6.3 Free API endpoints

```
/protocols                          — all protocols with TVL
/protocol/{protocol}                — historical TVL + breakdowns
/v2/chains                          — current TVL of all chains
/v2/historicalChainTvl/{chain}      — historical chain TVL
/stablecoins                        — stablecoin list
/stablecoincharts/all               — global stablecoin market cap history
/stablecoincharts/{chain}           — chain-specific stablecoin history
/overview/fees                      — protocol fee rankings
/summary/fees/{protocol}            — protocol fee time series
/pools                              — yield pool list
/chart/{pool}                       — pool APY/TVL history
```

### 6.4 Best DeFiLlama-derived factor features

- TVL growth (level, rate, chain distribution)
- Fee growth, revenue growth
- Fees / TVL, Revenue / market cap
- Stablecoin inflow regime (macro risk-on filter)
- Treasury quality / dilution risk overlays

---

## 7) Cross-source join logic

### Master asset table fields

```
internal_asset_id
symbol
artemis_symbol, artemis_id
coingecko_id
binance_symbol         (e.g., ETHUSDT)
defillama_slug
asset_type             (chain | protocol/app | token | stablecoin)
sector_tags, category_tags, chain_tags
exclusion_flags        (is_stable, is_wrapped, is_bridged, is_meme, ...)
```

### Identity anchor rules

- **Primary cross-source key**: `coingecko_id` — use it wherever possible to link Artemis, Binance, and CoinGecko
- Artemis: `symbol` and `artemis_id`; `/asset/symbols/` returns `coingecko_id` for direct mapping
- Binance: exchange pair symbol (e.g., `ETHUSDT`)
- DeFiLlama: protocol slug / chain name — maintain a separate protocol dimension table; join to token data only when economically justified

---

## 8) Factor families

### 8.1 Price momentum
Sources: CoinGecko, Binance
Construct: 7D/30D/90D price change; skip last 3–7 days (classic momentum skip)
Story: underreaction / slow information diffusion in crypto

### 8.2 Adoption / usage momentum
Sources: Artemis
Construct: z-scored change in adjusted txns, DAU, or active addresses
Story: real user activity growth may precede repricing. Use adjusted metrics — gamed activity inflates raw signals.

### 8.3 Monetization quality
Sources: Artemis (FEES, REVENUE), DeFiLlama
Construct: fees-to-mcap, revenue-to-mcap (trailing 30D/90D sums)
Story: protocols that convert activity into revenue efficiently should outperform

### 8.4 Capital efficiency
Sources: DeFiLlama (TVL) + CoinGecko/Artemis (fees/revenue)
Construct: fees / TVL, revenue / TVL
Story: more productive deployment of locked capital

### 8.5 Quality penalty
Sources: Artemis
Construct: `percent_gamed_txns` / `percent_gamed_volume` as a penalty weight; real/total ratio
Story: penalize assets where growth is synthetic

### 8.6 Stablecoin liquidity regime
Sources: Artemis stablecoin endpoints, DeFiLlama stablecoins page/API
Construct: stablecoin inflow momentum, total stablecoin market cap growth
Story: stablecoin expansion proxies macro crypto liquidity — use as risk-on regime filter

### 8.7 Breadth / concentration
Sources: Artemis breakdowns, DeFiLlama chain/protocol breakdowns
Construct: HHI or entropy across chain / facilitator / category dimensions
Story: broad-based activity is healthier than single-integrator dependence

### Suggested Track #1 starting composite
`price momentum + adjusted usage growth + monetization quality + stablecoin liquidity filter + gamed-activity penalty`

---

## 9) Recommended first production pull

### Layer A — market layer

From **CoinGecko**:
- daily price, market cap, 24h volume
- categories, supply / FDV fields

From **Binance** (exchange-listed subset):
- daily OHLCV
- quote volume, trade count

### Layer B — activity-quality layer

From **Artemis**:
- `txns`, `real_txns`, `volume`, `real_volume`
- `cumulative_buyers`, `cumulative_sellers`
- `percent_gamed_txns`, `percent_gamed_volume`
- `avg_txn_size`
- breakdowns by chain, protocol/facilitator, category (for selected assets)

### Layer C — business/capital layer

From **DeFiLlama**:
- protocol TVL
- chain TVL
- fees 24h / 7d / 30d
- revenue 24h / 7d / 30d
- treasury (where available)
- stablecoin market cap and inflow metrics

---

## 10) Data collection architecture

### Storage layers

```
raw/                ← immutable snapshots; never modify
  artemis/
  coingecko_api/
  coingecko_pages/
  binance/
  defillama/
clean/              ← standardized schemas, deduped
features/           ← factor tables for backtests
```

### Core clean tables

| Table | Key fields |
|---|---|
| `asset_master` | All cross-source ID mappings, tags, exclusion flags |
| `price_panel_daily` | date, asset_id, close, return_1d/7d/30d, volume_usd, rolling_vol |
| `artemis_activity_panel` | date, asset_id, all Artemis usage/monetization/quality metrics |
| `defillama_protocol_panel` | date, protocol, TVL, fees/revenue by horizon |
| `stablecoin_macro_panel` | date, total stablecoin mcap, inflows by chain |
| `factor_panel_daily` | date, asset_id, computed factor scores |
| `factor_panel_weekly` | same at weekly granularity |

### Snapshot discipline

Every raw snapshot file must store:
- `source`
- `endpoint` or page URL
- `request_params`
- `pulled_at` timestamp
- raw payload (JSON or HTML)

### Pull frequency

- Prices: daily
- Artemis fundamentals: daily or weekly depending on metric
- Stablecoins: daily

---

## 11) Credentials

Storage: `~/.hermes/.env` (global). Never commit to repo. Commit `.env.example` with variable names only.

| Variable | Source | Notes |
|---|---|---|
| `ARTEMIS_API_KEY` | Artemis account settings | Required for all REST API calls |
| `DEFILLAMA_API_TOKEN` | DeFiLlama | Unlocks higher rate limits on pro tier |
| `BINANCE_API_KEY` | Binance account | Optional; market data is public |
| `BINANCE_API_SECRET` | Binance account | Optional; same as above |

CoinGecko demo key passed via `x-cg-demo-api-key` header — treat like a secret even if demo-tier.

---

## 12) Reference URLs

| Resource | URL |
|---|---|
| Artemis docs index | `https://app.artemis.xyz/docs/llms.txt` |
| Artemis OpenAPI spec | `https://app.artemis.xyz/docs/api-reference/openapi.json` |
| Artemis stablecoin endpoint docs | `https://app.artemis.xyz/docs/api-reference/stablecoins/fetch-stablecoin-supply.md` |
| Artemis flows endpoint docs | `https://app.artemis.xyz/docs/api-reference/flows/get-flows-by-chain-netflow-inflow-or-outflow.md` |
| CoinGecko demo auth docs | `https://docs.coingecko.com/v3.0.1/reference/authentication` |
| Binance klines REST docs | `https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints` |
| Binance market-data-only domain FAQ | `https://developers.binance.com/docs/binance-spot-api-docs/faqs/market_data_only` |
| Binance bulk data portal | `https://data.binance.vision/` |
| Binance bulk data instructions | `https://github.com/binance/binance-public-data/` |
| DeFiLlama API docs | `https://api-docs.defillama.com/` |
