# Artemis — Data Inventory & Open Punch-list

Single canonical reference for what data the pipeline currently produces, plus the outstanding gaps. Read this before writing any analysis.

- Pipeline run id covered: `20260509T090254Z` (pulled `2026-05-09T09:02:54+00:00`)
- All clean tables live in `01_Data_Collection/data/clean/` as paired `*.parquet` + `*.csv`. The parquet file is canonical; CSV is a convenience.
- Universe: 113 symbols (13 large-cap, 57 mid-cap, 43 below-large-top-100), defined in `Coins.md`.

---

## 1 — What we have

### Identity / mapping tables

| Table | Rows | Key cols | Notes |
|---|---:|---|---|
| `asset_master.parquet` | 113 | `symbol`, `cohort`, `coingecko_id`, `mapping_status` | Universe definition. 111 of 113 mapped to CoinGecko (2 unmapped). Cohorts: large_cap (13), mid_cap_strict (57), below_large_top100_ext (43). |
| `binance_symbol_map.parquet` | 113 | `symbol`, `binance_symbol`, `quote_asset`, `mapping_status` | Resolves universe → tradeable Binance pair. 68 mapped, 45 unmapped (no spot listing on Binance). |
| `coingecko_coin_details.parquet` | 111 | `coingecko_id`, `categories`, `is_stablecoin`, `is_wrapped`, `is_bridged`, ATH/ATL, supply | Per-coin metadata. The three boolean flags drive universe exclusion for factor inputs. |
| `artemis_asset_symbols.parquet` | 1,009 | `artemis_id`, `symbol`, `coingecko_id`, `title`, `color` | Full Artemis catalogue. Wider than our universe — used to look up Artemis ids. |
| `defillama_protocol_map.parquet` | 121 | `symbol` → `defillama_slug`, `mapping_source`, `defillama_category`, `current_tvl_usd` | 23 deliberate slugs across 15 symbols (`override`); 97 explicit `skipped`; 1 `unmapped`. Categories: Dexs (7), Lending (5), CDP (3), Derivatives (2), RWA (2), Basis Trading (2), Bridge (1), Oracle (1), null (98). |

### Market / price tables

| Table | Rows | Date range | Key cols | Notes |
|---|---:|---|---|---|
| `coingecko_market_snapshot.parquet` | 111 | 2026-05-09 only | 31 cols incl. `current_price`, `market_cap`, `fdv`, `ath`, `atl`, 24h/7d/30d change | Current state, not a time series. Use for ranking and exclusion. |
| `coingecko_daily_ticks.parquet` | 38,173 | 2025-05-09 → 2026-05-09 | `date`, `coingecko_id`, `price_usd`, `market_cap_usd`, `total_volume_usd` | The default return / market-cap time series. ~344 days × 111 ids. |
| `binance_ohlcv_daily.parquet` | 22,464 | 2025-05-10 → 2026-05-09 | `binance_symbol`, OHLC, `base_volume`, `quote_volume`, `trade_count` | Clean OHLCV for the 68 Binance-listed names. Use for ATR / Trend (T) factor — daily ticks have no high/low. |

### On-chain activity (Artemis)

| Table | Rows | Date range | Key cols | Notes |
|---|---:|---|---|---|
| `artemis_activity_metrics.parquet` | 41,471 | 2025-05-09 → 2026-05-09 | wide: `dau`, `fees`, `revenue`, `volume`, `transactions`, ... | Wide format. **Many columns are entirely null** — see "metric coverage" below. |
| `artemis_activity_long.parquet` | 75,086 | 2025-05-09 → 2026-05-09 | `date`, `symbol`, `metric`, `value` | Long format, one row per (symbol, metric, date). 12 metrics requested, 6 with usable data. |

**Artemis metric coverage** (% missing in `artemis_activity_long.value` after `pd.to_numeric` coercion of the `'Metric not available for asset.'` sentinel):

| Metric | % null | Verdict |
|---|---:|---|
| `dau` | 11.5% | usable (top metric for activity work) |
| `fees` | 3.6% | usable |
| `revenue` | 3.9% | usable |
| `passive_revenue` | 4.1% | usable |
| `active_revenue` | 8.8% | usable |
| `volume` | 13.6% | usable but thinner |
| `active_addresses` | 100% | empty — Artemis returns sentinel for every (symbol, day) |
| `real_volume`, `real_transactions`, `transactions`, `gamed_volume_pct`, `gamed_transactions_pct` | 100% | empty — sentinel only |

