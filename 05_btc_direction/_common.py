"""Shared helpers for Stage 05 BTC direction reproduction scripts."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

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
    """Save HTML always and PNG only when explicitly enabled.

    Plotly/Kaleido can block while trying to discover or launch a browser in
    lightweight local environments. HTML is the stable Stage 05 artifact; set
    ARTEMIS_SAVE_PNG=1 to request PNG export.
    """
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


def chronological_split_indices(n_rows: int, train_frac: float = 0.70, val_frac: float = 0.15) -> tuple[slice, slice, slice]:
    if n_rows < 100:
        raise ValueError(f"Need at least 100 observations for chronological split, got {n_rows}")
    train_end = max(1, int(n_rows * train_frac))
    val_end = max(train_end + 1, int(n_rows * (train_frac + val_frac)))
    val_end = min(val_end, n_rows - 1)
    return slice(0, train_end), slice(train_end, val_end), slice(val_end, n_rows)


def classification_metrics(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, precision_score, recall_score

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
