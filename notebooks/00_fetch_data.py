"""
fetch_data.py — Single data fetch script for the Artemis quant pipeline.

Run once to pull all raw data. All subsequent notebooks read from disk only.
Re-running is safe: already-fetched files are skipped.

CoinGecko Demo key: historical data limited to last 365 days.
CoinGecko Pro key:  full history available (update COINGECKO_PLAN = "pro" below).

Usage:
    .venv/bin/python fetch_data.py
"""

import json
import os
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, date
from dotenv import load_dotenv

# ── Config ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# Set to "pro" if you have a paid CoinGecko key
COINGECKO_PLAN = os.getenv(
    "COINGECKO_PLAN", "demo"
)  # set to "pro" in .env for full history

CG_API_KEY = os.getenv("COINGECKO_API_KEY", "")
ARTEMIS_KEY = os.getenv("ARTEMIS_API_KEY", "")

# Date range for data fetch
# NOTE: Demo CoinGecko key → historical chart data limited to ~365 days back.
#       Switch COINGECKO_PLAN = "pro" for full 2021-2024 range.
END_DATE = date(2024, 12, 31)
START_DATE = date(2021, 1, 1)  # will be clamped for demo keys

UNIVERSE_SIZE = 50
SUPERSET_SIZE = 200  # candidate pool
MIN_LISTING_DAYS = 90

STABLECOIN_SYMBOLS = {
    "usdt",
    "usdc",
    "busd",
    "dai",
    "tusd",
    "usdp",
    "usdd",
    "frax",
    "lusd",
    "susd",
    "usde",
    "pyusd",
    "fdusd",
    "usds",
    "usdx",
    "gusd",
    "ust",
    "ustc",
    "cusd",
    "ceur",
    "eurc",
    "eurt",
    "eurs",
}
EXCLUDE_SYMBOLS = {
    "wbtc",
    "weth",
    "steth",
    "wsteth",
    "cbbtc",
    "weeth",
    "reth",
    "cbeth",
    "beth",
    "hbtc",
    "renbtc",
    "sbtc",
}

# Paths
RAW_CG = ROOT / "data" / "raw" / "coingecko"
RAW_ARTEMIS = ROOT / "data" / "raw" / "artemis"
PROCESSED = ROOT / "data" / "processed"

for d in [RAW_CG, RAW_CG / "market_chart", RAW_ARTEMIS, PROCESSED]:
    d.mkdir(parents=True, exist_ok=True)

# Artemis metrics to fetch
ARTEMIS_METRICS = "fees,revenue,dau,txns,tvl,mc,price"

# ── CoinGecko helpers ─────────────────────────────────────────────────────────

if COINGECKO_PLAN == "pro":
    CG_BASE = "https://pro-api.coingecko.com/api/v3"
    CG_HEADER = "x-cg-pro-api-key"
    CG_START_DATE = START_DATE
else:
    CG_BASE = "https://api.coingecko.com/api/v3"
    CG_HEADER = "x-cg-demo-api-key"
    # Demo: cap CG history to 365 days — but leave START_DATE (used by Artemis) unchanged
    CG_START_DATE = max(START_DATE, date.today() - timedelta(days=364))
    if CG_START_DATE > START_DATE:
        print(f"[WARN] Demo key: CoinGecko history clamped to {CG_START_DATE}.")
        print("       Artemis will still be fetched from {START_DATE}.")
        print("       Set COINGECKO_PLAN=pro in .env for full CG history.")


def cg_get(path: str, params: dict = None, retries: int = 5) -> dict:
    headers = {CG_HEADER: CG_API_KEY}
    url = CG_BASE + path
    for attempt in range(retries):
        r = requests.get(url, headers=headers, params=params or {}, timeout=30)
        if r.status_code == 429:
            wait = 10 * (2**attempt)
            print(f"  [429] Rate limited — sleeping {wait}s ...")
            time.sleep(wait)
            continue
        if r.status_code in (500, 502, 503):
            time.sleep(5)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"CG request failed after {retries} attempts: {url}")


def save_json(path: Path, data) -> None:
    with open(path, "w") as f:
        json.dump(data, f)


def load_json(path: Path):
    with open(path) as f:
        return json.load(f)


# ── Artemis helpers ───────────────────────────────────────────────────────────

ARTEMIS_BASE = "https://data-svc.artemisxyz.com"


