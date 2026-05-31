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


def sample_factor_panel_for_regime() -> pd.DataFrame:
    weeks = pd.date_range("2022-01-03", periods=90, freq="W-MON")
    rows = []
    for t, wk in enumerate(weeks):
        cycle_ret = [-0.04, -0.01, 0.035][t % 3]
        for i in range(18):
            rows.append(
                {
                    "week": wk,
                    "symbol": "BTC" if i == 0 else f"C{i:02d}",
                    "ret": cycle_ret + (i - 8) * 0.0005,
                    "fwd_ret": np.nan,
                    "mcap": 2_000_000_000.0 if i == 0 else 100_000_000.0 + i,
                    "cluster_id": i % 4,
                    "network_entropy": 1.8 + 0.01 * (t % 5),
                    "vol4": 0.1,
                }
            )
    panel = pd.DataFrame(rows)
    panel["fwd_ret"] = panel.groupby("symbol")["ret"].shift(-1)
    return panel


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


def test_xgboost_regime_detector_uses_chronological_train_test_split(monkeypatch) -> None:
    captured = {}

    class FakeXGBClassifier:
        def __init__(self, **kwargs):
            captured["params"] = kwargs

        def fit(self, x, y, sample_weight=None):
            captured["fit_weeks"] = list(x.index)
            captured["fit_y"] = list(y)
            return self

        def predict_proba(self, x):
            probs = np.tile(np.array([[0.15, 0.70, 0.15]]), (len(x), 1))
            probs[np.asarray(x["mktmom_z"] > 0.25), :] = [0.10, 0.20, 0.70]
            probs[np.asarray(x["mktmom_z"] < -0.25), :] = [0.70, 0.20, 0.10]
            return probs

        def predict(self, x):
            return self.predict_proba(x).argmax(axis=1)

    monkeypatch.setattr(stage14, "XGBClassifier", FakeXGBClassifier)

    panel = sample_factor_panel_for_regime()
    first_oos = pd.Timestamp("2023-03-13")
    regime = stage14.build_regime_panel(panel, first_oos=first_oos, persist=False)

    assert captured["fit_weeks"]
    assert max(captured["fit_weeks"]) < first_oos
    assert set(captured["fit_y"]) == {0, 1, 2}
    assert {"train", "test"}.issubset(set(regime["split"]))

    test_rows = regime[regime["week"] >= first_oos]
    assert not test_rows.empty
    prob_cols = ["p_RiskOff", "p_Neutral", "p_RiskOn"]
    assert test_rows[prob_cols].notna().all().all()
    np.testing.assert_allclose(test_rows[prob_cols].sum(axis=1).to_numpy(), 1.0, atol=1e-9)


def test_neural_network_signal_uses_xgboost_regime_features_and_train_split(monkeypatch) -> None:
    captured = {}

    class FakeMLPRegressor:
        def __init__(self, **kwargs):
            captured["params"] = kwargs

        def fit(self, x, y):
            captured["fit_weeks"] = list(x.index)
            captured["fit_columns"] = list(x.columns)
            captured["fit_y"] = np.asarray(y)
            return self

        def predict(self, x):
            return np.asarray(x["z_VolC"]) * 0.01 + np.asarray(x["p_RiskOn"]) * 0.02

    monkeypatch.setattr(stage14, "MLPRegressor", FakeMLPRegressor)

    panel = sample_factor_panel_for_regime()
    for i, fac in enumerate(stage14.FACTOR_ORDER):
        panel[f"z_{fac}"] = ((np.arange(len(panel)) + i) % 11 - 5) / 5
    weeks = pd.Series(sorted(panel["week"].unique()))
    regime = pd.DataFrame(
        {
            "week": weeks,
            "p_RiskOff": np.where(np.arange(len(weeks)) % 3 == 0, 0.70, 0.10),
            "p_Neutral": np.where(np.arange(len(weeks)) % 3 == 1, 0.70, 0.20),
            "p_RiskOn": np.where(np.arange(len(weeks)) % 3 == 2, 0.70, 0.10),
            "label": ["RiskOff", "Neutral", "RiskOn"] * 30,
            "split": np.where(weeks >= pd.Timestamp("2023-03-13"), "test", "train"),
        }
    )

    signal = stage14.build_neural_network_signal(
        panel,
        regime,
        first_oos=pd.Timestamp("2023-03-13"),
        persist=False,
    )

    assert captured["fit_weeks"]
    assert max(captured["fit_weeks"]) < pd.Timestamp("2023-03-13")
    assert set(["p_RiskOff", "p_Neutral", "p_RiskOn"]).issubset(captured["fit_columns"])
    assert "z_VolC" in captured["fit_columns"]
    assert np.isfinite(captured["fit_y"]).all()
    assert not signal.empty
    assert signal.loc[signal["week"] >= pd.Timestamp("2023-03-13"), "signal"].notna().all()
