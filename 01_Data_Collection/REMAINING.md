# Data Collection — Remaining Work

This is the open punch-list for the **Coins/Tokens** and **Sectors/Themes** sections of `Data Groupings.md`. Items are tagged by importance for the research pipeline.

Legend:
- **[P0 — CRITICAL]** load-bearing for the core ranking model (M / V / C / T factors and the sector layer)
- **[P1 — IMPORTANT]** materially improves signal quality, regime detection, or universe filtering
- **[P2 — NICE-TO-HAVE]** enriches reporting / context but is not on the critical path

---

## What was just fixed (no action required)

- `_extract_artemis_rows` coerces nested dict/list values; the `value` column is then `pd.to_numeric(errors="coerce")` so Artemis's `'Metric not available for asset.'` sentinel no longer breaks parquet write.
- `coingecko_coin_details` emits derived `is_stablecoin`, `is_wrapped`, `is_bridged` flags (universe exclusion).
- Artemis monetization metrics (`fees`, `revenue`, `active_revenue`, `passive_revenue`) live in `artemis_activity_long` (12 metrics total, 75,086 rows, 92.6% non-null).
- New **DeFiLlama** client + stage. Outputs:
  - `defillama_protocol_map` — universe → DeFiLlama slug, with `mapping_source` audit column (`override` / `gecko_id_fallback` / `skipped` / `unmapped`).
  - `defillama_protocol_tvl_daily` — daily TVL per protocol.
  - `defillama_fees_revenue_summary` — 24h / 7d / 30d / all-time + change for `dailyFees`, `dailyRevenue`, `dailyHoldersRevenue`.
- **DeFiLlama mapping rebuilt around `config/defillama_overrides.yaml`** (resolution: overrides → skip set → category-whitelisted gecko_id fallback → unmapped). Drops the noisy auto-match that produced ETH→ethereum-foundation, SOL→solana-farm, BNB→binance-cex, HYPE→hyperliquid-bridge as the only candidate, etc. Result: 23 deliberate DeFi slugs across 15 protocols (Aave V2/V3, Uniswap V2/V3/V4, PancakeSwap AMM/V3, Hyperliquid bridge/HLP/spot, Sky Lending, Ethena USDe, Ondo Yield/Markets, Morpho Blue, Pumpswap, JustLend, Jupiter Perps/Lend, Chainlink Requests). 88 symbols explicitly skipped.
- Latest coverage (no errors): `defillama_mapped_protocols=23, defillama_tvl_rows=21,951, defillama_fees_rows=51`.

## Known limitation: Artemis `dimensionType`

The `/data/{metrics}/?dimensionType=CHAIN|CATEGORY|PROTOCOL|VERSION` endpoint **does not return per-dimension broken-down series** for our universe. Same flat `{symbols: {SYM: {METRIC: list_or_sentinel}}}` shape as the non-dim call, with most pairs replaced by `'Metric not available for asset.'`. CHAIN, PROTOCOL and VERSION batches were even byte-identical (271,399 bytes, 463 sentinels each) — strongly suggesting the parameter is being silently ignored on this endpoint.

Dimension stage **disabled** in `config/settings.yaml` (`dimension_types: []`) until the right API surface is identified. The pipeline code path remains; re-populate the list to re-enable. See **P0 #2** below for the work.

Re-run the pipeline to materialise the tables:
```
01_Data_Collection/.venv/bin/python 01_Data_Collection/src/main.py --coins-file Coins.md
```

---

## Coins / Tokens — still missing

### [P0 — CRITICAL]

1. **DeFiLlama mapping audit.** ✅ DONE — `config/defillama_overrides.yaml` is in place, mapping is auditable via `defillama_protocol_map.mapping_source`. Future tweaks: as the universe shifts (new tokens added to `Coins.md`), add new symbols to either the `overrides` map (real DeFi protocol) or the `skip` list (chain native, CEX, RWA, pure stable, meme, gov-only). The default for unknown symbols is `unmapped`, which is safe.
2. **Identify the correct Artemis dimension API.** The current `dimensionType` query parameter does not return per-dimension data. Action: read the Artemis API docs (or contact support) to identify either (a) a different endpoint that returns chain-broken-down series for transactions/volume/DAU, or (b) the correct query syntax. Likely candidates to try: `groupBy=CHAIN`, separate `/data/{metric}/by-chain/` endpoint, or the metrics being suffixed e.g. `transactions_by_chain`. Once identified, repopulate `dimension_types:` in `settings.yaml` to re-enable. **Why critical:** by-chain / by-protocol breakdowns power the network-clusters and centrality factors in the research plan.

