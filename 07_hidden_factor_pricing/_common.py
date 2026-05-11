"""Shared helpers for Stage 06 hidden-factor pricing scripts."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "01_Data_Collection" / "data" / "clean"
STAGE = Path(__file__).resolve().parent
INPUT_DIR = STAGE / "inputs"
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
    for path in (INPUT_DIR, DATA_DIR, MANIFEST_DIR, TABLE_DIR, FIG_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def load_clean(name: str) -> pd.DataFrame:
    return pd.read_parquet(CLEAN / name)


def coerce_date(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()


def coerce_week(values: pd.Series) -> pd.Series:
    """Map dates to Monday-start weeks, matching the paper's weekly cadence."""
    dates = coerce_date(values)
    return dates.dt.to_period("W-SUN").dt.start_time


def exclude_symbols() -> set[str]:
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


def save_plotly(fig: Any, name: str, stem: str, *, width: int = 1300, height: int = 760) -> Path:
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
