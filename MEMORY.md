# Artemis Quant Competition — Project Memory

## What this project is

**Artemis Quant Competition — Track #1: Crypto Factor Rebalancing Strategy.**
Goal: build a defensible weekly-rebalanced long-short crypto factor portfolio across ~113 assets (all large-cap >$10B + top 100 below large-cap, CoinGecko snapshot 2026-05-08, excluding stablecoins/wrapped/bridged). Not a single-asset predictor. The competition rewards cross-sectional ranking power, regime robustness, turnover control, and economic interpretability.

**Current competition candidate: `08_nalfp` NALFP v3** (latest commit `66bea36`, 2026-05-29).

---

## Pipeline stages

| Stage | Folder | Purpose |
|---|---|---|
| 1 | `01_Data_Collection` | Data pipeline: Artemis API, CoinGecko, Binance, DeFiLlama |
| 2 | `02_Research` | 10-paper review + Track 1 research synthesis |
| 3 | `03_analysis` | Data quality, universe profiling, returns, on-chain activity, factor signals, cross-section |
| 4 | `04_factors` | RAAM v2 composite (M/V/C/T + F/S/G signals) |
| 5 | `05_btc_direction` | BTC direction paper reproduction (Dubey & Enke 2025) |
| 6 | `06_artemis_econometrics` | Weekly Fama-MacBeth panel + latent controls + network features |
| 7 | `07_hidden_factor_pricing` | Giglio-Xiu latent factor pricing (paper reproduction) |
| 8 | `08_nalfp` | **NALFP v3 — active competition submission** |

---

## NALFP v3 — current architecture (latest pull)

Three pillars:
1. **Network dynamics** (`01_network_dynamics.py`): rolling 12-week Spearman MST + Louvain → `within_cluster_mom`, `cross_cluster_rel`, `network_entropy`. 7–11 communities per week (mean entropy 2.175). Market is persistently fragmented.
2. **Factor zoo + Giglio-Xiu** (`02_factor_pricing.py`): 9 factor portfolios (RC, SMBC, MomC, VolC, FunC, SupC, NetMom, NetRel) → GX three-pass pricing → per-week IC time series (`factor_ic_timeseries.parquet`).
3. **IC-weighted signal combination** (`03_signal_combination.py`): *replaces* the v2 regime detector. Rolling 8-week mean IC, lagged 1 week (strictly OOS), IC-proportional weights across 6 tradeable factors (SMBC, MomC, VolC, FunC, NetMom, NetRel). Equal-weight fallback when all ICs ≤ 0 (~10% of weeks).

**Run order (v3):**
```
python3 08_nalfp/01_network_dynamics.py
python3 08_nalfp/02_factor_pricing.py
python3 08_nalfp/03_signal_combination.py   ← NOT 03_regime_detector.py
python3 08_nalfp/04_portfolio_construction.py
python3 08_nalfp/05_backtest.py
python3 08_nalfp/06_report.py
```

**Why v3 over v2:** The two-stream GX-vs-network adaptive blend (v2) overfitted the 24-week training-window λ̂. Per-factor IC-proportional weighting is the same convention validated in RAAM v2 (stage 04) and avoids fitting the regime boundary.

---

## Key results

### NALFP v3 OOS backtest (24-week OOS window)

| Strategy | OOS Ann.Return | OOS Sharpe | OOS MaxDD | OOS Turnover |
|---|---|---|---|---|
| **NALFP v3** | **+8.7%** | **+1.24** | **-3.47%** | **8.7%** |
| EW_mom_long | +66.2% | +1.52 | -24.80% | 33.8% |
| plus_lat (stage 06) | +129.0% | +3.75 | -7.39% | 65.1% |

NALFP v3 OOS Sharpe improved from -1.44 (v2) to +1.24 (v3). Bootstrap CI crosses zero (−2.01 to +4.80). NALFP is much lower-vol and lower-drawdown than benchmarks; does not yet beat them on raw return. `plus_lat` benchmark has only 16 OOS weeks (shorter window).

### IC-weighted factor mean weights (OOS)
| Factor | Full-sample IC | OOS IC | Mean OOS weight |
|---|---|---|---|
| VolC | 0.090 | 0.104 | **0.442** |
| NetRel | 0.046 | 0.022 | 0.185 |
| FunC | 0.001 | 0.017 | 0.144 |
| MomC | 0.026 | 0.020 | 0.107 |
| SMBC | 0.015 | 0.056 | 0.095 |
| NetMom | 0.006 | 0.002 | 0.075 |