def artemis_get(
    metric_names: str, symbols: str, start: str, end: str, retries: int = 4
) -> dict:
    url = f"{ARTEMIS_BASE}/data/api/{metric_names}/"
    params = {
        "symbols": symbols,
        "startDate": start,
        "endDate": end,
        "APIKey": ARTEMIS_KEY,
    }
    for attempt in range(retries):
        r = requests.get(url, params=params, timeout=90)
        if r.status_code == 429:
            wait = 10 * (2**attempt)
            print(f"  [429] Artemis rate limited — sleeping {wait}s ...")
            time.sleep(wait)
            continue
        if r.status_code in (500, 502, 503):
            time.sleep(5)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Artemis request failed after {retries} attempts")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: CoinGecko — Coin list
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("SECTION 1: CoinGecko coin list")
print("=" * 60)

coins_list_path = RAW_CG / "coins_list.json"
if coins_list_path.exists():
    coins_list = load_json(coins_list_path)
    print(f"  [SKIP] Loaded {len(coins_list):,} coins from cache.")
else:
    coins_list = cg_get("/coins/list", {"include_platform": "false"})
    save_json(coins_list_path, coins_list)
    print(f"  [OK]   Fetched and saved {len(coins_list):,} coins.")

coins_df = pd.DataFrame(coins_list)  # id, symbol, name


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: CoinGecko — Top-500 markets snapshot
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("SECTION 2: CoinGecko top-500 markets (today's snapshot)")
print("=" * 60)

markets_path = RAW_CG / "markets_top500.json"
if markets_path.exists():
    markets_rows = load_json(markets_path)
    print(f"  [SKIP] Loaded {len(markets_rows)} markets from cache.")
else:
    markets_rows = []
    for pg in range(1, 3):  # pages 1 & 2 → 500 coins
        print(f"  Fetching markets page {pg}/2 ...")
        markets_rows += cg_get(
            "/coins/markets",
            {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 250,
                "page": pg,
                "sparkline": "false",
            },
        )
        time.sleep(1.5)
    save_json(markets_path, markets_rows)
    print(f"  [OK]   Fetched and saved {len(markets_rows)} markets.")

markets_df = pd.DataFrame(markets_rows)


# ── Build superset ────────────────────────────────────────────────────────────

excl_all = STABLECOIN_SYMBOLS | EXCLUDE_SYMBOLS
mask = ~markets_df["symbol"].str.lower().isin(excl_all)
superset = (
    markets_df[mask]
    .dropna(subset=["market_cap"])
    .sort_values("market_cap", ascending=False)
    .head(SUPERSET_SIZE)
    .reset_index(drop=True)
)
superset_path = RAW_CG / "superset_coins.parquet"
superset.to_parquet(superset_path, index=False)
print(f"\n  Superset: {len(superset)} coins (saved to {superset_path.name})")
print("  Top 10:", superset["symbol"].str.upper().head(10).tolist())


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: CoinGecko — Historical market chart per coin (Pro only)
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("SECTION 3: CoinGecko historical market chart per coin")
print("=" * 60)

coin_ids = superset["id"].tolist()

if COINGECKO_PLAN != "pro":
    days_to_fetch = "365"
    print(f"  [INFO] Demo key — fetching last {days_to_fetch} days of market chart data.")
    cg_params_template = {"vs_currency": "usd", "days": days_to_fetch}
    endpoint_template = "/coins/{coin_id}/market_chart"
else:
    from_ts = int(datetime.combine(START_DATE, datetime.min.time()).timestamp())
    to_ts = int(datetime.combine(END_DATE, datetime.min.time()).timestamp())
    cg_params_template = {"vs_currency": "usd", "from": from_ts, "to": to_ts}
    endpoint_template = "/coins/{coin_id}/market_chart/range"

chart_dir = RAW_CG / "market_chart"
total = len(coin_ids)
fetched = 0
skipped = 0
failed = []

for i, coin_id in enumerate(coin_ids):
    out = chart_dir / f"{coin_id}.json"
    if out.exists():
        skipped += 1
        continue
    try:
        endpoint = endpoint_template.format(coin_id=coin_id)
        data = cg_get(endpoint, cg_params_template)
        save_json(out, data)
        fetched += 1
        print(
            f"  [{i + 1:>3}/{total}] {coin_id:<30} ✓  "
            f"({len(data.get('prices', []))} price points)"
        )
        time.sleep(1.2)
    except Exception as e:
        print(f"  [{i + 1:>3}/{total}] {coin_id:<30} FAILED: {e}")
        failed.append(coin_id)
        time.sleep(2)

print(f"\n  Done: {fetched} fetched, {skipped} skipped, {len(failed)} failed.")
if failed:
    print(f"  Failed coins: {failed}")
    save_json(RAW_CG / "market_chart_failures.json", failed)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Artemis — Fetch supported assets
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("SECTION 5: Artemis supported assets")
print("=" * 60)

