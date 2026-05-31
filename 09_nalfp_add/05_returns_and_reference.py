"""09 — Goal 2 / step 1: weekly crypto returns + macro reference basket.

Produces the two inputs the Sparse PCA (06) and CCA (07) need:

    returns_weekly.parquet    week x symbol -> weekly return (trading universe)
    reference_weekly.parquet  week -> returns/changes of a macro reference basket

The reference basket (the user's "SPY, BTC + 3-4 economically viable tickers")
is BTC (crypto market) plus FRED macro series:
    SPX     S&P 500 index        -> weekly return       (equity beta)
    GOLD    LBMA gold USD/oz      -> weekly return       (real-asset / haven)
    DXY     broad USD index       -> weekly return       (dollar)
    UST10Y  10y Treasury yield    -> weekly change (pp)  (rates)
    VIX     CBOE VIX              -> weekly change        (risk appetite)

Weeks are Monday-anchored to match the project panel convention.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
DATA_DIR = STAGE / "artifacts" / "data"
MANIFEST_DIR = STAGE / "artifacts" / "manifests"
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

FRED_SERIES = {           # logical name -> (FRED id, transform)
    "SPX": ("SP500", "ret"),
    "GOLD": ("GOLDPMGBD228NLBM", "ret"),
    "DXY": ("DTWEXBGS", "ret"),
    "UST10Y": ("DGS10", "chg"),
    "VIX": ("VIXCLS", "chg"),
}


def _fred_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("FRED_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def monday_week(idx: pd.DatetimeIndex) -> pd.Series:
    return idx.to_period("W-SUN").start_time


def fred_series(series_id: str, key: str) -> pd.Series:
    r = requests.get(FRED_BASE, params={"series_id": series_id, "api_key": key,
                                        "file_type": "json", "observation_start": "2017-01-01"},
                     timeout=25)
    r.raise_for_status()
    obs = r.json().get("observations", [])
    s = pd.Series({pd.Timestamp(o["date"]): o["value"] for o in obs})
    s = pd.to_numeric(s, errors="coerce").dropna().sort_index()
    time.sleep(0.4)
    return s


def to_weekly_last(s: pd.Series) -> pd.Series:
    df = s.to_frame("v")
    df["week"] = monday_week(df.index)
    return df.groupby("week")["v"].last()


def main() -> None:
    panel = pd.read_parquet(DATA_DIR / "price_mcap_panel_weekly.parquet")
    panel["week"] = pd.to_datetime(panel["week"])
    import json
    man = json.loads((MANIFEST_DIR / "universe_manifest.json").read_text())
    trade = set(man["trading_universe"]["symbols_ever_eligible"])

    # ---- crypto weekly returns ----
    px = (panel[panel["symbol"].isin(trade)]
          .pivot(index="week", columns="symbol", values="price")
          .sort_index())
    rets = px.pct_change()
    # NOTE: returns are intentionally left RAW (no winsorization). Several core
    # factors (VolC low-vol, MAXRET lottery-reversal) deliberately target the
    # extreme tails of the cross-section, so clipping per-week outliers would
    # blunt exactly the signal they trade. Downstream IC/GX tests are rank-based
    # (Spearman) and therefore already robust to outlier magnitude.
    rets_long = (rets.reset_index().melt(id_vars="week", var_name="symbol", value_name="ret")
                 .dropna(subset=["ret"]))
    rets_long = rets_long[np.isfinite(rets_long["ret"])]
    rets_long.to_parquet(DATA_DIR / "returns_weekly.parquet", index=False)
    print(f"  wrote returns_weekly.parquet  "
          f"({rets_long['symbol'].nunique()} symbols x {rets_long['week'].nunique()} weeks, "
          f"{len(rets_long):,} obs)")

    # ---- reference basket ----
    key = _fred_key()
    ref = {}
    btc_px = px["BTC"] if "BTC" in px.columns else None
    if btc_px is not None:
        ref["BTC"] = btc_px.pct_change()
    for name, (fid, how) in FRED_SERIES.items():
        try:
            raw = fred_series(fid, key)
        except requests.RequestException as e:
            print(f"  WARN {name} ({fid}): {e}")
            continue
        wk = to_weekly_last(raw)
        ref[name] = wk.pct_change() if how == "ret" else wk.diff()
        print(f"  {name:<7} {fid:<22} {len(wk)} weekly obs  ({raw.index.min().date()}..{raw.index.max().date()})")

    refdf = pd.DataFrame(ref).sort_index()
    refdf.index.name = "week"
    refdf = refdf.replace([np.inf, -np.inf], np.nan)
    refdf.to_parquet(DATA_DIR / "reference_weekly.parquet")
    refdf.to_csv(DATA_DIR / "reference_weekly.csv")
    print(f"\n  wrote reference_weekly.parquet  "
          f"({refdf.shape[1]} tickers x {refdf.shape[0]} weeks: {', '.join(refdf.columns)})")
    cov = refdf.dropna()
    print(f"  reference basket complete-rows window: {cov.index.min().date()} .. {cov.index.max().date()} "
          f"({len(cov)} weeks)")


if __name__ == "__main__":
    main()