VolC dominates (~44% weight) because it has the highest and most stable IC. NetRel second at 18.5%.

### GX factor zoo (52-week sample)
5 of 7 priced at |t|≥1.65 in observed-only model: VolC (t=+4.27), MomC (+3.44), NetMom (+3.37), NetRel (+3.37), SMBC (+3.00). In the full GX model: VolC (t=+3.24) and NetMom/NetRel (~t=+2.4) are most robust. Hidden factors H1–H3 are not statistically priced. Bai-Ng selected K_hidden=3 (capped; short T=24 training weeks).

### Earlier stage results
- **04_factors RAAM v2 ICs**: V=+0.21, C=+0.18, S=+0.12, M=+0.06, T≈0 (A1 bug — T signals silenced)
- **06_artemis_econometrics**: `plus_lat` model IC IR=+0.54, LS Sharpe=+3.74 (16 OOS weeks); `plus_net` was weak (IC IR=+0.20)
- **07_hidden_factor_pricing**: only `crypto_smb` survives GX latent controls (FMB t=2.19, latent-adj t=1.97)
- **05_btc_direction**: best classifier `l1__random_forest` balanced acc 53.94%; best trading `all__gradient_boosting` Sharpe 1.82

---

## Bug fixes pending (`.github/bug-fix-plan.md`)

Priority 04→05→06→07. Some already applied (C3, D1 confirmed in REPORT.md).

| ID | File | Fix | Status |
|---|---|---|---|
| A1 | `04_factors/04_RAAM_v2_composite.py:107` and `03_analysis/05_factor_signals.py:153` | T-factor ATR lower-band: `max() + atr` → `min() - atr` | **Not applied** |
| A2 | `04_factors/02_S_supply_absorption.py`, `04_RAAM_v2_composite.py` | Remove overhang tiled from current snapshot in IC test | **Not applied** |
| B1 | `05_btc_direction/02_feature_engineering.py` | Exogenous features missing `.shift(1)` lag | **Not applied** |
| C1 | `06_artemis_econometrics/04_latent_controls.py:97` | Window `i+1` → `i` (current week contaminates PC loads) | **Not applied** |
| C2 | `06_artemis_econometrics/06_backtest.py` | Remove contemporaneous mom regressor | Applied (confirmed in REPORT.md) |
| C3 | `06_artemis_econometrics/05_models.py` | Remove degenerate `base_lasso` | Applied (confirmed in REPORT.md) |
| D1 | `07_hidden_factor_pricing/05_report.py` | Add "Scope of This Test" in-sample framing section | Applied (confirmed in REPORT.md) |

---

## Research design rules (from 10-paper review)

These constrain all future factor and portfolio decisions:

1. **TVL alone is not alpha.** Use only as denominator: `fees/TVL`, `revenue/TVL`, `fees/mcap`, `revenue/mcap`.
2. **Quality-adjusted Artemis metrics beat raw.** Prefer `real_txns`, `real_volume`; penalize `pct_gamed_*`.
3. **Factor premia need latent-factor survival testing.** Test all new factors with GX / FMB controls before crediting them.
4. **Community-aware diversification required.** No single Louvain cluster > 40% of long-leg weight.
5. **Stablecoin inflow z-score** is the primary macro regime proxy (computed in `06_artemis_econometrics/01_build_panel.py`).
6. **Do not use shuffle-based CV.** Always chronological splits.
7. **Banded rebalancing** preserves alpha at lower turnover (Waterfall Rebalancing paper).

---

## Data sources

| Source | Provides | Access |
|---|---|---|
| Artemis API | Adjusted txns/vol, real vs. gamed, buyers/sellers, DAU, fees, revenue, stablecoin flows | `/asset/symbols/`, `/metrics/`, `/flows/top/` |
| CoinGecko | Price, mcap, volume, supply, FDV, exclusion flags | API + browser |
| Binance | OHLCV, quote vol, trade count | API; bulk: `data.binance.vision` |
| DeFiLlama | Protocol/chain TVL, fees/revenue, stablecoin inflows, treasury | `api-docs.defillama.com` |

Clean parquet files in `01_Data_Collection/data/clean/`:
- `coingecko_daily_ticks.parquet` — daily price/mcap/vol for all assets
- `coingecko_coin_details.parquet` — metadata + exclusion flags
- `artemis_activity_long.parquet` — on-chain activity (partial coverage)
- `asset_master.parquet` — symbol/ID master table

External code: `github.com/adambaybutt/crypto_asset_pricing` (DSLFM framework, reusable for characteristic model work).