artemis_assets_path = RAW_ARTEMIS / "supported_assets.json"
if artemis_assets_path.exists():
    artemis_assets = load_json(artemis_assets_path)
    print(f"  [SKIP] Loaded from cache.")
else:
    r = requests.get(
        f"{ARTEMIS_BASE}/data/api/supported-assets/",
        params={"APIKey": ARTEMIS_KEY},
        timeout=30,
    )
    r.raise_for_status()
    artemis_assets = r.json()
    save_json(artemis_assets_path, artemis_assets)
    print(f"  [OK] Fetched supported assets.")

# Build set of Artemis symbols
try:
    art_symbols_set = {
        s.upper() for s in artemis_assets.get("data", {}).get("symbols", [])
    }
except Exception:
    # fallback: try list format
    try:
        art_symbols_set = {s.upper() for s in artemis_assets if isinstance(s, str)}
    except Exception:
        art_symbols_set = set()

print(f"  Artemis covers {len(art_symbols_set)} symbols.")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Artemis — Fetch metrics for superset symbols
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("SECTION 6: Artemis metrics for superset")
print(f"  Metrics: {ARTEMIS_METRICS}")
print(f"  Range  : {START_DATE} → {END_DATE}")
print("=" * 60)

# Map superset CoinGecko symbols to uppercase for Artemis
superset_symbols_upper = superset["symbol"].str.upper().unique().tolist()

# Filter to symbols Artemis covers (if we have the set)
if art_symbols_set:
    covered = [s for s in superset_symbols_upper if s in art_symbols_set]
    not_covered = [s for s in superset_symbols_upper if s not in art_symbols_set]
    print(f"  Covered by Artemis: {len(covered)}")
    print(f"  Not covered       : {not_covered}")
else:
    covered = superset_symbols_upper
    print(f"  Sending all {len(covered)} symbols (coverage unknown).")

# Fetch in batches of 30 to stay within URL length limits
BATCH_SIZE = 30
art_start = str(START_DATE)
art_end = str(END_DATE)

artemis_out = RAW_ARTEMIS / "metrics_raw.json"
if artemis_out.exists():
    print(f"  [SKIP] {artemis_out.name} already exists.")
    all_data = load_json(artemis_out)
