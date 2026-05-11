"""06 — Publish a concise markdown report from Stage 05 artifacts."""
# %% Imports
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MANIFEST_DIR, ROOT, STAGE, TABLE_DIR

REPORT_PATH = STAGE / "REPORT.md"


def _pct(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2%}"


def _num(value: float) -> str:
    return "n/a" if pd.isna(value) else f"{value:.3f}"


def _link(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    metrics = pd.read_parquet(TABLE_DIR / "04_model_metrics.parquet")
    trading = pd.read_parquet(TABLE_DIR / "05_trading_summary.parquet")
    feature_summary = pd.read_parquet(TABLE_DIR / "03_feature_selection_summary.parquet")
    dataset = json.loads((MANIFEST_DIR / "01_dataset_manifest.json").read_text(encoding="utf-8"))
    train_eval = json.loads((MANIFEST_DIR / "04_train_eval_manifest.json").read_text(encoding="utf-8"))

    test_metrics = metrics.loc[metrics["split"].eq("test")].sort_values(["balanced_accuracy", "f1"], ascending=False)
    best_classifier = test_metrics.iloc[0]
    best_strategy = trading.iloc[0]
    feature_lines = [
        f"- {row.method}: {int(row.n_features)} features/components"
        for row in feature_summary.itertuples(index=False)
    ]

    text = f"""# Stage 05 — BTC Direction Paper Reproduction

This stage implements a first-pass reproduction scaffold for `Bitcoin price direction prediction using on-chain data and feature selection`.

## Data Window
- Rows: {dataset["rows"]:,}
- Dates: {dataset["start_date"]} to {dataset["end_date"]}
- Sources: Binance BTCUSDT OHLCV, CoinGecko BTC daily ticks, Artemis BTC activity, DeFiLlama stablecoin supply/inflows, and tracked-protocol TVL.

## Feature Selection
{chr(10).join(feature_lines)}

Feature selection is fit only on the first 70% of chronological observations. PCA keeps enough components to explain 95% of training variance.

## Classification Result
- Best test classifier: `{best_classifier.model_id}`
- Balanced accuracy: {_pct(best_classifier.balanced_accuracy)}
- Accuracy: {_pct(best_classifier.accuracy)}
- F1: {_num(best_classifier.f1)}
- ROC AUC: {_num(best_classifier.roc_auc)}

Validation-selected champion: `{train_eval["champion_by_validation_balanced_accuracy"]["model_id"]}`.

## Trading Result
- Best test strategy: `{best_strategy["model_id"]}` / `{best_strategy["mode"]}`
- Total return: {_pct(best_strategy.total_return)}
- Annualized return: {_pct(best_strategy.annualized_return)}
- Sharpe: {_num(best_strategy.sharpe)}
- Max drawdown: {_pct(best_strategy.max_drawdown)}

## Outputs
- Features: `{_link(TABLE_DIR / "03_feature_selection_summary.parquet")}`
- Model metrics: `{_link(TABLE_DIR / "04_model_metrics.parquet")}`
- Predictions: `{_link(TABLE_DIR / "04_predictions.parquet")}`
- Trading summary: `{_link(TABLE_DIR / "05_trading_summary.parquet")}`
- Equity chart: `{_link(STAGE / "figures" / "05_trading_simulation" / "01_test_equity_curves.html")}`

## Reproduction Notes
- This is a repo-native hybrid reproduction, not a strict Glassnode reproduction. Realized-value and unrealized-value feature families from the paper are not available in the current clean tables.
- The first implementation covers classical models plus L1, Boruta-style shadow selection, and PCA. CNN-LSTM and TCN are intentionally left for a later deep-learning extension.
- Signals are chronological and evaluated on a held-out test period; no shuffled cross-validation is used.
"""
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    print("done.")


if __name__ == "__main__":
    main()
