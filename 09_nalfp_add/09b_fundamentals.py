"""09b — Fetch 5-year FEES + TVL fundamentals for TVLC and FunC factors.

Primary source: Artemis API (FEES, CHAIN_TVL).
Fallback: DeFiLlama /v2/historicalChainTvl/{chain} for L1 TVL,
          DeFiLlama /protocol/{slug} for DeFi-protocol TVL.

Outputs
-------
  artifacts/data/fundamentals_weekly.parquet
    columns: symbol, week, fees_usd, tvl_usd, fees_to_mcap, tvl_to_mcap
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

STAGE = Path(__file__).resolve().parent
DATA  = STAGE / "artifacts" / "data"

ARTEMIS_KEY  = os.getenv("ARTEMIS_API_KEY", "")
ARTEMIS_BASE = "https://data-svc.artemisxyz.com"
LLAMA_BASE   = "https://api.llama.fi"

# DeFiLlama overrides (protocol-level TVL for DeFi tokens)
LLAMA_PROTOCOL_OVERRIDES: dict[str, list[str]] = {
    "AAVE":   ["aave-v3", "aave-v2"],
    "UNI":    ["uniswap-v3", "uniswap-v2"],
    "CAKE":   ["pancakeswap-amm", "pancakeswap-amm-v3"],
    "JST":    ["justlend"],
    "LINK":   ["chainlink-requests"],
    "JUP":    ["jupiter-perpetual-exchange"],
    "ENA":    ["ethena-usde"],
    "ONDO":   ["ondo-yield-assets"],
    "SKY":    ["sky-lending"],
    "MORPHO": ["morpho-blue"],
}
# DeFiLlama chain TVL name mapping (for L1 chains)
CHAIN_TVL_NAMES: dict[str, str] = {
    "ETH":  "Ethereum", "BNB": "BSC",     "SOL":  "Solana",
    "AVAX": "Avalanche","TRX": "Tron",    "ATOM": "CosmosHub",
    "DOT":  "Polkadot", "NEAR":"Near",    "ICP":  "ICP",
    "ADA":  "Cardano",  "ALGO":"Algorand","XRP":  "XRP",
    "HBAR": "Hedera",   "SUI": "Sui",     "APT":  "Aptos",
    "FIL":  "Filecoin", "VET": "VeChain", "ETC":  "EthereumClassic",
    "BCH":  "Bitcoin Cash","LTC":"Litecoin","DOGE":"Dogechain",
}

START = "2021-01-01"
END   = "2026-05-29"
BATCH = 10  # smaller batch to avoid timeouts


def _parse_series(pts) -> list[dict]:
    """Return only valid {date, val} dicts from an Artemis series."""
    if not isinstance(pts, list):
        return []
    return [p for p in pts if isinstance(p, dict) and "date" in p and p.get("val") is not None]


def artemis_fetch(metric: str, symbols: list[str]) -> pd.DataFrame:
    """Fetch one Artemis metric for all symbols. Returns long daily frame."""
    rows = []
    for i in range(0, len(symbols), BATCH):
        batch = symbols[i:i + BATCH]
        for attempt in range(3):
            try:
                r = requests.get(
                    f"{ARTEMIS_BASE}/data/{metric}/",
                    params={"symbols": ",".join(batch),
                            "startDate": START, "endDate": END,
                            "APIKey": ARTEMIS_KEY},
                    timeout=90,
                )
                r.raise_for_status()
                data = r.json()
                if not isinstance(data, dict):
                    break
                sym_data = data.get("data", {}).get("symbols", {})
                for sym_lower, metrics in sym_data.items():
                    if not isinstance(metrics, dict):
                        continue
                    for pt in _parse_series(metrics.get(metric, [])):
                        if pt["val"] and pt["val"] > 0:
                            rows.append({"symbol": sym_lower.upper(),
                                         "date": pt["date"],
                                         "value": float(pt["val"])})
                break
            except Exception as exc:
                if attempt == 2:
                    print(f"    WARN: Artemis {metric} batch {batch[:3]}… {exc}")
                else:
                    time.sleep(3 ** attempt)
    if not rows:
        return pd.DataFrame(columns=["symbol", "date", "value"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def llama_chain_tvl(chain_name: str) -> pd.DataFrame:
    """DeFiLlama /v2/historicalChainTvl/{chain}."""
    for attempt in range(3):
        try:
            r = requests.get(f"{LLAMA_BASE}/v2/historicalChainTvl/{chain_name}",
                             timeout=30)
            if r.status_code == 404:
                return pd.DataFrame()
            r.raise_for_status()
            pts = r.json()
            rows = [{"date": pd.Timestamp.fromtimestamp(p["date"]),
                     "value": float(p["totalLiquidityUSD"])}
                    for p in pts
                    if isinstance(p, dict) and p.get("totalLiquidityUSD", 0) > 0]
            return pd.DataFrame(rows)
        except Exception as exc:
            if attempt == 2:
                print(f"    WARN: DeFiLlama chain {chain_name}: {exc}")
            else:
                time.sleep(2)
    return pd.DataFrame()


def llama_protocol_tvl(slug: str) -> pd.DataFrame:
    """DeFiLlama /protocol/{slug} TVL history."""
    for attempt in range(3):
        try:
            r = requests.get(f"{LLAMA_BASE}/protocol/{slug}", timeout=30)
            if r.status_code == 404:
                return pd.DataFrame()
            r.raise_for_status()
            data = r.json()
            rows = [{"date": pd.Timestamp.fromtimestamp(p["date"]),
                     "value": float(p["totalLiquidityUSD"])}
                    for p in (data.get("tvl") or [])
                    if isinstance(p, dict) and p.get("totalLiquidityUSD", 0) > 0]
            return pd.DataFrame(rows)
        except Exception as exc:
            if attempt == 2:
                print(f"    WARN: DeFiLlama protocol {slug}: {exc}")
            else:
                time.sleep(2)
    return pd.DataFrame()


def to_weekly_wide(daily: pd.DataFrame, syms: list[str],
                   agg: str = "sum") -> pd.DataFrame:
    """Convert long daily frame to wide Monday-anchored weekly frame."""
    wide_cols = {}
    for sym in syms:
        d = daily[daily["symbol"] == sym].set_index("date")["value"].sort_index()
        if d.empty:
            continue
        fn = d.resample("W-MON", label="left", closed="left")
        wide_cols[sym] = fn.sum() if agg == "sum" else fn.last()
    if not wide_cols:
        return pd.DataFrame()
    return pd.DataFrame(wide_cols)


def main() -> None:
    panel = pd.read_parquet(DATA / "price_mcap_panel_weekly.parquet")
    panel["week"] = pd.to_datetime(panel["week"])
    syms = sorted(panel["symbol"].unique().tolist())
    print(f"Universe: {len(syms)} symbols")

    # ---- 1. Artemis FEES ----
    print("\nFetching FEES from Artemis ...")
    fees_daily = artemis_fetch("FEES", syms)
    n_fees = fees_daily["symbol"].nunique() if not fees_daily.empty else 0
    print(f"  {len(fees_daily):,} rows | {n_fees} symbols with FEES data")

    # ---- 2. Artemis CHAIN_TVL ----
    print("\nFetching CHAIN_TVL from Artemis ...")
    tvl_art = artemis_fetch("CHAIN_TVL", syms)
    art_tvl_syms = set(tvl_art["symbol"].unique()) if not tvl_art.empty else set()
    print(f"  {len(tvl_art):,} rows | {len(art_tvl_syms)} symbols")

    # ---- 3. DeFiLlama chain TVL (for L1s missing from Artemis) ----
    print("\nFetching DeFiLlama chain TVL ...")
    llama_rows = []
    for sym, chain in CHAIN_TVL_NAMES.items():
        if sym not in art_tvl_syms:
            df = llama_chain_tvl(chain)
            if not df.empty:
                df["symbol"] = sym
                llama_rows.append(df)
                print(f"  {sym} ({chain}): {len(df)} days")
            time.sleep(0.3)

    # ---- 4. DeFiLlama protocol TVL (for DeFi tokens) ----
    print("\nFetching DeFiLlama protocol TVL ...")
    for sym, slugs in LLAMA_PROTOCOL_OVERRIDES.items():
        if sym not in art_tvl_syms:
            slug_dfs = []
            for slug in slugs:
                df = llama_protocol_tvl(slug)
                if not df.empty:
                    slug_dfs.append(df)
                time.sleep(0.3)
            if slug_dfs:
                combined = pd.concat(slug_dfs).groupby("date")["value"].sum().reset_index()
                combined["symbol"] = sym
                llama_rows.append(combined)
                print(f"  {sym}: {len(combined)} days")

    tvl_llama = (pd.concat(llama_rows, ignore_index=True)
                 if llama_rows else pd.DataFrame(columns=["date", "value", "symbol"]))
    tvl_llama["date"] = pd.to_datetime(tvl_llama["date"])

    # Merge: Artemis preferred, DeFiLlama fallback
    tvl_daily = pd.concat([tvl_art, tvl_llama], ignore_index=True)
    tvl_daily = (tvl_daily.sort_values(["symbol", "date"])
                 .drop_duplicates(subset=["symbol", "date"], keep="first"))
    print(f"\nTotal TVL daily: {len(tvl_daily):,} rows | {tvl_daily['symbol'].nunique()} symbols")

    # ---- 5. Weekly wide frames ----
    print("\nBuilding weekly wide frames ...")
    fees_wide = to_weekly_wide(fees_daily, syms, agg="sum")
    tvl_wide  = to_weekly_wide(tvl_daily,  syms, agg="last")

    # ---- 6. Compute ratios vs reconstructed mcap ----
    mc_wide = (panel.pivot(index="week", columns="symbol", values="mcap")
               .sort_index())
    mc_wide.index = pd.to_datetime(mc_wide.index)

    def safe_ratio(num_wide: pd.DataFrame, den_wide: pd.DataFrame) -> pd.DataFrame:
        if num_wide.empty:
            return pd.DataFrame()
        n, d = num_wide.align(den_wide, join="inner", axis=0)
        n, d = n.align(d, join="inner", axis=1)
        r = n.div(d.replace(0, np.nan))
        q99 = r.stack(future_stack=True).quantile(0.99)
        return r.clip(upper=q99)

    fees_to_mcap = safe_ratio(fees_wide, mc_wide)
    tvl_to_mcap  = safe_ratio(tvl_wide,  mc_wide)

    # ---- 7. Melt to long and join ----
    def to_long(wide: pd.DataFrame, col_name: str) -> pd.DataFrame:
        if wide.empty:
            return pd.DataFrame(columns=["week", "symbol", col_name])
        m = wide.stack(future_stack=True).reset_index()
        m.columns = ["week", "symbol", col_name]
        m["week"] = pd.to_datetime(m["week"])
        return m

    fees_long = to_long(fees_wide,     "fees_usd")
    tvl_long  = to_long(tvl_wide,      "tvl_usd")
    fmc_long  = to_long(fees_to_mcap,  "fees_to_mcap")
    tmc_long  = to_long(tvl_to_mcap,   "tvl_to_mcap")

    out = fees_long
    for df in [tvl_long, fmc_long, tmc_long]:
        out = out.merge(df, on=["week", "symbol"], how="outer")
    out = out.sort_values(["week", "symbol"]).reset_index(drop=True)

    out.to_parquet(DATA / "fundamentals_weekly.parquet", index=False)
    print(f"\nSaved fundamentals_weekly.parquet: {len(out):,} rows")

    # Coverage summary
    has = out.groupby("symbol").agg(
        fees_weeks=("fees_usd",    lambda s: (s > 0).sum()),
        tvl_weeks =("tvl_usd",     lambda s: (s > 0).sum()),
    ).sort_values("fees_weeks", ascending=False)
    print("\nCoverage (weeks with non-zero data):")
    print(has.to_string())


if __name__ == "__main__":
    main()
