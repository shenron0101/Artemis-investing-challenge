from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).with_name("run.py")
SPEC = importlib.util.spec_from_file_location("stage14_run", MODULE_PATH)
stage14 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = stage14
SPEC.loader.exec_module(stage14)


def sample_candidate() -> stage14.Candidate:
    return stage14.Candidate(
        name="test",
        sleeve_core=0.40,
        sleeve_priced=0.30,
        sleeve_mispricing=0.25,
        sleeve_legacy=0.05,
        ic_blend=0.0,
        top_frac=0.30,
        gross_risk_on=1.00,
        gross_neutral=0.85,
        gross_risk_off=0.60,
        slow_factor_boost=1.0,
    )


def sample_signal_panel() -> pd.DataFrame:
    weeks = pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15"])
    rows = []
    for wk in weeks:
        for i in range(20):
            rows.append(
                {
                    "week": wk,
                    "symbol": f"C{i:02d}",
                    "cluster_id": i % 4,
                    "signal": np.linspace(-2.0, 2.0, 20)[i],
                    "vol4": 0.08 + i * 0.005,
                }
            )
    return pd.DataFrame(rows)


def sample_regime() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week": pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15"]),
            "p_RiskOff": [0.0, 0.0, 1.0],
            "p_Neutral": [0.0, 1.0, 0.0],
            "p_RiskOn": [1.0, 0.0, 0.0],
            "label": ["RiskOn", "Neutral", "RiskOff"],
        }
    )


def exposure_by_week(weights: pd.DataFrame) -> pd.DataFrame:
    return weights.groupby("week")["w"].agg(
        long_gross=lambda s: float(s.clip(lower=0).sum()),
        short_gross=lambda s: float(-s.clip(upper=0).sum()),
        gross=lambda s: float(s.abs().sum()),
        net=lambda s: float(s.sum()),
    )


def test_construct_weights_is_long_biased_and_regime_aware(monkeypatch) -> None:
    monkeypatch.setattr(stage14, "TURNOVER_CAP", 99.0)

    weights = stage14.construct_weights(sample_signal_panel(), sample_regime(), sample_candidate())
    exposure = exposure_by_week(weights)

    risk_on = exposure.loc[pd.Timestamp("2024-01-01")]
    neutral = exposure.loc[pd.Timestamp("2024-01-08")]
    risk_off = exposure.loc[pd.Timestamp("2024-01-15")]

    assert 0.88 <= risk_on.long_gross / risk_on.gross <= 0.91
    assert 0.09 <= risk_on.short_gross / risk_on.gross <= 0.12
    assert 0.73 <= neutral.long_gross / neutral.gross <= 0.77
    assert 0.23 <= neutral.short_gross / neutral.gross <= 0.27
    assert 0.68 <= risk_off.long_gross / risk_off.gross <= 0.72
    assert 0.28 <= risk_off.short_gross / risk_off.gross <= 0.32
    assert risk_on.gross > neutral.gross > risk_off.gross
    assert risk_on.net > neutral.net > risk_off.net


def test_construct_weights_sizes_longs_nonlinearly_and_caps_shorts(monkeypatch) -> None:
    monkeypatch.setattr(stage14, "TURNOVER_CAP", 99.0)

    weights = stage14.construct_weights(sample_signal_panel(), sample_regime(), sample_candidate())
    first_week = weights[weights["week"] == pd.Timestamp("2024-01-01")]
    longs = first_week[first_week["w"] > 0].sort_values("signal")
    shorts = first_week[first_week["w"] < 0]

    assert longs.iloc[-1]["w"] > longs.iloc[0]["w"] * 1.5
    assert shorts["w"].abs().max() <= stage14.MAX_SHORT_ASSET_WEIGHT + 1e-12
    assert longs["w"].max() > shorts["w"].abs().max()


def test_plotly_weight_bubble_animation_writes_all_week_frames(tmp_path) -> None:
    weights = stage14.construct_weights(sample_signal_panel(), sample_regime(), sample_candidate())
    out = tmp_path / "weekly_weight_bubbles.html"

    stage14.write_weight_bubble_animation(weights, sample_regime(), out, variant_name="Test Variant")

    html = out.read_text()
    assert "Plotly.newPlot" in html
    assert "Test Variant" in html
    assert "2024-01-01" in html
    assert "2024-01-08" in html
    assert "2024-01-15" in html
    assert "C19" in html
