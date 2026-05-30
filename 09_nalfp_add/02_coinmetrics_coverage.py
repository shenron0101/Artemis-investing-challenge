"""09 — Stage 1 / Task 2: CoinMetrics historical market-cap coverage audit.

Goal 1 needs a point-in-time, market-cap-ranked universe over ~5 years. Binance
gives 5y of *price* (audited in 01), but not market cap. Per the design decision
(2026-05-29) we source historical market cap from the **CoinMetrics community
API** (free) — confirmed free for BTC/ETH and other majors, gated to paid for
some newer assets (e.g. SOL).

This script probes, for every factor-eligible candidate, whether CoinMetrics
serves ``CapMrktCurUSD`` (market cap) and ``SplyCur`` (circulating supply) for
free, and how far back. It merges the result onto the Binance coverage table so
a single artifact answers: *for each asset, do we have both price and mcap, and
for how long?*

CoinMetrics asset IDs are lowercase tickers; a few hand-mapped exceptions live
in ``CM_ID_OVERRIDE``.

Outputs
-------
    artifacts/data/universe_coverage_full.parquet   (+ .csv)   Binance ∪ CoinMetrics
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
DATA_DIR = STAGE / "artifacts" / "data"

CM_BASE = "https://community-api.coinmetrics.io/v4"
CM_MCAP = "CapMrktCurUSD"
CM_SPLY = "SplyCur"
PROBE_START = "2016-01-01"
SLEEP = 0.25

# symbol (our universe) -> CoinMetrics asset id, where lowercase(symbol) is wrong.
CM_ID_OVERRIDE: dict[str, str] = {
    "IOTA": "miota",
}


def cm_get(metric: str, asset: str, *, start: str, end: str | None = None,
           page_size: int = 1) -> tuple[list, str | None]:
    """Return (rows, error_type). error_type is None on success."""
    params = {
        "assets": asset, "metrics": metric, "frequency": "1d",
        "start_time": start, "page_size": page_size,
    }
    if end:
        params["end_time"] = end
    for attempt in range(4):
        try:
            r = requests.get(f"{CM_BASE}/timeseries/asset-metrics", params=params, timeout=20)
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            j = r.json()
            if "error" in j:
                return [], j["error"].get("type", "error")
            return j.get("data", []), None
        except requests.RequestException:
            if attempt == 3:
                return [], "request_exception"
            time.sleep(1 + attempt)
    return [], "retries_exhausted"


def probe_asset(symbol: str) -> dict:
    cm_id = CM_ID_OVERRIDE.get(symbol.upper(), symbol.lower())
    out = {"cm_id": cm_id, "cm_mcap_available": False, "cm_supply_available": False,
           "cm_first_date": pd.NaT, "cm_last_date": pd.NaT, "cm_error": None}
    # circulating-supply availability (tier-2 fallback for reconstruction)
    srows, serr = cm_get(CM_SPLY, cm_id, start=PROBE_START, page_size=1)
    out["cm_supply_available"] = (serr is None and bool(srows))
    # earliest available mcap point
    rows, err = cm_get(CM_MCAP, cm_id, start=PROBE_START, page_size=1)
    if err is not None:
        out["cm_error"] = err
        return out
    if not rows:
        out["cm_error"] = "empty"
        return out
    out["cm_mcap_available"] = True
    out["cm_first_date"] = pd.to_datetime(rows[0]["time"]).tz_localize(None).normalize()
    # most recent point (liveness / last date)
    recent_start = (pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
    rrows, rerr = cm_get(CM_MCAP, cm_id, start=recent_start, page_size=30)
    if rerr is None and rrows:
        out["cm_last_date"] = pd.to_datetime(rrows[-1]["time"]).tz_localize(None).normalize()
    return out


def main() -> None:
    cov = pd.read_parquet(DATA_DIR / "universe_coverage.parquet")
    eligible = cov[~cov["is_stable_or_wrapped"]].copy()
    print(f"  probing CoinMetrics mcap for {len(eligible)} factor-eligible assets ...")

    recs = []
    for i, row in enumerate(eligible.itertuples(), 1):
        sym = row.symbol
        p = probe_asset(sym)
        p["symbol"] = sym
        now = pd.Timestamp.utcnow().tz_localize(None).normalize()
        if p["cm_mcap_available"] and pd.notna(p["cm_first_date"]):
            yrs = round((now - p["cm_first_date"]).days / 365.25, 2)
        else:
            yrs = 0.0
        p["cm_years_mcap"] = yrs
        recs.append(p)
        status = f"{yrs:>5}y" if p["cm_mcap_available"] else f"({p['cm_error']})"
        print(f"  [{i:>3}/{len(eligible)}] {sym:<14} {p['cm_id']:<10} {status}")
        time.sleep(SLEEP)

    cm = pd.DataFrame(recs)
    full = cov.merge(cm, on="symbol", how="left")

    # combined deep-history gate: needs BOTH Binance price AND CoinMetrics mcap >= threshold
    full["cm_mcap_available"] = full["cm_mcap_available"].fillna(False)
    full["cm_supply_available"] = full["cm_supply_available"].fillna(False)
    # reconstruction tier per coin (1 best -> 3 hack); needs a Binance price pair to be tradable
    def _tier(r):
        if not r["binance_pair"]:
            return "none"          # no price -> not tradable in our backtest
        if r["cm_mcap_available"]:
            return "1_real_mcap"   # use CoinMetrics CapMrktCurUSD directly
        if r["cm_supply_available"]:
            return "2_price_x_realsupply"
        return "3_price_x_anchor"  # the hack: price x recent-anchored supply
    full["mcap_tier"] = full.apply(_tier, axis=1)
    full["cm_years_mcap"] = full["cm_years_mcap"].fillna(0.0)
    full["deep_5y_both"] = (
        (full["years_history"] >= 5.0)
        & (full["cm_years_mcap"] >= 5.0)
        & (~full["is_stable_or_wrapped"])
    )
    full["tradable_priced"] = full["binance_pair"].notna() & full["cm_mcap_available"]

    full = full.sort_values(["cm_years_mcap", "years_history"], ascending=False,
                            na_position="last").reset_index(drop=True)
    full.to_parquet(DATA_DIR / "universe_coverage_full.parquet", index=False)
    full.to_csv(DATA_DIR / "universe_coverage_full.csv", index=False)
    print(f"\n  wrote {(DATA_DIR / 'universe_coverage_full.parquet').relative_to(ROOT)} ({len(full)} rows)")

    el = full[~full["is_stable_or_wrapped"]]
    print("\n  ===== combined coverage (factor-eligible) =====")
    print(f"  has Binance price pair         : {int(el['binance_pair'].notna().sum())}")
    print(f"  has CoinMetrics free mcap      : {int(el['cm_mcap_available'].sum())}")
    print(f"  has CoinMetrics free supply    : {int(el['cm_supply_available'].sum())}")
    print(f"  tradable AND priced (both)     : {int(el['tradable_priced'].sum())}")
    print(f"  deep >=5y on BOTH price & mcap  : {int(full['deep_5y_both'].sum())}")
    print("\n  reconstruction tier breakdown (factor-eligible):")
    print(el["mcap_tier"].value_counts().to_string())
    miss = el[el['binance_pair'].notna() & ~el['cm_mcap_available']]
    if len(miss):
        print(f"  has Binance but NO free mcap   : {sorted(miss['symbol'].tolist())}")


if __name__ == "__main__":
    main()
