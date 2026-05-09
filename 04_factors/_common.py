"""Shared helpers for the 04_factors/*.py notebooks.

Mirrors 03_analysis/_common.py and adds factor-specific helpers:
- exclude_symbols(): upper-case set of stable / wrapped / bridged tickers
- prices_wide(), log_returns_wide(): pivoted matrices for cross-sectional work
- forward_returns(prices, horizons=...): dict of forward-return frames
- spearman_ic(factor, fwd_ret): daily cross-sectional Spearman IC + summary
- cross_sectional_rank(panel, ascending): rank wrapper that respects exclusions
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
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


def save(fig, name: str, stem: str, *, width: int = 1300, height: int = 800) -> Path:
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
    """asset_master joined to the latest CoinGecko market snapshot.

    Adds fdv_usd from coingecko_coin_details (snapshot stores it as
    `fully_diluted_valuation`; details stores `fdv_usd`). We prefer the
    details column because it carries the supply-side fields too.
    """
    am = load("asset_master.parquet")
    snap = load("coingecko_market_snapshot.parquet")[
        [
            "coingecko_id",
            "market_cap",
            "current_price",
            "total_volume",
            "fully_diluted_valuation",
            "circulating_supply",
            "total_supply",
            "max_supply",
        ]
    ].rename(columns={"fully_diluted_valuation": "fdv"})
    return am.merge(snap, on="coingecko_id", how="left")


# ---------------------------------------------------------------------------
# Factor-specific helpers
# ---------------------------------------------------------------------------


def exclude_symbols() -> set[str]:
    """Upper-case set of symbols flagged stable/wrapped/bridged.

    coingecko_coin_details stores `symbol` lowercase but every other table
    upper-cases it. The bug from 05_factor_signals.py was forgetting to
    upper-case here, leaving the exclusion set effectively empty.
    """
    detail = load("coingecko_coin_details.parquet")
    flagged = detail.loc[
        detail[["is_stablecoin", "is_wrapped", "is_bridged"]]
        .fillna(False)
        .any(axis=1),
        "symbol",
    ]
    return set(flagged.astype(str).str.upper())


def _ticks() -> pd.DataFrame:
    df = load("coingecko_daily_ticks.parquet").copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])
    return df


def prices_wide() -> pd.DataFrame:
    """Wide price matrix indexed by date, columns are upper-case symbols."""
    df = _ticks()
    return df.pivot_table(
        index="date", columns="symbol", values="price_usd", aggfunc="last"
    ).sort_index()


def market_caps_wide(*, ffill_limit: int = 5) -> pd.DataFrame:
    """Wide market-cap matrix. Forward-fills up to `ffill_limit` days because
    coingecko_daily_ticks occasionally has NaN market_cap on the most recent
    rows for actively-traded names (data-freshness artifact, not a real gap).
    """
    df = _ticks()
    out = df.pivot_table(
        index="date", columns="symbol", values="market_cap_usd", aggfunc="last"
    ).sort_index()
    if ffill_limit:
        out = out.ffill(limit=ffill_limit)
    return out


def log_returns_wide() -> pd.DataFrame:
    p = prices_wide()
    return np.log(p / p.shift(1))


def forward_returns(prices: pd.DataFrame, horizons: Iterable[int] = (30, 60, 90)) -> dict[int, pd.DataFrame]:
    """Forward log return over h calendar days, aligned at t (so fwd_ret_t looks ahead)."""
    out: dict[int, pd.DataFrame] = {}
    for h in horizons:
        out[h] = np.log(prices.shift(-h) / prices)
    return out


def cross_sectional_rank(panel: pd.DataFrame, *, ascending: bool = False, exclude: set[str] | None = None) -> pd.DataFrame:
    """Rank each row of `panel` cross-sectionally.

    `ascending=False` → highest value gets rank 1 (best).
    Excluded columns are dropped before ranking.
    """
    if exclude:
        panel = panel.drop(columns=[c for c in panel.columns if c in exclude], errors="ignore")
    return panel.rank(axis=1, ascending=ascending, na_option="keep")


def spearman_ic(factor_panel: pd.DataFrame, fwd_ret: pd.DataFrame) -> pd.Series:
    """Daily cross-sectional Spearman ρ between `factor_panel` and `fwd_ret`.

    Both panels must share the same date index and at least overlapping columns.
    Returns a Series indexed by date.
    """
    common_cols = factor_panel.columns.intersection(fwd_ret.columns)
    f = factor_panel[common_cols]
    r = fwd_ret[common_cols]
    common_idx = f.index.intersection(r.index)
    f = f.loc[common_idx]
    r = r.loc[common_idx]

    ic_values = []
    for date in common_idx:
        fr = f.loc[date]
        rr = r.loc[date]
        mask = fr.notna() & rr.notna()
        if mask.sum() < 5:
            ic_values.append(np.nan)
            continue
        ic_values.append(fr[mask].rank().corr(rr[mask].rank()))
    return pd.Series(ic_values, index=common_idx, name="spearman_ic")


def ic_summary(ic: pd.Series) -> dict[str, float]:
    """Mean IC, IC std, and IR (mean / std). Skips NaNs."""
    s = ic.dropna()
    mean_ic = float(s.mean()) if len(s) else float("nan")
    std_ic = float(s.std()) if len(s) > 1 else float("nan")
    ir = mean_ic / std_ic if std_ic and not np.isnan(std_ic) and std_ic > 0 else float("nan")
    return dict(mean_ic=mean_ic, std_ic=std_ic, ir=ir, n=int(len(s)))