### [P1 — IMPORTANT]

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

### [P2 — NICE-TO-HAVE]

8. **CEX vs DEX volume split (DeFiLlama browser).** Used for liquidity quality scoring of small caps. Browser-scrape required.
9. **Holders revenue / incentives / earnings as a *time series* (DeFiLlama).** The summary endpoint we just added gives 24h/7d/30d aggregates. The full daily series requires `api.llama.fi/overview/fees/{chain}` plus `dataType` filtering and per-protocol timeline parsing.
10. **CoinGecko ATH/ATL from "browser" path.** Already covered by the API path (`coingecko_coin_details.ath_usd`, `ath_date_usd`, `atl_usd`, `atl_date_usd`). Mark this row in `Data Groupings.md` as redundant.

---

## Sectors / Themes — entirely missing

This whole section is currently uncollected. Highest leverage items first.

### [P0 — CRITICAL]

11. **Sector constituent lists.** Source: Artemis browser (no documented public API). Action: maintain `config/sectors.yaml` with `{sector_slug: [member symbols]}` curated by hand from the Artemis app. Without this we can't aggregate or do cross-sectional rank within a sector.
12. **Per-sector aggregate activity (Artemis).** Once constituents exist, roll up the existing `artemis_activity_long` to sector level: total + adjusted transactions, total + real volume, % gamed, buyers, sellers. Write to `sector_activity_daily`. **Why critical:** the average-correlation-momentum (C) factor in the Ranked Asset Allocation Model is computed at the asset-class / sector level — without it you cannot run that factor.

### [P1 — IMPORTANT]

13. **Market share by member.** Within each sector, daily `member_share = member_volume / sum(member_volume)`. Cheap derivative once #12 is in place. Write to `sector_member_share_daily`. **Why:** lets you detect sector consolidation (one winner) vs fragmentation, which materially changes the within-sector momentum trade.
14. **Sector-level fees/revenue/TVL roll-up (DeFiLlama).** Same idea as #12 but using `defillama_protocol_tvl_daily` and `defillama_fees_revenue_summary` aggregated by `defillama_category` (already captured in `defillama_protocol_map`). No additional pulls required — pure transformation.

### [P2 — NICE-TO-HAVE]

15. **Sector-level network / cluster metrics.** From the original research plan, sectors should have centrality + cluster stability metrics (per `02_Research/artemis_track1_research_consolidation.md`). Requires constituents (#11) + a return-correlation graph builder. This is research-pipeline work, not raw data collection — flag here for completeness.

---

## Cross-cutting infra gaps

- **No browser/HTML scraping path at all.** Every `Data Groupings.md` row marked "browser" (treasury composition, fundraising, token unlocks for non-listed protocols, sector constituents, off-peg history, USDT dominance, backing-type breakdowns) cannot be served by the current `clients.py` (HTTP/JSON only). If you want any of these, add a `BrowserScraper` class (Playwright or `httpx` + BeautifulSoup) and a politeness layer.
- **No retry / resume on partial failures.** A single 429 from DeFiLlama mid-run loses the rest of that stage. Consider per-slug checkpoint files in `data/raw/defillama/_checkpoints/` so re-running only fetches missing slugs.
- **Coverage report does not surface new tables.** `coverage_summary.csv` should also report `artemis_dimension_rows` and per-dimension counts. One-line addition in `pipeline.run`.

---

## Suggested order of attack

1. Re-run pipeline → confirm fixes are clean and Artemis stage no longer errors.
2. Validate DeFiLlama mapping (#1) and Artemis dimension shape (#2) — both P0.
3. Build sector constituents file (#11) — unblocks the entire sector roll-up branch (#12, #13, #14).
4. Add unlocks (#3) and stablecoin module (#7) — these are the macro-regime inputs.
5. Everything else is polish or scraping infra.
