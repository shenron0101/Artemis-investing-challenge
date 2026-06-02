from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).with_name("run.py")
SPEC = importlib.util.spec_from_file_location("stage15_run", MODULE_PATH)
stage15 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = stage15
SPEC.loader.exec_module(stage15)


def sample_book_returns() -> pd.DataFrame:
    weeks = pd.date_range("2024-01-01", periods=8, freq="W-MON")
    return pd.DataFrame(
        {
            "week": weeks,
            "mispricing": [0.01, 0.02, 0.03, 0.04, -0.02, -0.03, -0.04, -0.05],
            "core_rank": [-0.02, -0.01, -0.01, 0.00, 0.04, 0.05, 0.06, 0.07],
            "priced_tilt": [0.00, 0.01, -0.01, 0.00, 0.00, 0.01, -0.01, 0.00],
        }
    )


def sample_regime(weeks: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week": weeks,
            "p_RiskOff": [0.2, 0.2, 0.2, 0.2, 0.7, 0.7, 0.7, 0.7],
            "p_Neutral": [0.2] * len(weeks),
            "p_RiskOn": [0.6, 0.6, 0.6, 0.6, 0.1, 0.1, 0.1, 0.1],
        }
    )


def test_rolling_book_allocations_use_only_prior_returns() -> None:
    returns = sample_book_returns()
    regime = sample_regime(returns["week"])

    alloc = stage15.rolling_book_allocations(
        returns,
        regime,
        lookback=3,
        min_history=2,
        base_alloc={"mispricing": 0.5, "core_rank": 0.35, "priced_tilt": 0.15},
    )

    week_4 = alloc[alloc["week"] == returns.loc[3, "week"]].iloc[0]
    assert week_4["mispricing"] > week_4["core_rank"]

    week_5 = alloc[alloc["week"] == returns.loc[4, "week"]].iloc[0]
    assert week_5["mispricing"] > week_5["core_rank"]

    week_7 = alloc[alloc["week"] == returns.loc[6, "week"]].iloc[0]
    assert week_7["core_rank"] > week_7["mispricing"]
    assert np.isclose(week_7[["mispricing", "core_rank", "priced_tilt"]].sum(), 1.0)


def test_combine_book_weights_scales_each_subbook_by_weekly_allocation() -> None:
    weeks = pd.to_datetime(["2024-01-01", "2024-01-08"])
    subbooks = {
        "mispricing": pd.DataFrame(
            {
                "week": [weeks[0], weeks[0], weeks[1], weeks[1]],
                "symbol": ["A", "B", "A", "B"],
                "w": [0.4, -0.2, 0.5, -0.2],
            }
        ),
        "core_rank": pd.DataFrame(
            {
                "week": [weeks[0], weeks[0], weeks[1], weeks[1]],
                "symbol": ["A", "C", "A", "C"],
                "w": [0.2, -0.1, 0.1, -0.1],
            }
        ),
    }
    alloc = pd.DataFrame(
        {
            "week": weeks,
            "mispricing": [0.75, 0.25],
            "core_rank": [0.25, 0.75],
        }
    )

    combined = stage15.combine_book_weights(subbooks, alloc)
    first = combined[combined["week"] == weeks[0]].set_index("symbol")["w"]
    second = combined[combined["week"] == weeks[1]].set_index("symbol")["w"]

    assert np.isclose(first.loc["A"], 0.75 * 0.4 + 0.25 * 0.2)
    assert np.isclose(first.loc["B"], 0.75 * -0.2)
    assert np.isclose(first.loc["C"], 0.25 * -0.1)
    assert np.isclose(second.loc["A"], 0.25 * 0.5 + 0.75 * 0.1)
