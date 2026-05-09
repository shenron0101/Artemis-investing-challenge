"""Shared helpers for the 03_analysis/*.py notebooks.

Loaded explicitly by each analysis file so they can be run as standalone
scripts (`python 03_analysis/05_factor_signals.py`) and also cell-by-cell
in VS Code Interactive (`# %%` markers).
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "01_Data_Collection" / "data" / "clean"
FIG_ROOT = Path(__file__).resolve().parent / "figures"

LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=60, r=30, t=60, b=50),
)

QUAL = "Set2"
SEQ = "Viridis"
DIVERGE = "RdBu"


def fig_dir(stem: str) -> Path:
    d = FIG_ROOT / stem
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(fig, name: str, stem: str, *, width: int = 1280, height: int = 720) -> Path:
    out = fig_dir(stem)
    fig.update_layout(**LAYOUT)
    png_path = out / f"{name}.png"
    html_path = out / f"{name}.html"
    fig.write_image(png_path, width=width, height=height, scale=2)
    fig.write_html(html_path, include_plotlyjs="cdn", full_html=True)
    print(f"  saved {png_path.relative_to(ROOT)}")
    return png_path


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(CLEAN / name)


def universe_with_mcap() -> pd.DataFrame:
    """Return asset_master joined to the latest CoinGecko market snapshot."""
    am = load("asset_master.parquet")
    snap = load("coingecko_market_snapshot.parquet")[
        ["coingecko_id", "market_cap", "current_price", "total_volume"]
    ]
    return am.merge(snap, on="coingecko_id", how="left")
