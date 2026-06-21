"""Shared helpers for the network-dynamics producer (`00_network_dynamics.py`).

Loads the stage-02 econometrics characteristics panel and provides the small set
of artifact-writing / plotting helpers the network step needs. The cleaned
characteristics parquet is read directly from stage 02 so nothing is copied.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path(__file__).resolve().parent
ARTIFACTS = STAGE / "artifacts"
DATA_DIR = ARTIFACTS / "data"
MANIFEST_DIR = ARTIFACTS / "manifests"
FIG_ROOT = STAGE / "figures"

# Upstream weekly characteristics panel (already lagged) from stage 02.
UPSTREAM_02 = ROOT / "02_artemis_econometrics" / "artifacts" / "data"

LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=60, r=30, t=60, b=50),
)


def ensure_dirs() -> None:
    for path in (DATA_DIR, MANIFEST_DIR, FIG_ROOT):
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
    """Stage-02 weekly characteristics (already lagged) — long format."""
    df = pd.read_parquet(UPSTREAM_02 / "characteristics.parquet")
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
