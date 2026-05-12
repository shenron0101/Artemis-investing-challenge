"""Shared helpers for the 08_nalfp (NALFP) track.

Reuses the artifact-layout conventions from stage 06 / 07 so the upstream
characteristic and panel parquets can be loaded directly without copying.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
ARTIFACTS = STAGE / "artifacts"
DATA_DIR = ARTIFACTS / "data"
MANIFEST_DIR = ARTIFACTS / "manifests"
TABLE_DIR = ARTIFACTS / "tables"
FIG_ROOT = STAGE / "figures"

UPSTREAM_06 = ROOT / "06_artemis_econometrics" / "artifacts" / "data"
UPSTREAM_07 = ROOT / "07_hidden_factor_pricing" / "artifacts" / "data"
CLEAN = ROOT / "01_Data_Collection" / "data" / "clean"

LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=60, r=30, t=60, b=50),
)

# Walk-forward split. The IPCA panel begins at week 12 (clustering lookback
# burn-in), so on a 52-week sample we have ~40 usable weeks. We train on the
# first 24 of them and evaluate the strategy on the last 16 — same OOS length
# as the original plan, just measured from the first week the network signal
# is defined rather than from sample-start.
TRAIN_WEEKS = 24

# Universe of instruments fed into IPCA Z_it (lagged characteristics).
# Each instrument MUST have cross-sectional variance within a week, otherwise
# the per-week z-score collapses it to zero and the corresponding Γ row
# becomes mechanically uninformative. The two market-wide scalars
# (`network_entropy`, `stable_inflow_z`) were initially candidates here but
# were *removed* after validation showed they are broadcast and therefore
# unidentifiable inside IPCA — they now enter the model only as regime
# indicators in `03_regime_detector.py`, where they vary over time.
INSTRUMENT_COLS = [
    "mom_4w",        # M — 4-week momentum
    "vol_4w",        # V — realised volatility (low-vol premium)
    "log_mcap",      # size proxy
    "turnover",      # liquidity proxy
    "F_yield",       # fundamental yield
    "S_supply",      # supply-absorption composite
    "G_growth",      # activity-validated growth
    "within_cluster_mom",  # network: relative strength inside cluster
    "cross_cluster_rel",   # network: relative strength vs other clusters
]

# Market-wide regime indicators (vary over time, constant within a week).
# These are consumed by 03_regime_detector but never by IPCA itself.
REGIME_COLS = ["network_entropy", "stable_inflow_z"]


def ensure_dirs() -> None:
    for path in (DATA_DIR, MANIFEST_DIR, TABLE_DIR, FIG_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def write_frame(df: pd.DataFrame, path_stem: Path, *, csv: bool = True) -> Path:
    ensure_dirs()
    parquet_path = path_stem.with_suffix(".parquet")
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path, index=False)
    if csv:
        df.to_csv(path_stem.with_suffix(".csv"), index=False)
    print(f"  wrote {parquet_path.relative_to(ROOT)} rows={len(df):,}")
    return parquet_path


def write_json(obj: Any, path: Path) -> Path:
    ensure_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")
    return path


def save_plotly(fig: Any, name: str, stem: str, *, width: int = 1300, height: int = 720) -> Path:
    out = FIG_ROOT / stem
    out.mkdir(parents=True, exist_ok=True)
    fig.update_layout(**LAYOUT)
    html_path = out / f"{name}.html"
    fig.write_html(html_path, include_plotlyjs="cdn", full_html=True)
    if os.environ.get("ARTEMIS_SAVE_PNG") != "1":
        print(f"  saved {html_path.relative_to(ROOT)}")
        return html_path
    png_path = out / f"{name}.png"
    try:
        fig.write_image(png_path, width=width, height=height, scale=2)
        print(f"  saved {png_path.relative_to(ROOT)}")
        return png_path
    except Exception as exc:  # noqa: BLE001
        print(f"  saved {html_path.relative_to(ROOT)} (PNG skipped: {exc})")
        return html_path


def load_characteristics() -> pd.DataFrame:
    """Stage-06 weekly characteristics (already lagged) — long format."""
    df = pd.read_parquet(UPSTREAM_06 / "characteristics.parquet")
    df["week"] = pd.to_datetime(df["week"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df.sort_values(["week", "symbol"]).reset_index(drop=True)


def load_returns_wide() -> pd.DataFrame:
    """Wide pivot of ret_1w (week x symbol) — strictly historical, no shift."""
    char = load_characteristics()
    wide = char.pivot_table(index="week", columns="symbol", values="ret_1w", aggfunc="last")
    return wide.sort_index()


def cs_zscore(s: pd.Series) -> pd.Series:
    """Cross-sectional z-score within a single week (NaN-safe)."""
    mu = s.mean()
    sd = s.std()
    if sd == 0 or np.isnan(sd):
        return s * 0.0
    return (s - mu) / sd


def standardize_panel(df: pd.DataFrame, cols: Iterable[str], by: str = "week") -> pd.DataFrame:
    """Per-week cross-sectional z-score of selected columns; median-fill within week."""
    out = df.copy()
    cols = [c for c in cols if c in out.columns]
    for col in cols:
        med = out.groupby(by)[col].transform("median")
        out[col] = out[col].fillna(med)
        # any week that is still all-NaN gets a global median
        out[col] = out[col].fillna(out[col].median())
    grouped = out.groupby(by)[cols]
    means = grouped.transform("mean")
    stds = grouped.transform("std").replace(0, np.nan)
    out[cols] = (out[cols] - means) / stds
    out[cols] = out[cols].fillna(0.0)
    return out


def winsorize_cs(df: pd.DataFrame, cols: Iterable[str], p: float = 0.02, by: str = "week") -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col not in out.columns:
            continue
        lo = out.groupby(by)[col].transform(lambda x: x.quantile(p))
        hi = out.groupby(by)[col].transform(lambda x: x.quantile(1 - p))
        out[col] = out[col].clip(lower=lo, upper=hi)
    return out


def information_coefficient(signal: pd.Series, fwd_ret: pd.Series, by: pd.Series) -> pd.Series:
    """Per-period Spearman IC."""
    df = pd.DataFrame({"signal": signal, "ret": fwd_ret, "g": by}).dropna()
    return df.groupby("g").apply(
        lambda x: x["signal"].rank().corr(x["ret"].rank()) if len(x) > 5 else np.nan
    )
