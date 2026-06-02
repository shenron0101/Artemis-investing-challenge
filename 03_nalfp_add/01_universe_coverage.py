"""03 — Stage 1 / Task 1: Per-asset data-availability audit (Goal 1).

Measures, for every candidate asset in ``Coins.md``, how much continuous daily
price history Binance can provide. Binance is the only ≥5-year source in this
project — the CoinGecko free tier is hard-capped at 365 days (see
``01_Data_Collection/config/settings.yaml``), so the deep-history "core"
universe can only be built from Binance pairs.

For each symbol we resolve the best USDT-priority spot pair, then pull daily
klines from listing to now and compute:

    - binance_pair          resolved <BASE><QUOTE> spot symbol (or None)
    - first_tick / last_tick first and last daily bar dates (UTC)
    - n_bars                 daily bars actually returned
    - span_days              calendar days between first and last tick
    - pct_missing            1 - n_bars / (span_days + 1)
    - longest_run_days       longest gap-free run of consecutive daily bars
    - years_history          span_days / 365.25
    - has_5y / has_4y        boolean history-threshold gates

Outputs
-------
    artifacts/data/universe_coverage.parquet   (+ .csv)
    figures/universe_coverage.png              (history bar chart)

This script only reads public Binance market data; no API key is required for
``/exchangeInfo`` or ``/klines``.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
DATA_DIR = STAGE / "artifacts" / "data"
FIG_DIR = STAGE / "figures"
COINS_MD = ROOT / "Coins.md"

sys.path.insert(0, str(ROOT / "01_Data_Collection" / "src"))
from universe import load_universe_from_markdown  # noqa: E402

BINANCE_BASE = "https://api.binance.com"
QUOTE_PRIORITY = ["USDT", "FDUSD", "BUSD", "USDC"]
KLINE_LIMIT = 1000
DAY_MS = 86_400_000
SLEEP = 0.15  # polite pause between paginated kline calls

# Symbols that are stablecoins / wrapped / bridged — excluded from the factor
# universe by the competition rules, but we still audit and flag them so the
# coverage table is complete and the exclusion is auditable.
STABLE_WRAPPED = {
    "USDT", "USDC", "USDS", "USDE", "DAI", "TUSD", "FDUSD", "BUSD", "PYUSD",
    "USD1", "FRAX", "USDD", "GUSD", "LUSD", "USDP",
    "WBTC", "WETH", "WBETH", "WEETH", "WSTETH", "STETH", "CBBTC", "RETH",
    "WBT", "LBTC", "SOLVBTC", "BSC-USD", "SUSDE", "BUIDL",
}


def http_get(path: str, params: dict) -> object:
    url = f"{BINANCE_BASE}{path}"
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(1 + attempt)
    return None


def build_pair_map() -> dict[str, list[str]]:
    """baseAsset -> list of quote assets available as TRADING spot pairs."""
    info = http_get("/api/v3/exchangeInfo", {})
    out: dict[str, list[str]] = {}
    for s in info.get("symbols", []):
        if s.get("status") != "TRADING":
            continue
        if not s.get("isSpotTradingAllowed", False):
            continue
        out.setdefault(s["baseAsset"], []).append(s["quoteAsset"])
    return out


def resolve_pair(symbol: str, pair_map: dict[str, list[str]]) -> str | None:
    quotes = pair_map.get(symbol.upper())
    if not quotes:
        return None
    for q in QUOTE_PRIORITY:
        if q in quotes:
            return f"{symbol.upper()}{q}"
    return None


def fetch_daily(pair: str) -> pd.DatetimeIndex:
    """All available daily bar open-dates for a pair, paginated from listing."""
    dates: list[int] = []
    start = 0
    while True:
        rows = http_get(
            "/api/v3/klines",
            {"symbol": pair, "interval": "1d", "startTime": start, "limit": KLINE_LIMIT},
        )
        if not rows:
            break
        dates.extend(r[0] for r in rows)
        if len(rows) < KLINE_LIMIT:
            break
        start = rows[-1][0] + DAY_MS
        time.sleep(SLEEP)
    if not dates:
        return pd.DatetimeIndex([])
    return pd.to_datetime(sorted(set(dates)), unit="ms", utc=True).normalize()


def longest_run(days: pd.DatetimeIndex) -> int:
    if len(days) == 0:
        return 0
    gaps = days.to_series().diff().dt.days.fillna(1)
    best = run = 1
    for g in gaps.iloc[1:]:
        run = run + 1 if g == 1 else 1
        best = max(best, run)
    return int(best)


def main() -> None:
    uni = load_universe_from_markdown(COINS_MD)
    print(f"  parsed {len(uni)} candidate assets from Coins.md")

    print("  fetching Binance exchangeInfo ...")
    pair_map = build_pair_map()
    print(f"  {len(pair_map)} base assets trade on Binance spot")

    today = pd.Timestamp.utcnow().normalize()
    records = []
    for i, row in uni.iterrows():
        sym = row["symbol"]
        is_excl = sym.upper() in STABLE_WRAPPED
        pair = resolve_pair(sym, pair_map)
        rec = {
            "symbol": sym,
            "coin_name": row["coin_name"],
            "cohort": row["cohort"],
            "overall_rank": row["overall_rank"],
            "is_stable_or_wrapped": is_excl,
            "binance_pair": pair,
        }
        if pair is not None:
            days = fetch_daily(pair)
            if len(days):
                first, last = days[0], days[-1]
                span = (last - first).days
                rec.update(
                    first_tick=first.tz_localize(None),
                    last_tick=last.tz_localize(None),
                    n_bars=len(days),
                    span_days=span,
                    pct_missing=round(1 - len(days) / (span + 1), 4) if span > 0 else 0.0,
                    longest_run_days=longest_run(days),
                    years_history=round(span / 365.25, 2),
                    stale_days=int((today - last).days),
                )
        records.append(rec)
        tag = pair or "—"
        yrs = rec.get("years_history", 0.0)
        flag = " [excl]" if is_excl else ""
        print(f"  [{i + 1:>3}/{len(uni)}] {sym:<14} {tag:<12} {yrs:>5} yr{flag}")

    cov = pd.DataFrame(records)
    for col in ("first_tick", "last_tick", "n_bars", "span_days", "pct_missing",
                "longest_run_days", "years_history", "stale_days"):
        if col not in cov.columns:
            cov[col] = pd.NA
    cov["has_5y"] = (cov["years_history"] >= 5.0) & (~cov["is_stable_or_wrapped"])
    cov["has_4y"] = (cov["years_history"] >= 4.0) & (~cov["is_stable_or_wrapped"])
    cov = cov.sort_values(["years_history"], ascending=False, na_position="last").reset_index(drop=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cov.to_parquet(DATA_DIR / "universe_coverage.parquet", index=False)
    cov.to_csv(DATA_DIR / "universe_coverage.csv", index=False)
    print(f"\n  wrote {(DATA_DIR / 'universe_coverage.parquet').relative_to(ROOT)} ({len(cov)} rows)")

    # ---- summary ----
    tradable = cov[~cov["is_stable_or_wrapped"]]
    n_pair = tradable["binance_pair"].notna().sum()
    print("\n  ===== coverage summary (factor-eligible assets) =====")
    print(f"  factor-eligible candidates : {len(tradable)}")
    print(f"  with a Binance pair        : {n_pair}")
    print(f"  with >= 5y history         : {int(cov['has_5y'].sum())}")
    print(f"  with >= 4y history         : {int(cov['has_4y'].sum())}")

    # ---- plot ----
    _plot(cov)


def _plot(cov: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = cov[(~cov["is_stable_or_wrapped"]) & cov["years_history"].notna()].copy()
    d = d.sort_values("years_history", ascending=True)
    if d.empty:
        print("  (no plottable rows)")
        return
    fig, ax = plt.subplots(figsize=(10, max(6, len(d) * 0.18)))
    colors = ["#2c7fb8" if y >= 5 else ("#7fcdbb" if y >= 4 else "#cccccc")
              for y in d["years_history"]]
    ax.barh(d["symbol"], d["years_history"], color=colors)
    for thr, lab in ((5, "5y"), (4, "4y")):
        ax.axvline(thr, ls="--", lw=1, color="#d95f0e")
        ax.text(thr, len(d) - 0.5, f" {lab}", color="#d95f0e", va="top", fontsize=8)
    ax.set_xlabel("Years of continuous Binance daily history")
    ax.set_title("Stage 09 — per-asset data availability (factor-eligible universe)")
    ax.tick_params(axis="y", labelsize=6)
    fig.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "universe_coverage.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"  wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
