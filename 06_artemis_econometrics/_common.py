"""Shared helpers for the Stage 06 artemis-econometrics track.

Builds a cross-sectional, weekly crypto research pipeline:
 - panel construction utilities (date / week coercion, weekly last)
 - artifact paths and writers
 - exclusion list mirrors 04_factors / 06_hidden_factor_pricing
 - plotly save helper that matches 05_btc_direction conventions
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "01_Data_Collection" / "data" / "clean"
STAGE = Path(__file__).resolve().parent
ARTIFACTS = STAGE / "artifacts"
DATA_DIR = ARTIFACTS / "data"
MANIFEST_DIR = ARTIFACTS / "manifests"
TABLE_DIR = ARTIFACTS / "tables"
FIG_ROOT = STAGE / "figures"

LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=60, r=30, t=60, b=50),
)


def ensure_dirs() -> None:
    for path in (DATA_DIR, MANIFEST_DIR, TABLE_DIR, FIG_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def load_clean(name: str) -> pd.DataFrame:
    return pd.read_parquet(CLEAN / name)


def coerce_date(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()


def coerce_week(values: pd.Series) -> pd.Series:
    """Monday-start weeks (W-SUN period start)."""
    return coerce_date(values).dt.to_period("W-SUN").dt.start_time


def exclude_symbols() -> set[str]:
    """Upper-case set of symbols flagged stablecoin / wrapped / bridged."""
    detail = load_clean("coingecko_coin_details.parquet")
    flagged = detail.loc[
        detail[["is_stablecoin", "is_wrapped", "is_bridged"]]
        .fillna(False)
        .any(axis=1),
        "symbol",
    ]
    return set(flagged.astype(str).str.upper())


def write_frame(df: pd.DataFrame, path_stem: Path, *, csv: bool = True) -> Path:
    ensure_dirs()
    parquet_path = path_stem.with_suffix(".parquet")
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path, index=False)
    if csv:
        df.to_csv(path_stem.with_suffix(".csv"), index=False)
    print(f"  wrote {parquet_path.relative_to(ROOT)} rows={len(df):,}")
    return parquet_path


def write_json(obj: dict[str, Any] | list[Any], path: Path) -> Path:
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


def cross_z(panel: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score (each row across columns)."""
    return panel.sub(panel.mean(axis=1), axis=0).div(panel.std(axis=1), axis=0)


def winsorize_cs(panel: pd.DataFrame, p: float = 0.01) -> pd.DataFrame:
    """Winsorize each row at the given two-sided percentile."""
    if p <= 0:
        return panel
    lo = panel.quantile(p, axis=1)
    hi = panel.quantile(1 - p, axis=1)
    out = panel.clip(lower=lo, upper=hi, axis=0)
    return out


def standardize_features(df: pd.DataFrame, cols: Iterable[str], *, by: str = "week") -> pd.DataFrame:
    """Per-week cross-sectional z-score of selected columns."""
    out = df.copy()
    cols = [c for c in cols if c in out.columns]
    grouped = out.groupby(by)[cols]
    means = grouped.transform("mean")
    stds = grouped.transform("std")
    out[cols] = (out[cols] - means) / stds.replace(0, np.nan)
    return out


def safe_log(values: pd.Series | np.ndarray) -> pd.Series | np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = np.where(arr > 0, arr, np.nan)
    return np.log(arr)