else:
    all_data = {}
    batches = [covered[i : i + BATCH_SIZE] for i in range(0, len(covered), BATCH_SIZE)]
    for bi, batch in enumerate(batches):
        sym_str = ",".join(batch)
        print(f"  Batch {bi + 1}/{len(batches)}: {sym_str[:80]}...")
        try:
            resp = artemis_get(ARTEMIS_METRICS, sym_str, art_start, art_end)
            batch_data = resp.get("data", {}).get("symbols", {})
            all_data.update(batch_data)
            print(f"    → received data for {len(batch_data)} symbols")
            time.sleep(2)
        except Exception as e:
            print(f"    ERROR: {e}")
            time.sleep(5)

    save_json(artemis_out, all_data)
    print(
        f"  [OK] Saved Artemis raw data for {len(all_data)} symbols → {artemis_out.name}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: Artemis — Build fundamentals panel parquet
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("SECTION 7: Building Artemis panel parquet")
print("=" * 60)

art_panel_path = PROCESSED / "panel_artemis_daily.parquet"
if art_panel_path.exists():
    print(f"  [SKIP] {art_panel_path.name} already exists.")
else:
    records = []
    for symbol, metrics in all_data.items():
        for metric_name, series in metrics.items():
            if not isinstance(series, list):
                continue  # skip "N/A" or other non-list values
            for pt in series:
                if not isinstance(pt, dict):
                    continue
                records.append(
                    {
                        "symbol": symbol.upper(),
                        "date": pt["date"],
                        "metric": metric_name,
                        "value": pt["val"],
                    }
                )

    art_panel_long = pd.DataFrame(records)
    if art_panel_long.empty:
        print("  [WARN] No Artemis records to build panel — skipping.")
    else:
        art_panel_long["date"] = pd.to_datetime(art_panel_long["date"]).dt.date

        # Pivot to wide: one column per metric
        art_panel = art_panel_long.pivot_table(
            index=["symbol", "date"], columns="metric", values="value", aggfunc="last"
        ).reset_index()
        art_panel.columns.name = None

        art_panel.to_parquet(art_panel_path, index=False)
        print(f"  [OK] Saved {len(art_panel):,} rows → {art_panel_path.name}")
        print(f"       Symbols: {art_panel['symbol'].nunique()}")
        print(
            f"       Metrics: {[c for c in art_panel.columns if c not in ['symbol', 'date']]}"
        )
        if len(art_panel):
            print(
                f"       Dates  : {art_panel['date'].min()} → {art_panel['date'].max()}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 (deferred): Build panel_market_daily.parquet
#   Primary source: Artemis price + mc columns from the panel built above.
#   Fallback: CoinGecko market chart files (Pro key only).
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("SECTION 4: Building panel_market_daily.parquet")
print("=" * 60)

panel_path = PROCESSED / "panel_market_daily.parquet"
if panel_path.exists():
    print(f"  [SKIP] {panel_path.name} already exists.")
else:
    # Load Artemis panel if not already in memory
    if not art_panel_path.exists():
        print("  [WARN] Artemis panel missing — cannot build market panel.")
    else:
        _ap = pd.read_parquet(art_panel_path)
        _ap["date"] = pd.to_datetime(_ap["date"]).dt.date

        keep_cols = ["symbol", "date"]
        rename_map = {}
        if "price" in _ap.columns:
            keep_cols.append("price")
            rename_map["price"] = "price_usd"
        if "mc" in _ap.columns:
            keep_cols.append("mc")
            rename_map["mc"] = "market_cap"

        market_panel = _ap[keep_cols].rename(columns=rename_map)
        market_panel = market_panel.dropna(
            subset=["price_usd", "market_cap"], how="all"
        )
        market_panel = market_panel.sort_values(["symbol", "date"]).reset_index(
            drop=True
        )

        market_panel.to_parquet(panel_path, index=False)
        print(f"  [OK] Saved {len(market_panel):,} rows → {panel_path.name}")
        print(
            f"       Symbols: {market_panel['symbol'].nunique()}, "
            f"Dates: {market_panel['date'].min()} → {market_panel['date'].max()}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: Build universe_monthly.parquet from historical market caps
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("SECTION 8: Building universe_monthly.parquet")
print("=" * 60)

universe_path = PROCESSED / "universe_monthly.parquet"
if universe_path.exists():
    print(f"  [SKIP] {universe_path.name} already exists.")
else:
    panel = pd.read_parquet(PROCESSED / "panel_market_daily.parquet")
    panel["date"] = pd.to_datetime(panel["date"])

    # Month-end rebalance dates
    rebal_dates = pd.date_range(START_DATE, END_DATE, freq="ME")

    # Exclude stables/wrapped
    excl_upper = {s.upper() for s in excl_all}

    rows = []
    for dt in rebal_dates:
        day_data = panel[panel["date"] == dt][["symbol", "market_cap"]].dropna()
        if day_data.empty:
            window = panel[
                (panel["date"] >= dt - pd.Timedelta(days=5)) & (panel["date"] <= dt)
            ]
            day_data = (
                window.sort_values("date")
                .drop_duplicates("symbol", keep="last")[["symbol", "market_cap"]]
                .dropna()
            )

        day_data = day_data[~day_data["symbol"].str.upper().isin(excl_upper)]
        day_data = day_data.sort_values("market_cap", ascending=False).head(
            UNIVERSE_SIZE
        )

        for rank, row in enumerate(day_data.itertuples(), start=1):
            rows.append(
                {
                    "date": dt.date(),
                    "symbol": row.symbol.upper(),
                    "mcap_rank": rank,
                    "market_cap": row.market_cap,
                }
            )

    universe_df = pd.DataFrame(rows)
    universe_df.to_parquet(universe_path, index=False)
    print(f"  [OK] Saved {len(universe_df):,} rows → {universe_path.name}")
    print(f"       Rebalance dates: {universe_df['date'].nunique()}")


# ── Final summary ─────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("FETCH COMPLETE — saved files:")
print("=" * 60)
for p in sorted((RAW_CG / "market_chart").glob("*.json")):
    pass  # don't print 200 files
for p in [
    RAW_CG / "coins_list.json",
    RAW_CG / "markets_top500.json",
    RAW_CG / "superset_coins.parquet",
    RAW_ARTEMIS / "supported_assets.json",
    RAW_ARTEMIS / "metrics_raw.json",
    PROCESSED / "panel_market_daily.parquet",
    PROCESSED / "panel_artemis_daily.parquet",
    PROCESSED / "universe_monthly.parquet",
]:
    size = f"{p.stat().st_size / 1024:.1f} KB" if p.exists() else "MISSING"
    print(f"  {'✓' if p.exists() else '✗'}  {p.relative_to(ROOT)}  [{size}]")

n_charts = len(list((RAW_CG / "market_chart").glob("*.json")))
print(f"  ✓  data/raw/coingecko/market_chart/  [{n_charts} files]")
