"""02 — Feature engineering for next-day BTC direction."""
# %% Imports
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.errors import PerformanceWarning

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, MANIFEST_DIR, write_frame, write_json

STEM = Path(__file__).stem
BASE_PATH = DATA_DIR / "btc_direction_base.parquet"
warnings.filterwarnings("ignore", category=PerformanceWarning)

# Exogenous feature prefixes that are computed at row t but must be lagged to t-1
# because the underlying series publish T+1 in practice (volume, on-chain, DeFi).
EXOGENOUS_PREFIXES = (
    "base_volume",
    "quote_volume",
    "trade_count",
    "cg_",
    "log_base_volume",
    "log_quote_volume",
    "log_trade_count",
    "log_cg_",
    "log_artemis_",
    "log_defillama_",
    "defillama_",
)


def _safe_log(series: pd.Series) -> pd.Series:
    return np.log(series.where(series > 0))


def _rolling_z(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=max(3, window // 3)).mean()
    std = series.rolling(window, min_periods=max(3, window // 3)).std()
    return (series - mean) / std.replace(0, np.nan)


def _add_lags(out: pd.DataFrame, source: pd.Series, name: str, lags: tuple[int, ...] = (1, 2, 3, 7, 14)) -> list[str]:
    created: list[str] = []
    for lag in lags:
        col = f"{name}_lag{lag}"
        out[col] = source.shift(lag)
        created.append(col)
    return created


def engineer_features(base: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    df = base.sort_values("date").reset_index(drop=True).copy()
    features = pd.DataFrame({"date": df["date"]})
    groups: dict[str, list[str]] = {
        "market_microstructure": [],
        "technical_price": [],
        "onchain_activity": [],
        "stablecoin_liquidity": [],
        "defi_liquidity": [],
    }

    close = pd.to_numeric(df["close"], errors="coerce")
    open_ = pd.to_numeric(df["open"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")

    log_close = _safe_log(close)
    ret_1d = log_close.diff()
    simple_ret_1d = close.pct_change()
    features["log_return_1d_lag1"] = ret_1d.shift(1)
    features["simple_return_1d_lag1"] = simple_ret_1d.shift(1)
    features["intraday_oc_return"] = np.log(close / open_).replace([np.inf, -np.inf], np.nan)
    features["high_low_range"] = ((high - low) / close).replace([np.inf, -np.inf], np.nan)
    features["close_location"] = ((close - low) / (high - low)).replace([np.inf, -np.inf], np.nan)
    groups["market_microstructure"].extend(
        ["log_return_1d_lag1", "simple_return_1d_lag1", "intraday_oc_return", "high_low_range", "close_location"]
    )

    for col in ["base_volume", "quote_volume", "trade_count", "cg_total_volume_usd", "cg_market_cap_usd"]:
        if col not in df.columns:
            continue
        log_col = f"log_{col}"
        features[log_col] = _safe_log(pd.to_numeric(df[col], errors="coerce"))
        groups["market_microstructure"].append(log_col)
        groups["market_microstructure"].extend(_add_lags(features, features[log_col].diff(), f"{log_col}_diff"))
        for window in (7, 30):
            z_col = f"{log_col}_z{window}"
            features[z_col] = _rolling_z(features[log_col], window)
            groups["market_microstructure"].append(z_col)

    for window in (3, 7, 14, 30, 60):
        ret_col = f"log_return_{window}d_lag1"
        vol_col = f"realized_vol_{window}d_lag1"
        ma_col = f"ma_gap_{window}d"
        features[ret_col] = (log_close - log_close.shift(window)).shift(1)
        features[vol_col] = ret_1d.rolling(window, min_periods=max(3, window // 3)).std().shift(1) * np.sqrt(365)
        features[ma_col] = (close / close.rolling(window, min_periods=max(3, window // 3)).mean() - 1.0).shift(1)
        groups["technical_price"].extend([ret_col, vol_col, ma_col])

    for col in [c for c in df.columns if c.startswith("artemis_")]:
        raw = pd.to_numeric(df[col], errors="coerce")
        if raw.notna().sum() < 100 or raw.nunique(dropna=True) <= 1:
            continue
        log_col = f"log_{col}"
        diff_col = f"{log_col}_diff1"
        features[log_col] = _safe_log(raw)
        features[diff_col] = features[log_col].diff()
        groups["onchain_activity"].extend([log_col, diff_col])
        groups["onchain_activity"].extend(_add_lags(features, features[log_col], log_col))
        for window in (7, 30):
            z_col = f"{log_col}_z{window}"
            features[z_col] = _rolling_z(features[log_col], window)
            groups["onchain_activity"].append(z_col)

    liquidity_groups = {
        "stablecoin_liquidity": [c for c in df.columns if c.startswith("defillama_stablecoin_")],
        "defi_liquidity": [c for c in df.columns if c.startswith("defillama_tracked_")],
    }
    for group, cols in liquidity_groups.items():
        for col in cols:
            raw = pd.to_numeric(df[col], errors="coerce")
            if raw.notna().sum() < 100 or raw.nunique(dropna=True) <= 1:
                continue
            log_col = f"log_{col}" if "inflow" not in col else col
            features[log_col] = _safe_log(raw) if "inflow" not in col else raw
            groups[group].append(log_col)
            groups[group].extend(_add_lags(features, features[log_col].diff(), f"{log_col}_diff"))
            for window in (7, 30):
                z_col = f"{log_col}_z{window}"
                features[z_col] = _rolling_z(features[log_col], window)
                groups[group].append(z_col)

    exo_cols = [
        c
        for c in features.columns
        if c != "date" and any(c.startswith(p) or c == p for p in EXOGENOUS_PREFIXES)
    ]
    features[exo_cols] = features[exo_cols].shift(1)

    target_log_return = log_close.shift(-1) - log_close
    target_simple_return = close.shift(-1) / close - 1.0
    features["target_next_day_up"] = (target_log_return > 0).astype(int)
    features["target_return_1d_log"] = target_log_return
    features["target_return_1d_simple"] = target_simple_return
    features["close"] = close
    features["next_close"] = close.shift(-1)

    feature_cols = [col for cols in groups.values() for col in cols]
    feature_cols = [col for col in dict.fromkeys(feature_cols) if col in features.columns]
    coverage = features[feature_cols].notna().mean()
    keep = coverage[coverage >= 0.60].index.tolist()
    dropped = [col for col in feature_cols if col not in keep]
    groups = {group: [col for col in cols if col in keep] for group, cols in groups.items()}

    model_df = features[["date", "close", "next_close", "target_next_day_up", "target_return_1d_log", "target_return_1d_simple"] + keep]
    model_df = model_df.dropna(subset=["date", "close", "next_close", "target_return_1d_log"]).reset_index(drop=True)
    return model_df, {"feature_groups": groups, "dropped_low_coverage": dropped, "feature_columns": keep}


def main() -> None:
    if not BASE_PATH.exists():
        raise FileNotFoundError(f"Run 01_build_dataset.py first: missing {BASE_PATH}")
    base = pd.read_parquet(BASE_PATH)
    df, catalog = engineer_features(base)
    write_frame(df, DATA_DIR / "btc_direction_features")
    write_json(
        {
            "rows": int(len(df)),
            "start_date": df["date"].min(),
            "end_date": df["date"].max(),
            **catalog,
            "target": "target_next_day_up equals 1 when next daily close is above current daily close.",
            "leakage_control": "Technical price features are lagged to t-1; exogenous volume, CoinGecko, Artemis, and DeFi liquidity features are globally shifted one row to reflect T+1 publication timing.",
        },
        MANIFEST_DIR / "02_feature_catalog.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
