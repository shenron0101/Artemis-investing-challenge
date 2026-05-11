"""03 - Build external and repo-native regime inputs.

Strict paper parity would add weekly Fama-French equity factors, industry
portfolios, Fear & Greed, Altseason, CVX, and hack-loss series. This script
keeps those inputs separable: users can drop CSVs into 06_hidden_factor_pricing
/inputs, while the default run writes repo-native crypto regime proxies.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, INPUT_DIR, MANIFEST_DIR, coerce_date, coerce_week, load_clean, write_frame, write_json

PANEL_PATH = DATA_DIR / "weekly_asset_panel.parquet"
FACTOR_PATH = DATA_DIR / "observed_factor_returns.parquet"


def _numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def load_external_csvs() -> tuple[pd.DataFrame, list[dict[str, object]]]:
    frames: list[pd.DataFrame] = []
    manifest: list[dict[str, object]] = []
    for path in sorted(INPUT_DIR.glob("*.csv")):
        raw = pd.read_csv(path)
        date_col = next((col for col in raw.columns if col.lower() in {"week", "date", "timestamp"}), None)
        if date_col is None:
            manifest.append({"file": path.name, "status": "skipped", "reason": "no date/week column"})
            continue
        raw["week"] = coerce_week(raw[date_col])
        value_cols = [col for col in raw.columns if col not in {date_col, "week"}]
        raw = _numeric(raw, value_cols)
        renamed = raw[["week"] + value_cols].rename(
            columns={col: f"external_{path.stem}_{col}" for col in value_cols}
        )
        frames.append(renamed.groupby("week", as_index=False).last())
        manifest.append({"file": path.name, "status": "loaded", "columns": value_cols})
    if not frames:
        return pd.DataFrame(columns=["week"]), manifest
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="week", how="outer")
    return out.sort_values("week"), manifest


def build_native_inputs() -> pd.DataFrame:
    panel = pd.read_parquet(PANEL_PATH)
    factors = pd.read_parquet(FACTOR_PATH)
    wide = panel.pivot_table(index="week", columns="symbol", values="ret_1w", aggfunc="last").sort_index()
    btc = wide["BTC"] if "BTC" in wide.columns else pd.Series(np.nan, index=wide.index)
    alt = wide.drop(columns=["BTC"], errors="ignore").mean(axis=1)

    stable = load_clean("defillama_stablecoin_inflows_daily.parquet").copy()
    stable["date"] = coerce_date(stable["date"])
    stable["week"] = coerce_week(stable["date"])
    stable = _numeric(stable, ["supply_usd", "inflow_usd"])
    all_chain = stable.loc[stable["chain"].astype(str).str.upper().eq("ALL")].copy()
    if all_chain.empty:
        all_chain = stable.groupby(["week"], as_index=False)[["supply_usd", "inflow_usd"]].sum(min_count=1)
    else:
        all_chain = all_chain.sort_values("date").groupby("week", as_index=False).tail(1)
    all_chain = all_chain.sort_values("week")
    all_chain["native_stablecoin_supply_chg"] = all_chain["supply_usd"].pct_change()
    all_chain = all_chain[["week", "native_stablecoin_supply_chg", "inflow_usd"]].rename(
        columns={"inflow_usd": "native_stablecoin_inflow_usd"}
    )

    tvl = load_clean("defillama_protocol_tvl_daily.parquet").copy()
    tvl["date"] = coerce_date(tvl["date"])
    tvl["week"] = coerce_week(tvl["date"])
    tvl = _numeric(tvl, ["tvl_usd"])
    tvl_weekly = tvl.groupby(["week", "defillama_slug"], as_index=False).tail(1)
    tvl_weekly = tvl_weekly.groupby("week", as_index=False)["tvl_usd"].sum(min_count=1).sort_values("week")
    tvl_weekly["native_defi_tvl_chg"] = tvl_weekly["tvl_usd"].pct_change()
    tvl_weekly = tvl_weekly[["week", "native_defi_tvl_chg"]]

    native = factors[["week", "crypto_market"]].copy()
    native = native.merge(pd.DataFrame({"week": wide.index, "native_btc_ret": btc.to_numpy(), "native_alt_equal_weight_ret": alt.to_numpy()}), on="week", how="outer")
    native["native_alt_minus_btc_ret"] = native["native_alt_equal_weight_ret"] - native["native_btc_ret"]
    native["native_market_vol_4w"] = native["crypto_market"].rolling(4, min_periods=3).std() * np.sqrt(52)
    native = native.merge(all_chain, on="week", how="left").merge(tvl_weekly, on="week", how="left")
    return native.drop(columns=["crypto_market"]).sort_values("week")


def main() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"Run 01_build_panel.py first: missing {PANEL_PATH}")
    if not FACTOR_PATH.exists():
        raise FileNotFoundError(f"Run 02_observed_factors.py first: missing {FACTOR_PATH}")
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    native = build_native_inputs()
    external, external_manifest = load_external_csvs()
    combined = native.merge(external, on="week", how="outer") if not external.empty else native
    combined = combined.replace([np.inf, -np.inf], np.nan).sort_values("week")
    write_frame(combined, DATA_DIR / "external_and_regime_inputs")
    write_json(
        {
            "rows": int(len(combined)),
            "start_week": combined["week"].min(),
            "end_week": combined["week"].max(),
            "input_dir": str(INPUT_DIR.relative_to(INPUT_DIR.parents[1])),
            "loaded_external_csvs": external_manifest,
            "missing_paper_inputs": [
                "Fama-French weekly equity factors",
                "Fama-French industry portfolios",
                "CoinMarketCap Fear & Greed index",
                "CoinMarketCap Altcoin Season index",
                "CVX crypto implied volatility index",
                "weekly hack-loss scaled by market capitalization",
            ],
            "native_proxy_columns": [col for col in native.columns if col != "week"],
        },
        MANIFEST_DIR / "03_external_inputs_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
