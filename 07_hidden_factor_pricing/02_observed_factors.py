"""02 - Build observed crypto factors.

Factors mirror the paper's crypto-side construction:
- market: weekly value-weighted crypto return
- SMB: value-weighted small-minus-big by lagged market cap
- MOM: value-weighted winner-minus-loser by prior 5-week cumulative return
- TVL: value-weighted high-minus-low by lagged TVL / market cap
- TVL orthogonalized to market returns
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, MANIFEST_DIR, TABLE_DIR, write_frame, write_json

PANEL_PATH = DATA_DIR / "weekly_asset_panel.parquet"


def _vwret(rows: pd.DataFrame) -> float:
    rows = rows.dropna(subset=["ret_1w", "lag_market_cap_usd"]).copy()
    rows = rows.loc[rows["lag_market_cap_usd"].gt(0)]
    if rows.empty:
        return float("nan")
    w = rows["lag_market_cap_usd"] / rows["lag_market_cap_usd"].sum()
    return float((w * rows["ret_1w"]).sum())


def _long_short(rows: pd.DataFrame, signal: str, *, high_minus_low: bool = True, min_assets: int = 8) -> dict[str, float]:
    rows = rows.dropna(subset=["ret_1w", "lag_market_cap_usd", signal]).copy()
    rows = rows.loc[rows["lag_market_cap_usd"].gt(0)]
    if len(rows) < min_assets:
        return {"return": float("nan"), "long_n": 0, "short_n": 0, "eligible_n": int(len(rows))}
    rows = rows.sort_values(signal)
    leg_n = max(2, int(np.floor(len(rows) * 0.25)))
    low = rows.head(leg_n)
    high = rows.tail(leg_n)
    long_leg, short_leg = (high, low) if high_minus_low else (low, high)
    return {
        "return": _vwret(long_leg) - _vwret(short_leg),
        "long_n": int(len(long_leg)),
        "short_n": int(len(short_leg)),
        "eligible_n": int(len(rows)),
    }


def _orthogonalize(y: pd.Series, x: pd.Series) -> pd.Series:
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    out = pd.Series(np.nan, index=y.index, name=f"{y.name}_orth")
    if len(df) < 8:
        return out
    X = np.column_stack([np.ones(len(df)), df["x"].to_numpy()])
    beta = np.linalg.lstsq(X, df["y"].to_numpy(), rcond=None)[0]
    out.loc[df.index] = df["y"] - X @ beta
    return out


def build_factors(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    records: list[dict[str, object]] = []
    count_records: list[dict[str, object]] = []
    for week, rows in panel.groupby("week"):
        market = _vwret(rows)
        smb = _long_short(rows, "log_lag_market_cap", high_minus_low=False, min_assets=8)
        mom = _long_short(rows, "mom_5w", high_minus_low=True, min_assets=8)
        tvl = _long_short(rows, "lag_tvl_to_mcap", high_minus_low=True, min_assets=6)
        records.append(
            {
                "week": week,
                "crypto_market": market,
                "crypto_smb": smb["return"],
                "crypto_mom": mom["return"],
                "crypto_tvl": tvl["return"],
            }
        )
        for name, payload in (("crypto_smb", smb), ("crypto_mom", mom), ("crypto_tvl", tvl)):
            count_records.append({"week": week, "factor": name, **payload})

    factors = pd.DataFrame(records).sort_values("week")
    factors["crypto_tvl_orth"] = _orthogonalize(
        factors.set_index("week")["crypto_tvl"],
        factors.set_index("week")["crypto_market"],
    ).to_numpy()
    counts = pd.DataFrame(count_records).sort_values(["week", "factor"])
    return factors, counts


def summarize_factors(factors: pd.DataFrame) -> pd.DataFrame:
    factor_cols = [col for col in factors.columns if col != "week"]
    rows = []
    for col in factor_cols:
        s = factors[col].dropna()
        rows.append(
            {
                "factor": col,
                "n_weeks": int(len(s)),
                "mean_weekly": float(s.mean()) if len(s) else float("nan"),
                "std_weekly": float(s.std()) if len(s) > 1 else float("nan"),
                "min_weekly": float(s.min()) if len(s) else float("nan"),
                "median_weekly": float(s.median()) if len(s) else float("nan"),
                "max_weekly": float(s.max()) if len(s) else float("nan"),
                "annualized_mean_52w": float(s.mean() * 52) if len(s) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"Run 01_build_panel.py first: missing {PANEL_PATH}")
    panel = pd.read_parquet(PANEL_PATH)
    factors, counts = build_factors(panel)
    summary = summarize_factors(factors)
    corr = factors.drop(columns=["week"]).corr().reset_index().rename(columns={"index": "factor"})
    write_frame(factors, DATA_DIR / "observed_factor_returns")
    write_frame(counts, TABLE_DIR / "02_factor_leg_counts")
    write_frame(summary, TABLE_DIR / "02_observed_factor_summary")
    write_frame(corr, TABLE_DIR / "02_observed_factor_correlations")
    write_json(
        {
            "rows": int(len(factors)),
            "start_week": factors["week"].min(),
            "end_week": factors["week"].max(),
            "factor_columns": [col for col in factors.columns if col != "week"],
            "construction_note": "TVL uses lagged TVL / market cap, top quartile minus bottom quartile, then a market-orthogonal residual.",
        },
        MANIFEST_DIR / "02_observed_factors_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