**Implication:** the "real vs gamed" usage-quality story is **not** currently available from Artemis at the symbol level. The activity stack we can actually visualise is `dau`, `fees`, `revenue`, `volume` (+ `active_revenue` / `passive_revenue` for the revenue split).

### Protocol economics (DeFiLlama)

| Table | Rows | Date range | Key cols | Notes |
|---|---:|---|---|---|
| `defillama_protocol_tvl_daily.parquet` | 21,951 | 2019-01-04 → 2026-05-09 | `date`, `defillama_slug`, `tvl_usd` | TVL history for 19 slugs. Some go back to 2019 (Aave, Uniswap); newer protocols (Hyperliquid, Pumpswap, Sky) start in 2024-25. |
| `defillama_fees_revenue_summary.parquet` | 51 | snapshot | `defillama_slug`, `data_type` ∈ {`dailyFees`, `dailyRevenue`, `dailyHoldersRevenue`}, `total24h`, `total7d`, `total30d`, `totalAllTime`, change cols | Aggregates only — no time series for fees yet (P2 #9 in the punch-list). |

### QA

| Table | Rows | Notes |
|---|---:|---|
| `coverage_summary.parquet` | 1 | One row per pipeline run summarising volumes per stage. |

**Latest coverage row** (`run_id=20260509T090254Z`):

| field | value |
|---|---:|
| universe_assets | 113 |
| coingecko_mapped_assets | 111 |
| coingecko_daily_ticks_rows | 38,173 |
| binance_mapped_assets | 68 |
| binance_ohlcv_rows | 22,464 |
| defillama_mapped_protocols | 23 |
| defillama_tvl_rows | 21,951 |
| defillama_fees_rows | 51 |
| artemis_assets_rows | 1,009 |
| artemis_activity_rows | 41,471 |
| artemis_activity_long_rows | 75,086 |

---

## 2 — How to load each table

```python
from pathlib import Path
import pandas as pd
CLEAN = Path("01_Data_Collection/data/clean")

ticks   = pd.read_parquet(CLEAN / "coingecko_daily_ticks.parquet")
ohlcv   = pd.read_parquet(CLEAN / "binance_ohlcv_daily.parquet")
master  = pd.read_parquet(CLEAN / "asset_master.parquet")
mkt     = pd.read_parquet(CLEAN / "coingecko_market_snapshot.parquet")
detail  = pd.read_parquet(CLEAN / "coingecko_coin_details.parquet")
act_w   = pd.read_parquet(CLEAN / "artemis_activity_metrics.parquet")
act_l   = pd.read_parquet(CLEAN / "artemis_activity_long.parquet")
tvl     = pd.read_parquet(CLEAN / "defillama_protocol_tvl_daily.parquet")
dl_map  = pd.read_parquet(CLEAN / "defillama_protocol_map.parquet")
fees    = pd.read_parquet(CLEAN / "defillama_fees_revenue_summary.parquet")
```

---

## 3 — Open punch-list (verbatim from `01_Data_Collection/REMAINING.md`)

> The original `REMAINING.md` is intentionally left in place; it is the source of truth. The copy below is a snapshot — refresh it from source if you change the original.

### Legend

- **[P0 — CRITICAL]** load-bearing for the core ranking model (M / V / C / T factors and the sector layer)
- **[P1 — IMPORTANT]** materially improves signal quality, regime detection, or universe filtering
- **[P2 — NICE-TO-HAVE]** enriches reporting / context but is not on the critical path

### What was just fixed (no action required)

- `_extract_artemis_rows` coerces nested dict/list values; the `value` column is then `pd.to_numeric(errors="coerce")` so Artemis's `'Metric not available for asset.'` sentinel no longer breaks parquet write.
- `coingecko_coin_details` emits derived `is_stablecoin`, `is_wrapped`, `is_bridged` flags (universe exclusion).
- Artemis monetization metrics (`fees`, `revenue`, `active_revenue`, `passive_revenue`) live in `artemis_activity_long` (12 metrics total, 75,086 rows, 92.6% non-null).
- New **DeFiLlama** client + stage. Outputs:
  - `defillama_protocol_map` — universe → DeFiLlama slug, with `mapping_source` audit column (`override` / `gecko_id_fallback` / `skipped` / `unmapped`).
  - `defillama_protocol_tvl_daily` — daily TVL per protocol.
  - `defillama_fees_revenue_summary` — 24h / 7d / 30d / all-time + change for `dailyFees`, `dailyRevenue`, `dailyHoldersRevenue`.
- **DeFiLlama mapping rebuilt around `config/defillama_overrides.yaml`** (resolution: overrides → skip set → category-whitelisted gecko_id fallback → unmapped). Drops the noisy auto-match that produced ETH→ethereum-foundation, SOL→solana-farm, BNB→binance-cex, HYPE→hyperliquid-bridge as the only candidate, etc. Result: 23 deliberate DeFi slugs across 15 protocols. 88 symbols explicitly skipped.
- Latest coverage (no errors): `defillama_mapped_protocols=23, defillama_tvl_rows=21,951, defillama_fees_rows=51`.

### Known limitation: Artemis `dimensionType`

The `/data/{metrics}/?dimensionType=CHAIN|CATEGORY|PROTOCOL|VERSION` endpoint **does not return per-dimension broken-down series** for our universe. Same flat `{symbols: {SYM: {METRIC: list_or_sentinel}}}` shape as the non-dim call, with most pairs replaced by `'Metric not available for asset.'`. CHAIN, PROTOCOL and VERSION batches were even byte-identical (271,399 bytes, 463 sentinels each) — strongly suggesting the parameter is being silently ignored on this endpoint.

Dimension stage **disabled** in `config/settings.yaml` (`dimension_types: []`) until the right API surface is identified. The pipeline code path remains; re-populate the list to re-enable. See **P0 #2** below for the work.

Re-run the pipeline to materialise the tables:
```
01_Data_Collection/.venv/bin/python 01_Data_Collection/src/main.py --coins-file Coins.md
```

### Coins / Tokens — still missing

#### [P0 — CRITICAL]

1. **DeFiLlama mapping audit.** ✅ DONE — `config/defillama_overrides.yaml` is in place, mapping is auditable via `defillama_protocol_map.mapping_source`. Future tweaks: as the universe shifts (new tokens added to `Coins.md`), add new symbols to either the `overrides` map (real DeFi protocol) or the `skip` list (chain native, CEX, RWA, pure stable, meme, gov-only). The default for unknown symbols is `unmapped`, which is safe.
2. **Identify the correct Artemis dimension API.** The current `dimensionType` query parameter does not return per-dimension data. Action: read the Artemis API docs (or contact support) to identify either (a) a different endpoint that returns chain-broken-down series for transactions/volume/DAU, or (b) the correct query syntax. Likely candidates to try: `groupBy=CHAIN`, separate `/data/{metric}/by-chain/` endpoint, or the metrics being suffixed e.g. `transactions_by_chain`. Once identified, repopulate `dimension_types:` in `settings.yaml` to re-enable. **Why critical:** by-chain / by-protocol breakdowns power the network-clusters and centrality factors in the research plan.

#### [P1 — IMPORTANT]

3. **Token unlocks (DeFiLlama).** Endpoint exists publicly at `api.llama.fi/emissions` and per-token unlock schedules at `api.llama.fi/emission/{slug}`. Add a `_pull_defillama_unlocks` method writing `defillama_unlocks_schedule` (slug, date, amount, % of supply). **Why critical-ish:** unlock cliffs are a known forward return suppressor — a momentum factor that ignores them will overweight tokens about to dilute.
4. **Treasury composition (DeFiLlama).** No public bulk endpoint; the doc notes it as `browser`. Either:
   - Use the unofficial `https://api.llama.fi/treasury` (returns total) + per-protocol `https://api.llama.fi/treasury/{slug}` if available, OR
   - Stand up a tiny browser/HTML scraper for `defillama.com/protocol/{slug}#treasury`.
   Output target: `defillama_treasury` with columns `slug, total_usd, majors_pct, stables_pct, own_token_pct`.
5. **Fundraising / total raised (DeFiLlama).** Available via `api.llama.fi/raises` (bulk) and `api.llama.fi/raises/{slug}`. Add `defillama_raises` (slug, date, amount, round, valuation, lead investors). **Why:** lets the regime layer separate well-capitalised survivors from runway-risk names.
6. **Staked amount.** No bulk DeFiLlama endpoint. Closest is `api.llama.fi/protocols` (`staking` field on supported protocols). Pull and persist in `defillama_protocol_map.staking_usd`. Browser-only for the rest.
7. **Stablecoin module (Artemis + DeFiLlama).** Per `Data Groupings.md`, stablecoins are a macro-signal layer:
   - Artemis: total supply, supply by chain (`usdc-eth` syntax), supply by category-chain (`payments-eth`), transfer volume, transactions, DAU.
   - DeFiLlama: `/stablecoins`, `/stablecoincharts/all`, `/stablecoincharts/{chain}`, `/stablecoin/{id}` for off-peg + dominance.
   Add a `_pull_stablecoins` stage. **Why important:** stablecoin netflow is the dominant cross-asset crypto regime indicator.

#### [P2 — NICE-TO-HAVE]

8. **CEX vs DEX volume split (DeFiLlama browser).** Used for liquidity quality scoring of small caps. Browser-scrape required.
9. **Holders revenue / incentives / earnings as a *time series* (DeFiLlama).** The summary endpoint we just added gives 24h/7d/30d aggregates. The full daily series requires `api.llama.fi/overview/fees/{chain}` plus `dataType` filtering and per-protocol timeline parsing.
10. **CoinGecko ATH/ATL from "browser" path.** Already covered by the API path (`coingecko_coin_details.ath_usd`, `ath_date_usd`, `atl_usd`, `atl_date_usd`). Mark this row in `Data Groupings.md` as redundant.

### Sectors / Themes — entirely missing

This whole section is currently uncollected. Highest leverage items first.

#### [P0 — CRITICAL]

11. **Sector constituent lists.** Source: Artemis browser (no documented public API). Action: maintain `config/sectors.yaml` with `{sector_slug: [member symbols]}` curated by hand from the Artemis app. Without this we can't aggregate or do cross-sectional rank within a sector.
12. **Per-sector aggregate activity (Artemis).** Once constituents exist, roll up the existing `artemis_activity_long` to sector level: total + adjusted transactions, total + real volume, % gamed, buyers, sellers. Write to `sector_activity_daily`. **Why critical:** the average-correlation-momentum (C) factor in the Ranked Asset Allocation Model is computed at the asset-class / sector level — without it you cannot run that factor.

#### [P1 — IMPORTANT]

13. **Market share by member.** Within each sector, daily `member_share = member_volume / sum(member_volume)`. Cheap derivative once #12 is in place. Write to `sector_member_share_daily`. **Why:** lets you detect sector consolidation (one winner) vs fragmentation, which materially changes the within-sector momentum trade.
14. **Sector-level fees/revenue/TVL roll-up (DeFiLlama).** Same idea as #12 but using `defillama_protocol_tvl_daily` and `defillama_fees_revenue_summary` aggregated by `defillama_category` (already captured in `defillama_protocol_map`). No additional pulls required — pure transformation.

#### [P2 — NICE-TO-HAVE]

15. **Sector-level network / cluster metrics.** From the original research plan, sectors should have centrality + cluster stability metrics (per `02_Research/artemis_track1_research_consolidation.md`). Requires constituents (#11) + a return-correlation graph builder. This is research-pipeline work, not raw data collection — flag here for completeness.

### Cross-cutting infra gaps

- **No browser/HTML scraping path at all.** Every `Data Groupings.md` row marked "browser" (treasury composition, fundraising, token unlocks for non-listed protocols, sector constituents, off-peg history, USDT dominance, backing-type breakdowns) cannot be served by the current `clients.py` (HTTP/JSON only). If you want any of these, add a `BrowserScraper` class (Playwright or `httpx` + BeautifulSoup) and a politeness layer.
- **No retry / resume on partial failures.** A single 429 from DeFiLlama mid-run loses the rest of that stage. Consider per-slug checkpoint files in `data/raw/defillama/_checkpoints/` so re-running only fetches missing slugs.
- **Coverage report does not surface new tables.** `coverage_summary.csv` should also report `artemis_dimension_rows` and per-dimension counts. One-line addition in `pipeline.run`.

### Suggested order of attack

1. Re-run pipeline → confirm fixes are clean and Artemis stage no longer errors.
2. Validate DeFiLlama mapping (#1) and Artemis dimension shape (#2) — both P0.
3. Build sector constituents file (#11) — unblocks the entire sector roll-up branch (#12, #13, #14).
4. Add unlocks (#3) and stablecoin module (#7) — these are the macro-regime inputs.
5. Everything else is polish or scraping infra.
