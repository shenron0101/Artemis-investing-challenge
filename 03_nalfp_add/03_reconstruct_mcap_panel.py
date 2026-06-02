"""03 — Stage 1 / Task 3: reconstruct a 5-year price + market-cap panel.

The CoinGecko free tier caps daily history at 365 days, which bottlenecked all
prior research to 52 weeks. We rebuild a ~5-year panel from data we *can* get,
using the identity ``market_cap = price x circulating_supply``. Because price
swings by 10x while circulating supply moves slowly, historical market cap is
well approximated by 5y Binance price times a supply anchor.

Per-coin reconstruction, tiered by accuracy (from ``universe_coverage_full``):
    tier 1  real mcap          -> CoinMetrics CapMrktCurUSD (full history)
    tier 2  price x realsupply -> Binance close x CoinMetrics SplyCur
    tier 3  price x anchor     -> Binance close x current circulating supply
                                  (CoinGecko snapshot, held constant) -- the hack

The recent ~365 days (our OOS window) is backed by real mcap wherever a tier-1
series exists; only the older ~4 years is estimated. For tier-1 coins we also
compute the reconstruction error (price x current-supply vs real mcap) bucketed
by years-back, so the trustworthiness of the estimate is quantified, not assumed.

Outputs
-------
    artifacts/data/price_mcap_panel_weekly.parquet   week x symbol: price, mcap, source
    artifacts/data/mcap_reconstruction_error.parquet validation: |est/real-1| by years-back
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
DATA_DIR = STAGE / "artifacts" / "data"

sys.path.insert(0, str(STAGE))

BINANCE_BASE = "https://api.binance.com"
CM_BASE = "https://community-api.coinmetrics.io/v4"
CG_BASE = "https://api.coingecko.com/api/v3"
KLINE_LIMIT = 1000
DAY_MS = 86_400_000


def _env_cg_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("COINGECKO_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


CG_KEY = _env_cg_key()


def http_json(url: str, params: dict, *, tries: int = 4) -> object:
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, timeout=25)
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(1 + attempt)
    return None


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def binance_daily_close(pair: str) -> pd.Series:
    """Daily close indexed by UTC date, from listing to now."""
    rows_all, start = [], 0
    while True:
        rows = http_json(f"{BINANCE_BASE}/api/v3/klines",
                         {"symbol": pair, "interval": "1d", "startTime": start, "limit": KLINE_LIMIT})
        if not rows:
            break
        rows_all.extend(rows)
        if len(rows) < KLINE_LIMIT:
            break
        start = rows[-1][0] + DAY_MS
        time.sleep(0.12)
    if not rows_all:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows_all], unit="ms", utc=True).tz_localize(None).normalize()
    close = pd.Series([float(r[4]) for r in rows_all], index=idx, name="price")
    return close[~close.index.duplicated(keep="last")].sort_index()


def cm_metric_series(cm_id: str, metric: str) -> pd.Series:
    """Full daily history of a CoinMetrics metric, paginated."""
    out, token = {}, None
    while True:
        params = {"assets": cm_id, "metrics": metric, "frequency": "1d",
                  "start_time": "2016-01-01", "page_size": 10000}
        if token:
            params["next_page_token"] = token
        j = http_json(f"{CM_BASE}/timeseries/asset-metrics", params)
        if not isinstance(j, dict) or "data" not in j:
            break
        for row in j["data"]:
            v = row.get(metric)
            if v is not None:
                out[pd.to_datetime(row["time"]).tz_localize(None).normalize()] = float(v)
        token = j.get("next_page_token")
        if not token:
            break
        time.sleep(0.15)
    return pd.Series(out, name=metric).sort_index()


def cg_current_supply() -> pd.DataFrame:
    """Current circulating supply + id per symbol from the markets snapshot."""
    rows = []
    for page in (1, 2):
        j = http_json(f"{CG_BASE}/coins/markets",
                      {"vs_currency": "usd", "order": "market_cap_desc",
                       "per_page": 250, "page": page, "x_cg_demo_api_key": CG_KEY})
        if isinstance(j, list):
            rows.extend(j)
        time.sleep(2.5)
    recs = [{"symbol": x["symbol"].upper(), "cg_id": x["id"],
             "cg_supply": x.get("circulating_supply"), "cg_mcap": x.get("market_cap")}
            for x in rows if x.get("circulating_supply")]
    df = pd.DataFrame(recs)
    # resolve ticker collisions: keep the highest-mcap coin per symbol
    return (df.sort_values("cg_mcap", ascending=False)
              .drop_duplicates("symbol", keep="first")
              .set_index("symbol"))


def cg_recent_mcap(cg_id: str) -> pd.Series:
    """Real daily market cap for the last 365 days (CoinGecko free window)."""
    j = http_json(f"{CG_BASE}/coins/{cg_id}/market_chart",
                  {"vs_currency": "usd", "days": 365, "interval": "daily",
                   "x_cg_demo_api_key": CG_KEY})
    time.sleep(2.2)
    if not isinstance(j, dict) or not j.get("market_caps"):
        return pd.Series(dtype=float)
    mc = j["market_caps"]
    idx = pd.to_datetime([p[0] for p in mc], unit="ms", utc=True).tz_localize(None).normalize()
    s = pd.Series([p[1] for p in mc], index=idx, name="mcap")
    return s[~s.index.duplicated(keep="last")].sort_index()


def supply_backfill(price: pd.Series, real_mcap_recent: pd.Series) -> pd.Series:
    """Estimate a daily circulating-supply trajectory for the whole price span.

    Implied supply over the real-mcap window is supply = mcap / price. We fit
    log(supply) ~ a + b*t over that window and extrapolate backward in time, so
    older dates get a *smaller* supply (emissions hadn't happened yet) instead
    of today's inflated figure. Supply is clamped to (0, max observed].
    """
    common = pd.concat({"p": price, "m": real_mcap_recent}, axis=1).dropna()
    if len(common) < 30:
        return pd.Series(dtype=float)
    implied = (common["m"] / common["p"]).clip(lower=1e-9)
    t0 = implied.index.min()
    days = (implied.index - t0).days.to_numpy(dtype=float)
    b, a = np.polyfit(days, np.log(implied.to_numpy()), 1)
    # clamp the *per-day* log-supply drift to a sane annual band so backward
    # extrapolation cannot blow up. The bounds are expressed per day:
    #   lower = -3%/yr  -> -0.03/365   (supply shrinks slowly at most)
    #   upper = +50%/yr ->  0.50/365   (emissions grow fast but not absurdly)
    # NB: the previous upper bound of 0.05 was an unintended per-*day* cap
    # (~1500%/yr) that allowed unrealistically steep early-period supply.
    b = float(np.clip(b, -0.03 / 365.0, 0.50 / 365.0))
    all_days = (price.index - t0).days.to_numpy(dtype=float)
    supply = np.exp(a + b * all_days)
    supply = np.clip(supply, 1e-9, implied.max())
    return pd.Series(supply, index=price.index, name="supply")


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def main() -> None:
    cov = pd.read_parquet(DATA_DIR / "universe_coverage_full.parquet")
    coins = cov[cov["binance_pair"].notna() & ~cov["is_stable_or_wrapped"]].copy()
    print(f"  reconstructing {len(coins)} priced, factor-eligible coins")

    print("  fetching CoinGecko current-supply snapshot ...")
    supply_snap = cg_current_supply()
    print(f"    matched current supply for {len(supply_snap)} symbols")

    panel_rows = []
    err_rows = []
    today = pd.Timestamp.utcnow().tz_localize(None).normalize()

    for i, r in enumerate(coins.itertuples(), 1):
        sym, pair, tier, cm_id = r.symbol, r.binance_pair, r.mcap_tier, r.cm_id
        price = binance_daily_close(pair)
        if price.empty:
            print(f"  [{i:>2}/{len(coins)}] {sym:<12} no price, skip")
            continue

        cg_id = supply_snap.loc[sym, "cg_id"] if sym in supply_snap.index else None
        cur_supply = supply_snap.loc[sym, "cg_supply"] if sym in supply_snap.index else np.nan

        # real mcap for the recent 365d (exact, covers the OOS window for every coin)
        real_recent = cg_recent_mcap(cg_id) if cg_id else pd.Series(dtype=float)

        # growth-anchored supply estimate -> estimated mcap for the deep backfill
        supply_est = supply_backfill(price, real_recent)
        if supply_est.empty:
            supply_est = pd.Series(cur_supply, index=price.index)  # last-resort constant
        est_mcap = (price * supply_est).dropna()

        mcap = est_mcap.reindex(price.index)
        source = pd.Series("est_price_x_supply_trend", index=price.index)

        # splice exact real mcap into the recent window
        if not real_recent.empty:
            ra = real_recent.reindex(price.index)
            mcap[ra.notna()] = ra[ra.notna()]
            source[ra.notna()] = "real_cg_recent"

        # tier-1: authoritative full-history real mcap from CoinMetrics
        real_deep = cm_metric_series(cm_id, "CapMrktCurUSD") if tier == "1_real_mcap" else pd.Series(dtype=float)
        if not real_deep.empty:
            rd = real_deep.reindex(price.index)
            mcap[rd.notna()] = rd[rd.notna()]
            source[rd.notna()] = "real_cm"

        # validation: grade the *estimate method* (price x supply_trend) against CM real
        if tier == "1_real_mcap" and not est_mcap.empty and not real_deep.empty:
            both = pd.concat({"est": est_mcap, "real": real_deep.reindex(price.index)}, axis=1).dropna()
            if len(both) > 30:
                yb = ((today - both.index).days / 365.25).astype(int)
                ape = (both["est"] / both["real"] - 1.0).abs()
                for years_back, g in ape.groupby(yb):
                    err_rows.append({"symbol": sym, "years_back": int(years_back),
                                     "median_abs_pct_err": float(g.median()), "n": int(len(g))})

        df = pd.DataFrame({"price": price, "mcap": mcap, "source": source})
        df = df.dropna(subset=["price"])
        df["symbol"], df["tier"] = sym, tier
        panel_rows.append(df.reset_index().rename(columns={"index": "date"}))
        yrs = round((price.index[-1] - price.index[0]).days / 365.25, 2)
        nmc = int(df["mcap"].notna().sum())
        print(f"  [{i:>2}/{len(coins)}] {sym:<12} {tier:<22} {yrs:>4}y price, {nmc} mcap pts")

    daily = pd.concat(panel_rows, ignore_index=True)

    # ---- weekly (Monday-anchored last obs), matching project convention ----
    daily["week"] = daily["date"].dt.to_period("W-SUN").dt.start_time  # Monday-start week
    wk = (daily.sort_values("date")
               .groupby(["symbol", "week"], as_index=False)
               .agg(price=("price", "last"), mcap=("mcap", "last"),
                    source=("source", "last"), tier=("tier", "last")))
    wk.to_parquet(DATA_DIR / "price_mcap_panel_weekly.parquet", index=False)
    wk.to_csv(DATA_DIR / "price_mcap_panel_weekly.csv", index=False)
    print(f"\n  wrote price_mcap_panel_weekly.parquet  "
          f"({wk['symbol'].nunique()} symbols x {wk['week'].nunique()} weeks, {len(wk):,} rows)")

    if err_rows:
        err = (pd.DataFrame(err_rows)
                 .groupby("years_back")
                 .apply(lambda g: pd.Series({
                     "median_abs_pct_err": np.average(g["median_abs_pct_err"], weights=g["n"]),
                     "n_coins": g["symbol"].nunique()}), include_groups=False)
                 .reset_index())
        err.to_parquet(DATA_DIR / "mcap_reconstruction_error.parquet", index=False)
        print("\n  ===== reconstruction error: price x current-supply vs real mcap =====")
        print("  (how far the constant-supply estimate drifts as we go back in time)")
        for _, e in err.iterrows():
            print(f"   {int(e['years_back'])}y back: median |est/real - 1| = "
                  f"{e['median_abs_pct_err']*100:5.1f}%   ({int(e['n_coins'])} tier-1 coins)")

    span = wk.groupby("symbol")["week"].nunique()
    print(f"\n  weekly-obs per coin: median={int(span.median())}, "
          f"max={int(span.max())}, coins>=200wk={int((span>=200).sum())}")


if __name__ == "__main__":
    main()
