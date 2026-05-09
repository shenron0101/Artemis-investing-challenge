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
