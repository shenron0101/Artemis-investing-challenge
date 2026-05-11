"""04 — Chronological training and evaluation for BTC next-day direction."""
# %% Imports
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.decomposition import PCA
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, MANIFEST_DIR, TABLE_DIR, chronological_split_indices, classification_metrics, write_frame, write_json

FEATURE_PATH = DATA_DIR / "btc_direction_features.parquet"
SELECTION_PATH = MANIFEST_DIR / "03_feature_selection_manifest.json"
RANDOM_STATE = 42


def _load_selection() -> dict:
    return json.loads(SELECTION_PATH.read_text(encoding="utf-8"))


def _models() -> dict[str, object]:
    return {
        "logistic": LogisticRegression(class_weight="balanced", max_iter=2000, random_state=RANDOM_STATE),
        "random_forest": RandomForestClassifier(
            n_estimators=500,
            max_depth=6,
            min_samples_leaf=5,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=RANDOM_STATE,
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=250,
            learning_rate=0.03,
            max_depth=2,
            random_state=RANDOM_STATE,
        ),
    }


def _pipeline(model: object, *, pca_components: int | None = None) -> Pipeline:
    steps: list[tuple[str, object]] = [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
    if pca_components is not None:
        steps.append(("pca", PCA(n_components=pca_components, random_state=RANDOM_STATE)))
    steps.append(("model", clone(model)))
    return Pipeline(steps)


def _predict_frame(pipe: Pipeline, rows: pd.DataFrame, feature_cols: list[str], split: str, model_id: str) -> pd.DataFrame:
    X = rows[feature_cols]
    proba = pipe.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    return pd.DataFrame(
        {
            "date": rows["date"].to_numpy(),
            "split": split,
            "model_id": model_id,
            "feature_set": model_id.split("__", 1)[0],
            "model": model_id.split("__", 1)[1],
            "close": rows["close"].to_numpy(),
            "next_close": rows["next_close"].to_numpy(),
            "target_next_day_up": rows["target_next_day_up"].astype(int).to_numpy(),
            "target_return_1d_log": rows["target_return_1d_log"].to_numpy(),
            "target_return_1d_simple": rows["target_return_1d_simple"].to_numpy(),
            "proba_up": proba,
            "y_pred": pred,
        }
    )


def _score(preds: pd.DataFrame) -> dict[str, float]:
    y_true = preds["target_next_day_up"].astype(int)
    y_pred = preds["y_pred"].astype(int)
    out = classification_metrics(y_true, y_pred)
    try:
        out["roc_auc"] = float(roc_auc_score(y_true, preds["proba_up"]))
    except ValueError:
        out["roc_auc"] = float("nan")
    return out


def _baseline_predictions(df: pd.DataFrame, train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame) -> list[pd.DataFrame]:
    majority = int(train["target_next_day_up"].mean() >= 0.5)
    prev_direction = df["target_next_day_up"].shift(1).fillna(majority).astype(int)
    outputs: list[pd.DataFrame] = []
    for split_name, rows in (("validation", val), ("test", test)):
        for model_id, pred, proba in (
            ("baseline__majority_train_class", pd.Series(majority, index=rows.index), pd.Series(float(majority), index=rows.index)),
            ("baseline__previous_direction", prev_direction.loc[rows.index], prev_direction.loc[rows.index].astype(float)),
        ):
            outputs.append(
                pd.DataFrame(
                    {
                        "date": rows["date"].to_numpy(),
                        "split": split_name,
                        "model_id": model_id,
                        "feature_set": "baseline",
                        "model": model_id.split("__", 1)[1],
                        "close": rows["close"].to_numpy(),
                        "next_close": rows["next_close"].to_numpy(),
                        "target_next_day_up": rows["target_next_day_up"].astype(int).to_numpy(),
                        "target_return_1d_log": rows["target_return_1d_log"].to_numpy(),
                        "target_return_1d_simple": rows["target_return_1d_simple"].to_numpy(),
                        "proba_up": proba.to_numpy(),
                        "y_pred": pred.astype(int).to_numpy(),
                    }
                )
            )
    return outputs


def main() -> None:
    if not FEATURE_PATH.exists():
        raise FileNotFoundError(f"Run 02_feature_engineering.py first: missing {FEATURE_PATH}")
    if not SELECTION_PATH.exists():
        raise FileNotFoundError(f"Run 03_feature_selection.py first: missing {SELECTION_PATH}")

    df = pd.read_parquet(FEATURE_PATH).sort_values("date").reset_index(drop=True)
    selection = _load_selection()
    train_slice, val_slice, test_slice = chronological_split_indices(len(df))
    train, val, test = df.iloc[train_slice], df.iloc[val_slice], df.iloc[test_slice]

    feature_sets = {
        "all": selection["all"]["features"],
        "l1": selection["l1"]["features"],
        "boruta_shadow": selection["boruta_shadow"]["features"],
        "pca": selection["all"]["features"],
    }
    pca_components = int(selection["pca"]["n_components"])

    prediction_frames = _baseline_predictions(df, train, val, test)
    metrics: list[dict[str, object]] = []

    for preds in prediction_frames:
        scores = _score(preds)
        metrics.append({"model_id": preds["model_id"].iloc[0], "split": preds["split"].iloc[0], **scores})

    for feature_set, feature_cols in feature_sets.items():
        if not feature_cols:
            continue
        for model_name, model in _models().items():
            model_id = f"{feature_set}__{model_name}"
            pipe = _pipeline(model, pca_components=pca_components if feature_set == "pca" else None)
            pipe.fit(train[feature_cols], train["target_next_day_up"].astype(int))

            for split_name, rows in (("validation", val), ("test", test)):
                preds = _predict_frame(pipe, rows, feature_cols, split_name, model_id)
                prediction_frames.append(preds)
                scores = _score(preds)
                metrics.append({"model_id": model_id, "split": split_name, **scores})

    pred_df = pd.concat(prediction_frames, ignore_index=True).sort_values(["split", "model_id", "date"])
    metrics_df = pd.DataFrame(metrics).sort_values(["split", "balanced_accuracy", "f1"], ascending=[True, False, False])
    write_frame(pred_df, TABLE_DIR / "04_predictions")
    write_frame(metrics_df, TABLE_DIR / "04_model_metrics")

    val_scores = metrics_df.loc[metrics_df["split"].eq("validation")].sort_values(
        ["balanced_accuracy", "f1", "roc_auc"], ascending=False
    )
    champion = val_scores.iloc[0].to_dict()
    write_json(
        {
            "split_dates": {
                "train": [train["date"].min(), train["date"].max()],
                "validation": [val["date"].min(), val["date"].max()],
                "test": [test["date"].min(), test["date"].max()],
            },
            "champion_by_validation_balanced_accuracy": champion,
            "models": list(_models().keys()),
            "feature_sets": {key: len(value) for key, value in feature_sets.items()},
        },
        MANIFEST_DIR / "04_train_eval_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
