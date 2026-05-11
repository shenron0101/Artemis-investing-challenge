"""03 — L1, Boruta-style, and PCA feature selection."""
# %% Imports
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATA_DIR, MANIFEST_DIR, TABLE_DIR, chronological_split_indices, write_frame, write_json

FEATURE_PATH = DATA_DIR / "btc_direction_features.parquet"
CATALOG_PATH = MANIFEST_DIR / "02_feature_catalog.json"
RANDOM_STATE = 42
warnings.filterwarnings("ignore", message=".*penalty.*deprecated.*", category=FutureWarning)
warnings.filterwarnings("ignore", message="Inconsistent values: penalty=l1.*", category=UserWarning)


def _load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _training_xy(df: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    train_slice, _, _ = chronological_split_indices(len(df))
    train = df.iloc[train_slice]
    return train[feature_cols], train["target_next_day_up"].astype(int)


def select_l1(X: pd.DataFrame, y: pd.Series) -> tuple[list[str], pd.DataFrame]:
    pipe = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    penalty="l1",
                    solver="liblinear",
                    C=0.20,
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    pipe.fit(X, y)
    coef = pipe.named_steps["model"].coef_[0]
    ranking = pd.DataFrame({"feature": X.columns, "l1_abs_coef": np.abs(coef), "l1_coef": coef}).sort_values(
        "l1_abs_coef", ascending=False
    )
    selected = ranking.loc[ranking["l1_abs_coef"] > 1e-8, "feature"].tolist()
    if len(selected) < 5:
        selected = ranking.head(min(20, len(ranking)))["feature"].tolist()
    return selected, ranking


def select_boruta_shadow(X: pd.DataFrame, y: pd.Series, *, n_iter: int = 30) -> tuple[list[str], pd.DataFrame]:
    """Small Boruta-style fallback using RF real-vs-shadow importance tests."""
    imputer = SimpleImputer(strategy="median")
    X_imp = pd.DataFrame(imputer.fit_transform(X), columns=X.columns, index=X.index)
    rng = np.random.default_rng(RANDOM_STATE)
    hits = pd.Series(0, index=X.columns, dtype=float)
    margins = pd.Series(0.0, index=X.columns, dtype=float)

    for i in range(n_iter):
        shadow = X_imp.apply(lambda s: rng.permutation(s.to_numpy()), axis=0)
        shadow.columns = [f"shadow__{col}" for col in X.columns]
        both = pd.concat([X_imp, shadow], axis=1)
        rf = RandomForestClassifier(
            n_estimators=300,
            max_depth=6,
            min_samples_leaf=5,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=RANDOM_STATE + i,
        )
        rf.fit(both, y)
        imp = pd.Series(rf.feature_importances_, index=both.columns)
        threshold = float(np.percentile(imp.loc[imp.index.str.startswith("shadow__")], 95))
        real = imp.loc[X.columns]
        hits += (real > threshold).astype(float)
        margins += real - threshold

    ranking = pd.DataFrame(
        {
            "feature": X.columns,
            "boruta_hit_rate": (hits / n_iter).to_numpy(),
            "boruta_mean_margin": (margins / n_iter).to_numpy(),
        }
    ).sort_values(["boruta_hit_rate", "boruta_mean_margin"], ascending=False)
    selected = ranking.loc[ranking["boruta_hit_rate"] >= 0.60, "feature"].tolist()
    if len(selected) < 5:
        selected = ranking.head(min(25, len(ranking)))["feature"].tolist()
    return selected, ranking


def fit_pca(X: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    pipe = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("pca", PCA(n_components=0.95, random_state=RANDOM_STATE)),
        ]
    )
    pipe.fit(X)
    pca = pipe.named_steps["pca"]
    n_components = int(pca.n_components_)
    loadings = pd.DataFrame(
        pca.components_.T,
        index=X.columns,
        columns=[f"pc{i + 1}" for i in range(n_components)],
    ).reset_index(names="feature")
    manifest = {
        "method": "pca",
        "n_components": n_components,
        "explained_variance_ratio": [float(x) for x in pca.explained_variance_ratio_],
        "cumulative_explained_variance": float(np.sum(pca.explained_variance_ratio_)),
    }
    return manifest, loadings


def main() -> None:
    if not FEATURE_PATH.exists():
        raise FileNotFoundError(f"Run 02_feature_engineering.py first: missing {FEATURE_PATH}")
    df = pd.read_parquet(FEATURE_PATH)
    catalog = _load_catalog()
    feature_cols = catalog["feature_columns"]
    X_train, y_train = _training_xy(df, feature_cols)

    l1_features, l1_ranking = select_l1(X_train, y_train)
    boruta_features, boruta_ranking = select_boruta_shadow(X_train, y_train)
    pca_manifest, pca_loadings = fit_pca(X_train)

    write_frame(l1_ranking, TABLE_DIR / "03_l1_feature_ranking")
    write_frame(boruta_ranking, TABLE_DIR / "03_boruta_feature_ranking")
    write_frame(pca_loadings, TABLE_DIR / "03_pca_loadings")

    summary = [
        {"method": "all", "n_features": len(feature_cols)},
        {"method": "l1", "n_features": len(l1_features)},
        {"method": "boruta_shadow", "n_features": len(boruta_features)},
        {"method": "pca", "n_features": pca_manifest["n_components"]},
    ]
    write_frame(pd.DataFrame(summary), TABLE_DIR / "03_feature_selection_summary")
    write_json(
        {
            "split": "Feature selection fit on the first 70% of observations only.",
            "all": {"features": feature_cols},
            "l1": {"features": l1_features},
            "boruta_shadow": {
                "features": boruta_features,
                "note": "Boruta-style random-forest shadow test fallback; external boruta package is not required.",
            },
            "pca": pca_manifest,
        },
        MANIFEST_DIR / "03_feature_selection_manifest.json",
    )
    print("done.")


if __name__ == "__main__":
    main()
